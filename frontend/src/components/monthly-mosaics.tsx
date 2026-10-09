"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type MosaicLayout } from "@/components/mosaic-canvas";
import { RemixStudio } from "@/components/remix-studio";
import { useMonthlyArtwork } from "@/components/monthly-artwork";
import type { Album } from "@/components/album-detail";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const buttonClass = "mosaic-button";

type MonthlyMosaic = MosaicLayout & {
  id: string;
  month: string;
  generated_at: string;
  listening_basis: "spotify_short_term";
  source_track_count: number;
  album_ids: string[];
  artwork?: Record<string, Album>;
  artwork_expires_at?: string | null;
};
type MonthlyArchive = { current_month: string; items: MonthlyMosaic[] };
type Failure = { message: string; reconnect: boolean; authenticationExpired: boolean };

class MonthlyRequestError extends Error {
  constructor(message: string, public reconnect = false, public authenticationExpired = false) { super(message); }
}

function monthLabel(month: string) {
  return new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

async function request<T>(signal: AbortSignal, generate = false): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/me/monthly-mosaics`, {
    method: generate ? "POST" : "GET", credentials: "include", cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
    ...(generate ? { headers: { "Content-Type": "application/json" }, body: "{}" } : {}),
  });
  if (response.status === 401) throw new MonthlyRequestError("Your session expired. Connect Spotify to continue.", true, true);
  if (response.status === 403) throw new MonthlyRequestError("Reconnect Spotify to access your recent top tracks.", true);
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    throw new MonthlyRequestError(`Spotify is limiting requests. ${wait ? `Wait ${wait} seconds, then try again.` : "Wait a little, then try again."}`);
  }
  if (response.status === 422) {
    const body: { detail?: string } = await response.json();
    if (body.detail === "spotify_no_recent_listening") throw new MonthlyRequestError("No recent Spotify tracks yet. Listen to more music, then try again.");
  }
  if (!response.ok) throw new MonthlyRequestError("Could not load or save your artwork. Please try again.");
  return response.json();
}

function failureOf(failure: unknown): Failure {
  if (failure instanceof MonthlyRequestError) return { message: failure.message, reconnect: failure.reconnect, authenticationExpired: failure.authenticationExpired };
  return { message: failure instanceof DOMException && failure.name === "TimeoutError"
    ? "The request took too long. Try again or refresh your collection to check whether the artwork was saved."
    : "Could not reach Mosaic. Try again or refresh your collection to check whether the artwork was saved.", reconnect: false, authenticationExpired: false };
}

function ErrorMessage({ failure }: { failure: Failure }) {
  return <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-700">{failure.message}</p>{failure.reconnect && <a href={`${API_BASE_URL}/api/auth/spotify/start`} className="mosaic-button-primary mt-3">Connect Spotify</a>}</div>;
}

function ArtworkProgress({ label, completed, total }: { label: string; completed?: number; total?: number }) {
  const determinate = completed !== undefined && total !== undefined;
  return <div className="mt-5" role="status">
    <p className="text-sm text-text-secondary">{label}{determinate && total > 0 ? ` ${Math.floor(completed / total * 100)}%` : ""}</p>
    {determinate ? <progress aria-label={label} max={Math.max(total, 1)} value={completed} className="mt-3 h-1.5 w-full accent-accent" /> : <div role="progressbar" aria-label={label} className="mt-3 h-1.5 overflow-hidden rounded-full bg-accent-soft"><span className="block h-full w-1/3 rounded-full bg-accent motion-safe:animate-pulse" /></div>}
  </div>;
}

function SavedArtwork({ mosaic, showMonth, onReady, onAuthenticationExpired }: { mosaic: MonthlyMosaic; showMonth: boolean; onReady: (id: string) => void; onAuthenticationExpired: () => void }) {
  const metadata = useMonthlyArtwork(mosaic.tiles, `/api/me/monthly-mosaics/${mosaic.id}/albums`, mosaic.artwork, mosaic.artwork_expires_at);
  useEffect(() => {
    if (metadata.authenticationExpired) onAuthenticationExpired();
    else if (metadata.ready) onReady(mosaic.id);
  }, [metadata.authenticationExpired, metadata.ready, mosaic.id, onReady, onAuthenticationExpired]);
  return (
    <section aria-label={`${monthLabel(mosaic.month)} artwork`} className="min-w-0">
      {showMonth && <h2 className="mosaic-display text-3xl">{monthLabel(mosaic.month)}</h2>}
      {metadata.ready ? <RemixStudio mosaic={mosaic} albums={metadata.albums} /> : <div className="mx-auto mt-6 flex aspect-square max-w-xl items-center justify-center rounded-2xl bg-accent-soft/40 p-6"><div className="w-full max-w-sm"><ArtworkProgress label="Bringing your artwork together…" completed={metadata.completed} total={metadata.total} /></div></div>}
      {metadata.ready && metadata.error && <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-700">{metadata.error}</p><div className="mt-3 flex flex-wrap gap-3"><button type="button" onClick={metadata.retry} className={buttonClass}>Retry artwork</button><a href={`${API_BASE_URL}/api/auth/spotify/start`} className={buttonClass}>Reconnect Spotify</a></div></div>}
    </section>
  );
}

export function MonthlyMosaics() {
  const [archive, setArchive] = useState<MonthlyArchive | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<Failure | null>(null);
  const [actionError, setActionError] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingArtworkId, setPendingArtworkId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const action = useRef<AbortController | null>(null);
  const loadingRequest = useRef<AbortController | null>(null);

  const expireAuthentication = useCallback(() => {
    // A metadata 401 also invalidates an in-flight archive refresh, so its earlier
    // authenticated response cannot restore the private view after expiry.
    loadingRequest.current?.abort();
    setArchive(null);
    setSelectedId(null);
    setPendingArtworkId(null);
    setStatus("");
    setLoading(false);
    setActionError(null);
    setLoadError({ message: "Your session expired. Connect Spotify to continue.", reconnect: true, authenticationExpired: true });
  }, []);

  const finishArtwork = useCallback((id: string) => {
    if (id !== pendingArtworkId) return;
    setPendingArtworkId(null);
    const mosaic = archive?.items.find((item) => item.id === id);
    if (mosaic) setStatus(`${monthLabel(mosaic.month)} saved.`);
  }, [archive, pendingArtworkId]);

  useEffect(() => {
    const controller = new AbortController();
    loadingRequest.current = controller;
    async function load() {
      try {
        const result = await request<MonthlyArchive>(controller.signal);
        if (controller.signal.aborted) return;
        setArchive(result);
        setSelectedId((current) => result.items.some((item) => item.id === current) ? current : result.items[0]?.id ?? null);
        setLoadError(null);
      } catch (failure) {
        if (!controller.signal.aborted) {
          const error = failureOf(failure);
          if (error.authenticationExpired) { setArchive(null); setSelectedId(null); setPendingArtworkId(null); }
          setLoadError(error);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [reload]);

  useEffect(() => () => action.current?.abort(), []);

  function refresh() {
    setLoading(true);
    setStatus("");
    setActionError(null);
    setReload((value) => value + 1);
  }

  async function generate() {
    if (!archive || action.current || pendingArtworkId || loading || archive.items.some((item) => item.month === archive.current_month)) return;
    const controller = new AbortController();
    action.current = controller;
    setBusy(true);
    setActionError(null);
    setStatus("");
    try {
      const result = await request<MonthlyMosaic>(controller.signal, true);
      if (controller.signal.aborted) return;
      setArchive((current) => ({ current_month: result.month, items: [result, ...(current?.items ?? []).filter((item) => item.id !== result.id)].sort((a, b) => b.month.localeCompare(a.month)) }));
      setSelectedId(result.id);
      setPendingArtworkId(result.id);
    } catch (failure) {
      if (!controller.signal.aborted) {
        const error = failureOf(failure);
        if (error.authenticationExpired) {
          setArchive(null);
          setSelectedId(null);
          setPendingArtworkId(null);
          setLoadError(error);
        } else setActionError(error);
      }
    } finally {
      if (!controller.signal.aborted) { setBusy(false); action.current = null; }
    }
  }

  if (!archive) return <div className="mt-8">{loading ? <ArtworkProgress label="Loading your monthly collection..." /> : <>{loadError && <ErrorMessage failure={loadError} />}<button type="button" onClick={refresh} className={`${buttonClass} mt-4`}>Try again</button></>}</div>;
  const currentSaved = archive.items.find((item) => item.month === archive.current_month);
  const selected = archive.items.find((item) => item.id === selectedId);
  const working = busy || !!pendingArtworkId;
  return (
    <div className="mt-8 space-y-6">
      {!currentSaved && <section aria-labelledby="generation-heading" className="rounded-2xl bg-accent-soft/60 p-5 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 id="generation-heading" className="text-xl font-medium">Make room for {new Date(`${archive.current_month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", timeZone: "UTC" })}.</h2>
            <p className="mt-2 text-sm text-text-secondary">Your recent listening, made into something to keep.</p>
          </div>
          <button type="button" onClick={() => void generate()} disabled={working || loading || !!loadError} className="mosaic-button-primary">{busy ? "Creating…" : pendingArtworkId ? "Preparing…" : "Create this month’s mosaic"}</button>
        </div>
      </section>}
      {busy && <ArtworkProgress label="Creating your mosaic…" />}
      {status && <p role="status" className="text-sm text-accent">{status}</p>}
      {actionError && <ErrorMessage failure={actionError} />}
      {loadError && <ErrorMessage failure={loadError} />}
      <div className="flex items-center justify-between gap-3 border-b border-border pb-5">
        {archive.items.length > 1 ? <nav aria-label="Saved months" className="min-w-0">
          <ul className="flex gap-2 overflow-x-auto p-1">{archive.items.map((item) => <li key={item.id} className="shrink-0"><button type="button" disabled={working} onClick={() => setSelectedId(item.id)} aria-pressed={selectedId === item.id} className={`${buttonClass} ${selectedId === item.id ? "border-accent bg-accent-soft" : "border-transparent"}`}>{monthLabel(item.month)}</button></li>)}</ul>
        </nav> : selected ? <h2 className="mosaic-display text-3xl">{monthLabel(selected.month)}</h2> : <span />}
        <button type="button" onClick={refresh} disabled={working || loading} className={`${buttonClass} shrink-0`} aria-label={loading ? "Refreshing collection" : "Refresh collection"}>
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6.1 7a7 7 0 0 1 11.8-.9L20 9M4 15l2.1 2.9A7 7 0 0 0 17.9 17" /></svg>
          <span className="hidden sm:inline">{loading ? "Refreshing…" : "Refresh"}</span>
        </button>
      </div>
      {selected && !busy && <SavedArtwork key={selected.id} mosaic={selected} showMonth={archive.items.length > 1} onReady={finishArtwork} onAuthenticationExpired={expireAuthentication} />}
      <details className="border-t border-border pt-2 text-sm text-text-secondary">
        <summary className="min-h-11 cursor-pointer py-3">About your collection</summary>
        <div className="max-w-2xl space-y-2 pb-3 leading-6">
          <p>Your collection is private. Only designs you choose to share have a public link.</p>
          <p>Based on your Spotify top tracks from roughly the last four weeks, rather than calendar-month play counts.</p>
          <p>One mosaic per month, saved automatically. Customizing a design keeps your monthly artwork unchanged. New months begin at midnight UTC.</p>
          {selected && <p>{monthLabel(selected.month)}: saved {new Date(selected.generated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })} (UTC) · {selected.source_track_count} source tracks.</p>}
        </div>
      </details>
    </div>
  );
}
