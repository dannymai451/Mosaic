"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function logout() {
    if (busy) return;
    setBusy(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error("Logout failed");
      router.replace("/");
      router.refresh();
    } catch {
      setError("Could not log out. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button type="button" onClick={() => void logout()} disabled={busy} className="mosaic-button disabled:opacity-60">
        {busy ? "Logging out…" : "Log out"}
      </button>
      {error && <p role="alert" className="max-w-xs text-right text-sm text-red-700">{error}</p>}
    </div>
  );
}
