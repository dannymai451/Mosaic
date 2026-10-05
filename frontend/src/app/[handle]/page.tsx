import Link from "next/link";
import { notFound } from "next/navigation";
import { ProfileCard, type PublicProfile } from "@/components/profile-card";
import { ShareProfile } from "@/components/share-profile";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default async function SharedProfilePage({ params }: {
  params: Promise<{ handle: string }>;
}) {
  const { handle: routeHandle } = await params;
  let handle: string;
  try {
    handle = decodeURIComponent(routeHandle);
  } catch {
    notFound();
  }
  // A dynamic segment captures the entire @username. Existing generated names
  // can exceed 30 characters and remain readable until their owner edits them.
  if (!/^@[a-z0-9_]{3,37}$/.test(handle)) notFound();
  let profile: PublicProfile | null = null;
  let missing = false;
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/profiles/${encodeURIComponent(handle.slice(1))}/public`,
      { cache: "no-store", signal: AbortSignal.timeout(10000) },
    );
    missing = response.status === 404;
    if (response.ok) profile = await response.json();
  } catch {
    // Keep upstream outages distinct from missing/private profiles.
  }
  if (missing) notFound();

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-12">
        <Link href="/" className="inline-flex min-h-11 items-center text-sm font-semibold uppercase tracking-[0.25em] text-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400">Mosaic</Link>
        <h1 className="mt-5 text-xl font-semibold">Music profile</h1>
        {profile ? <div className="mt-6 space-y-6"><ProfileCard profile={profile} /><ShareProfile username={profile.username} /></div> : (
          <div className="mt-6 rounded-2xl border border-zinc-800 p-6">
            <p role="alert">Could not load this profile. Please try again.</p>
            <a href={`/${handle}`} className="mt-4 inline-flex min-h-11 items-center text-green-400 underline">Try again</a>
          </div>
        )}
      </div>
    </main>
  );
}
