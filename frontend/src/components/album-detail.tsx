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
};

export function AlbumDetail({ album, onClose }: { album: Album; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  return (
    <dialog ref={dialog} onClose={(event) => {
      // Strict Mode reopens the dialog after cleanup; ignore its queued close event.
      if (!event.currentTarget.open) onClose();
    }} aria-labelledby="album-detail-title" className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900 p-6 text-white backdrop:bg-black/75">
      <button type="button" autoFocus onClick={onClose} className="mb-5 min-h-11 rounded-full border border-zinc-600 px-5 focus-visible:outline-2 focus-visible:outline-green-400">Close details</button>
      {album.imageUrl && <Image src={album.imageUrl} alt={`Cover of ${album.name}`} width={300} height={300} unoptimized className="mx-auto aspect-square w-full object-contain" />}
      <h2 id="album-detail-title" className="mt-5 break-words text-2xl font-bold">{album.name}</h2>
      <p className="mt-2 break-words text-zinc-300">{album.artists.join(", ") || "Unknown artist"}</p>
      <p className="mt-3 text-sm text-zinc-400">{album.releaseDate || "Release date unavailable"} · {album.totalTracks} tracks</p>
      <a href={album.spotifyUrl} target="_blank" rel="noopener noreferrer" className="mt-6 inline-flex min-h-11 items-center rounded-full bg-green-500 px-5 font-semibold text-black focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400">Open in Spotify</a>
    </dialog>
  );
}
