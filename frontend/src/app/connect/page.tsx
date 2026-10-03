"use client";

import { useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied:
    "Spotify connection was cancelled. You can try again whenever you're ready.",

  missing_state:
    "The sign-in request expired or could not be verified. Please try connecting again.",

  state_mismatch:
    "The sign-in request could not be verified. Please start the connection again.",

  missing_code:
    "Spotify did not return an authorization code. Please try again.",

  token_exchange_failed:
    "Spotify could not complete the sign-in. Please try connecting again.",

  spotify_unauthorized:
    "Spotify rejected the authorization. Please reconnect your account.",

  spotify_forbidden:
    "Spotify did not allow access to the requested profile information.",

  spotify_rate_limited:
    "Spotify is temporarily limiting requests. Please wait a little and try again.",

  spotify_unavailable:
    "Spotify could not be reached. Please try again shortly.",

  spotify_profile_failed:
    "Your Spotify profile could not be loaded. Please try connecting again.",
};

export default function ConnectPage() {
  const [message, setMessage] = useState(
    "Connect your Spotify account to continue."
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get("error");

    if (error) {
      setMessage(
        ERROR_MESSAGES[error] ??
          "Something went wrong while connecting Spotify. Please try again."
      );
    }
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-6 text-white">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
        <p className="text-sm font-medium uppercase tracking-[0.25em] text-green-400">
          Mosaic
        </p>

        <h1 className="mt-3 text-3xl font-bold">
          Connect Spotify
        </h1>

        <p className="mt-4 text-zinc-400">
          {message}
        </p>

        <a
          href={`${API_BASE_URL}/api/auth/spotify/start`}
          className="mt-8 inline-block rounded-full bg-green-500 px-7 py-3 font-semibold text-black transition hover:bg-green-400"
        >
          Connect Spotify
        </a>

        <a
          href="/"
          className="mt-5 block text-sm text-zinc-500 hover:text-zinc-300"
        >
          Back home
        </a>
      </div>
    </main>
  );
}