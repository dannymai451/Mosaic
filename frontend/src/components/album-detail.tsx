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
    }} aria-labelledby="album-detail-title" className={`fixed inset-0 max-h-[90dvh] max-w-md overflow-y-auto border border-zinc-700 bg-zinc-900 p-5 pt-12 text-white [scrollbar-width:none] [&::-webkit-scrollbar]:hidden backdrop:bg-black/75 ${showListeningTrack ? "m-0 mt-auto w-full rounded-t-3xl pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:m-auto sm:w-[calc(100%-2rem)] sm:rounded-3xl" : "m-auto w-[calc(100%-2rem)] rounded-2xl"}`}>
      <button type="button" autoFocus aria-label="Close details" onClick={onClose} className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center text-zinc-300 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400">
        <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"><path d="m6 6 12 12M18 6 6 18" /></svg>
      </button>
      {album.imageUrl && <Image src={album.imageUrl} alt={`Cover of ${album.name}`} width={300} height={300} unoptimized className="mx-auto aspect-square max-h-[30dvh] w-auto max-w-full object-contain" />}
      <h2 id="album-detail-title" className="mt-4 break-words text-2xl font-bold">{track?.name ?? album.name}</h2>
      <p className="mt-1 break-words text-zinc-300">{(track?.artists ?? album.artists).join(", ") || "Unknown artist"}</p>
      {showListeningTrack && !track && <p className="mt-3 text-sm leading-6 text-zinc-400">{album.trackDetailsUnavailable ? "Song details are currently unavailable." : "No song was saved with this artwork."}</p>}
      <a href={track?.spotifyUrl ?? album.spotifyUrl} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex min-h-11 items-center rounded-full bg-green-500 px-5 font-semibold text-black focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400">{track ? "Open song in Spotify" : showListeningTrack ? "Open album in Spotify" : "Open in Spotify"}</a>
      {onShowArtwork && <button type="button" onClick={onShowArtwork} className="ml-3 mt-3 min-h-11 text-sm underline underline-offset-4">Show in artwork</button>}
      {onPrevious && onNext && <nav aria-label="Browse songs" className="mt-5 flex items-center justify-between border-t border-white/10 pt-3"><button type="button" onClick={onPrevious} className="min-h-11 rounded-full border border-white/20 px-4">← Previous</button><span className="text-xs text-zinc-400" aria-live="polite">{position}</span><button type="button" onClick={onNext} className="min-h-11 rounded-full border border-white/20 px-4">Next →</button></nav>}
    </dialog>
  );
}
