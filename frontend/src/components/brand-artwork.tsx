const rows = ["000000000", "011101110", "111111111", "111111111", "011111110", "001111100", "000111000", "000010000", "000000000"];
const colors = ["#b4be94", "#cf7856", "#dfc7a3", "#3f554b", "#a9bec0", "#e2b858", "#796c89"];

/** Decorative cover-inspired tiles; never presented as someone's listening data. */
export function BrandArtwork() {
  return (
    <div aria-hidden="true" className="mx-auto w-full max-w-lg rotate-[-4deg] rounded-[3px] border border-[#e1dccf] bg-[#ece7dc] p-5 shadow-[0_24px_60px_-28px_#534b3b70] sm:p-8">
      <svg viewBox="0 0 450 450" className="w-full">
        {rows.flatMap((row, y) => [...row].map((cell, x) => {
          if (cell === "0") return null;
          const index = x + y * 9;
          const base = colors[index % colors.length];
          const ink = colors[(index + 3) % colors.length];
          return <svg key={index} x={x * 50 + 1} y={y * 50 + 1} width="48" height="48" viewBox="0 0 48 48">
            <rect width="48" height="48" fill={base} />
            {index % 4 === 0 ? <><circle cx="24" cy="24" r="20" fill={ink} /><circle cx="24" cy="24" r="11" fill={base} /><circle cx="24" cy="24" r="3" fill={ink} /></>
              : index % 4 === 1 ? <><path d="M0 48L24 0L48 48Z" fill={ink} /><circle cx="24" cy="30" r="9" fill="#f2e8d4" /></>
              : index % 4 === 2 ? <><path d="M0 0H24V48H0Z" fill={ink} /><circle cx="24" cy="24" r="17" fill="#f2e8d4" opacity=".75" /><path d="M24 7A17 17 0 0 1 24 41Z" fill={base} /></>
              : <><path d="M-8 48L48-8M0 56L56 0M8 64L64 8" stroke={ink} strokeWidth="8" /><circle cx="13" cy="13" r="8" fill="#f2e8d4" /></>}
          </svg>;
        }))}
      </svg>
      <div className="flex items-center justify-between border-t border-[#c9c3b5] pt-4 text-[10px] tracking-[0.16em] text-[#626957]">
        <span>MADE OF MUSIC</span><span>mosaic</span>
      </div>
    </div>
  );
}
