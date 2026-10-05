"use client";

import { MosaicCanvas, type MosaicLayout } from "@/components/mosaic-canvas";
import { useMosaicAlbums } from "@/components/mosaic-albums";

export function PublicMosaic({ layout, username }: { layout: MosaicLayout; username: string }) {
  const { albums, error, loading, retry } = useMosaicAlbums(layout.tiles.map((tile) => tile.spotifyAlbumId), `/api/profiles/${encodeURIComponent(username)}/albums`);
  return (
    <section aria-labelledby="public-mosaic-heading" className="rounded-2xl border border-zinc-700 bg-zinc-900 p-4 sm:p-6">
      <h2 id="public-mosaic-heading" className="mb-5 text-xl font-semibold">Featured Album mosaic</h2>
      {layout.tiles.length ? <MosaicCanvas layout={layout} albums={albums} /> : <p className="text-sm text-zinc-400">This mosaic has no albums yet.</p>}
      <p className="mt-4 text-sm text-zinc-400">Tap an album for details and a link to Spotify.</p>
      {loading && <p role="status" className="mt-3 text-sm text-zinc-400">Loading album artwork...</p>}
      {error && <div className="mt-3"><p role="alert" className="text-sm text-red-300">{error}</p><button type="button" onClick={retry} className="mt-2 min-h-11 text-sm text-green-400 underline">Retry artwork</button></div>}
    </section>
  );
}
