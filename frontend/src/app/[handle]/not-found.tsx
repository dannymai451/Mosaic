import Link from "next/link";

export default function ProfileNotFound() {
  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-12 text-white">
      <div className="mx-auto max-w-xl rounded-2xl border border-zinc-800 p-6">
        <h1 className="text-2xl font-bold">Profile unavailable</h1>
        <p className="mt-3 text-zinc-300">This profile is private or does not exist.</p>
        <Link href="/" className="mt-5 inline-flex min-h-11 items-center text-green-400 underline">Go to Mosaic</Link>
      </div>
    </main>
  );
}
