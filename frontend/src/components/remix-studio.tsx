"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import type { Album } from "@/components/album-detail";
import { ArtworkExplorer } from "@/components/artwork-explorer";
import { exportArtwork } from "@/components/artwork-export";
import { mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import { control, defaultStyle, jsonBody, layoutFor, remixRequest, type Remix, type RemixStyle, type ShapePreset } from "@/components/remix-design";

const palettes = [
  { name: "Forest", background: defaultStyle.background_color, frame: defaultStyle.frame_color },
  { name: "Midnight", background: "#15131c", frame: "#efaa73" },
  { name: "Paper", background: "#e8e2d6", frame: "#38342f" },
  { name: "Rose", background: "#351820", frame: "#e67b66" },
  { name: "Lilac", background: "#24213a", frame: "#b9a4ed" },
  { name: "Moss", background: "#17211b", frame: "#cef189" },
];
type Snapshot = MosaicLayout & { id: string; month: string };

export function RemixStudio({ mosaic, albums }: { mosaic: Snapshot; albums: Record<string, Album> }) {
  const [presets, setPresets] = useState<ShapePreset[]>([]);
  const [remixes, setRemixes] = useState<Remix[]>([]);
  const [active, setActive] = useState<Remix | null>(null);
  const [editing, setEditing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("My design");
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
  useEffect(() => {
    if (!editing) return;
    editor.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 1279px)").matches) editor.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [editing]);

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
    setName(remix?.name ?? `${new Date(`${mosaic.month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", timeZone: "UTC" })} design`);
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
      remember(saved); setEditing(false); setStatus("Design saved.");
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function sharing(enable: boolean) {
    if (!active) return;
    setBusy(true); setError(null);
    try {
      if (enable) { const result = await remixRequest<{ share_id: string }>(`/api/me/remixes/${active.id}/share`, { method: "POST" }); remember({ ...active, share_id: result.share_id }); setStatus("Share link ready."); }
      else { await remixRequest(`/api/me/remixes/${active.id}/share`, { method: "DELETE" }); remember({ ...active, share_id: null }); setStatus("Sharing off. Previous link disabled."); }
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
      setStatus("Card ready.");
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
    try { await navigator.clipboard.writeText(shareUrl); setStatus("Link copied."); }
    catch { setError("Copy the link from the field below."); }
  }
  async function removeRemix() {
    if (!active || !window.confirm(`Delete “${active.name}” and disable its shared link? Your monthly artwork stays saved.`)) return;
    setBusy(true);
    try { await remixRequest(`/api/me/remixes/${active.id}`, { method: "DELETE" }); setRemixes((items) => items.filter((item) => item.id !== active.id)); setActive(null); setStatus("Design deleted."); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="mt-6">
    <div className={editing ? "grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]" : ""}>
      <div className="min-w-0"><ArtworkExplorer key={`${editing ? "draft" : active?.id ?? "original"}`} layout={layout} albums={displayAlbums} style={visibleStyle} background={visibleBackground} toolbarAction={!editing && <button type="button" disabled={busy || !presets.length} className="mosaic-button-primary" onClick={() => start(null)}>Customize</button>} /></div>
      {editing && <div ref={editor} tabIndex={-1} aria-label="Customize artwork" className="scroll-mt-6 space-y-6 rounded-2xl border border-border bg-surface p-4 outline-none sm:p-5">
        <h3 className="mosaic-display text-2xl">Make it yours</h3>
        <fieldset disabled={busy} className="space-y-6 disabled:opacity-60">
          <label className="block text-xs text-text-secondary">Design name<input maxLength={60} value={name} onChange={(event) => setName(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm text-text-primary" /></label>
          <fieldset><legend className="mb-3 text-sm font-medium text-text-secondary">Shape</legend><div className="grid grid-cols-4 gap-2">{presets.map((preset) => <button type="button" key={preset.key} aria-pressed={style.shape === preset.key} onClick={() => change("shape", preset.key)} className={`min-h-20 rounded-xl border p-2 text-center transition ${style.shape === preset.key ? "border-accent bg-accent-soft text-accent" : "border-border text-text-secondary hover:border-accent"}`}><svg aria-hidden="true" viewBox="0 0 12 12" className="mx-auto mb-2 h-9 w-9" fill="currentColor">{preset.coordinates.map((point) => <rect key={`${point.x}:${point.y}`} x={point.x} y={point.y} width=".85" height=".85" />)}</svg><span className="text-[11px]">{preset.label}</span></button>)}</div></fieldset>
          <fieldset><legend className="mb-3 text-sm font-medium text-text-secondary">Background</legend><div className="flex flex-wrap gap-2">{palettes.map((palette) => <button type="button" key={palette.name} title={palette.name} aria-label={`${palette.name} palette`} aria-pressed={style.background_color === palette.background && style.frame_color === palette.frame} className={`h-11 w-11 rounded-full border-2 focus-visible:outline-2 focus-visible:outline-accent ${style.background_color === palette.background && style.frame_color === palette.frame ? "border-accent ring-2 ring-accent/25 ring-offset-2 ring-offset-surface" : "border-border"}`} style={{ background: `linear-gradient(135deg, ${palette.background} 60%, ${palette.frame} 60%)` }} onClick={() => { change("background_color", palette.background); change("frame_color", palette.frame); }} />)}</div><label className="mt-3 flex min-h-11 items-center justify-between text-sm">Custom color<input type="color" aria-label="Background color" value={style.background_color} onChange={(event) => change("background_color", event.target.value)} className="h-11 w-14 cursor-pointer rounded-lg border-0 bg-transparent" /></label>
            <label className={`${control} mt-3 w-full cursor-pointer focus-within:outline-2 focus-within:outline-offset-4 focus-within:outline-accent`}>Add a photo<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 8_000_000) { setError("Choose a JPEG, PNG, or WebP photo under 8 MB."); return; } if (photoUrl.current) URL.revokeObjectURL(photoUrl.current); photoUrl.current = URL.createObjectURL(file); setPhoto(file); setBackground(photoUrl.current); setRemovePhoto(false); setError(null); setExportFile(null); setDownload(null); }} /></label>
            <p className="mt-2 text-[11px] leading-5 text-text-secondary">JPEG, PNG or WebP · up to 8 MB. Visible when shared.</p>
            {background && <><Range label="Photo darkness" value={style.photo_dim} max={80} onChange={(value) => change("photo_dim", value)} /><Range label="Photo horizontal position" value={style.photo_x} max={100} onChange={(value) => change("photo_x", value)} /><Range label="Photo vertical position" value={style.photo_y} max={100} onChange={(value) => change("photo_y", value)} /><button type="button" className={`${control} mt-2`} onClick={() => { setBackground(null); setPhoto(null); setRemovePhoto(true); }}>Remove photo</button></>}
          </fieldset>
          <details className="border-t border-border pt-2"><summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">Frame &amp; corners</summary><fieldset className="mt-2"><legend className="sr-only">Frame</legend><div className="grid grid-cols-2 gap-2">{(["none", "line", "double", "mat"] as const).map((frame) => <button type="button" key={frame} aria-pressed={style.frame_style === frame} onClick={() => change("frame_style", frame)} className={`${control} capitalize ${style.frame_style === frame ? "border-accent bg-accent-soft text-accent" : "text-text-secondary"}`}>{frame === "mat" ? "Gallery mat" : frame}</button>)}</div><label className="mt-3 flex min-h-11 items-center justify-between text-sm">Frame color<input type="color" aria-label="Frame color" value={style.frame_color} onChange={(event) => change("frame_color", event.target.value)} className="h-11 w-14 cursor-pointer bg-transparent" /></label><Range label="Frame width" value={style.frame_width} min={1} max={24} onChange={(value) => change("frame_width", value)} /><Range label="Rounded corners" value={style.corner_radius} max={48} onChange={(value) => change("corner_radius", value)} /></fieldset></details>
        </fieldset>
        {active?.share_id && editingId === active.id && <p className="text-xs leading-5 text-accent/80">Saving updates the design on your existing shared link.</p>}
        <div className="sticky bottom-2 flex gap-2 rounded-2xl bg-surface/95 py-2 backdrop-blur"><button disabled={busy} className="mosaic-button-primary flex-1" onClick={() => void save()}>{busy ? "Saving…" : "Save design"}</button><button disabled={busy} className={control} onClick={() => { setEditing(false); setError(null); }}>Cancel</button></div>
      </div>}
    </div>
    {!editing && <>
      {remixes.length > 0 && <section className="mt-6 border-t border-border pt-5" aria-label="Saved designs"><h3 className="mb-3 text-sm font-medium text-text-secondary">Your designs</h3><div className="flex flex-wrap gap-2"><button className={`${control} ${!active ? "border-accent bg-accent-soft text-accent" : ""}`} aria-pressed={!active} onClick={() => { setActive(null); setExportFile(null); setDownload(null); }}>Monthly artwork</button>{remixes.map((remix) => <button className={`${control} max-w-full ${active?.id === remix.id ? "border-accent bg-accent-soft text-accent" : ""}`} key={remix.id} aria-pressed={active?.id === remix.id} onClick={() => { setActive(remix); setExportFile(null); setDownload(null); }}><span className="h-3 w-3 shrink-0 rounded-full border border-border" style={{ backgroundColor: remix.style.background_color }} /><span className="truncate">{remix.name}</span></button>)}</div>{active && <div className="mt-3 flex gap-2"><button disabled={busy} className={control} onClick={() => start(active)}>Edit design</button><button disabled={busy} className={`${control} text-text-secondary`} onClick={() => void removeRemix()}>Delete</button></div>}</section>}
      <details className="mt-6 border-t border-border pt-2">
        <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent">Download &amp; share</summary>
        <div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} className={control} onClick={() => void prepare("story")}>{busy ? "Working…" : "Create story card"}</button><button disabled={busy} className={control} onClick={() => void prepare("square")}>Create square card</button></div>
        {download && exportFile && <div className="mt-4 flex flex-wrap items-center gap-4"><Image src={download} alt="Exported artwork card preview" width={216} height={exportFile.name.includes("story") ? 384 : 216} unoptimized className="max-h-72 w-auto rounded-xl border border-border" /><div className="flex flex-wrap gap-2"><a className="mosaic-button-primary" href={download} download={exportFile.name}>Download PNG</a>{typeof navigator !== "undefined" && navigator.canShare?.({ files: [exportFile] }) && <button className={control} onClick={() => void nativeShare()}>Share from device</button>}</div></div>}
        {active ? <div className="mt-5 border-t border-border pt-4">{shareUrl ? <><label className="block text-xs text-text-secondary">Interactive artwork link<input readOnly aria-label="Artwork share link" value={shareUrl} onFocus={(event) => event.target.select()} className="mt-2 min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm text-text-primary" /></label><div className="mt-3 flex flex-wrap gap-2"><button className={control} onClick={() => void copyLink()}>Copy link</button><a className={control} href={shareUrl} target="_blank" rel="noopener noreferrer">Preview shared page ↗</a><button disabled={busy} className={`${control} text-text-secondary`} onClick={() => void sharing(false)}>Turn sharing off</button></div><p className="mt-3 text-xs leading-5 text-text-secondary">Anyone with the link can see this design, your name, photo, and songs.</p></> : <><p className="mb-3 text-xs leading-5 text-text-secondary">Anyone with the link can see this design, your name, photo, and songs. Other months stay private.</p><button disabled={busy} className={control} onClick={() => void sharing(true)}>Create share link</button></>}</div> : <p className="mt-4 text-xs text-text-secondary">Save a design to share a link.</p>}
      </details>
    </>}
    {status && <p role="status" className="mt-4 text-sm leading-6 text-accent">{status}</p>}
    {error && <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-700">{error}</p>{!presets.length && <button className={`${control} mt-2`} onClick={() => setReload((value) => value + 1)}>Try again</button>}</div>}
  </div>;
}

function Range({ label, value, min = 0, max, onChange }: { label: string; value: number; min?: number; max: number; onChange: (value: number) => void }) {
  return <label className="mt-4 block text-xs text-text-secondary"><span className="flex justify-between">{label}<span className="tabular-nums">{value}</span></span><input type="range" aria-label={label} min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 h-11 w-full accent-accent" /></label>;
}
