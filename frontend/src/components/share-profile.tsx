"use client";

import { useState } from "react";

export function ShareProfile({ username }: { username: string }) {
  const [status, setStatus] = useState("");
  const [manualLink, setManualLink] = useState("");
  const [sharing, setSharing] = useState(false);

  async function share(copyOnly = false) {
    if (sharing) return;
    const url = new URL(`/@${encodeURIComponent(username)}`, window.location.origin).href;
    setSharing(true);
    setStatus("");
    setManualLink("");
    try {
      if (!copyOnly && navigator.share) {
        try {
          await navigator.share({ title: `@${username} on Mosaic`, url });
          setStatus("Sharing complete.");
          return;
        } catch (error) {
          if (error instanceof Error && error.name === "AbortError") return;
          // Unsupported sharing or an unavailable target can still use copy-link.
        }
      }
      await navigator.clipboard.writeText(url);
      setStatus("Link copied.");
    } catch {
      setManualLink(url);
      setStatus("Copy this link to share your profile.");
    } finally {
      setSharing(false);
    }
  }

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={() => share()} disabled={sharing} className="inline-flex min-h-11 items-center justify-center rounded-full border border-green-500 bg-green-500 px-5 py-2 text-sm font-semibold text-black hover:bg-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400 disabled:opacity-60">{sharing ? "Sharing…" : "Share profile"}</button>
        <button type="button" onClick={() => share(true)} disabled={sharing} className="inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-5 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400 disabled:opacity-60">Copy link</button>
      </div>
      <p role="status" className="mt-2 text-sm text-zinc-300">{status}</p>
      {manualLink && <label className="mt-3 block text-sm text-zinc-300">Profile link<input aria-label="Profile link" readOnly value={manualLink} onFocus={(event) => event.target.select()} className="mt-2 min-h-11 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 text-white" /></label>}
    </div>
  );
}
