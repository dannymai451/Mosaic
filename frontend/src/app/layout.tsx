import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mosaic Spotify Application",
  description: "Mosaic web application.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
