import Image from "next/image";
import type { ReactNode } from "react";
import { imageAddress, type RemixStyle } from "@/components/remix-design";

export function ArtworkFrame({ style, background, children }: { style: RemixStyle; background?: string | null; children: ReactNode }) {
  const width = style.frame_style === "none" ? 0 : style.frame_style === "mat" ? style.frame_width + 12 : style.frame_width;
  return <div style={{ containerType: "inline-size" }}><div className="relative isolate overflow-hidden" style={{ backgroundColor: style.background_color, borderColor: style.frame_color, borderStyle: style.frame_style === "double" ? "double" : "solid", borderWidth: `${width / 4}cqw`, borderRadius: `${style.corner_radius / 4}cqw`, padding: "8%" }}>
    {background && <><Image src={imageAddress(background)!} alt="" fill unoptimized className="pointer-events-none -z-10 object-cover" style={{ objectPosition: `${style.photo_x}% ${style.photo_y}%` }} /><div className="pointer-events-none absolute inset-0 -z-10 bg-black" style={{ opacity: style.photo_dim / 100 }} /></>}
    {children}
  </div></div>;
}
