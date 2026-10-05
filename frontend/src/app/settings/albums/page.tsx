import Link from "next/link";
import { AlbumPicker } from "@/components/album-picker";

export default function AlbumsPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
        <Link href="/dashboard" className="inline-flex min-h-11 items-center text-sm text-zinc-300 underline focus-visible:outline-2 focus-visible:outline-green-400">Back to dashboard</Link>
        <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Choose your Featured Albums</h1>
        <p className="mt-3 max-w-xl text-zinc-400">Build a collection that represents your taste. Album selection is private to you while you prepare your mosaic.</p>
        <AlbumPicker />
      </div>
    </main>
  );
}
