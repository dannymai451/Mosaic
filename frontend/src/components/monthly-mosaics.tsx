"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type MosaicLayout } from "@/components/mosaic-canvas";
import { RemixStudio } from "@/components/remix-studio";
import { useMonthlyArtwork } from "@/components/monthly-artwork";
import type { Album } from "@/components/album-detail";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-4 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400 disabled:opacity-50";

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
  if (response.status === 401) throw new MonthlyRequestError("Your session is missing or expired. Connect Spotify to open your private collection.", true, true);
  if (response.status === 403) throw new MonthlyRequestError("Reconnect Spotify to allow access to your recent top tracks. Your saved months are still here.", true);
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    throw new MonthlyRequestError(`Spotify is limiting requests. ${wait ? `Wait ${wait} seconds, then try again.` : "Wait a little, then try again."} Your saved months are still here.`);
  }
  if (response.status === 422) {
    const body: { detail?: string } = await response.json();
    if (body.detail === "spotify_no_recent_listening") throw new MonthlyRequestError("Spotify has no recent top tracks for you yet. Listen to more music and try generating later. No empty artwork has been saved.");
  }
  if (!response.ok) throw new MonthlyRequestError("Could not load or save your artwork. Your previous months are safe; please try again.");
  return response.json();
}

function failureOf(failure: unknown): Failure {
  if (failure instanceof MonthlyRequestError) return { message: failure.message, reconnect: failure.reconnect, authenticationExpired: failure.authenticationExpired };
  return { message: failure instanceof DOMException && failure.name === "TimeoutError"
    ? "The request took too long. Try again or refresh your collection to check whether the artwork was saved."
    : "Could not reach Mosaic. Try again or refresh your collection to check whether the artwork was saved.", reconnect: false, authenticationExpired: false };
}

function ErrorMessage({ failure }: { failure: Failure }) {
  return <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-300">{failure.message}</p>{failure.reconnect && <a href={`${API_BASE_URL}/api/auth/spotify/start`} className={`${buttonClass} mt-3`}>Connect Spotify</a>}</div>;
}

