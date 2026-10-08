"use client";

import { useEffect, useRef, useState } from "react";
import type { Album } from "@/components/album-detail";
import { mosaicAlbumKey, type MosaicTile } from "@/components/mosaic-canvas";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function placeholder(id: string): Album {
  return { id, name: "Unavailable album", artists: [], imageUrl: null, spotifyUrl: `https://open.spotify.com/album/${id}`, releaseDate: "", totalTracks: 0, trackDetailsUnavailable: true };
}

// Decode the same unoptimized URL that the canvas uses before revealing any tiles.
function prepareImage(url: string, signal: AbortSignal): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new window.Image();
    let settled = false;
    const finish = (loaded: boolean) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
      image.onload = null;
      image.onerror = null;
      if (!loaded) image.src = "";
      resolve(loaded);
    };
    const abort = () => finish(false);
    const timeout = window.setTimeout(() => finish(false), 10000);
    signal.addEventListener("abort", abort, { once: true });
    image.onload = () => {
      void image.decode().then(() => finish(image.naturalWidth > 0), () => finish(false));
    };
    image.onerror = () => finish(false);
    if (signal.aborted) finish(false);
    else image.src = url;
  });
}

class ArtworkAuthenticationError extends Error {}

type ArtworkState = { albums: Record<string, Album>; ready: boolean; completed: number; total: number; error: string | null; authenticationExpired: boolean };

// Monthly artwork is revealed as a complete canvas; legacy mosaics keep their existing loader.
export function useMonthlyArtwork(tiles: MosaicTile[], path: string, initialAlbums?: Record<string, Album>, initialExpiresAt?: string | null, publicView = false) {
  const requestsKey = JSON.stringify([...new Map(tiles.map((tile) => [mosaicAlbumKey(tile), {
    spotifyAlbumId: tile.spotifyAlbumId, ...(tile.spotifyTrackId ? { spotifyTrackId: tile.spotifyTrackId } : {}),
  }])).values()]);
  const total = JSON.parse(requestsKey).length * 2;
  const [state, setState] = useState<ArtworkState>({ albums: {}, ready: false, completed: 0, total, error: null, authenticationExpired: false });
  const [retry, setRetry] = useState(0);
  const known = useRef<Record<string, Album>>({});
  const decoded = useRef(new Set<string>());
  const initial = useRef({ albums: initialAlbums, expiresAt: initialExpiresAt });

  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(45000)]);
    const references = JSON.parse(requestsKey) as Pick<MosaicTile, "spotifyAlbumId" | "spotifyTrackId">[];
    const albums: Record<string, Album> = {};
    let completed = 0;
    let error: string | null = null;
    let imageFailures = 0;
    let songDetailsFailures = 0;
    let authenticationExpired = false;
    const attemptedImages = new Map<string, boolean>();

    const advance = () => {
      completed += 1;
      if (!controller.signal.aborted) setState((current) => ({ ...current, completed }));
    };
    async function load() {
      try {
        for (const reference of references) {
          const id = reference.spotifyAlbumId;
          const key = mosaicAlbumKey(reference);
          if (signal.aborted) throw new DOMException("Artwork preparation timed out", "TimeoutError");
          let album: Album | undefined = known.current[key];
          const seed = initial.current;
          if (!album && seed.expiresAt && Date.parse(seed.expiresAt) > Date.now()) {
            album = seed.albums?.[key];
            if (album) known.current[key] = album;
          }
          // A transient track lookup failure is unresolved metadata. A retry run
          // fetches it once again; older snapshots without stored track IDs stay cached.
          if (!album || album.trackDetailsUnavailable) {
            const query = reference.spotifyTrackId ? `?track_id=${encodeURIComponent(reference.spotifyTrackId)}` : "";
            const response = await fetch(`${API_BASE_URL}${path}/${id}${query}`, {
              credentials: "include", cache: "no-store",
              signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
            });
            if (response.status === 429) {
              const wait = response.headers.get("Retry-After");
              throw new Error(`Spotify is limiting requests. ${wait ? `Wait ${wait} seconds, then retry artwork.` : "Wait a little, then retry artwork."}`);
            }
            if (response.status === 401) throw new ArtworkAuthenticationError("Your session is missing or expired. Connect Spotify to open your private collection.");
            if (response.status === 403) throw new Error(publicView ? "The music is unavailable right now. The creator may need to reconnect Spotify." : "Album details are unavailable. Reconnect Spotify, then retry artwork.");
            if (response.status === 404) {
              album = placeholder(id);
              error = "Some albums are unavailable. Their placeholders and Spotify links remain usable; retry artwork to check again.";
            }
            else if (!response.ok) throw new Error("Could not load all album details. Retry artwork when Spotify is available.");
            else { album = await response.json() as Album; known.current[key] = album; }
          }
          if (controller.signal.aborted) return;
          if (album.trackDetailsUnavailable) songDetailsFailures += 1;
          advance();
          const imageUrl = album.imageUrl;
          if (imageUrl && !decoded.current.has(imageUrl)) {
            let loaded = attemptedImages.get(imageUrl);
            if (loaded === undefined) {
              loaded = await prepareImage(imageUrl, signal);
              attemptedImages.set(imageUrl, loaded);
            }
            if (controller.signal.aborted) return;
            if (loaded) decoded.current.add(imageUrl);
            else { imageFailures += 1; album = { ...album, imageUrl: null }; }
          }
          albums[key] = album;
          advance();
        }
      } catch (failure) {
        if (controller.signal.aborted) return;
        authenticationExpired = failure instanceof ArtworkAuthenticationError;
        error = failure instanceof Error && failure.name === "Error" ? failure.message : "Artwork preparation took too long or could not finish. Retry to load missing covers.";
      } finally {
        if (!controller.signal.aborted) {
          if (authenticationExpired) {
            // Never reveal the private canvas, even briefly, after a confirmed 401.
            setState({ albums: {}, ready: false, completed: 0, total: references.length * 2, error, authenticationExpired: true });
            return;
          }
          // Settle unavailable albums as usable placeholders, including remaining requests
          // after a rate limit. Retry only unresolved metadata/images next time.
          for (const reference of references) {
            const key = mosaicAlbumKey(reference);
            if (albums[key]) continue;
            const cached = known.current[key] ?? placeholder(reference.spotifyAlbumId);
            albums[key] = { ...cached, imageUrl: cached.imageUrl && decoded.current.has(cached.imageUrl) ? cached.imageUrl : null };
          }
          if (imageFailures && !error) error = "Some album covers could not load. Placeholders keep your complete shape visible; retry artwork to try those covers again.";
          if (songDetailsFailures && !error) error = "Some song details are unavailable. Your artwork and album links are ready; retry artwork to try loading the songs again.";
          setState({ albums, ready: true, completed: references.length * 2, total: references.length * 2, error, authenticationExpired: false });
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [requestsKey, path, retry, publicView]);

  return { ...state, retry: () => {
    setState((current) => ({ ...current, ready: false, completed: 0, error: null, authenticationExpired: false }));
    setRetry((value) => value + 1);
  } };
}
