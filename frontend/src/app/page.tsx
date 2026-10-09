import Link from "next/link";
import { BrandArtwork } from "@/components/brand-artwork";
import { MosaicBrand } from "@/components/mosaic-brand";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-text-primary">
      <div className="mosaic-shell">
        <header className="flex items-center justify-between gap-6 py-6 sm:py-8">
          <MosaicBrand />
          <Link href="/connect" className="mosaic-button">
            Sign in
          </Link>
        </header>

        <section className="grid items-center gap-12 pb-12 pt-12 sm:pb-20 sm:pt-20 lg:min-h-[calc(100svh-120px)] lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pt-10">
          <div className="max-w-xl">
            <h1 className="mosaic-display text-[clamp(3.4rem,6.4vw,6rem)] leading-[1.04] tracking-[-0.055em]">
              Your music,
              <br />
              a month in <span className="italic text-accent">art.</span>
            </h1>
            <p className="mt-7 max-w-sm text-lg leading-8 text-text-secondary">
              Turn your Spotify listening into a mosaic worth keeping.
            </p>
            <a
              href={`${API_BASE_URL}/api/auth/spotify/start`}
              className="mosaic-button-primary mt-9 gap-3"
            >
              Connect Spotify
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.6">
                <path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
          </div>
          <div className="mx-auto w-full max-w-xl lg:translate-y-[-1rem]">
            <BrandArtwork />
          </div>
        </section>
      </div>
    </main>
  );
}
