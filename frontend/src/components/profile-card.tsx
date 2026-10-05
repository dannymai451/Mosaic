import Image from "next/image";
import type { MosaicLayout } from "@/components/mosaic-canvas";

export const THEMES = {
  midnight: { label: "Midnight", card: "bg-zinc-900 text-white", accent: "text-green-400", swatch: "bg-zinc-950" },
  paper: { label: "Paper", card: "bg-stone-100 text-stone-900", accent: "text-emerald-800", swatch: "bg-stone-100" },
  plum: { label: "Plum", card: "bg-purple-950 text-white", accent: "text-purple-200", swatch: "bg-purple-950" },
} as const;

export type Theme = keyof typeof THEMES;
export type PublicProfile = {
  username: string;
  displayName: string;
  bio: string;
  theme: { preset?: string };
  images: { url: string }[];
  mosaic?: MosaicLayout | null;
};

export function themePreset(preset?: string): Theme {
  return preset && Object.hasOwn(THEMES, preset) ? preset as Theme : "midnight";
}

export function ProfileCard({ profile, visibility }: {
  profile: PublicProfile;
  visibility?: "private" | "public";
}) {
  const theme = THEMES[themePreset(profile.theme.preset)];
  return (
    <div className={`min-w-0 rounded-2xl border border-zinc-700 p-6 sm:p-8 ${theme.card}`}>
      {profile.images[0]?.url ? (
        <Image src={profile.images[0].url} alt="" width={64} height={64} unoptimized className="h-16 w-16 rounded-full object-cover" />
      ) : (
        <div aria-hidden="true" className={`flex h-16 w-16 items-center justify-center rounded-full border border-current text-2xl ${theme.accent}`}>♪</div>
      )}
      <h2 className="mt-5 break-words text-2xl font-bold">{profile.displayName}</h2>
      <p className={`mt-1 break-all text-sm ${theme.accent}`}>@{profile.username}</p>
      <p className="mt-5 whitespace-pre-wrap break-words text-sm leading-6">{profile.bio || "Your bio will appear here."}</p>
      {visibility && <p className={`mt-6 text-sm font-semibold ${theme.accent}`}>{visibility === "private" ? "Private profile" : "Public profile"}</p>}
    </div>
  );
}
