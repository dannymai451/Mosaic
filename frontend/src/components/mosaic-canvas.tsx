"use client";

import Image from "next/image";
import { useState } from "react";
import { AlbumDetail, type Album } from "@/components/album-detail";

export type MosaicTile = { x: number; y: number; spotifyAlbumId: string; spotifyTrackId?: string | null };
export function mosaicAlbumKey(tile: Pick<MosaicTile, "spotifyAlbumId" | "spotifyTrackId">) {
  return `${tile.spotifyAlbumId}:${tile.spotifyTrackId ?? ""}`;
}
export type MosaicLayout = {
  preset_key: "heart" | "star" | "music-note" | "blank" | "pumpkin" | "ghost" | "bat" | "skull";
  grid_width: number;
  grid_height: number;
  tiles: MosaicTile[];
};
export type SavedMosaic = MosaicLayout & { id: string; is_active: boolean };
export type MosaicPreset = {
  key: MosaicLayout["preset_key"];
  label: string;
  grid_width: number;
  grid_height: number;
  coordinates: { x: number; y: number }[];
};

export function MosaicCanvas({ layout, albums, tileAlbums, onPlace, onSelect, selectedKey, disabled = false, linkToSpotify = false, showListeningTrack = false, eagerImages = false }: {
  layout: MosaicLayout;
  albums: Record<string, Album>;
  tileAlbums?: Record<string, Album>;
  onPlace?: (x: number, y: number) => void;
  onSelect?: (tile: MosaicTile) => void;
  selectedKey?: string;
  disabled?: boolean;
  linkToSpotify?: boolean;
  showListeningTrack?: boolean;
  eagerImages?: boolean;
}) {
  const [detail, setDetail] = useState<Album | null>(null);
  const tiles = new Map(layout.tiles.map((tile) => [`${tile.x},${tile.y}`, tile]));

  return (
    <>
      <div aria-label={onPlace ? "Mosaic placement canvas" : "Album mosaic"} className={`grid w-full ${layout.preset_key === "pumpkin" ? "gap-0.5" : "gap-1"}`} style={{ gridTemplateColumns: `repeat(${layout.grid_width}, minmax(0, 1fr))` }}>
        {Array.from({ length: layout.grid_width * layout.grid_height }, (_, index) => {
          const x = index % layout.grid_width;
          const y = Math.floor(index / layout.grid_width);
          const tile = tiles.get(`${x},${y}`);
          const album = tile && (tileAlbums?.[mosaicAlbumKey(tile)] ?? albums[tile.spotifyAlbumId]);
          const label = album?.name ?? (tile ? `Album ${tile.spotifyAlbumId}` : "Empty cell");
          const songTitle = showListeningTrack ? album?.representativeTrack?.name : undefined;
          const detailLabel = songTitle ? `${songTitle}, from ${label}` : label;
          const cover = album?.imageUrl ? (
            <Image src={album.imageUrl} alt="" width={150} height={150} unoptimized loading={eagerImages ? "eager" : "lazy"} decoding={eagerImages ? "sync" : "async"} className="aspect-square w-full object-contain" />
          ) : <span aria-hidden="true" className="flex aspect-square w-full items-center justify-center bg-zinc-800 text-xs text-zinc-300">{tile ? "♪" : "+"}</span>;
          const className = `aspect-square min-w-0 overflow-hidden ${showListeningTrack ? "rounded-[2px]" : "rounded-sm"} focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400 ${tile && selectedKey === mosaicAlbumKey(tile) ? "ring-2 ring-amber-300 ring-offset-1" : ""}`;
          if (onPlace) return (
            <button key={index} type="button" disabled={disabled} onClick={() => onPlace(x, y)} aria-label={`Row ${y + 1}, column ${x + 1}: ${label}. Place or erase tile.`} title={label} className={`${className} border border-zinc-700 disabled:opacity-60`}>
              {cover}
            </button>
          );
          if (!tile) return <span key={index} aria-hidden="true" className="aspect-square" />;
          if (linkToSpotify) return <a key={index} href={album?.spotifyUrl ?? `https://open.spotify.com/album/${tile.spotifyAlbumId}`} target="_blank" rel="noopener noreferrer" aria-label={`Open ${label} in Spotify, row ${y + 1}, column ${x + 1} (opens in a new tab)`} title={`Open ${label} in Spotify`} className={className}>{cover}</a>;
          if (album) return <button key={index} type="button" data-song={mosaicAlbumKey(tile)} onClick={() => onSelect ? onSelect(tile) : setDetail(album)} aria-label={`Details for ${detailLabel}, row ${y + 1}, column ${x + 1}`} title={showListeningTrack ? detailLabel : label} className={className}>
            {cover}
          </button>;
          return <a key={index} href={`https://open.spotify.com/album/${tile.spotifyAlbumId}`} target="_blank" rel="noopener noreferrer" aria-label={`Open ${label} in Spotify`} className={className}>{cover}</a>;
        })}
      </div>
      {detail && <AlbumDetail album={detail} onClose={() => setDetail(null)} showListeningTrack={showListeningTrack} />}
    </>
  );
}
