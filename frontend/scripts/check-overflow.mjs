// Logs in as each role, visits every route in every language at five widths, and fails on any horizontal overflow.
//   node scripts/check-overflow.mjs            needs the API on :8000 (python -m scripts.dev_server) and the app on :5173
//   (npm run dev, or npm run preview -- --port 5173)
// Uses the system Chrome (no browser download). Screenshots go to ../.impeccable/review/.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.BASE ?? "http://localhost:5173";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", ".impeccable", "review");
mkdirSync(OUT, { recursive: true });
const WIDTHS = (process.env.WIDTHS ?? "360,390,768,1024,1440").split(",").map(Number);
const LANGS = (process.env.LANGS ?? "en,ta,hi,te,kn,ml").split(",");
const PW = "Demo@12345";

const ROLES = {
  public: { login: null, routes: ["/", "/login", "/login?as=doctor", "/register", "/terms", "/privacy", "/admin"] },
  ravi: { login: "ravi", routes: ["/hub", "/hub/members", "/hub/notifications", "/hub/plan/@koushal", "/hub/upload/@koushal", "/hub/manual/@koushal"] },
  meena: { login: "meena", routes: ["/hub", "/hub/plan/@koushal"] },
  koushal: { login: "koushal", routes: ["/hub", "/hub/members", "/hub/plan/@self"] },
  sureshkumar: { login: "sureshkumar", routes: ["/hub", "/hub/members", "/hub/plan/@self"] },
  "dr.sanjay": { login: "dr.sanjay", routes: ["/doctor", "/doctor/review/@first", "/doctor/patients"] },
  "dr.mallu": { login: "dr.mallu", routes: ["/doctor", "/doctor/patients"] },
  admin: { login: "admin", admin: true, routes: ["/admin/overview", "/admin/doctors", "/admin/routing", "/admin/hubs", "/admin/audit", "/admin/system"] },
};

const failures = [];
let checked = 0;
const browser = await chromium.launch({ channel: "chrome" });

async function api(ctx, path) {
  const r = await ctx.request.get(BASE + path);
  return r.ok() ? r.json() : null;
}

for (const [name, role] of Object.entries(ROLES)) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const ids = {};
  if (role.login) {
    await page.goto(BASE + (role.admin ? "/admin" : "/login"));
    await page.fill('input[autocomplete="username"]', role.login);
    await page.fill('input[type="password"]', PW);
    await page.click('button:has-text("Sign")');
    await page.waitForURL((u) => !/\/(login|admin)$/.test(u.pathname), { timeout: 15000 }).catch(() => {});
    const me = await api(ctx, "/me");
    ids.self = me?.id;
    if (me?.role === "family" || me?.role === "patient") {
      for (const h of (await api(ctx, "/hubs")) ?? []) for (const p of h.patients) ids[p.name.toLowerCase()] = p.patient_id;
    }
    if (me?.role === "doctor") ids.first = ((await api(ctx, "/review/queue")) ?? [])[0]?.id;
  }
  for (const route of role.routes) {
    const path = route.replace(/@(\w+)/, (_, k) => ids[k] ?? "missing");
    if (path.includes("missing") || path.endsWith("/undefined")) { console.log(`skip ${name} ${route} (no id)`); continue; }
    for (const lang of LANGS) {
      await page.addInitScript((l) => { try { localStorage.setItem("lang", l); } catch {} }, lang);
      for (const w of WIDTHS) {
        await page.setViewportSize({ width: w, height: 900 });
        await page.goto(BASE + path, { waitUntil: "networkidle" }).catch(() => {});
        await page.waitForTimeout(250);
        const res = await page.evaluate(() => {
          const out = [], iw = window.innerWidth;
          if (document.documentElement.scrollWidth > iw) out.push(`page scrollWidth ${document.documentElement.scrollWidth} > ${iw}`);
          const clipped = (el) => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o !== "visible") return true; } return false; };
          for (const el of document.querySelectorAll("body *")) {
            if (!(el instanceof HTMLElement) || el.closest("[data-allow-overflow]") || el.closest("svg")) continue;
            const cs = getComputedStyle(el), r = el.getBoundingClientRect();
            if (cs.display === "none" || cs.visibility === "hidden" || r.width <= 1 || r.height <= 1 || cs.position === "fixed" || clipped(el)) continue;
            const tag = `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)}`;
            if (r.right > iw + 1) { out.push(`${tag} right ${Math.round(r.right)} > ${iw}`); continue; }
            if (cs.overflowX === "visible" && cs.display !== "inline" && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1 && !["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName)) out.push(`${tag} content ${el.scrollWidth} > box ${el.clientWidth}`);
          }
          return out.slice(0, 4);
        });
        checked++;
        if (res.length) { failures.push(`${name} ${path} ${lang} ${w}px: ${res.join("; ")}`); }
        if (lang === "en" && (w === 390 || w === 1440)) await page.screenshot({ path: join(OUT, `${name}-${path.replace(/[^\w]+/g, "_").slice(0, 40)}-${w}.png`), fullPage: false });
      }
    }
  }
  await ctx.close();
}
await browser.close();
console.log(`checked ${checked} page views`);
if (failures.length) { console.log(`\n${failures.length} FAIL`); for (const f of failures.slice(0, 60)) console.log(" ", f); process.exit(1); }
console.log("PASS: no overflow at any width, role or language");
