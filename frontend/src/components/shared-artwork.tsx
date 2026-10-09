"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArtworkExplorer } from "@/components/artwork-explorer";
import { MosaicBrand } from "@/components/mosaic-brand";
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
  return <main className="min-h-screen bg-background px-5 py-6 text-text-primary sm:px-8 sm:py-10"><div className="mx-auto max-w-3xl">
    <nav aria-label="Main navigation" className="mb-12 flex items-center justify-between gap-4"><MosaicBrand /><Link href="/connect" className={control}>Make yours ↗</Link></nav>
    {loading ? <p role="status" className="py-16 text-center text-text-secondary">Opening artwork…</p> : design ? <SharedContent design={design} shareId={shareId} /> : <section className="rounded-3xl border border-border bg-surface p-8"><h1 className="mosaic-display text-3xl">Artwork unavailable</h1><p role="alert" className="mt-3 leading-7 text-text-secondary">{error}</p><button className={`${control} mt-6`} onClick={() => { setLoading(true); setReload((value) => value + 1); }}>Try again</button></section>}
    <footer className="mt-10 border-t border-border pt-6 text-center"><Link href="/connect" className="mosaic-button-primary">Create your own artwork</Link></footer>
  </div></main>;
}

function SharedContent({ design, shareId }: { design: SharedDesign; shareId: string }) {
  const metadata = useMonthlyArtwork(design.layout.tiles, `/api/artworks/${shareId}/albums`, undefined, undefined, true);
  const month = new Date(`${design.month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  return <>
    <header className="mb-8"><p className="mosaic-eyebrow">{month}</p><h1 className="mosaic-display mt-3 break-words text-4xl sm:text-5xl">{design.name}</h1><p className="mt-3 text-sm text-text-secondary">By <span className="text-text-primary">{design.display_name}</span></p></header>
    {metadata.ready ? <ArtworkExplorer layout={design.layout} albums={metadata.albums} style={design.style} background={design.background_url} /> : <div className="rounded-3xl border border-border bg-surface p-8"><p role="status" className="text-sm text-text-secondary">Preparing the artwork…</p><progress aria-label="Preparing artwork" max={Math.max(1, metadata.total)} value={metadata.completed} className="mt-4 w-full accent-accent" /></div>}
    {metadata.error && <div className="mt-5"><p role="alert" className="text-sm leading-6 text-text-secondary">{metadata.error}</p><button className={`${control} mt-3`} onClick={metadata.retry}>Retry music</button></div>}
    <p className="mt-6 text-center text-xs leading-6 text-text-secondary">Based on roughly four weeks of Spotify listening.</p>
  </>;
}
