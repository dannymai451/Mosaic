"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { MosaicCanvas, type MosaicLayout, type MosaicPreset, type SavedMosaic } from "@/components/mosaic-canvas";
import { useMosaicAlbums } from "@/components/mosaic-albums";
import { ShareProfile } from "@/components/share-profile";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-4 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400 disabled:opacity-50";
const blank: MosaicLayout = { preset_key: "blank", grid_width: 9, grid_height: 9, tiles: [] };
type OwnerProfile = { username: string; visibility: "private" | "public" };

async function request<T>(path: string, signal: AbortSignal, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/me${path}`, {
    ...options, credentials: "include", cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
  });
  if (response.status === 401) throw new Error("Your session expired. Connect Spotify again.");
  if (response.status === 422) throw new Error("The layout is invalid or an album is no longer in your Featured Albums. Your draft is still here; check your selection and retry.");
  if (response.status === 409) throw new Error("A mosaic already exists. Reload the builder to edit it.");
  if (!response.ok) throw new Error("Could not complete the request. Your draft is still here; please try again.");
  return response.json();
}

function layoutOf(mosaic: MosaicLayout): MosaicLayout {
  return { preset_key: mosaic.preset_key, grid_width: mosaic.grid_width, grid_height: mosaic.grid_height, tiles: mosaic.tiles };
}

export function MosaicEditor() {
  const [saved, setSaved] = useState<SavedMosaic | null>(null);
  const [draft, setDraft] = useState<MosaicLayout>(blank);
  const [history, setHistory] = useState<MosaicLayout[]>([]);
  const [featured, setFeatured] = useState<string[]>([]);
  const [presets, setPresets] = useState<MosaicPreset[]>([]);
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [erase, setErase] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const action = useRef<AbortController | null>(null);
  const metadata = useMosaicAlbums(featured, "/api/me/albums");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [mosaics, selection, presetList, owner] = await Promise.all([
          request<SavedMosaic[]>("/mosaics", controller.signal),
          request<{ albumIds: string[] }>("/featured-albums", controller.signal),
          request<MosaicPreset[]>("/mosaic-presets", controller.signal),
          request<OwnerProfile>("", controller.signal),
        ]);
        if (controller.signal.aborted) return;
        const mosaic = mosaics[0] ?? null;
        setSaved(mosaic);
        setDraft(mosaic ? layoutOf(mosaic) : blank);
        setFeatured(selection.albumIds);
        setSelected(selection.albumIds[0] ?? null);
        setPresets(presetList);
        setProfile(owner);
        setLoadError(null);
      } catch (failure) {
        if (!controller.signal.aborted) setLoadError(failure instanceof Error && failure.name === "Error" ? failure.message : "Could not load the builder. Check that the API is running and try again.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [reload]);

  useEffect(() => () => action.current?.abort(), []);

  function edit(next: MosaicLayout, message: string) {
    if (busy || JSON.stringify(next) === JSON.stringify(draft)) return;
    setHistory((current) => [...current.slice(-49), draft]);
    setDraft(next);
    setActionError(null);
    setStatus(message);
  }

  function applyPreset(preset: MosaicPreset) {
    edit({
      preset_key: preset.key, grid_width: preset.grid_width, grid_height: preset.grid_height,
      tiles: featured.length ? preset.coordinates.map((point, index) => ({ ...point, spotifyAlbumId: featured[index % featured.length] })) : [],
    }, `${preset.label} applied to your draft.`);
  }

  function place(x: number, y: number) {
    if (!erase && !selected) { setStatus("Choose a Featured Album first."); return; }
    const remaining = draft.tiles.filter((tile) => tile.x !== x || tile.y !== y);
    edit({ ...draft, tiles: erase ? remaining : [...remaining, { x, y, spotifyAlbumId: selected! }] }, `${erase ? "Erased" : "Placed album at"} row ${y + 1}, column ${x + 1}.`);
  }

  async function save() {
    if (action.current) return;
    const controller = new AbortController();
    action.current = controller;
    setBusy(true);
    setActionError(null);
    setStatus("");
    try {
      let current = saved;
      if (!current) {
        current = await request<SavedMosaic>("/mosaics", controller.signal, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preset_key: "blank" }),
        });
        if (controller.signal.aborted) return;
        setSaved(current);
      }
      const result = await request<SavedMosaic>(`/mosaics/${current.id}`, controller.signal, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft),
      });
      if (controller.signal.aborted) return;
      setSaved(result);
      setDraft(layoutOf(result));
      setHistory([]);
      setStatus(result.is_active ? "Mosaic saved. Your active design is updated." : "Mosaic saved. Set Active to show it on your public profile.");
    } catch (failure) {
      if (!controller.signal.aborted) setActionError(failure instanceof Error && failure.name === "Error" ? failure.message : "Could not save. Your draft is still here; try again.");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); action.current = null; }
    }
  }

  async function activate() {
    if (!saved || action.current) return;
    const controller = new AbortController();
    action.current = controller;
    setBusy(true);
    setActionError(null);
    try {
      const result = await request<SavedMosaic>(`/mosaics/${saved.id}/activate`, controller.signal, { method: "POST" });
      if (!controller.signal.aborted) { setSaved(result); setStatus("Mosaic is active. Profile visibility controls who can view it."); }
    } catch (failure) {
      if (!controller.signal.aborted) setActionError(failure instanceof Error && failure.name === "Error" ? failure.message : "Could not activate the mosaic. Try again.");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); action.current = null; }
    }
  }

  const dirty = !saved || JSON.stringify(layoutOf(saved)) !== JSON.stringify(draft);
  if (loading) return <p role="status" className="mt-8 text-zinc-400">Loading your mosaic...</p>;
  if (loadError) return <div className="mt-8"><p role="alert" className="text-red-300">{loadError}</p><div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={() => { setLoading(true); setReload((value) => value + 1); }} className={buttonClass}>Try again</button><a href={`${API_BASE_URL}/api/auth/spotify/start`} className={buttonClass}>Connect Spotify</a></div></div>;

  return (
    <div className="mt-8 space-y-6">
      <div className="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <section aria-labelledby="presets-heading" className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <h2 id="presets-heading" className="text-xl font-semibold">Presets</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-400">One click fills a shape with your Featured Albums. Covers repeat when needed. Blank clears the grid.</p>
          <div className="mt-4 flex flex-wrap gap-3 lg:flex-col">
            {presets.map((preset) => <button key={preset.key} type="button" disabled={busy || (preset.key !== "blank" && !featured.length)} onClick={() => applyPreset(preset)} className={buttonClass}>{preset.label}</button>)}
          </div>
        </section>
        <section aria-labelledby="canvas-heading" className="min-w-0 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="canvas-heading" className="text-xl font-semibold">Your mosaic</h2><span className="text-sm text-zinc-400">{draft.tiles.length} tiles · {draft.grid_width} × {draft.grid_height}</span></div>
          <p id="placement-help" className="mb-4 text-sm leading-6 text-zinc-400">Choose an album below, then click a cell. With a keyboard, Tab to a cell and press Enter or Space. Use Erase tiles to clear individual cells.</p>
          <div className="mx-auto max-w-xl" aria-describedby="placement-help"><MosaicCanvas layout={draft} albums={metadata.albums} onPlace={place} disabled={busy} /></div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" aria-pressed={erase} disabled={busy} onClick={() => setErase((value) => !value)} className={`${buttonClass} ${erase ? "border-green-400 text-green-300" : ""}`}>Erase tiles</button>
            <button type="button" disabled={busy || !history.length} onClick={() => { setDraft(history[history.length - 1]); setHistory((current) => current.slice(0, -1)); setActionError(null); setStatus("Last edit undone."); }} className={buttonClass}>Undo</button>
            <button type="button" disabled={busy || !dirty} onClick={() => edit(saved ? layoutOf(saved) : blank, "Reset to your last save.")} className={buttonClass}>Reset</button>
            <button type="button" disabled={busy || !dirty} onClick={() => void save()} className={`${buttonClass} border-green-500 bg-green-500 text-black`}>{busy ? "Working..." : "Save mosaic"}</button>
            <button type="button" disabled={busy || !saved || dirty || saved.is_active} onClick={() => void activate()} className={buttonClass}>{saved?.is_active ? "Active mosaic" : "Set Active"}</button>
          </div>
          <p role="status" className="mt-4 min-h-6 text-sm text-green-300">{status || (dirty ? "You have unsaved changes." : "Your layout is saved.")}</p>
          {actionError && <p role="alert" className="mt-3 text-sm text-red-300">{actionError}</p>}
        </section>
      </div>
      <section aria-labelledby="tray-heading" className="rounded-2xl border border-zinc-800 p-5 sm:p-6">
        <h2 id="tray-heading" className="text-xl font-semibold">Album tray</h2>
        <p className="mt-2 text-sm text-zinc-400">{erase ? "Erase mode is on. Choose an album to return to placement." : "Select a cover to place it on the grid."} <Link href="/settings/albums" className="inline-flex min-h-11 items-center text-green-400 underline">Choose Featured Albums</Link></p>
        {!featured.length && <p className="mt-3 text-zinc-300">Save Featured Albums first, then return here to build a shape.</p>}
        <ul className="mt-4 grid auto-rows-fr grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {featured.map((id) => {
            const album = metadata.albums[id];
            return <li key={id} className="flex min-w-0 flex-col"><button type="button" disabled={busy} aria-pressed={!erase && selected === id} onClick={() => { setSelected(id); setErase(false); setStatus(`Selected ${album?.name ?? "album"}. Choose a cell to place it.`); }} className={`flex w-full flex-1 flex-col rounded-xl border p-2 text-left focus-visible:outline-2 focus-visible:outline-green-400 ${!erase && selected === id ? "border-green-400" : "border-zinc-700"}`}>
              {album?.imageUrl ? <Image src={album.imageUrl} alt="" width={150} height={150} unoptimized className="aspect-square w-full shrink-0 object-contain" /> : <span className="flex aspect-square w-full shrink-0 items-center justify-center bg-zinc-800 text-zinc-400">♪</span>}
              <span title={album?.name ?? `Album ${id}`} className="mt-2 min-h-10 w-full line-clamp-2 break-words text-sm font-semibold leading-5">{album?.name ?? `Album ${id}`}</span><span title={album?.artists.join(", ") || "Unknown artist"} className="mt-1 min-h-8 w-full line-clamp-2 break-words text-xs leading-4 text-zinc-400">{album?.artists.join(", ") || "Unknown artist"}</span>
            </button><a href={`https://open.spotify.com/album/${id}`} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 shrink-0 items-center text-xs text-green-400 underline">Open in Spotify</a></li>;
          })}
        </ul>
        {metadata.loading && <p role="status" className="mt-4 text-sm text-zinc-400">Loading album artwork. You can edit while covers load.</p>}
        {metadata.error && <div className="mt-3"><p role="alert" className="text-sm text-red-300">{metadata.error}</p><div className="mt-3 flex flex-wrap gap-3"><button type="button" onClick={metadata.retry} className={buttonClass}>Retry artwork</button><a href={`${API_BASE_URL}/api/auth/spotify/start`} className={buttonClass}>Reconnect Spotify</a></div></div>}
      </section>
      <section className="rounded-2xl border border-zinc-800 p-5">
        <h2 className="text-xl font-semibold">Share your design</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Save and set your mosaic active, then make your profile public in <Link href="/settings/profile" className="text-green-400 underline">profile settings</Link>. Later saves update the active design. Unsaved edits stay in this builder and are lost when you leave.</p>
        {profile?.visibility === "public" && saved?.is_active && <div className="mt-4"><Link href={`/@${profile.username}`} className="inline-flex min-h-11 items-center text-green-400 underline">View public profile</Link><ShareProfile username={profile.username} /></div>}
        {profile?.visibility === "private" && <p className="mt-3 text-sm text-zinc-300">Your profile is private. Setting a mosaic active keeps it private.</p>}
      </section>
    </div>
  );
}
