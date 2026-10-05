"use client";

import { useEffect, useRef, useState } from "react";
import type { Album } from "@/components/album-detail";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Resolve only selected IDs, sequentially, so rate limits stop further requests.
export function useMosaicAlbums(albumIds: string[], path: string) {
  const [albums, setAlbums] = useState<Record<string, Album>>({});
  const known = useRef<Record<string, Album>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const idsKey = JSON.stringify([...new Set(albumIds)]);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        for (const id of JSON.parse(idsKey) as string[]) {
          if (known.current[id]) continue;
          const response = await fetch(`${API_BASE_URL}${path}/${id}`, {
            credentials: path.startsWith("/api/me/") ? "include" : "omit",
            cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
          });
          if (controller.signal.aborted) return;
          if (response.status === 404) {
            known.current[id] = { id, name: "Unavailable album", artists: [], imageUrl: null, spotifyUrl: `https://open.spotify.com/album/${id}`, releaseDate: "", totalTracks: 0 };
          } else {
            if (response.status === 429) {
              const wait = response.headers.get("Retry-After");
              throw new Error(`Spotify is busy. ${wait ? `Wait ${wait} seconds, then retry artwork.` : "Wait a little, then retry artwork."}`);
            }
            if (response.status === 401 || response.status === 403) throw new Error("Album details are unavailable. The owner may need to reconnect Spotify.");
            if (!response.ok) throw new Error("Could not load album details. Your layout is still available; retry artwork.");
            known.current[id] = await response.json();
          }
          if (controller.signal.aborted) return;
          setAlbums({ ...known.current });
        }
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error && failure.name === "Error" ? failure.message : "Could not reach album details. Retry artwork.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [idsKey, path, retry]);

  return { albums, error, loading, retry: () => setRetry((value) => value + 1) };
}
