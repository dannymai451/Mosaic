"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { AlbumDetail, type Album } from "@/components/album-detail";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-4 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400 disabled:opacity-50";
type AlbumPage = { items: Album[]; total: number; nextOffset: number | null };
type Selection = { albumIds: string[] };

class RequestError extends Error {
  constructor(message: string, public reconnect = false) { super(message); }
}

async function request<T>(path: string, signal: AbortSignal, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/me/${path}`, {
    ...options, credentials: "include", cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(30000)]),
  });
  if (response.status === 401) throw new RequestError("Your session expired. Connect Spotify again.", true);
  if (response.status === 403) throw new RequestError("Reconnect Spotify to allow access to your saved albums.", true);
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    throw new RequestError(`Spotify is busy. ${wait ? `Wait ${wait} seconds, then try again.` : "Wait a little, then try again."}`);
  }
  if (response.status === 422) throw new RequestError("An added album is no longer saved in your Spotify library, or the selection is invalid. Remove it and try again.");
  if (!response.ok) throw new RequestError("Could not complete the request. Check that the API is running, then try again.");
  return response.json();
}

function failure(error: unknown): RequestError {
  return error instanceof RequestError ? error : new RequestError("Could not reach the API or the request timed out. Please try again.");
}

export function AlbumPicker() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [known, setKnown] = useState<Record<string, Album>>({});
  const [saved, setSaved] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectionReady, setSelectionReady] = useState(false);
  const [libraryReady, setLibraryReady] = useState(false);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<RequestError | null>(null);
  const [selectionError, setSelectionError] = useState<RequestError | null>(null);
  const [saveError, setSaveError] = useState<RequestError | null>(null);
  const [detailError, setDetailError] = useState<RequestError | null>(null);
  const [detail, setDetail] = useState<Album | null>(null);
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const pageController = useRef<AbortController | null>(null);
  const saveController = useRef<AbortController | null>(null);
  const detailController = useRef<AbortController | null>(null);
  const selectionLoaded = useRef(false);

  function remember(items: Album[]) {
    setKnown((current) => ({ ...current, ...Object.fromEntries(items.map((album) => [album.id, album])) }));
  }

  useEffect(() => {
    const controller = new AbortController();
    pageController.current = controller;
    async function load() {
      const results = await Promise.allSettled([
        selectionLoaded.current ? Promise.resolve(null) : request<Selection>("featured-albums", controller.signal),
        request<AlbumPage>("albums?limit=20&offset=0", controller.signal),
      ]);
      if (controller.signal.aborted) return;
      const [selection, library] = results;
      if (selection.status === "fulfilled" && selection.value !== null) {
        setSaved(selection.value.albumIds);
        setSelected(selection.value.albumIds);
        selectionLoaded.current = true;
        setSelectionReady(true);
        setSelectionError(null);
      } else if (selection.status === "rejected") setSelectionError(failure(selection.reason));
      if (library.status === "fulfilled") {
        setAlbums(library.value.items);
        remember(library.value.items);
        setTotal(library.value.total);
        setNextOffset(library.value.nextOffset);
        setLibraryReady(true);
        setLoadError(null);
      } else setLoadError(failure(library.reason));
      setLoading(false);
      pageController.current = null;
    }
    void load();
    return () => { controller.abort(); };
  }, [reload]);

  useEffect(() => () => {
    pageController.current?.abort();
    saveController.current?.abort();
    detailController.current?.abort();
  }, []);

  async function loadMore() {
    if (pageController.current || nextOffset === null) return;
    const controller = new AbortController();
    pageController.current = controller;
    setLoading(true);
    setLoadError(null);
    try {
      const page = await request<AlbumPage>(`albums?limit=20&offset=${nextOffset}`, controller.signal);
      if (controller.signal.aborted) return;
      setAlbums((current) => [...new Map([...current, ...page.items].map((album) => [album.id, album])).values()]);
      remember(page.items);
      setTotal(page.total);
      setNextOffset(page.nextOffset);
    } catch (error) {
      if (!controller.signal.aborted) setLoadError(failure(error));
    } finally {
      if (!controller.signal.aborted) { setLoading(false); pageController.current = null; }
    }
  }

  function toggle(id: string) {
    if (!selectionReady || saveController.current) return;
    setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : current.length < 100 ? [...current, id] : current);
    setStatus("");
    setSaveError(null);
  }

  async function save() {
    if (!selectionReady || saveController.current) return;
    const controller = new AbortController();
    saveController.current = controller;
    setSaving(true);
    setSaveError(null);
    setStatus("");
    try {
      const result = await request<Selection>("featured-albums", controller.signal, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ album_ids: selected }),
      });
      if (controller.signal.aborted) return;
      setSaved(result.albumIds);
      setSelected(result.albumIds);
      setStatus("Featured Albums saved.");
    } catch (error) {
      if (!controller.signal.aborted) setSaveError(failure(error));
    } finally {
      if (!controller.signal.aborted) { setSaving(false); saveController.current = null; }
    }
  }

  async function showDetails(id: string) {
    setDetailError(null);
    if (known[id]) { setDetail(known[id]); return; }
    if (detailController.current) return;
    const controller = new AbortController();
    detailController.current = controller;
    setDetailLoading(id);
    try {
      const album = await request<Album>(`albums/${id}`, controller.signal);
      if (!controller.signal.aborted) { remember([album]); setDetail(album); }
    } catch (error) {
      if (!controller.signal.aborted) setDetailError(failure(error));
    } finally {
      if (!controller.signal.aborted) { setDetailLoading(null); detailController.current = null; }
    }
  }

  const dirty = JSON.stringify(saved) !== JSON.stringify(selected);
  const reconnect = [loadError, selectionError, saveError, detailError].some((error) => error?.reconnect);

  return (
    <div className="mt-8 space-y-8">
      <section aria-labelledby="featured-heading" className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5 sm:p-8">
        <h2 id="featured-heading" className="text-xl font-semibold">Featured Albums <span className="text-sm font-normal text-zinc-400">{selected.length}/100</span></h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Choose the albums for your future mosaic, then save. Unsaved changes are lost when you leave or refresh.</p>
        {!selectionReady && !selectionError && <p role="status" className="mt-4">Loading your selection...</p>}
        {selectionError && <p role="alert" className="mt-4 text-red-300">{selectionError.message}</p>}
        {selectionReady && selected.length === 0 && <p className="mt-4 text-sm text-zinc-400">No Featured Albums yet. Add one from your saved library below.</p>}
        <ul className="mt-5 space-y-3">
          {selected.map((id) => (
            <li key={id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-700 p-3">
              <div className="min-w-0 w-full sm:w-auto sm:flex-1"><p className="break-words font-medium">{known[id]?.name ?? `Album ${id}`}</p><p className="text-sm text-zinc-400">{known[id]?.artists.join(", ") ?? "Load details to see this saved selection."}</p></div>
              <button type="button" disabled={detailLoading !== null} onClick={() => void showDetails(id)} aria-label={`Details for ${known[id]?.name ?? id}`} className={buttonClass}>{detailLoading === id ? "Loading..." : "Details"}</button>
              <button type="button" disabled={saving} onClick={() => toggle(id)} aria-label={`Remove ${known[id]?.name ?? id}`} className={buttonClass}>Remove</button>
            </li>
          ))}
        </ul>
        <div className="mt-5 flex flex-wrap gap-3">
          <button type="button" disabled={!selectionReady || saving || !dirty} onClick={() => void save()} className={`${buttonClass} border-green-500 bg-green-500 text-black`}>{saving ? "Saving..." : "Save Featured Albums"}</button>
          <button type="button" disabled={!selectionReady || saving || !dirty} onClick={() => { setSelected(saved); setSaveError(null); setStatus("Selection reset to your last save."); }} className={buttonClass}>Reset edits</button>
        </div>
        {saveError && <p role="alert" className="mt-4 text-red-300">{saveError.message} Your selection is still here; you can retry saving.</p>}
        <p role="status" className="mt-3 min-h-6 text-sm text-green-300">{status || (dirty ? "You have unsaved changes." : "")}</p>
      </section>

      <section aria-labelledby="library-heading" aria-busy={loading} className="rounded-2xl border border-zinc-800 p-5 sm:p-8">
        <h2 id="library-heading" className="text-xl font-semibold">Your saved Spotify albums</h2>
        <p className="mt-2 text-sm text-zinc-400">{libraryReady ? `${albums.length} albums loaded of ${total}.` : "Albums you have saved in Spotify will appear here."}</p>
        {libraryReady && total === 0 && <p className="mt-5 text-zinc-300">Your saved album library is empty. Save an album in Spotify, then reload this page.</p>}
        <ul className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {albums.map((album) => (
            <li key={album.id} className="flex min-w-0 flex-col rounded-xl border border-zinc-800 bg-zinc-900 p-3">
              <button type="button" onClick={() => setDetail(album)} aria-label={`Details for ${album.name}`} className="block w-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400">
                {album.imageUrl ? <Image src={album.imageUrl} alt={`Cover of ${album.name}`} width={300} height={300} unoptimized className="aspect-square w-full object-contain" /> : <span className="flex aspect-square items-center justify-center bg-zinc-800 text-sm text-zinc-400">No artwork</span>}
              </button>
              <h3 className="mt-3 break-words text-sm font-semibold">{album.name}</h3>
              <p className="mt-1 break-words text-xs text-zinc-400">{album.artists.join(", ") || "Unknown artist"}</p>
              <div className="mt-auto pt-2">
                <a href={album.spotifyUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center text-xs text-green-400 underline focus-visible:outline-2 focus-visible:outline-green-400">Open in Spotify</a>
                <button type="button" aria-pressed={selected.includes(album.id)} aria-label={`${selected.includes(album.id) ? "Remove" : "Add"} ${album.name}`} disabled={!selectionReady || saving || (!selected.includes(album.id) && selected.length >= 100)} onClick={() => toggle(album.id)} className={`${buttonClass} mt-2 w-full whitespace-nowrap max-sm:px-2 ${selected.includes(album.id) ? "border-green-400 text-green-300" : ""}`}>{selected.includes(album.id) ? "Selected" : "Add album"}</button>
              </div>
            </li>
          ))}
        </ul>
        {loading && <p role="status" className="mt-6 text-zinc-400">Loading saved albums...</p>}
        {loadError && <p role="alert" className="mt-6 text-red-300">{loadError.message}</p>}
        {!selectionReady && selectionError && <button type="button" disabled={loading} onClick={() => { setLoading(true); setReload((value) => value + 1); }} className={`mt-4 ${buttonClass}`}>Try again</button>}
        {selectionReady && !libraryReady && loadError && <button type="button" disabled={loading} onClick={() => { setLoading(true); setReload((value) => value + 1); }} className={`mt-4 ${buttonClass}`}>Try again</button>}
        {libraryReady && nextOffset !== null && <button type="button" disabled={loading} onClick={() => void loadMore()} className={`mt-6 ${buttonClass}`}>{loadError ? "Retry loading more" : "Load more"}</button>}
      </section>
      {detailError && <p role="alert" className="text-red-300">{detailError.message}</p>}
      {reconnect && <a href={`${API_BASE_URL}/api/auth/spotify/start`} className={buttonClass}>Reconnect Spotify</a>}
      {detail && <AlbumDetail album={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
