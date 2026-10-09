"use client";
import { useEffect, useRef, useState } from "react";
import MonthlyPage from "@/app/monthly/page";
import { SharedArtwork } from "@/components/shared-artwork";
import { layoutFor, type Remix, type RemixStyle, type ShapePreset } from "@/components/remix-design";
import type { Album } from "@/components/album-detail";
import { mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import fixture from "./fixtures.json";

const source = fixture.mosaic as MosaicLayout & { id: string; month: string };
const shapes = fixture.shapes as ShapePreset[];
const palette = ["#9d5340", "#8d908a", "#26474d", "#c3a78f", "#323c68", "#b08b3c", "#70485d"];
const albums: Record<string, Album> = Object.fromEntries(source.tiles.map((tile, index) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="${palette[index % palette.length]}"/><circle cx="150" cy="120" r="90" fill="#121212" opacity=".4"/><path d="M0 300L150 80L300 300" fill="#e9e0cf" opacity=".4"/><text x="24" y="265" fill="white" font-family="sans-serif" font-size="24">AFTER HOURS ${index+1}</text></svg>`;
  return [mosaicAlbumKey(tile), {id:tile.spotifyAlbumId,name:`Album ${index+1}`,artists:["The Night Shift"],imageUrl:`data:image/svg+xml,${encodeURIComponent(svg)}`,spotifyUrl:`https://open.spotify.com/album/${tile.spotifyAlbumId}`,releaseDate:"",totalTracks:10,representativeTrack:{id:tile.spotifyTrackId!,name:`Midnight song ${index+1}`,artists:["The Night Shift"],spotifyUrl:`https://open.spotify.com/track/${tile.spotifyTrackId}`}}];
}));
let records: Remix[] = [];
const shareId = "11111111-1111-4111-8111-111111111111";

function monthlySnapshot() {
  return {
    ...source,
    generated_at: `${source.month}-08T12:00:00Z`,
    listening_basis: "spotify_short_term",
    source_track_count: 50,
    album_ids: [...new Set(source.tiles.map((tile) => tile.spotifyAlbumId))],
    artwork: albums,
    artwork_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
  };
}

function albumResponse(url: URL) {
  const albumId = url.pathname.split("/").at(-1);
  const trackId = url.searchParams.get("track_id");
  const album = trackId
    ? albums[`${albumId}:${trackId}`]
    : Object.values(albums).find((item) => item.id === albumId);
  return album ? Response.json(album) : Response.json({ detail: "Album not found" }, { status: 404 });
}

export default function Preview() {
  const [ready, setReady] = useState(false);
  const [visitor, setVisitor] = useState(false);
  const [collectionState, setCollectionState] = useState<"saved" | "empty">("saved");
  const [revision, setRevision] = useState(0);
  const hasMonthlyArtwork = useRef(true);

  function showCollection(state: "saved" | "empty") {
    hasMonthlyArtwork.current = state === "saved";
    setCollectionState(state);
    setVisitor(false);
    setRevision((value) => value + 1);
  }

  useEffect(() => {
    const original = window.fetch;
    window.fetch = async (input, init) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, window.location.origin);
      const method = init?.method ?? (input instanceof Request ? input.method : "GET");
      if (url.pathname === "/api/me/monthly-mosaics") {
        if (method === "POST") {
          hasMonthlyArtwork.current = true;
          setCollectionState("saved");
          return Response.json(monthlySnapshot(), { status: 201 });
        }
        if (method === "GET") return Response.json({ current_month: source.month, items: hasMonthlyArtwork.current ? [monthlySnapshot()] : [] });
        return Response.json({ detail: "Unsupported preview action" }, { status: 405 });
      }
      if (url.pathname.startsWith(`/api/me/monthly-mosaics/${source.id}/albums/`)) return albumResponse(url);
      if (!url.pathname.startsWith("/api/me/remix") && !url.pathname.endsWith("/remixes") && !url.pathname.startsWith("/api/artworks/")) {
        // The fixture never falls through to a live API, including unmocked writes.
        if (url.pathname.startsWith("/api/")) return Response.json({ detail: "Preview endpoint not mocked" }, { status: 404 });
        return original(input, init);
      }
      if (url.pathname.endsWith("remix-shapes")) return Response.json({items:shapes});
      if (url.pathname.endsWith("/remixes") && method === "GET") return Response.json({items:records});
      if (url.pathname.startsWith("/api/artworks/")) {
        const remix = records.find((item) => item.share_id === shareId);
        if (!remix) return Response.json({detail:"Artwork not found"},{status:404});
        if (url.pathname.includes("/albums/")) return albumResponse(url);
        return Response.json({...remix,display_name:"Jamie"});
      }
      const id = url.pathname.split("/")[4];
      if (url.pathname.endsWith("/share")) {
        const remix = records.find((item) => item.id === id)!;
        remix.share_id = method === "DELETE" ? null : shareId;
        return method === "DELETE" ? new Response(null,{status:204}) : Response.json({share_id:shareId});
      }
      if (url.pathname.endsWith("/background")) {
        const remix = records.find((item) => item.id === id)!;
        remix.background_url = method === "DELETE" ? null : URL.createObjectURL(init!.body as Blob);
        return Response.json(remix);
      }
      if (method === "DELETE") { records = records.filter((item) => item.id !== id); return new Response(null,{status:204}); }
      const body = JSON.parse(init!.body as string) as {name:string;style:RemixStyle};
      const old = records.find((item) => item.id === id);
      const saved: Remix = {...body,id:old?.id??crypto.randomUUID(),month:source.month,share_id:old?.share_id??null,background_url:old?.background_url??null,layout:layoutFor(shapes.find((item)=>item.key===body.style.shape)!,source.tiles)};
      records = [...records.filter((item) => item.id !== saved.id),saved];
      return Response.json(saved,{status:method==='POST'?201:200});
    };
    // Mount the preview on the next browser frame, after its fetch mock is installed.
    const frame = window.requestAnimationFrame(() => setReady(true));
    return () => { window.cancelAnimationFrame(frame); window.fetch = original; };
  }, []);
  return <>
    <div className="border-b border-border bg-accent-soft/50 px-4 py-2 text-text-primary">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2" role="group" aria-label="Preview scenarios">
        <span className="mr-1 text-xs font-medium text-text-secondary">QA preview</span>
        <button type="button" className="mosaic-button" aria-pressed={!visitor && collectionState === "saved"} onClick={() => showCollection("saved")}>Saved collection</button>
        <button type="button" className="mosaic-button" aria-pressed={!visitor && collectionState === "empty"} onClick={() => showCollection("empty")}>Empty collection</button>
        <button type="button" className="mosaic-button" aria-pressed={visitor} onClick={() => setVisitor((value) => !value)}>{visitor ? "Back to collection" : "Preview visitor view"}</button>
      </div>
    </div>
    {ready && (visitor ? <SharedArtwork shareId={shareId} /> : <MonthlyPage key={revision} />)}
  </>;
}
