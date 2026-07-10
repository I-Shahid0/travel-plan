/** One-off capture for quick design checks: node scripts/shoot-one.ts <url> <out> [width] [signedIn] */
import { chromium } from "playwright-core";

const url = process.argv[2]!;
const out = process.argv[3]!;
const width = Number(process.argv[4] ?? 390);
const signedIn = process.argv.includes("signedIn");
const BASE = "http://localhost:3001";

async function main() {
  const { spawn } = await import("node:child_process");
  const chrome = spawn(
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    [
      "--headless=new",
      "--remote-debugging-port=9224",
      "--no-first-run",
      "--no-default-browser-check",
      "--user-data-dir=" + process.env.TEMP + "/meridian-shoot-one",
    ],
    { stdio: "ignore" },
  );
  await new Promise((resolve) => setTimeout(resolve, 2500));
  const browser = await chromium.connectOverCDP("http://localhost:9224");
  const context = await browser.newContext({ deviceScaleFactor: 1 });

  if (signedIn) {
    const page = await context.newPage();
    await page.goto(`${BASE}/sign-in`, { waitUntil: "networkidle" });
    await page.fill("#auth-email", "amelia@meridian.test");
    await page.fill("#auth-password", "starlight-atlas-9");
    await page.click("button[type=submit]");
    await page.waitForURL("**/search**", { timeout: 15000 });
    await page.close();
  }

  const page = await context.newPage();
  await page.setViewportSize({ width, height: 900 });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out, fullPage: false });
  await browser.close();
  chrome.kill();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
