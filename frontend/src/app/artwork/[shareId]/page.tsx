import { notFound } from "next/navigation";
import { SharedArtwork } from "@/components/shared-artwork";

export const metadata = { title: "A month in music · Mosaic", description: "An artwork made from recent listening. Explore the songs inside, then make your own.", robots: { index: false, follow: false } };

export default async function ArtworkPage({ params }: { params: Promise<{ shareId: string }> }) {
  const { shareId } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(shareId)) notFound();
  return <SharedArtwork shareId={shareId} />;
}
