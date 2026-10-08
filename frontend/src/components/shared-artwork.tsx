"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArtworkExplorer } from "@/components/artwork-explorer";
import { useMonthlyArtwork } from "@/components/monthly-artwork";
import { API, control, type Remix } from "@/components/remix-design";

export type SharedDesign = Omit<Remix, "id" | "share_id"> & { display_name: string };

export function SharedArtwork({ shareId }: { shareId: string }) {
  const [design, setDesign] = useState<SharedDesign | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`${API}/api/artworks/${shareId}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
        if (!response.ok) throw new Error(response.status === 404 ? "This artwork is private or its link is no longer available." : "This artwork could not load. Try again in a moment.");
        const result = await response.json();
        if (!controller.signal.aborted) { setDesign(result); setError(null); }
      } catch (failure) { if (!controller.signal.aborted) { setDesign(null); setError((failure as Error).message); } }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [shareId, reload]);
  return <main className="min-h-screen bg-[#101014] px-4 py-6 text-[#eee9df] sm:px-6 sm:py-10"><div className="mx-auto max-w-2xl">
    <nav className="mb-10 flex items-center justify-between"><Link href="/" className="text-xl font-semibold tracking-tight">mosaic<span className="text-orange-200">.</span></Link><Link href="/connect" className={control}>Make yours ↗</Link></nav>
    {loading ? <p role="status" className="py-16 text-center text-zinc-400">Opening artwork…</p> : design ? <SharedContent design={design} shareId={shareId} /> : <section className="rounded-3xl border border-white/10 p-8"><h1 className="text-2xl">Artwork unavailable</h1><p role="alert" className="mt-3 leading-7 text-zinc-400">{error}</p><button className={`${control} mt-6`} onClick={() => { setLoading(true); setReload((value) => value + 1); }}>Try again</button></section>}
    <footer className="mt-10 border-t border-white/10 pt-6 text-center"><p className="text-sm text-zinc-400">Your listening has a look.</p><Link href="/connect" className={`${control} mt-4 bg-orange-200 text-zinc-950`}>Create your own artwork</Link></footer>
  </div></main>;
}

function SharedContent({ design, shareId }: { design: SharedDesign; shareId: string }) {
  const metadata = useMonthlyArtwork(design.layout.tiles, `/api/artworks/${shareId}/albums`, undefined, undefined, true);
  const month = new Date(`${design.month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  return <>
    <header className="mb-7"><p className="text-[10px] uppercase tracking-[.25em] text-orange-200">{month} / A month in music</p><h1 className="mt-3 break-words text-3xl font-medium tracking-tight sm:text-5xl">{design.name}</h1><p className="mt-3 text-sm text-zinc-400">Made by <span className="text-zinc-200">{design.display_name}</span> from their recent Spotify listening.</p></header>
    {metadata.ready ? <ArtworkExplorer layout={design.layout} albums={metadata.albums} style={design.style} background={design.background_url} /> : <div className="rounded-3xl border border-white/10 p-8"><p role="status" className="text-sm text-zinc-400">Preparing the artwork…</p><progress aria-label="Preparing artwork" max={Math.max(1, metadata.total)} value={metadata.completed} className="mt-4 w-full accent-orange-200" /></div>}
    {metadata.error && <div className="mt-5"><p role="alert" className="text-sm leading-6 text-zinc-400">{metadata.error}</p><button className={`${control} mt-3`} onClick={metadata.retry}>Retry music</button></div>}
    <p className="mt-6 text-center text-xs leading-6 text-zinc-500">Explore the covers or browse Songs. A snapshot of roughly four weeks of listening, captured when this month’s artwork was made.</p>
  </>;
}
