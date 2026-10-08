import Link from "next/link";
import { MonthlyMosaics } from "@/components/monthly-mosaics";

export default function MonthlyPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
        <nav aria-label="Account navigation" className="flex flex-wrap justify-between gap-4 text-sm text-zinc-300">
          <Link href="/dashboard" className="inline-flex min-h-11 items-center underline focus-visible:outline-2 focus-visible:outline-green-400">Back to dashboard</Link>
          <Link href="/settings/profile" className="inline-flex min-h-11 items-center underline focus-visible:outline-2 focus-visible:outline-green-400">Account settings</Link>
        </nav>
        <p className="mt-5 text-xs font-medium uppercase tracking-[0.25em] text-orange-200">Mosaic / Your collection</p>
        <h1 className="mt-3 text-4xl font-medium tracking-tight sm:text-6xl">Your music. Your canvas.</h1>
        <p className="mt-4 max-w-xl text-sm leading-7 text-zinc-400 sm:text-base">A monthly snapshot of your recent listening. Make it yours with seasonal shapes, personal backgrounds, and a frame that fits your mood.</p>
        <MonthlyMosaics />
      </div>
    </main>
  );
}
