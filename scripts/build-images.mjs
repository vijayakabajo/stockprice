// Generates the site's raster images from SVG into web/static/web/img/:
//   favicon.svg, apple-touch-icon.png (180), logo-512.png (Organization logo),
//   og-default.png (1200x630 share card), and per-guide hero images as
//   AVIF + WebP (served to browsers) + PNG (Open Graph / fallback).
// Run with `npm run build:images` after changing the brand or adding a guide.
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "web/static/web/img");
const SITE = process.env.SITE_NAME || "Equity Profiles";
const ACCENT = "#911AED", DEEP = "#6E12B4", BG = "#F7F5FB", INK = "#211E2B", MUTED = "#67627A";
const FONT = "Segoe UI, Helvetica Neue, Arial, sans-serif";

const mark = (size) => `
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${ACCENT}"/><stop offset="1" stop-color="${DEEP}"/></linearGradient></defs>
  <rect width="64" height="64" rx="16" fill="url(#g)"/>
  <path d="M10 44l12-12 10 8L44 24l12 12" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="44" cy="24" r="5" fill="#fff"/>
</svg>`;

const card = (title, subtitle, art) => `
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${ACCENT}"/><stop offset="1" stop-color="${DEEP}"/></linearGradient></defs>
  <rect width="1200" height="630" fill="${BG}"/>
  <rect x="0" y="0" width="1200" height="10" fill="url(#g)"/>
  <g transform="translate(80 80)">${mark(64).replace(/<\?xml.*?\?>/, "").replace("<svg", '<svg x="0" y="0"')}</g>
  <text x="164" y="124" font-family="${FONT}" font-size="34" font-weight="700" fill="${INK}">${SITE}</text>
  <text x="80" y="300" font-family="${FONT}" font-size="64" font-weight="800" fill="${INK}">${title}</text>
  <text x="80" y="370" font-family="${FONT}" font-size="30" fill="${MUTED}">${subtitle}</text>
  ${art}
</svg>`;

const bars = (labels) => labels.map((l, i) => {
  const h = 210 - i * 32, x = 80 + i * 150;
  return `<rect x="${x}" y="${590 - h * 0.85}" width="110" height="${h * 0.85}" rx="10" fill="${i === 0 ? "url(#g)" : "#D9D2E8"}"/>` +
    `<text x="${x + 55}" y="${575 - h * 0.85}" text-anchor="middle" font-family="${FONT}" font-size="20" fill="${MUTED}">${l}</text>`;
}).join("");

const guides = {
  "what-is-market-cap": card("What is market cap?", "Share price × shares outstanding, and how stocks are sized", bars(["Mega", "Large", "Mid", "Small", "Micro", "Nano"])),
  "what-is-a-spac": card("What is a SPAC?", "A listed shell company that merges with a private business",
    `<rect x="80" y="440" width="300" height="120" rx="16" fill="url(#g)"/><text x="230" y="512" text-anchor="middle" font-family="${FONT}" font-size="34" font-weight="700" fill="#fff">SPAC</text>
     <path d="M410 500h220" stroke="${MUTED}" stroke-width="6" stroke-linecap="round"/><path d="M610 480l24 20-24 20" fill="none" stroke="${MUTED}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
     <rect x="660" y="440" width="420" height="120" rx="16" fill="#fff" stroke="#D9D2E8" stroke-width="3"/><text x="870" y="512" text-anchor="middle" font-family="${FONT}" font-size="30" font-weight="600" fill="${INK}">Operating business</text>`),
  "what-is-an-adr": card("What is an ADR?", "How non-U.S. companies list on U.S. exchanges",
    `<circle cx="200" cy="500" r="80" fill="none" stroke="${ACCENT}" stroke-width="6"/><path d="M120 500h160M200 420c40 40 40 120 0 160M200 420c-40 40-40 120 0 160" fill="none" stroke="${ACCENT}" stroke-width="5"/>
     <path d="M310 500h190" stroke="${MUTED}" stroke-width="6" stroke-linecap="round"/>
     <rect x="520" y="450" width="260" height="100" rx="16" fill="#fff" stroke="#D9D2E8" stroke-width="3"/><text x="650" y="510" text-anchor="middle" font-family="${FONT}" font-size="28" font-weight="600" fill="${INK}">Depositary bank</text>
     <path d="M800 500h120" stroke="${MUTED}" stroke-width="6" stroke-linecap="round"/>
     <rect x="940" y="450" width="180" height="100" rx="16" fill="url(#g)"/><text x="1030" y="512" text-anchor="middle" font-family="${FONT}" font-size="30" font-weight="700" fill="#fff">U.S.</text>`),
};

await mkdir(join(out, "guides"), { recursive: true });
await writeFile(join(out, "favicon.svg"), mark(64).trim());
await sharp(Buffer.from(mark(180))).png().toFile(join(out, "apple-touch-icon.png"));
await sharp(Buffer.from(mark(512))).png().toFile(join(out, "logo-512.png"));
await sharp(Buffer.from(card("U.S. stock profiles, answer first.", "Market cap, sector, exchange and filings, every figure dated", bars(["", "", "", "", "", ""])))).png({ compressionLevel: 9 }).toFile(join(out, "og-default.png"));

for (const [slug, svg] of Object.entries(guides)) {
  const image = sharp(Buffer.from(svg));
  await image.clone().png({ compressionLevel: 9 }).toFile(join(out, "guides", `${slug}.png`));
  await image.clone().webp({ quality: 82 }).toFile(join(out, "guides", `${slug}.webp`));
  await image.clone().avif({ quality: 60 }).toFile(join(out, "guides", `${slug}.avif`));
}
console.log("images written to web/static/web/img/");
