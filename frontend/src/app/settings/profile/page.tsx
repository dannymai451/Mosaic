"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const THEMES = {
  midnight: { label: "Midnight", card: "bg-zinc-900 text-white", accent: "text-green-400", swatch: "bg-zinc-950" },
  paper: { label: "Paper", card: "bg-stone-100 text-stone-900", accent: "text-emerald-800", swatch: "bg-stone-100" },
  plum: { label: "Plum", card: "bg-purple-950 text-white", accent: "text-purple-200", swatch: "bg-purple-950" },
} as const;

type Theme = keyof typeof THEMES;
type ProfileDraft = {
  username: string;
  displayName: string;
  bio: string;
  visibility: "private" | "public";
  theme: Theme;
};
type OwnerProfile = Omit<ProfileDraft, "theme"> & {
  theme: { preset?: string };
  images: { url: string }[];
};
type Errors = Partial<Record<"username" | "displayName" | "bio", string>>;

const inputClass = "mt-2 min-h-11 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-3 text-base text-white outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/30";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-5 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400";

function ProfileForm({ profile }: { profile: OwnerProfile }) {
  const initial: ProfileDraft = {
    username: profile.username,
    displayName: profile.displayName,
    bio: profile.bio,
    visibility: profile.visibility,
    theme: profile.theme.preset && profile.theme.preset in THEMES
      ? profile.theme.preset as Theme : "midnight",
  };
  const [draft, setDraft] = useState(initial);
  const [preview, setPreview] = useState(initial);
  const [errors, setErrors] = useState<Errors>({});
  const [status, setStatus] = useState("");
  const theme = THEMES[preview.theme];

  function change<K extends keyof ProfileDraft>(field: K, value: ProfileDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setStatus("");
  }

  function previewChanges(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Errors = {};
    if (!/^[a-z0-9_]{3,30}$/.test(draft.username)) {
      nextErrors.username = "Use 3–30 lowercase letters, numbers, or underscores.";
    }
    if (!draft.displayName.trim()) {
      nextErrors.displayName = "Enter a display name.";
    } else if (draft.displayName.length > 255) {
      nextErrors.displayName = "Use 255 characters or fewer.";
    }
    if (draft.bio.length > 500) nextErrors.bio = "Use 500 characters or fewer.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      setStatus("");
      const firstField = Object.keys(nextErrors)[0];
      document.getElementById(firstField)?.focus();
      return;
    }
    setPreview({ ...draft, displayName: draft.displayName.trim() });
    setStatus("Preview updated. Your changes have not been saved.");
  }

  function reset() {
    setDraft(initial);
    setPreview(initial);
    setErrors({});
    setStatus("Edits reset to your current profile.");
  }

  return (
    <div className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <form noValidate onSubmit={previewChanges} className="min-w-0 rounded-2xl border border-zinc-800 bg-zinc-900 p-5 sm:p-8">
        <h2 className="text-xl font-semibold">Profile details</h2>
        <p id="draft-notice" className="mt-2 text-sm leading-6 text-zinc-400">Preview your edits here. Saving will be available in the next step; changes are lost when you leave or refresh.</p>

        <div className="mt-6">
          <label htmlFor="username" className="text-sm font-semibold">Username</label>
          <input id="username" name="username" value={draft.username} onChange={(event) => change("username", event.target.value)} maxLength={30} required autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-invalid={Boolean(errors.username)} aria-describedby={`username-help${errors.username ? " username-error" : ""}`} className={inputClass} />
          <p id="username-help" className="mt-2 text-xs leading-5 text-zinc-400">3–30 lowercase letters, numbers, or underscores. Username availability will be checked when saving is added.</p>
          {errors.username && <p id="username-error" className="mt-2 text-sm text-red-300">{errors.username}</p>}
        </div>

        <div className="mt-6">
          <label htmlFor="displayName" className="text-sm font-semibold">Display name</label>
          <input id="displayName" name="displayName" value={draft.displayName} onChange={(event) => change("displayName", event.target.value)} maxLength={255} required autoComplete="nickname" aria-invalid={Boolean(errors.displayName)} aria-describedby={errors.displayName ? "displayName-error" : undefined} className={inputClass} />
          {errors.displayName && <p id="displayName-error" className="mt-2 text-sm text-red-300">{errors.displayName}</p>}
        </div>

        <div className="mt-6">
          <label htmlFor="bio" className="text-sm font-semibold">Bio <span className="font-normal text-zinc-400">(optional)</span></label>
          <textarea id="bio" name="bio" value={draft.bio} onChange={(event) => change("bio", event.target.value)} maxLength={500} rows={4} aria-invalid={Boolean(errors.bio)} aria-describedby={`bio-count${errors.bio ? " bio-error" : ""}`} className={`${inputClass} resize-y`} placeholder="Tell people a little about you and your music." />
          <p id="bio-count" className="mt-2 text-right text-xs text-zinc-400">{draft.bio.length}/500 characters</p>
          {errors.bio && <p id="bio-error" className="mt-2 text-sm text-red-300">{errors.bio}</p>}
        </div>

        <fieldset className="mt-6">
          <legend className="text-sm font-semibold">Visibility</legend>
          <p id="visibility-help" className="mt-2 text-xs leading-5 text-zinc-400">When saving and sharing are available, private profiles will be visible only to you. Public profiles will be viewable by anyone with your link.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {(["private", "public"] as const).map((visibility) => (
              <label key={visibility} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-zinc-700 px-4 py-3 has-checked:border-green-400 has-checked:bg-green-400/5">
                <input type="radio" name="visibility" value={visibility} checked={draft.visibility === visibility} onChange={() => change("visibility", visibility)} aria-describedby="visibility-help" className="h-4 w-4 accent-green-400" />
                <span className="text-sm capitalize">{visibility}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="mt-6">
          <legend className="text-sm font-semibold">Theme</legend>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {(Object.keys(THEMES) as Theme[]).map((key) => (
              <label key={key} className="flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border border-zinc-700 px-3 py-3 has-checked:border-green-400 has-checked:bg-green-400/5">
                <input type="radio" name="theme" value={key} checked={draft.theme === key} onChange={() => change("theme", key)} className="h-4 w-4 shrink-0 accent-green-400" />
                <span aria-hidden="true" className={`h-4 w-4 shrink-0 rounded-full border border-zinc-500 ${THEMES[key].swatch}`} />
                <span className="text-sm">{THEMES[key].label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mt-8 flex flex-wrap gap-3">
          <button type="submit" aria-describedby="draft-notice" className={`${buttonClass} border-green-500 bg-green-500 text-black hover:bg-green-400`}>Preview changes</button>
          <button type="button" onClick={reset} className={buttonClass}>Reset edits</button>
        </div>
        <p role="status" className="mt-4 min-h-6 text-sm text-green-300">{status}</p>
      </form>

      <aside aria-label="Profile preview" className="min-w-0">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-400">Profile preview · unsaved</p>
        <div className={`rounded-2xl border border-zinc-700 p-6 sm:p-8 ${theme.card}`}>
          {profile.images[0]?.url ? (
            <Image src={profile.images[0].url} alt="" width={64} height={64} unoptimized className="h-16 w-16 rounded-full object-cover" />
          ) : (
            <div aria-hidden="true" className={`flex h-16 w-16 items-center justify-center rounded-full border border-current text-2xl ${theme.accent}`}>♪</div>
          )}
          <h2 className="mt-5 break-words text-2xl font-bold">{preview.displayName}</h2>
          <p className={`mt-1 break-all text-sm ${theme.accent}`}>@{preview.username}</p>
          <p className="mt-5 whitespace-pre-wrap break-words text-sm leading-6">{preview.bio || "Your bio will appear here."}</p>
          <p className={`mt-6 text-sm font-semibold ${theme.accent}`}>{preview.visibility === "private" ? "Private profile" : "Public profile"}</p>
        </div>
        <p className="mt-3 text-xs leading-5 text-zinc-400">Select Preview changes to refresh this preview. This does not publish your profile.</p>
      </aside>
    </div>
  );
}

export default function ProfileSettingsPage() {
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "signed-out" | "error">("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function loadProfile() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/me`, {
          credentials: "include",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        });
        if (controller.signal.aborted) return;
        if (response.status === 401) {
          setState("signed-out");
          return;
        }
        if (!response.ok) throw new Error("Could not load profile");
        const data: OwnerProfile = await response.json();
        if (controller.signal.aborted) return;
        setProfile(data);
        setState("ready");
      } catch {
        if (!controller.signal.aborted) setState("error");
      }
    }
    loadProfile();
    return () => controller.abort();
  }, [attempt]);

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
        <Link href="/dashboard" className="inline-flex min-h-11 items-center text-sm text-zinc-300 hover:text-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400">← Dashboard</Link>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.25em] text-green-400">Mosaic</p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl">Edit your profile</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-400">Make your music profile feel like you.</p>
        {state === "loading" && <p role="status" className="mt-8 text-zinc-300">Loading your profile…</p>}
        {state === "signed-out" && <div className="mt-8 rounded-2xl border border-zinc-800 p-6"><p role="alert">Connect Spotify to edit your profile. Your session may have expired.</p><Link href="/connect" className={`mt-5 ${buttonClass}`}>Connect Spotify</Link></div>}
        {state === "error" && <div className="mt-8 rounded-2xl border border-zinc-800 p-6"><p role="alert">Could not load your profile. Check that the backend is running and try again.</p><button type="button" onClick={() => { setState("loading"); setAttempt((value) => value + 1); }} className={`mt-5 ${buttonClass}`}>Try again</button></div>}
        {state === "ready" && profile && <ProfileForm profile={profile} />}
      </div>
    </main>
  );
}
