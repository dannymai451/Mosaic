import Link from "next/link";
import { MosaicEditor } from "@/components/mosaic-editor";

export default function BuilderPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
        <Link href="/dashboard" className="inline-flex min-h-11 items-center text-sm text-zinc-300 underline focus-visible:outline-2 focus-visible:outline-green-400">Back to dashboard</Link>
        <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Build your mosaic</h1>
        <p className="mt-3 max-w-xl text-zinc-400">Arrange your Featured Album covers into a shape that represents you.</p>
        <MosaicEditor />
      </div>
    </main>
  );
}
