import type { Album } from "@/components/album-detail";
import { mosaicAlbumKey, type MosaicLayout } from "@/components/mosaic-canvas";
import { API, imageAddress, type RemixStyle } from "@/components/remix-design";

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new window.Image();
    const timer = window.setTimeout(() => reject(new Error("A cover took too long to load. Please try again.")), 15000);
    if (!url.startsWith("blob:") && !url.startsWith("data:")) image.crossOrigin = url.startsWith(API) ? "use-credentials" : "anonymous";
    image.onload = () => { window.clearTimeout(timer); resolve(image); };
    image.onerror = () => { window.clearTimeout(timer); reject(new Error("A cover could not be exported. Retry after the artwork finishes loading.")); };
    image.src = url;
  });
}

function fillImage(context: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, width: number, height: number, focusX = 50, focusY = 50) {
  const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
  const sourceWidth = width / scale, sourceHeight = height / scale;
  context.drawImage(image, (image.naturalWidth - sourceWidth) * focusX / 100, (image.naturalHeight - sourceHeight) * focusY / 100, sourceWidth, sourceHeight, x, y, width, height);
}

export async function exportArtwork({ layout, albums, style, background, month, format }: { layout: MosaicLayout; albums: Record<string, Album>; style: RemixStyle; background: string | null; month: string; format: "story" | "square" }): Promise<Blob> {
  const urls = [...new Set(layout.tiles.map((tile) => albums[mosaicAlbumKey(tile)]?.imageUrl).filter((url): url is string => !!url))];
  const images = new Map(await Promise.all(urls.map(async (url) => [url, await loadImage(url)] as const)));
  const photo = background ? await loadImage(imageAddress(background)!) : null;
  const canvas = document.createElement("canvas");
  canvas.width = 1080; canvas.height = format === "story" ? 1920 : 1080;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser cannot export the artwork.");
  context.fillStyle = style.background_color; context.fillRect(0, 0, canvas.width, canvas.height);
  // A subtle dark surround gives the card consistent contrast on any background.
  context.fillStyle = "rgba(0,0,0,.18)"; context.fillRect(0, 0, canvas.width, canvas.height);
  const size = format === "story" ? 944 : 900;
  const x = (1080 - size) / 2, y = (canvas.height - size) / 2;
  const scale = size / 400;
  const frameWidth = (style.frame_style === "none" ? 0 : style.frame_style === "mat" ? style.frame_width + 12 : style.frame_width) * scale;
  const radius = style.corner_radius * scale;
  context.save(); context.beginPath(); context.roundRect(x, y, size, size, radius); context.clip();
  context.fillStyle = style.background_color; context.fillRect(x, y, size, size);
  if (photo) { fillImage(context, photo, x, y, size, size, style.photo_x, style.photo_y); context.fillStyle = `rgba(0,0,0,${style.photo_dim / 100})`; context.fillRect(x, y, size, size); }
  if (frameWidth) {
    context.strokeStyle = style.frame_color;
    if (style.frame_style === "double") {
      context.lineWidth = frameWidth / 3;
      for (const inset of [frameWidth / 6, frameWidth * 5 / 6]) { context.beginPath(); context.roundRect(x + inset, y + inset, size - inset * 2, size - inset * 2, Math.max(0, radius - inset)); context.stroke(); }
    } else { context.lineWidth = frameWidth; context.beginPath(); context.roundRect(x + frameWidth / 2, y + frameWidth / 2, size - frameWidth, size - frameWidth, Math.max(0, radius - frameWidth / 2)); context.stroke(); }
  }
  const inset = frameWidth + size * 0.08, area = size - 2 * inset;
  const gap = (layout.preset_key === "pumpkin" ? 2 : 4) * scale;
  const tileSize = (area - gap * (layout.grid_width - 1)) / layout.grid_width;
  for (const tile of layout.tiles) {
    const cover = albums[mosaicAlbumKey(tile)]?.imageUrl;
    const image = cover ? images.get(cover) : undefined;
    const left = x + inset + tile.x * (tileSize + gap), top = y + inset + tile.y * (tileSize + gap);
    context.save(); context.beginPath(); context.roundRect(left, top, tileSize, tileSize, Math.min(2 * scale, tileSize / 5)); context.clip();
    if (image) context.drawImage(image, left, top, tileSize, tileSize);
    else { context.fillStyle = "#3f3f46"; context.fillRect(left, top, tileSize, tileSize); context.fillStyle = "#d4d4d8"; context.font = `${tileSize / 2}px sans-serif`; context.textAlign = "center"; context.fillText("♪", left + tileSize / 2, top + tileSize * 0.7); }
    context.restore();
  }
  context.restore();
  const label = new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).toUpperCase();
  context.textAlign = "center";
  // Text sits on a dark chip, keeping color choices readable without a text-heavy card.
  const textY = format === "story" ? 280 : 46;
  context.fillStyle = "rgba(0,0,0,.75)"; context.beginPath(); context.roundRect(330, textY - 30, 420, 64, 32); context.fill();
  context.fillStyle = "#f4f0e8"; context.font = "500 25px Arial"; context.fillText(label, 540, textY + 10);
  const footerY = format === "story" ? 1575 : 1045;
  context.fillStyle = "rgba(0,0,0,.75)"; context.beginPath(); context.roundRect(305, footerY - 35, 470, 66, 33); context.fill();
  context.fillStyle = "#f4f0e8"; context.font = "500 24px Arial"; context.fillText("mosaic  /  my month in music", 540, footerY + 8);
  return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("The artwork could not be exported.")), "image/png"));
}
