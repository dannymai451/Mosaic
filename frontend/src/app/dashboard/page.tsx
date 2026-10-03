"use client";

import { useEffect, useState } from "react";

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
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function logout() {
    setLogoutError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Logout failed");
      }

      window.location.href = "/";
    } catch (err) {
      console.error(err);
      setLogoutError("Could not log out. Please try again.");
    }
  }

  useEffect(() => {
    async function loadUser() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/me`, {
          credentials: "include",
        });

        if (response.status === 401) {
          setError("Your session is missing or expired.");
          return;
        }

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const data: CurrentUser = await response.json();
        setUser(data);
      } catch (err) {
        console.error(err);
        setError("Could not load your connected Spotify profile.");
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, []);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">
        <p className="text-zinc-400">Loading your Spotify profile...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">
        <div className="text-center">
          <p className="mb-6 text-zinc-300">{error}</p>

          <a
            href={`${API_BASE_URL}/api/auth/spotify/start`}
            className="rounded-full bg-green-500 px-6 py-3 font-semibold text-black"
          >
            Connect Spotify
          </a>
        </div>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  const avatarUrl = user.images?.[0]?.url;

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-5xl px-6 py-16">
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-sm font-medium uppercase tracking-[0.25em] text-green-400">
              Mosaic
            </p>

            <h1 className="text-4xl font-bold">Dashboard</h1>
          </div>

          <button
            onClick={logout}
            className="rounded-full border border-zinc-700 px-5 py-2 text-sm text-zinc-300 transition hover:border-zinc-500 hover:text-white"
          >
            Log out
          </button>
        </header>

        {logoutError && (
          <p role="alert" className="mt-4 text-right text-sm text-red-400">
            {logoutError}
          </p>
        )}

        <div className="mt-12 flex items-center gap-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt=""
              className="h-24 w-24 rounded-full object-cover"
            />
          ) : (
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-zinc-800 text-3xl">
              ♪
            </div>
          )}

          <div>
            <p className="text-sm text-zinc-400">Connected as</p>

            <h2 className="mt-1 text-2xl font-semibold">
              {user.displayName || "Spotify user"}
            </h2>

            <p className="mt-2 text-sm text-green-400">
              Spotify connected successfully
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
