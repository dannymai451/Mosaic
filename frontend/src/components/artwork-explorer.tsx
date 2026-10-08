"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { AlbumDetail, type Album } from "@/components/album-detail";
import { MosaicCanvas, mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import { ArtworkFrame } from "@/components/artwork-frame";
import { control, defaultStyle, uniqueSongs, type RemixStyle } from "@/components/remix-design";

export function ArtworkExplorer({ layout, albums, style = defaultStyle, background }: { layout: MosaicLayout; albums: Record<string, Album>; style?: RemixStyle; background?: string | null }) {
  const [mode, setMode] = useState<"artwork" | "songs">("artwork");
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<string>();
  const [filter, setFilter] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const songs = uniqueSongs(layout.tiles);
  const current = selected === null ? undefined : albums[mosaicAlbumKey(songs[selected])];
  useEffect(() => {
    if (!fullscreen) return;
    const element = dialog.current;
    const previous = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    element?.showModal();
    return () => { element?.close(); document.documentElement.style.overflow = previous; };
  }, [fullscreen]);
  useEffect(() => {
    if (!highlight || mode !== "artwork") return;
    viewport.current?.querySelector<HTMLElement>(`[data-song="${highlight}"]`)?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
  }, [highlight, zoom, mode]);
  const choose = (index: number) => { setSelected(index); setHighlight(mosaicAlbumKey(songs[index])); };
  const view = <>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div className="inline-flex rounded-full bg-white/5 p-1" aria-label="Artwork view">{(["artwork", "songs"] as const).map((item) => <button key={item} type="button" aria-pressed={mode === item} onClick={() => setMode(item)} className={`min-h-11 rounded-full px-5 text-sm capitalize ${mode === item ? "bg-[#eee9df] text-zinc-950" : "text-zinc-400"}`}>{item}{item === "songs" ? ` · ${songs.length}` : ""}</button>)}</div>
      <button type="button" className={control} onClick={() => setFullscreen(!fullscreen)}>{fullscreen ? "Close full screen" : "Explore full screen ↗"}</button>
    </div>
    {mode === "artwork" ? <>
      <div ref={viewport} className="mx-auto aspect-square w-full max-w-[min(100%,65dvh)] overflow-auto overscroll-contain rounded-2xl" tabIndex={0} aria-label="Scrollable artwork. Use zoom controls or switch to Songs for larger targets.">
        <div style={{ width: `${zoom * 100}%` }}><ArtworkFrame style={style} background={background}><MosaicCanvas layout={layout} albums={{}} tileAlbums={albums} selectedKey={highlight} onSelect={(tile) => choose(songs.findIndex((song) => mosaicAlbumKey(song) === mosaicAlbumKey(tile)))} showListeningTrack eagerImages /></ArtworkFrame></div>
      </div>
      <div className="mt-4 flex items-center justify-center gap-2" aria-label="Artwork zoom"><button className={control} aria-label="Zoom out" disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - 0.5))}>−</button><button className={control} onClick={() => setZoom(1)}>Fit</button><output className="min-w-12 text-center text-xs tabular-nums text-zinc-400">{Math.round(zoom * 100)}%</output><button className={control} aria-label="Zoom in" disabled={zoom >= 3} onClick={() => setZoom(Math.min(3, zoom + 0.5))}>+</button></div>
      <p className="mt-3 text-center text-xs leading-5 text-zinc-400">Tap a cover to explore. Zoom in or use Songs for an easier browse.</p>
    </> : <div>
      <label className="mb-3 block"><span className="sr-only">Find a song or artist</span><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Find a song or artist" className="min-h-12 w-full rounded-xl border border-white/15 bg-white/5 px-4 text-sm outline-offset-4" /></label>
      <ul className="max-h-[65dvh] space-y-1 overflow-y-auto">{songs.map((song, index) => {
        const album = albums[mosaicAlbumKey(song)];
        const title = album?.representativeTrack?.name ?? album?.name ?? "Saved song";
        const artists = (album?.representativeTrack?.artists ?? album?.artists ?? []).join(", ");
        if (!`${title} ${artists}`.toLowerCase().includes(filter.toLowerCase())) return null;
        return <li key={mosaicAlbumKey(song)}><button type="button" onClick={() => choose(index)} className="flex min-h-20 w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-orange-300">{album?.imageUrl ? <Image src={album.imageUrl} alt="" width={56} height={56} unoptimized className="h-14 w-14 shrink-0 rounded-lg" /> : <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-white/10">♪</span>}<span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{title}</span><span className="mt-1 block truncate text-xs text-zinc-400">{artists || "Open to explore"}</span></span><span aria-hidden="true" className="pr-2 text-zinc-500">↗</span></button></li>;
      })}</ul>
    </div>}
  </>;
  return <>
    {!fullscreen && view}
    {fullscreen && <dialog ref={dialog} onClose={(event) => { if (!event.currentTarget.open) setFullscreen(false); }} aria-label="Explore artwork" className="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none overflow-y-auto bg-[#101014] p-4 text-white sm:p-8"><div className="mx-auto max-w-3xl">{view}</div></dialog>}
    {current && selected !== null && <AlbumDetail album={current} showListeningTrack onClose={() => setSelected(null)} onPrevious={() => choose((selected - 1 + songs.length) % songs.length)} onNext={() => choose((selected + 1) % songs.length)} position={`${selected + 1} / ${songs.length}`} onShowArtwork={() => { setSelected(null); setMode("artwork"); setZoom(2.5); setHighlight(mosaicAlbumKey(songs[selected])); }} />}
  </>;
}
