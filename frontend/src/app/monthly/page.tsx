import { LogoutButton } from "@/components/logout-button";
import { MonthlyMosaics } from "@/components/monthly-mosaics";
import { MosaicBrand } from "@/components/mosaic-brand";

export default function MonthlyPage() {
  return (
    <main className="min-h-screen bg-background text-text-primary">
      <div className="mosaic-shell pb-12">
        <nav aria-label="Collection navigation" className="flex min-h-24 items-center justify-between gap-4 border-b border-border py-4 text-sm">
          <MosaicBrand href="/dashboard" />
          <LogoutButton />
        </nav>
        <div className="pt-10 sm:pt-14">
          <h1 className="mosaic-display text-4xl sm:text-6xl">Your collection.</h1>
        </div>
        <MonthlyMosaics />
      </div>
    </main>
  );
}
