"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlbumDetail, type Album } from "@/components/album-detail";
import { MosaicCanvas, mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import { ArtworkFrame } from "@/components/artwork-frame";
import { control, defaultStyle, uniqueSongs, type RemixStyle } from "@/components/remix-design";

export function ArtworkExplorer({ layout, albums, style = defaultStyle, background, toolbarAction }: { layout: MosaicLayout; albums: Record<string, Album>; style?: RemixStyle; background?: string | null; toolbarAction?: ReactNode }) {
  const [mode, setMode] = useState<"artwork" | "songs">("artwork");
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<string>();
  const [filter, setFilter] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const songs = uniqueSongs(layout.tiles);
  const filteredSongs = songs.map((song, index) => {
    const album = albums[mosaicAlbumKey(song)];
    const title = album?.representativeTrack?.name ?? album?.name ?? "Saved song";
    const artists = (album?.representativeTrack?.artists ?? album?.artists ?? []).join(", ");
    return { song, index, album, title, artists };
  }).filter(({ title, artists }) => `${title} ${artists}`.toLowerCase().includes(filter.toLowerCase()));
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
      <div className="inline-flex rounded-full bg-accent-soft/60 p-1" aria-label="Artwork view">{(["artwork", "songs"] as const).map((item) => <button key={item} type="button" aria-pressed={mode === item} onClick={() => setMode(item)} className={`min-h-11 rounded-full px-3 text-sm capitalize transition sm:px-5 ${mode === item ? "bg-surface text-text-primary shadow-sm" : "text-text-secondary hover:text-text-primary"}`}>{item}</button>)}</div>
      <div className="ml-auto flex items-center gap-2">
        <button type="button" className={`${control} !w-11 !px-0`} title={fullscreen ? "Close full screen" : "Full screen"} aria-label={fullscreen ? "Close full screen" : "Full screen"} onClick={() => setFullscreen(!fullscreen)}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{fullscreen ? <path d="m6 6 12 12M18 6 6 18" /> : <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />}</svg></button>
        {!fullscreen && toolbarAction}
      </div>
    </div>
    {mode === "artwork" ? <>
      <div ref={viewport} className="mx-auto aspect-square w-full max-w-[min(100%,65dvh)] overflow-auto overscroll-contain rounded-2xl" tabIndex={0} aria-label="Scrollable artwork. Select a cover to see its song, use zoom controls, or switch to Songs for larger targets.">
        <div style={{ width: `${zoom * 100}%` }}><ArtworkFrame style={style} background={background}><MosaicCanvas layout={layout} albums={{}} tileAlbums={albums} selectedKey={highlight} onSelect={(tile) => choose(songs.findIndex((song) => mosaicAlbumKey(song) === mosaicAlbumKey(tile)))} showListeningTrack eagerImages /></ArtworkFrame></div>
      </div>
      <div className="mt-4 flex items-center justify-center gap-1" aria-label="Artwork zoom"><button className="min-h-11 min-w-11 rounded-full text-xl text-text-secondary transition hover:bg-accent-soft disabled:opacity-30" aria-label="Zoom out" disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - 0.5))}>−</button><button className="min-h-11 rounded-full px-3 text-xs text-text-secondary transition hover:bg-accent-soft" aria-label="Fit artwork" onClick={() => setZoom(1)}>Fit</button><output className="min-w-12 text-center text-xs tabular-nums text-text-secondary">{Math.round(zoom * 100)}%</output><button className="min-h-11 min-w-11 rounded-full text-xl text-text-secondary transition hover:bg-accent-soft disabled:opacity-30" aria-label="Zoom in" disabled={zoom >= 3} onClick={() => setZoom(Math.min(3, zoom + 0.5))}>+</button></div>
    </> : <div>
      <label className="mb-3 block"><span className="sr-only">Find a song or artist</span><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Find a song or artist" className="min-h-12 w-full rounded-xl border border-border bg-surface px-4 text-sm outline-offset-4" /></label>
      <ul className="max-h-[65dvh] space-y-1 overflow-y-auto">{filteredSongs.map(({ song, index, album, title, artists }) => {
        return <li key={mosaicAlbumKey(song)}><button type="button" onClick={() => choose(index)} className="flex min-h-20 w-full items-center gap-3 rounded-xl p-2 text-left transition hover:bg-accent-soft/60 focus-visible:outline-2 focus-visible:outline-accent">{album?.imageUrl ? <Image src={album.imageUrl} alt="" width={56} height={56} unoptimized className="h-14 w-14 shrink-0 rounded-lg" /> : <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">♪</span>}<span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{title}</span><span className="mt-1 block truncate text-xs text-text-secondary">{artists || "Open to explore"}</span></span><span aria-hidden="true" className="pr-2 text-text-secondary">↗</span></button></li>;
      })}</ul>
      {filteredSongs.length === 0 && <p role="status" className="py-10 text-center text-sm text-text-secondary">No songs found. Try another song or artist.</p>}
    </div>}
  </>;
  return <>
    {!fullscreen && view}
    {fullscreen && <dialog ref={dialog} onClose={(event) => { if (!event.currentTarget.open) setFullscreen(false); }} aria-label="Explore artwork" className="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none overflow-y-auto bg-background p-4 text-text-primary sm:p-8"><div className="mx-auto max-w-3xl">{view}</div></dialog>}
    {current && selected !== null && <AlbumDetail album={current} showListeningTrack onClose={() => setSelected(null)} onPrevious={() => choose((selected - 1 + songs.length) % songs.length)} onNext={() => choose((selected + 1) % songs.length)} position={`${selected + 1} / ${songs.length}`} onShowArtwork={() => { setSelected(null); setMode("artwork"); setZoom(2.5); setHighlight(mosaicAlbumKey(songs[selected])); }} />}
  </>;
}
