const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">
      <div className="flex max-w-lg flex-col items-center gap-6 px-6 text-center">
        <div>
          <p className="mb-2 text-sm font-medium uppercase tracking-[0.25em] text-green-400">
            Mosaic
          </p>

          <h1 className="text-5xl font-bold tracking-tight">
            Your music,
            <br />
            a month in art.
          </h1>
        </div>

        <p className="text-lg text-zinc-400">
          Turn your recent listening into album-cover art. Save one mosaic each
          month and revisit your music, month by month.
        </p>
        <p className="text-sm leading-6 text-zinc-500">Based on your Spotify top tracks from roughly the last four weeks. Your monthly collection stays private.</p>

        <a
          href={`${API_BASE_URL}/api/auth/spotify/start`}
          className="rounded-full bg-green-500 px-8 py-3 font-semibold text-black transition hover:bg-green-400"
        >
          Connect Spotify
        </a>
      </div>
    </main>
  );
}
