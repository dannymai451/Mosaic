"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MosaicBrand } from "@/components/mosaic-brand";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied:
    "Spotify connection was cancelled. You can try again whenever you're ready.",

  missing_state:
    "Your sign-in expired. Connect again to pick up where you left off.",

  state_mismatch:
    "We couldn’t verify your sign-in. Please connect again.",

  missing_code:
    "Spotify couldn’t finish connecting. Please try again.",

  token_exchange_failed:
    "Spotify could not complete the sign-in. Please try connecting again.",

  spotify_unauthorized:
    "Please reconnect your Spotify account to continue.",

  spotify_forbidden:
    "Spotify did not allow access to the requested profile information.",

  spotify_rate_limited:
    "Spotify is temporarily limiting requests. Please wait a little and try again.",

  spotify_unavailable:
    "Spotify could not be reached. Please try again shortly.",

  spotify_profile_failed:
    "Your Spotify profile could not be loaded. Please try connecting again.",
};

const DEFAULT_MESSAGE = "Connect your Spotify account to continue.";

function ConnectMessage() {
  const error = useSearchParams().get("error");
  return error
    ? ERROR_MESSAGES[error] ??
        "Something went wrong while connecting Spotify. Please try again."
    : DEFAULT_MESSAGE;
}

export default function ConnectPage() {
  return (
    <main className="min-h-screen bg-background text-text-primary">
      <div className="mosaic-shell">
        <header className="flex items-center py-6 sm:py-8">
          <MosaicBrand />
        </header>
        <section className="flex min-h-[70svh] items-center justify-center py-12">
          <div className="w-full max-w-md rounded-[2rem] border border-border bg-surface px-7 py-12 text-center sm:px-10">
            <div aria-hidden="true" className="mx-auto mb-7 flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-2xl text-accent">
              ♪
            </div>
            <h1 className="mosaic-display text-4xl tracking-tight sm:text-5xl">
              Let your music in.
            </h1>

            <p className="mt-5 leading-7 text-text-secondary" role="status">
              <Suspense fallback={DEFAULT_MESSAGE}>
                <ConnectMessage />
              </Suspense>
            </p>

            <a
              href={`${API_BASE_URL}/api/auth/spotify/start`}
              className="mosaic-button-primary mt-8"
            >
              Connect Spotify
            </a>

            <Link
              href="/"
              className="mx-auto mt-5 flex min-h-11 w-fit items-center text-sm text-text-secondary transition hover:text-text-primary"
            >
              Back home
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
