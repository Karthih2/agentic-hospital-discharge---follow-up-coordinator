/** Flat illustrations in the palette: mint paper, tile surfaces, 2px navy outlines, square corners. No gradients,
 * no shadows. All decorative, so aria-hidden. Colours come from the CSS tokens. */
import type { ReactNode } from "react";

const INK = "var(--color-ink)", TILE = "var(--color-tile)", MINT = "var(--color-mint)", DEEP = "var(--color-ground-deep)",
  TEAL = "var(--color-teal)", LINE = "var(--color-line)", BLUE = "var(--color-pending)", GREEN = "var(--color-done)",
  AMBER = "var(--color-review)";
const sw = { stroke: INK, strokeWidth: 2, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

function Frame({ w, h, children, className = "" }: { w: number; h: number; children: ReactNode; className?: string }) {
  return <svg viewBox={`0 0 ${w} ${h}`} className={`h-auto w-full ${className}`} aria-hidden="true" focusable="false">{children}</svg>;
}

/** Hero: a follow-up plan sheet, a calendar card and a capsule. */
export function HeroArt({ className = "" }: { className?: string }) {
  return (
    <Frame w={440} h={360} className={className}>
      <rect x="2" y="2" width="436" height="356" rx="4" fill={DEEP} stroke={LINE} strokeWidth="1" />
      <rect x="120" y="30" width="240" height="300" rx="4" fill={TILE} {...sw} />
      <rect x="196" y="18" width="88" height="28" rx="4" fill={TEAL} {...sw} />
      <rect x="150" y="76" width="22" height="22" rx="4" fill={GREEN} {...sw} />
      <path d="M155 87l5 5 8-9" fill="none" stroke={TILE} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="184" y="80" width="140" height="8" rx="2" fill={INK} />
      <rect x="184" y="94" width="90" height="6" rx="2" fill={LINE} />
      <rect x="150" y="124" width="22" height="22" rx="4" fill={BLUE} {...sw} />
      <rect x="184" y="128" width="120" height="8" rx="2" fill={INK} />
      <rect x="184" y="142" width="100" height="6" rx="2" fill={LINE} />
      <rect x="150" y="172" width="22" height="22" rx="4" fill={BLUE} {...sw} />
      <rect x="184" y="176" width="146" height="8" rx="2" fill={INK} />
      <rect x="184" y="190" width="70" height="6" rx="2" fill={LINE} />
      <rect x="146" y="226" width="190" height="64" rx="4" fill={DEEP} stroke={AMBER} strokeWidth="2" strokeDasharray="6 5" />
      <rect x="160" y="242" width="22" height="22" rx="4" fill={AMBER} {...sw} />
      <rect x="194" y="244" width="110" height="8" rx="2" fill={INK} />
      <rect x="194" y="258" width="80" height="6" rx="2" fill={LINE} />
      <rect x="28" y="96" width="112" height="120" rx="4" fill={TILE} {...sw} />
      <rect x="28" y="96" width="112" height="30" rx="4" fill={TEAL} {...sw} />
      <rect x="44" y="84" width="8" height="22" rx="2" fill={INK} /><rect x="116" y="84" width="8" height="22" rx="2" fill={INK} />
      <rect x="46" y="142" width="20" height="20" rx="3" fill={MINT} {...sw} />
      <rect x="76" y="142" width="20" height="20" rx="3" fill={TILE} {...sw} />
      <rect x="106" y="142" width="20" height="20" rx="3" fill={TILE} {...sw} />
      <rect x="46" y="174" width="20" height="20" rx="3" fill={TILE} {...sw} />
      <rect x="76" y="174" width="20" height="20" rx="3" fill={TILE} {...sw} />
      <g transform="rotate(-28 350 300)">
        <rect x="312" y="282" width="80" height="36" rx="18" fill={TILE} {...sw} />
        <path d="M352 282h22a18 18 0 010 36h-22z" fill={MINT} {...sw} />
      </g>
      <g transform="translate(362 52)">
        <rect width="52" height="52" rx="4" fill={TILE} {...sw} />
        <path d="M26 14v24M14 26h24" stroke={TEAL} strokeWidth="6" strokeLinecap="square" />
      </g>
    </Frame>
  );
}

/** Empty list: an open tray with nothing in it. */
export function EmptyArt({ className = "" }: { className?: string }) {
  return (
    <Frame w={200} h={140} className={className}>
      <path d="M30 70h140l14 52H16z" fill={TILE} {...sw} />
      <path d="M16 122h168v8H16z" fill={MINT} {...sw} />
      <rect x="64" y="22" width="72" height="56" rx="4" fill={DEEP} stroke={INK} strokeWidth="2" strokeDasharray="5 5" />
      <path d="M84 50h32M84 62h20" stroke={LINE} strokeWidth="4" strokeLinecap="round" />
    </Frame>
  );
}

/** Error: a sheet with a tear and an alert square. */
export function ErrorArt({ className = "" }: { className?: string }) {
  return (
    <Frame w={200} h={150} className={className}>
      <path d="M52 14h72l28 28v94H52z" fill={TILE} {...sw} />
      <path d="M124 14v28h28" fill={DEEP} {...sw} />
      <path d="M70 92l14-10 12 14 14-12 16 10" fill="none" stroke={AMBER} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="90" y="46" width="24" height="24" rx="4" fill={AMBER} {...sw} />
      <path d="M102 52v9" stroke={TILE} strokeWidth="3" strokeLinecap="round" /><circle cx="102" cy="65" r="1.8" fill={TILE} />
      <rect x="70" y="112" width="64" height="6" rx="2" fill={LINE} />
    </Frame>
  );
}

/** Language picker: three speech tiles with their own scripts. */
export function LanguageArt({ className = "" }: { className?: string }) {
  const glyph = (x: number, y: number, ch: string, fill: string) => (
    <g>
      <path d={`M${x} ${y}h70a4 4 0 014 4v44a4 4 0 01-4 4H${x + 28}l-14 14v-14H${x}a4 4 0 01-4-4V${y + 4}a4 4 0 014-4z`} fill={fill} {...sw} />
      <text x={x + 35} y={y + 40} textAnchor="middle" fontFamily="var(--font-display)" fontWeight="700" fontSize="30" fill={INK}>{ch}</text>
    </g>
  );
  return (
    <Frame w={260} h={150} className={className}>
      {glyph(10, 14, "A", MINT)}{glyph(100, 40, "அ", TILE)}{glyph(176, 10, "अ", DEEP)}
    </Frame>
  );
}

/** Doctor review: a sheet with a highlighted line and a magnifier. */
export function ReviewArt({ className = "" }: { className?: string }) {
  return (
    <Frame w={220} h={150} className={className}>
      <rect x="30" y="14" width="124" height="122" rx="4" fill={TILE} {...sw} />
      <rect x="46" y="34" width="92" height="6" rx="2" fill={LINE} />
      <rect x="42" y="52" width="100" height="18" rx="2" fill={MINT} />
      <rect x="46" y="58" width="80" height="6" rx="2" fill={INK} />
      <rect x="46" y="84" width="92" height="6" rx="2" fill={LINE} /><rect x="46" y="100" width="60" height="6" rx="2" fill={LINE} />
      <circle cx="150" cy="96" r="24" fill={DEEP} fillOpacity="0.6" {...sw} />
      <path d="M168 114l24 22" stroke={INK} strokeWidth="6" strokeLinecap="round" />
    </Frame>
  );
}
