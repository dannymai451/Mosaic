import type { MosaicLayout, MosaicTile } from "@/components/mosaic-canvas";

export const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export type ShapeKey = "pumpkin" | "ghost" | "bat" | "skull";
export type RemixStyle = { shape: ShapeKey; background_color: string; frame_style: "none" | "line" | "double" | "mat"; frame_color: string; frame_width: number; corner_radius: number; photo_dim: number; photo_x: number; photo_y: number };
export type Remix = { id: string; name: string; month: string; style: RemixStyle; layout: MosaicLayout; background_url: string | null; share_id: string | null };
export type ShapePreset = { key: ShapeKey; label: string; coordinates: { x: number; y: number }[]; grid_width: number; grid_height: number };
export const defaultStyle: RemixStyle = { shape: "pumpkin", background_color: "#222720", frame_style: "line", frame_color: "#66715a", frame_width: 4, corner_radius: 24, photo_dim: 30, photo_x: 50, photo_y: 50 };
export const control = "mosaic-button";

export function imageAddress(path: string | null) { return path?.startsWith("/api/") ? `${API}${path}` : path; }
export function uniqueSongs(tiles: MosaicTile[]) {
  return [...new Map(tiles.map((tile) => [`${tile.spotifyAlbumId}:${tile.spotifyTrackId ?? ""}`, tile])).values()];
}
export function layoutFor(preset: ShapePreset, tiles: MosaicTile[]): MosaicLayout {
  const songs = uniqueSongs(tiles);
  return { preset_key: preset.key, grid_width: preset.grid_width, grid_height: preset.grid_height, tiles: songs.length ? preset.coordinates.map((point, index) => ({ ...songs[index % songs.length], ...point })) : [] };
}
export async function remixRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { credentials: "include", cache: "no-store", ...init, signal: init.signal ?? AbortSignal.timeout(20000) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session expired. Reconnect Spotify, then try again.");
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Could not save this change. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}
export function jsonBody(value: unknown): RequestInit { return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) }; }