function ArtworkProgress({ label, completed, total }: { label: string; completed?: number; total?: number }) {
  const determinate = completed !== undefined && total !== undefined;
  return <div className="mt-5" role="status">
    <p className="text-sm text-zinc-300">{label}{determinate && total > 0 ? ` ${Math.floor(completed / total * 100)}%` : ""}</p>
    {determinate ? <progress aria-label={label} max={Math.max(total, 1)} value={completed} className="mt-3 h-2 w-full accent-green-400" /> : <div role="progressbar" aria-label={label} className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-800"><span className="block h-full w-1/3 rounded-full bg-green-400 motion-safe:animate-pulse" /></div>}
  </div>;
}

function SavedArtwork({ mosaic, onReady, onAuthenticationExpired }: { mosaic: MonthlyMosaic; onReady: (id: string) => void; onAuthenticationExpired: () => void }) {
  const metadata = useMonthlyArtwork(mosaic.tiles, `/api/me/monthly-mosaics/${mosaic.id}/albums`, mosaic.artwork, mosaic.artwork_expires_at);
  const shape = { heart: "Heart", star: "Star", "music-note": "Music note", blank: "Custom", pumpkin: "Pumpkin", ghost: "Ghost", bat: "Bat", skull: "Skull" }[mosaic.preset_key];
  useEffect(() => {
    if (metadata.authenticationExpired) onAuthenticationExpired();
    else if (metadata.ready) onReady(mosaic.id);
  }, [metadata.authenticationExpired, metadata.ready, mosaic.id, onReady, onAuthenticationExpired]);
  return (
    <section aria-labelledby="artwork-heading" className="min-w-0 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="artwork-heading" className="text-2xl font-semibold">{monthLabel(mosaic.month)}</h2>
        <span className="text-sm text-zinc-400">{shape} · {mosaic.album_ids.length} albums</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-zinc-400">Saved on {new Date(mosaic.generated_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" })} (UTC), from {mosaic.source_track_count} top tracks over roughly the preceding four weeks. This is a listening snapshot, rather than a count of every play in a calendar month.</p>
      {metadata.ready ? <RemixStudio mosaic={mosaic} albums={metadata.albums} /> : <div className="mx-auto mt-6 flex aspect-square max-w-xl items-center justify-center rounded-xl border border-zinc-800 p-6"><div className="w-full max-w-sm"><ArtworkProgress label="Preparing song details and covers..." completed={metadata.completed} total={metadata.total} /><p className="mt-4 text-sm leading-6 text-zinc-500">Your saved artwork will appear together when its covers are ready.</p></div></div>}
      {metadata.ready && metadata.error && <div className="mt-4"><p role="alert" className="text-sm leading-6 text-red-300">{metadata.error} Your saved shape and Spotify links are still available.</p><div className="mt-3 flex flex-wrap gap-3"><button type="button" onClick={metadata.retry} className={buttonClass}>Retry artwork</button><a href={`${API_BASE_URL}/api/auth/spotify/start`} className={buttonClass}>Reconnect Spotify</a></div></div>}
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
    setLoadError({ message: "Your session is missing or expired. Connect Spotify to open your private collection.", reconnect: true, authenticationExpired: true });
  }, []);

  const finishArtwork = useCallback((id: string) => {
    if (id !== pendingArtworkId) return;
    setPendingArtworkId(null);
    const mosaic = archive?.items.find((item) => item.id === id);
    if (mosaic) setStatus(`${monthLabel(mosaic.month)} is saved in your private collection.`);
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
      <section aria-labelledby="generation-heading" className="rounded-2xl border border-zinc-800 p-5 sm:p-6">
        <h2 id="generation-heading" className="text-xl font-semibold">{monthLabel(archive.current_month)}</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{currentSaved ? "This month's artwork is saved. Come back next month for a new shape and listening snapshot." : "Generate when you're ready. Your artwork saves automatically and stays as it was created, so previous months remain yours to revisit."} One artwork per month, with months changing at midnight UTC.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" onClick={() => void generate()} disabled={working || loading || !!currentSaved || !!loadError} className={`${buttonClass} border-green-500 bg-green-500 text-black`}>{busy ? "Generating artwork..." : pendingArtworkId ? "Preparing artwork..." : currentSaved ? "This month is saved" : "Generate this month's artwork"}</button>
          <button type="button" onClick={refresh} disabled={working || loading} className={buttonClass}>{loading ? "Refreshing..." : "Refresh collection"}</button>
          {currentSaved && selectedId !== currentSaved.id && <button type="button" disabled={working} onClick={() => setSelectedId(currentSaved.id)} className={buttonClass}>View this month</button>}
        </div>
        {busy && <ArtworkProgress label="Generating and saving your listening snapshot..." />}
        {status && <p role="status" className="mt-4 text-sm text-green-300">{status}</p>}
        {actionError && <ErrorMessage failure={actionError} />}
        {loadError && <ErrorMessage failure={loadError} />}
      </section>
      {archive.items.length ? <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Saved months" className="self-start rounded-2xl border border-zinc-800 p-5">
          <h2 className="font-semibold">Your saved months</h2>
          <ul className="mt-4 flex flex-wrap gap-3 lg:flex-col">{archive.items.map((item) => <li key={item.id}><button type="button" disabled={working} onClick={() => setSelectedId(item.id)} aria-pressed={selectedId === item.id} className={`${buttonClass} ${selectedId === item.id ? "border-green-400 text-green-300" : ""}`}>{monthLabel(item.month)}</button></li>)}</ul>
        </nav>
        {selected && !busy && <SavedArtwork key={selected.id} mosaic={selected} onReady={finishArtwork} onAuthenticationExpired={expireAuthentication} />}
      </div> : !busy && <section className="rounded-2xl border border-dashed border-zinc-700 p-8 text-center"><h2 className="text-xl font-semibold">Your collection starts here</h2><p className="mt-3 text-zinc-400">Generate your first artwork above. Each saved month will appear here.</p></section>}
      <p className="text-sm leading-6 text-zinc-500">Your collection stays private. Only designs you choose to share are accessible through their links.</p>
    </div>
  );
}
