"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ProfileCard, THEMES, themePreset, type Theme } from "@/components/profile-card";
import { ShareProfile } from "@/components/share-profile";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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
type Errors = Partial<Record<keyof ProfileDraft, string>>;

const inputClass = "mt-2 min-h-11 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-3 text-base text-white outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/30";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 px-5 py-2 text-sm font-semibold hover:border-green-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-green-400";

function toDraft(profile: OwnerProfile): ProfileDraft {
  return {
    username: profile.username,
    displayName: profile.displayName,
    bio: profile.bio,
    visibility: profile.visibility,
    theme: themePreset(profile.theme.preset),
  };
}

function ProfileForm({ profile }: { profile: OwnerProfile }) {
  const initial = toDraft(profile);
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState(initial);
  const [preview, setPreview] = useState(initial);
  const [errors, setErrors] = useState<Errors>({});
  const [status, setStatus] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const saveController = useRef<AbortController | null>(null);
  useEffect(() => () => saveController.current?.abort(), []);

  function change<K extends keyof ProfileDraft>(field: K, value: ProfileDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setStatus("");
    setSaveError("");
  }

  function validate(): boolean {
    const nextErrors: Errors = {};
    // Legacy generated usernames remain usable when editing other fields.
    if (draft.username !== saved.username && !/^[a-z0-9_]{3,30}$/.test(draft.username)) {
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
      return false;
    }
    return true;
  }

  function previewChanges() {
    if (!validate()) return;
    setPreview({ ...draft, displayName: draft.displayName.trim() });
    setStatus("Preview updated. Your changes have not been saved.");
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveController.current || !validate()) return;
    const changes: Record<string, unknown> = {};
    if (draft.username !== saved.username) changes.username = draft.username;
    if (draft.displayName.trim() !== saved.displayName) changes.display_name = draft.displayName.trim();
    if (draft.bio !== saved.bio) changes.bio = draft.bio;
    if (draft.visibility !== saved.visibility) changes.visibility = draft.visibility;
    if (draft.theme !== saved.theme) changes.theme = { preset: draft.theme };
    if (!Object.keys(changes).length) {
      setStatus("No changes to save.");
      return;
    }
    const controller = new AbortController();
    saveController.current = controller;
    setSaving(true);
    setStatus("");
    setSaveError("");
    setSignedOut(false);
    try {
      const response = await fetch(`${API_BASE_URL}/api/me/profile`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
      });
      if (controller.signal.aborted) return;
      if (response.status === 401) {
        setSignedOut(true);
        setSaveError("Your session expired. Connect Spotify again to save your profile.");
        return;
      }
      if (response.status === 409) {
        setErrors({ username: "This username is unavailable. Choose another." });
        setSaveError("Your changes were not saved. Choose an available username.");
        document.getElementById("username")?.focus();
        return;
      }
      if (response.status === 422) {
        const data = await response.json();
        const fieldErrors: Errors = {};
        if (Array.isArray(data.detail)) {
          for (const issue of data.detail) {
            const field = issue.loc?.[1] === "display_name" ? "displayName" : issue.loc?.[1];
            if (["username", "displayName", "bio", "visibility", "theme"].includes(field)) {
              fieldErrors[field as keyof ProfileDraft] = "Check this value and try again.";
            }
          }
        }
        setErrors(fieldErrors);
        setSaveError("Your changes were not saved. Check the profile fields and try again.");
        document.getElementById(Object.keys(fieldErrors)[0])?.focus();
        return;
      }
      if (!response.ok) throw new Error("Save failed");
      const result: OwnerProfile = await response.json();
      if (controller.signal.aborted) return;
      const next = toDraft(result);
      setSaved(next);
      setDraft(next);
      setPreview(next);
      setErrors({});
      setStatus("Profile saved.");
    } catch {
      if (!controller.signal.aborted) setSaveError("Could not confirm the save. Your edits are still here; try saving again.");
    } finally {
      saveController.current = null;
      if (!controller.signal.aborted) setSaving(false);
    }
  }

  function reset() {
    setDraft(saved);
    setPreview(saved);
    setErrors({});
    setSaveError("");
    setStatus("Edits reset to your current profile.");
  }

  return (
    <div className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <form noValidate onSubmit={save} aria-busy={saving} className="min-w-0 rounded-2xl border border-zinc-800 bg-zinc-900 p-5 sm:p-8">
        <h2 className="text-xl font-semibold">Profile details</h2>
        <p id="draft-notice" className="mt-2 text-sm leading-6 text-zinc-400">Preview your edits, then save them. Unsaved changes are lost when you leave or refresh.</p>

        <fieldset disabled={saving} className="min-w-0">

        <div className="mt-6">
          <label htmlFor="username" className="text-sm font-semibold">Username</label>
          <input id="username" name="username" value={draft.username} onChange={(event) => change("username", event.target.value)} maxLength={30} required autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-invalid={Boolean(errors.username)} aria-describedby={`username-help${errors.username ? " username-error" : ""}`} className={inputClass} />
          <p id="username-help" className="mt-2 text-xs leading-5 text-zinc-400">3–30 lowercase letters, numbers, or underscores. Changing your username changes your shared link.</p>
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
          <p id="visibility-help" className="mt-2 text-xs leading-5 text-zinc-400">Private profiles are visible only to you. Save as public to let anyone with your link view your profile.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {(["private", "public"] as const).map((visibility) => (
              <label key={visibility} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-zinc-700 px-4 py-3 has-checked:border-green-400 has-checked:bg-green-400/5">
                <input type="radio" name="visibility" value={visibility} checked={draft.visibility === visibility} onChange={() => change("visibility", visibility)} aria-describedby="visibility-help" className="h-4 w-4 accent-green-400" />
                <span className="text-sm capitalize">{visibility}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {errors.visibility && <p role="alert" className="mt-2 text-sm text-red-300">{errors.visibility}</p>}

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
        {errors.theme && <p role="alert" className="mt-2 text-sm text-red-300">{errors.theme}</p>}

        <div className="mt-8 flex flex-wrap gap-3">
          <button type="submit" className={`${buttonClass} border-green-500 bg-green-500 text-black hover:bg-green-400 disabled:opacity-60`}>{saving ? "Saving…" : "Save changes"}</button>
          <button type="button" onClick={previewChanges} aria-describedby="draft-notice" className={buttonClass}>Preview changes</button>
          <button type="button" onClick={reset} className={buttonClass}>Reset edits</button>
        </div>
        </fieldset>
        {saveError && <p role="alert" className="mt-4 text-sm text-red-300">{saveError}</p>}
        {signedOut && <Link href="/connect" className={`mt-4 ${buttonClass}`}>Connect Spotify</Link>}
        <p role="status" className="mt-4 min-h-6 text-sm text-green-300">{status}</p>
      </form>

      <aside aria-label="Profile preview" className="min-w-0">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-400">Profile preview</p>
        <ProfileCard profile={{ ...preview, theme: { preset: preview.theme }, images: profile.images }} visibility={preview.visibility} />
        <p className="mt-3 text-xs leading-5 text-zinc-400">Select Preview changes to refresh this preview. This does not publish your profile.</p>
        {saved.visibility === "public" ? (
          <div className="mt-6 space-y-4">
            <Link href={`/@${saved.username}`} className="inline-flex min-h-11 items-center break-all text-sm text-green-400 underline">View public profile</Link>
            <ShareProfile key={saved.username} username={saved.username} />
          </div>
        ) : <p className="mt-6 text-sm text-zinc-400">Save your profile as public to share it.</p>}
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
