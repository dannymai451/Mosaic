"use client";
import { useEffect, useState } from "react";
import { RemixStudio } from "@/components/remix-studio";
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
export default function Preview() {
  const [ready, setReady] = useState(false);
  const [visitor, setVisitor] = useState(false);
  useEffect(() => {
    const original = window.fetch;
    window.fetch = async (input, init) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, window.location.origin);
      if (!url.pathname.startsWith("/api/me/remix") && !url.pathname.endsWith("/remixes") && !url.pathname.startsWith("/api/artworks/")) return original(input, init);
      if (url.pathname.endsWith("remix-shapes")) return Response.json({items:shapes});
      const method = init?.method ?? "GET";
      if (url.pathname.endsWith("/remixes") && method === "GET") return Response.json({items:records});
      if (url.pathname.startsWith("/api/artworks/")) {
        const remix = records.find((item) => item.share_id === shareId);
        if (!remix) return Response.json({detail:"Artwork not found"},{status:404});
        if (url.pathname.includes("/albums/")) return Response.json(albums[`${url.pathname.split('/').at(-1)}:${url.searchParams.get('track_id')??''}`]);
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
  return <><div className="bg-zinc-950 p-3 text-white"><button className="min-h-11 rounded-full border px-4" onClick={()=>setVisitor(!visitor)}>{visitor?'Back to studio':'Preview visitor view'}</button></div>{ready && (visitor ? <SharedArtwork shareId={shareId}/> : <main className="min-h-screen bg-[#101014] p-4 text-white sm:p-8"><div className="mx-auto max-w-5xl"><p className="text-xs uppercase tracking-[.25em] text-orange-200">Mosaic / October 2026</p><h1 className="mt-3 text-4xl tracking-tight">Your music. Your canvas.</h1><RemixStudio mosaic={source} albums={albums}/></div></main>)}</>;
}
