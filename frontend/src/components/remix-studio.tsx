"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import type { Album } from "@/components/album-detail";
import { ArtworkExplorer } from "@/components/artwork-explorer";
import { exportArtwork } from "@/components/artwork-export";
import { mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import { control, defaultStyle, jsonBody, layoutFor, remixRequest, type Remix, type RemixStyle, type ShapePreset } from "@/components/remix-design";

const palettes = [
  { name: "Midnight", background: "#15131c", frame: "#efaa73" },
  { name: "Bone", background: "#e8e2d6", frame: "#38342f" },
  { name: "Blood moon", background: "#351820", frame: "#e67b66" },
  { name: "Witching hour", background: "#24213a", frame: "#b9a4ed" },
  { name: "Acid", background: "#17211b", frame: "#cef189" },
];
type Snapshot = MosaicLayout & { id: string; month: string };

export function RemixStudio({ mosaic, albums }: { mosaic: Snapshot; albums: Record<string, Album> }) {
  const [presets, setPresets] = useState<ShapePreset[]>([]);
  const [remixes, setRemixes] = useState<Remix[]>([]);
  const [active, setActive] = useState<Remix | null>(null);
  const [editing, setEditing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("October after dark");
  const [style, setStyle] = useState<RemixStyle>(defaultStyle);
  const [background, setBackground] = useState<string | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  const photoUrl = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const [exportFile, setExportFile] = useState<File | null>(null);
  const downloadUrl = useRef<string | null>(null);
  const [download, setDownload] = useState<string | null>(null);
  const editor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      remixRequest<{ items: ShapePreset[] }>("/api/me/remix-shapes", { signal: controller.signal }),
      remixRequest<{ items: Remix[] }>(`/api/me/monthly-mosaics/${mosaic.id}/remixes`, { signal: controller.signal }),
    ]).then(([shapes, saved]) => { if (!controller.signal.aborted) { setPresets(shapes.items); setRemixes(saved.items); setError(null); } }).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [mosaic.id, reload]);
  useEffect(() => () => { if (photoUrl.current) URL.revokeObjectURL(photoUrl.current); if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current); }, []);

  const chosen = presets.find((preset) => preset.key === style.shape);
  const layout = editing && chosen ? layoutFor(chosen, mosaic.tiles) : active?.layout ?? mosaic;
  const visibleStyle = editing ? style : active?.style ?? defaultStyle;
  const visibleBackground = editing ? background : active?.background_url ?? null;
  // Older snapshots can have a representative song without a song ID on each tile.
  const displayAlbums = { ...albums };
  for (const tile of layout.tiles) {
    const key = mosaicAlbumKey(tile);
    displayAlbums[key] ??= albums[`${tile.spotifyAlbumId}:`];
  }
  const shareUrl = active?.share_id && typeof window !== "undefined" ? `${window.location.origin}/artwork/${active.share_id}` : null;
  const change = <K extends keyof RemixStyle>(key: K, value: RemixStyle[K]) => { setStyle((current) => ({ ...current, [key]: value })); setExportFile(null); setDownload(null); };
  const remember = (saved: Remix) => { setActive(saved); setRemixes((current) => [...current.filter((item) => item.id !== saved.id), saved]); };
  function start(remix: Remix | null) {
    setEditingId(remix?.id ?? null); setStyle(remix?.style ?? defaultStyle);
    setName(remix?.name ?? `${new Date(`${mosaic.month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", timeZone: "UTC" })} after dark`);
    setBackground(remix?.background_url ?? null); setPhoto(null); setRemovePhoto(false);
    setEditing(true); setError(null); setStatus(""); setExportFile(null); setDownload(null);
  }
  async function save() {
    setBusy(true); setError(null);
    try {
      let saved = await remixRequest<Remix>(editingId ? `/api/me/remixes/${editingId}` : `/api/me/monthly-mosaics/${mosaic.id}/remixes`, { method: editingId ? "PUT" : "POST", ...jsonBody({ name, style }) });
      setEditingId(saved.id); // Retrying a failed image upload updates the same saved design.
      if (photo) saved = await remixRequest<Remix>(`/api/me/remixes/${saved.id}/background`, { method: "PUT", body: photo });
      else if (removePhoto) saved = await remixRequest<Remix>(`/api/me/remixes/${saved.id}/background`, { method: "DELETE" });
      remember(saved); setEditing(false); setStatus("Remix saved to your collection.");
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function sharing(enable: boolean) {
    if (!active) return;
    setBusy(true); setError(null);
    try {
      if (enable) { const result = await remixRequest<{ share_id: string }>(`/api/me/remixes/${active.id}/share`, { method: "POST" }); remember({ ...active, share_id: result.share_id }); setStatus("Your link is ready. Anyone with it can explore this design and its songs."); }
      else { await remixRequest(`/api/me/remixes/${active.id}/share`, { method: "DELETE" }); remember({ ...active, share_id: null }); setStatus("Sharing is off. The previous link no longer works."); }
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function prepare(format: "story" | "square") {
    setBusy(true); setError(null); setExportFile(null); setDownload(null);
    try {
      const blob = await exportArtwork({ layout, albums: displayAlbums, style: visibleStyle, background: visibleBackground, month: mosaic.month, format });
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
      downloadUrl.current = URL.createObjectURL(blob); setDownload(downloadUrl.current);
      setExportFile(new File([blob], `mosaic-${mosaic.month}-${format}.png`, { type: "image/png" }));
      setStatus("Your card is ready. Download it or share it from your device.");
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function nativeShare() {
    if (!exportFile) return;
    try { await navigator.share({ files: [exportFile], ...(shareUrl ? { url: shareUrl } : {}) }); }
    catch (failure) { if ((failure as Error).name !== "AbortError") setError("Your device could not share the card. Use Download and Copy link instead."); }
  }
  async function copyLink() {
    if (!shareUrl) return;
    try { await navigator.clipboard.writeText(shareUrl); setStatus("Link copied. Add it as the link sticker on your story."); }
    catch { setError("Copy the link from the field below."); }
  }
  async function removeRemix() {
    if (!active || !window.confirm(`Delete “${active.name}” and disable its shared link? Your original monthly artwork stays saved.`)) return;
    setBusy(true);
    try { await remixRequest(`/api/me/remixes/${active.id}`, { method: "DELETE" }); setRemixes((items) => items.filter((item) => item.id !== active.id)); setActive(null); setStatus("Remix deleted."); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="mt-6">
    {!editing && <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[.25em] text-orange-200/70">Your listening, reimagined</p><h3 className="mt-1 text-lg font-medium">{active?.name ?? "The original"}</h3></div><button type="button" disabled={busy || !presets.length} className={`${control} border-orange-200/40 bg-orange-200 text-zinc-950 hover:bg-orange-100`} onClick={() => start(null)}>✦ Remix this artwork</button></div>}
    <div className={editing ? "grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]" : ""}>
      <div className="min-w-0"><ArtworkExplorer key={`${editing ? "draft" : active?.id ?? "original"}`} layout={layout} albums={displayAlbums} style={visibleStyle} background={visibleBackground} /></div>
      {editing && <div ref={editor} className="space-y-6 rounded-2xl border border-white/10 bg-black/15 p-4 sm:p-5">
        <div className="flex items-center justify-between"><h3 className="text-lg font-semibold">Make it yours</h3><span className="text-[10px] uppercase tracking-widest text-orange-200">Halloween collection</span></div>
        <fieldset disabled={busy} className="space-y-6 disabled:opacity-60">
          <label className="block text-xs text-zinc-400">Design name<input maxLength={60} value={name} onChange={(event) => setName(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-white/15 bg-white/5 px-3 text-sm text-white" /></label>
          <fieldset><legend className="mb-3 text-xs font-medium uppercase tracking-widest text-zinc-400">01 / Shape</legend><div className="grid grid-cols-4 gap-2">{presets.map((preset) => <button type="button" key={preset.key} aria-pressed={style.shape === preset.key} onClick={() => change("shape", preset.key)} className={`min-h-20 rounded-xl border p-2 text-center transition ${style.shape === preset.key ? "border-orange-200 bg-orange-200/10 text-orange-100" : "border-white/10 text-zinc-400 hover:border-white/40"}`}><svg aria-hidden="true" viewBox="0 0 12 12" className="mx-auto mb-2 h-9 w-9" fill="currentColor">{preset.coordinates.map((point) => <rect key={`${point.x}:${point.y}`} x={point.x} y={point.y} width=".85" height=".85" />)}</svg><span className="text-[11px]">{preset.label}</span></button>)}</div></fieldset>
          <fieldset><legend className="mb-3 text-xs font-medium uppercase tracking-widest text-zinc-400">02 / Background</legend><div className="flex flex-wrap gap-2">{palettes.map((palette) => <button type="button" key={palette.name} title={palette.name} aria-label={`${palette.name} palette`} className="h-11 w-11 rounded-full border-2 border-white/15 focus-visible:outline-2 focus-visible:outline-orange-200" style={{ background: `linear-gradient(135deg, ${palette.background} 60%, ${palette.frame} 60%)` }} onClick={() => { change("background_color", palette.background); change("frame_color", palette.frame); }} />)}</div><label className="mt-3 flex min-h-11 items-center justify-between text-sm">Custom color<input type="color" aria-label="Background color" value={style.background_color} onChange={(event) => change("background_color", event.target.value)} className="h-11 w-14 cursor-pointer rounded-lg border-0 bg-transparent" /></label>
            <label className={`${control} mt-3 w-full cursor-pointer`}>Upload a photo<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 8_000_000) { setError("Choose a JPEG, PNG, or WebP photo under 8 MB."); return; } if (photoUrl.current) URL.revokeObjectURL(photoUrl.current); photoUrl.current = URL.createObjectURL(file); setPhoto(file); setBackground(photoUrl.current); setRemovePhoto(false); setError(null); setExportFile(null); setDownload(null); }} /></label>
            <p className="mt-2 text-[11px] leading-5 text-zinc-500">JPEG, PNG or WebP · up to 8 MB. Your photo is included if you share this design.</p>
            {background && <><Range label="Photo darkness" value={style.photo_dim} max={80} onChange={(value) => change("photo_dim", value)} /><Range label="Photo horizontal position" value={style.photo_x} max={100} onChange={(value) => change("photo_x", value)} /><Range label="Photo vertical position" value={style.photo_y} max={100} onChange={(value) => change("photo_y", value)} /><button type="button" className={`${control} mt-2`} onClick={() => { setBackground(null); setPhoto(null); setRemovePhoto(true); }}>Remove photo</button></>}
          </fieldset>
          <fieldset><legend className="mb-3 text-xs font-medium uppercase tracking-widest text-zinc-400">03 / Frame</legend><div className="grid grid-cols-2 gap-2">{(["none", "line", "double", "mat"] as const).map((frame) => <button type="button" key={frame} aria-pressed={style.frame_style === frame} onClick={() => change("frame_style", frame)} className={`${control} capitalize ${style.frame_style === frame ? "border-orange-200 text-orange-100" : "text-zinc-400"}`}>{frame === "mat" ? "Gallery mat" : frame}</button>)}</div><label className="mt-3 flex min-h-11 items-center justify-between text-sm">Frame color<input type="color" aria-label="Frame color" value={style.frame_color} onChange={(event) => change("frame_color", event.target.value)} className="h-11 w-14 cursor-pointer bg-transparent" /></label><Range label="Frame width" value={style.frame_width} min={1} max={24} onChange={(value) => change("frame_width", value)} /><Range label="Rounded corners" value={style.corner_radius} max={48} onChange={(value) => change("corner_radius", value)} /></fieldset>
        </fieldset>
        {active?.share_id && editingId === active.id && <p className="text-xs leading-5 text-orange-100/80">Saving updates the design on your existing shared link.</p>}
        <div className="sticky bottom-2 flex gap-2 rounded-2xl bg-[#17151b]/95 p-2 backdrop-blur"><button disabled={busy} className={`${control} flex-1 bg-orange-200 text-zinc-950`} onClick={() => void save()}>{busy ? "Saving…" : "Save remix"}</button><button disabled={busy} className={control} onClick={() => { setEditing(false); setError(null); }}>Cancel</button></div>
      </div>}
    </div>
    {!editing && <>
      {remixes.length > 0 && <section className="mt-7 border-t border-white/10 pt-5" aria-label="Saved designs"><div className="mb-3 flex items-center justify-between"><h3 className="text-xs uppercase tracking-widest text-zinc-400">Your designs</h3><span className="text-xs text-zinc-500">{remixes.length} / 12</span></div><div className="flex flex-wrap gap-2"><button className={`${control} ${!active ? "border-orange-200 text-orange-100" : ""}`} aria-pressed={!active} onClick={() => { setActive(null); setExportFile(null); setDownload(null); }}>Original</button>{remixes.map((remix) => <button className={`${control} max-w-full ${active?.id === remix.id ? "border-orange-200 text-orange-100" : ""}`} key={remix.id} aria-pressed={active?.id === remix.id} onClick={() => { setActive(remix); setExportFile(null); setDownload(null); }}><span className="h-3 w-3 shrink-0 rounded-full border border-white/20" style={{ backgroundColor: remix.style.background_color }} /><span className="truncate">{remix.name}</span></button>)}</div>{active && <div className="mt-3 flex gap-2"><button disabled={busy} className={control} onClick={() => start(active)}>Edit design</button><button disabled={busy} className={`${control} text-zinc-400`} onClick={() => void removeRemix()}>Delete</button></div>}</section>}
      <section className="mt-7 rounded-2xl border border-white/10 bg-white/[.025] p-4 sm:p-5" aria-label="Share artwork"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] uppercase tracking-[.25em] text-orange-200/70">Made to be seen</p><h3 className="mt-1 text-xl font-medium">A little art. A lot of you.</h3></div><span aria-hidden="true" className="text-3xl text-orange-200">↗</span></div><p className="mt-2 max-w-md text-sm leading-6 text-zinc-400">Export a clean card for your story or feed. Add a link so friends can explore the music inside.</p><div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} className={control} onClick={() => void prepare("story")}>{busy ? "Working…" : "Create story card"}</button><button disabled={busy} className={control} onClick={() => void prepare("square")}>Create square card</button></div>
        {download && exportFile && <div className="mt-4 flex flex-wrap items-center gap-4"><Image src={download} alt="Exported artwork card preview" width={216} height={exportFile.name.includes("story") ? 384 : 216} unoptimized className="max-h-72 w-auto rounded-xl border border-white/10" /><div className="flex flex-wrap gap-2"><a className={`${control} bg-orange-200 text-zinc-950`} href={download} download={exportFile.name}>Download PNG</a>{typeof navigator !== "undefined" && navigator.canShare?.({ files: [exportFile] }) && <button className={control} onClick={() => void nativeShare()}>Share from device</button>}</div></div>}
        {active ? <div className="mt-5 border-t border-white/10 pt-4">{shareUrl ? <><label className="block text-xs text-zinc-400">Interactive artwork link<input readOnly aria-label="Artwork share link" value={shareUrl} onFocus={(event) => event.target.select()} className="mt-2 min-h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white" /></label><div className="mt-3 flex flex-wrap gap-2"><button className={control} onClick={() => void copyLink()}>Copy link</button><a className={control} href={shareUrl} target="_blank" rel="noopener noreferrer">Preview shared page ↗</a><button disabled={busy} className={`${control} text-zinc-400`} onClick={() => void sharing(false)}>Turn sharing off</button></div><p className="mt-3 text-xs leading-5 text-zinc-500">Anyone with this link can see this design, your display name, its photo, and its songs. Add the link as a sticker when posting your story.</p></> : <><p className="mb-3 text-xs leading-5 text-zinc-400">Create a public link for this design, your display name, its photo, and its songs. Your other months stay private.</p><button disabled={busy} className={control} onClick={() => void sharing(true)}>Create share link</button></>}</div> : <p className="mt-4 text-xs text-zinc-500">Save a remix to create an interactive share link.</p>}
      </section>
    </>}
    {status && <p role="status" className="mt-4 text-sm leading-6 text-orange-100">{status}</p>}
    {error && <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-300">{error}</p>{!presets.length && <button className={`${control} mt-2`} onClick={() => setReload((value) => value + 1)}>Retry studio</button>}</div>}
  </div>;
}

function Range({ label, value, min = 0, max, onChange }: { label: string; value: number; min?: number; max: number; onChange: (value: number) => void }) {
  return <label className="mt-4 block text-xs text-zinc-400"><span className="flex justify-between">{label}<span className="tabular-nums">{value}</span></span><input type="range" aria-label={label} min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 h-11 w-full accent-orange-200" /></label>;
}
