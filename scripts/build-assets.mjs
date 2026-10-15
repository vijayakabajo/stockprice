// Builds the site's static assets into web/static/web/ (committed, so a
// deploy needs no Node):
//
//   assets/css/site.css  -> bundle @imports -> PurgeCSS -> minify -> css/site.css
//   assets/js/site.js    -> minify                               -> js/site.js
//   @fontsource packages -> the three latin woff2 files we use    -> fonts/
//
// Run with `npm run build` (or `make assets`) after editing anything in assets/.
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import { PurgeCSS } from "purgecss";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "web/static/web");
const targets = ["chrome111", "edge111", "firefox114", "safari16.4"];

// Where class names can appear. Python is included because template tags
// (web/templatetags/web.py) emit classes such as "mono-tile".
const content = [
  "web/templates/**/*.html",
  "web/templatetags/*.py",
  "web/views.py",
  "assets/js/*.js",
].map((p) => join(root, p).replaceAll("\\", "/"));

// Selectors PurgeCSS cannot see in source: state set by attributes or JS.
const safelist = {
  standard: ["is-me", "js"],
  greedy: [/aria-/, /data-theme/, /hidden/, /:target/, /:focus/],
};

async function css() {
  const bundled = await esbuild.build({
    entryPoints: [join(root, "assets/css/site.css")],
    bundle: true,
    write: false,
    external: ["*.woff2"],
    logLevel: "warning",
  });
  const raw = bundled.outputFiles[0].text;
  const [purged] = await new PurgeCSS().purge({
    content,
    css: [{ raw }],
    safelist,
    fontFace: false,
    keyframes: true,
    variables: false,
  });
  const minified = await esbuild.transform(purged.css, { loader: "css", minify: true, target: targets });
  await writeFile(join(out, "css/site.css"), minified.code);
  return { before: raw.length, after: minified.code.length };
}

async function js() {
  const result = await esbuild.build({
    entryPoints: [join(root, "assets/js/site.js")],
    bundle: true,
    minify: true,
    format: "iife",
    target: targets,
    outfile: join(out, "js/site.js"),
    logLevel: "warning",
  });
  return (await readFile(join(out, "js/site.js"))).length;
}

async function fonts() {
  const files = [
    ["@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-wght-normal.woff2", "bricolage-grotesque-latin-wght.woff2"],
    ["@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2", "ibm-plex-mono-latin-400.woff2"],
    ["@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-600-normal.woff2", "ibm-plex-mono-latin-600.woff2"],
    ["@fontsource-variable/bricolage-grotesque/LICENSE", "LICENSE-bricolage-grotesque.txt"],
    ["@fontsource/ibm-plex-mono/LICENSE", "LICENSE-ibm-plex-mono.txt"],
  ];
  await mkdir(join(out, "fonts"), { recursive: true });
  for (const [from, to] of files) await copyFile(join(root, "node_modules", from), join(out, "fonts", to));
}

await Promise.all(["css", "js", "fonts"].map((d) => mkdir(join(out, d), { recursive: true })));
const [cssSize, jsSize] = await Promise.all([css(), js(), fonts()]);
console.log(`css: ${(cssSize.before / 1024).toFixed(1)} KB bundled -> ${(cssSize.after / 1024).toFixed(1)} KB purged+minified`);
console.log(`js:  ${(jsSize / 1024).toFixed(1)} KB minified`);
