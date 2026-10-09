import Link from "next/link";

export function MosaicBrand({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} aria-label="Mosaic home" className="inline-flex min-h-11 shrink-0 items-center gap-2.5 text-text-primary">
      <span aria-hidden="true" className="grid h-6 w-6 grid-cols-2 gap-[3px] rotate-[-6deg]">
        <span className="rounded-[3px] bg-accent" /><span className="rounded-[3px] bg-[#b6c697]" />
        <span className="rounded-[3px] bg-[#d49c7e]" /><span className="rounded-[3px] bg-accent" />
      </span>
      <span className="text-2xl font-semibold tracking-[-0.07em]">mosaic</span>
    </Link>
  );
}
