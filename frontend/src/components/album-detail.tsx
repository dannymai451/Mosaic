"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";

export type Album = {
  id: string;
  name: string;
  artists: string[];
  imageUrl: string | null;
  spotifyUrl: string;
  releaseDate: string;
  totalTracks: number;
  representativeTrack?: { id: string; name: string; artists: string[]; spotifyUrl: string } | null;
  trackDetailsUnavailable?: boolean;
};

export function AlbumDetail({ album, onClose, showListeningTrack = false, onPrevious, onNext, onShowArtwork, position }: { album: Album; onClose: () => void; showListeningTrack?: boolean; onPrevious?: () => void; onNext?: () => void; onShowArtwork?: () => void; position?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const track = showListeningTrack ? album.representativeTrack : null;
  useEffect(() => {
    const element = dialog.current;
    const previousOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    element?.showModal();
    return () => {
      element?.close();
      document.documentElement.style.overflow = previousOverflow;
    };
  }, []);

  return (
    <dialog ref={dialog} onClose={(event) => {
      // Strict Mode reopens the dialog after cleanup; ignore its queued close event.
      if (!event.currentTarget.open) onClose();
    }} aria-labelledby="album-detail-title" className={`fixed inset-0 max-h-[90dvh] max-w-md overflow-y-auto border border-border bg-surface p-6 pt-14 text-text-primary shadow-2xl [scrollbar-width:none] [&::-webkit-scrollbar]:hidden backdrop:bg-[#252820]/45 backdrop:backdrop-blur-sm ${showListeningTrack ? "m-0 mt-auto w-full rounded-t-3xl pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:m-auto sm:w-[calc(100%-2rem)] sm:rounded-3xl" : "m-auto w-[calc(100%-2rem)] rounded-3xl"}`}>
      <button type="button" autoFocus aria-label="Close details" onClick={onClose} className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-full text-text-secondary transition hover:bg-accent-soft hover:text-text-primary focus-visible:outline-2 focus-visible:outline-accent">
        <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"><path d="m6 6 12 12M18 6 6 18" /></svg>
      </button>
      {album.imageUrl && <Image src={album.imageUrl} alt={`Cover of ${album.name}`} width={300} height={300} unoptimized className="mx-auto aspect-square max-h-[30dvh] w-auto max-w-full rounded-xl object-contain" />}
      <h2 id="album-detail-title" className="mt-5 break-words text-2xl font-semibold tracking-tight">{track?.name ?? album.name}</h2>
      <p className="mt-1 break-words text-text-secondary">{(track?.artists ?? album.artists).join(", ") || "Unknown artist"}</p>
      {showListeningTrack && !track && <p className="mt-3 text-sm leading-6 text-text-secondary">{album.trackDetailsUnavailable ? "Song details are currently unavailable." : "No song was saved with this artwork."}</p>}
      <div className="mt-5 flex flex-wrap items-center gap-3"><a href={track?.spotifyUrl ?? album.spotifyUrl} target="_blank" rel="noopener noreferrer" className="mosaic-button-primary">{track ? "Open song in Spotify" : showListeningTrack ? "Open album in Spotify" : "Open in Spotify"}</a>
      {onShowArtwork && <button type="button" onClick={onShowArtwork} className="min-h-11 text-sm text-text-secondary underline underline-offset-4 hover:text-accent">Show in artwork</button>}</div>
      {onPrevious && onNext && <nav aria-label="Browse songs" className="mt-5 flex items-center justify-between gap-2 border-t border-border pt-4"><button type="button" onClick={onPrevious} className="mosaic-button">← Previous</button><span className="text-xs tabular-nums text-text-secondary" aria-live="polite">{position}</span><button type="button" onClick={onNext} className="mosaic-button">Next →</button></nav>}
    </dialog>
  );
}
