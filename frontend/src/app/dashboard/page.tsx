"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LogoutButton } from "@/components/logout-button";
import { BrandArtwork } from "@/components/brand-artwork";
import { MosaicBrand } from "@/components/mosaic-brand";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type SpotifyImage = {
  url: string;
  height?: number | null;
  width?: number | null;
};

type CurrentUser = {
  displayName: string | null;
  images: SpotifyImage[];
};

export default function DashboardPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function retryLoad() {
    window.location.reload();
  }

  useEffect(() => {
    async function loadUser() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/me`, {
          credentials: "include",
          signal: AbortSignal.timeout(10000),
        });

        if (response.status === 401) {
          setError("Please reconnect Spotify to get back to your collection.");
          return;
        }

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const data: CurrentUser = await response.json();
        setUser(data);
      } catch (err) {
        console.error(err);
        setError(
          err instanceof DOMException && err.name === "TimeoutError"
            ? "Loading took too long. Please try again."
            : "Could not load your profile. Please try again."
        );
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, []);

  const avatarUrl = user?.images?.[0]?.url;

  return (
    <main className="min-h-screen bg-background text-text-primary">
      <div className="mosaic-shell">
        <header className="flex flex-wrap items-center justify-between gap-x-5 gap-y-3 border-b border-border py-6 sm:py-8">
          <MosaicBrand href="/dashboard" />
          {user && <LogoutButton />}
        </header>

        {loading ? (
          <div className="flex min-h-[65svh] items-center justify-center">
            <p role="status" className="text-text-secondary">Getting things ready…</p>
          </div>
        ) : error ? (
          <section className="mx-auto max-w-md py-24 text-center">
            <h1 className="mosaic-display text-4xl tracking-tight">Welcome back.</h1>
            <p role="alert" className="mt-5 leading-7 text-text-secondary">{error}</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <button onClick={retryLoad} className="mosaic-button">Try again</button>
              <a href={`${API_BASE_URL}/api/auth/spotify/start`} className="mosaic-button-primary">
                Connect Spotify
              </a>
            </div>
          </section>
        ) : user ? (
          <div className="pb-16 pt-12 sm:pt-16">
            <div className="mb-10 flex items-center gap-4 sm:mb-12">
              {avatarUrl && (
                <img src={avatarUrl} alt="" className="h-12 w-12 shrink-0 rounded-full object-cover sm:h-14 sm:w-14" />
              )}
              <h1 className="mosaic-display min-w-0 text-4xl leading-tight tracking-tight [overflow-wrap:anywhere] sm:text-5xl">
                {user.displayName ? `Hi, ${user.displayName}.` : "Welcome back."}
              </h1>
            </div>

            <section className="grid overflow-hidden rounded-[2rem] border border-border bg-surface md:grid-cols-[1.1fr_1fr]">
              <div className="flex flex-col items-start justify-center px-7 py-10 sm:p-12 lg:p-16">
                <h2 className="mosaic-display text-4xl tracking-tight sm:text-5xl">Your collection</h2>
                <p className="mt-4 text-base leading-7 text-text-secondary">Your music, month by month.</p>
                <Link href="/monthly" className="mosaic-button-primary mt-8 gap-3">
                  Open collection
                  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.6">
                    <path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </Link>
              </div>
              <div className="bg-accent-soft/50 px-8 py-8 sm:p-10">
                <div className="mx-auto max-w-sm"><BrandArtwork /></div>
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}
