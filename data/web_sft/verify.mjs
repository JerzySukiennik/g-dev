// Open every generated page in a real browser and keep only the ones that work.
//
// A page passes when it throws no errors, shows something, and does what its
// checks say: animates, changes on hover, changes on click, survives key presses.
// "Changes" means the rendered pixels differ, so a hover rule that does nothing
// visible fails.
//
// Usage: node verify.mjs pages.jsonl verified.jsonl [shots_dir] [concurrency]

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire("/Users/jurek/Downloads/Claude/Projects/Flop/node_modules/");
const { chromium } = require("playwright-core");
const EXE = "/Users/jurek/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-x64/chrome-headless-shell";

const [inFile, outFile, shotsDir = "", conc = "3"] = process.argv.slice(2);
const rows = fs.readFileSync(inFile, "utf8").trim().split("\n").map((l) => JSON.parse(l));
if (shotsDir) fs.mkdirSync(shotsDir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function check(browser, row) {
  const reasons = [];
  const ctx = await browser.newContext({ viewport: { width: 640, height: 480 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const c = row.checks || {};
  try {
    await page.setContent(row.response, { waitUntil: "load" });
    await sleep(c.delay || 30);
    const visible = await page.evaluate(() => [...document.body.querySelectorAll("*")]
      .filter((e) => e.tagName !== "SCRIPT" && e.tagName !== "STYLE")
      .some((e) => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; }));
    if (!visible) reasons.push("nothing visible");
    const s0 = await page.screenshot();
    let last = s0;
    if (c.animated) {
      await sleep(350);
      const s1 = await page.screenshot();
      if (s0.equals(s1)) reasons.push("not animated");
      last = s1;
    }
    if (c.hover) {
      const before = await page.screenshot();
      await page.hover(c.hover, { timeout: 2000 });
      await sleep(c.wait || 300);
      const after = await page.screenshot();
      if (before.equals(after)) reasons.push("hover changes nothing");
      last = after;
    }
    if (c.click) {
      const before = await page.screenshot();
      await page.click(c.click, { timeout: 2000 });
      await sleep(c.wait || 200);
      const after = await page.screenshot();
      if (before.equals(after)) reasons.push("click changes nothing");
      last = after;
    }
    if (c.keys) {
      for (const k of c.keys) { await page.keyboard.press(k); await sleep(60); }
      await sleep(200);
      last = await page.screenshot();
    }
    if (errors.length) reasons.push("errors: " + errors.slice(0, 2).join(" | ").slice(0, 160));
    if (shotsDir && !reasons.length && shotCount[row.pattern] < 3) {
      fs.writeFileSync(path.join(shotsDir, `${row.pattern}-${row.id}.png`), last);
      shotCount[row.pattern]++;
    }
  } catch (e) {
    reasons.push("exception: " + String(e.message || e).split("\n")[0].slice(0, 160));
  }
  await ctx.close();
  return reasons;
}

const shotCount = Object.fromEntries([...new Set(rows.map((r) => r.pattern))].map((p) => [p, 0]));
const browser = await chromium.launch({ executablePath: EXE });
const out = fs.createWriteStream(outFile);
let next = 0, done = 0;
const stats = {};
async function worker() {
  while (next < rows.length) {
    const row = rows[next++];
    const reasons = await check(browser, row);
    const s = (stats[row.pattern] ||= { ok: 0, bad: 0, why: {} });
    if (reasons.length) { s.bad++; const k = reasons[0].slice(0, 70); s.why[k] = (s.why[k] || 0) + 1; }
    else s.ok++;
    out.write(JSON.stringify({ ...row, ok: !reasons.length, reasons }) + "\n");
    if (++done % 200 === 0) console.log(`${done}/${rows.length}`);
  }
}
await Promise.all(Array.from({ length: Number(conc) }, worker));
await browser.close();
out.end();
for (const [p, s] of Object.entries(stats)) console.log(p.padEnd(16), `ok ${s.ok}  bad ${s.bad}`, s.bad ? JSON.stringify(s.why) : "");
