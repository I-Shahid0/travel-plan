/**
 * Design-review screenshot rig (dev tool, not shipped).
 * Usage: bun scripts/shoot.ts <outDir> [signedIn]
 * Signs in as the seeded reviewer account when `signedIn` is passed,
 * then captures every page/state at desktop + mobile widths.
 */
import { chromium, type BrowserContext, type Page } from "playwright-core";

const BASE = process.env.SHOOT_BASE ?? "http://localhost:3001";
const outDir = process.argv[2] ?? "shots";
const signedIn = process.argv.includes("signedIn");

const EMAIL = "amelia@meridian.test";
const PASSWORD = "starlight-atlas-9";

async function shoot(
  context: BrowserContext,
  name: string,
  url: string,
  opts: { width?: number; fullPage?: boolean; settle?: number; interact?: (page: Page) => Promise<void> } = {},
) {
  const page = await context.newPage();
  await page.setViewportSize({ width: opts.width ?? 1440, height: 900 });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(opts.settle ?? 1200);
  if (opts.interact) await opts.interact(page);
  // walk the page so IntersectionObserver reveals fire before capture
  await page.evaluate(async () => {
    const step = window.innerHeight * 0.8;
    for (let y = 0; y <= document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: opts.fullPage ?? true });
  await page.close();
  console.log(`✓ ${name}`);
}

async function main() {
  // Bun + Windows can't drive Playwright's pipe transport — launch Chrome
  // ourselves with a CDP port and connect to it instead.
  const { spawn } = await import("node:child_process");
  const chromeProcess = spawn(
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    [
      "--headless=new",
      "--remote-debugging-port=9223",
      "--no-first-run",
      "--no-default-browser-check",
      "--user-data-dir=" + process.env.TEMP + "/meridian-shoot-profile",
    ],
    { stdio: "ignore" },
  );
  await new Promise((resolve) => setTimeout(resolve, 2500));

  const browser = await chromium.connectOverCDP("http://localhost:9223");
  const context = await browser.newContext({ deviceScaleFactor: 1 });
  const cleanup = () => {
    try {
      chromeProcess.kill();
    } catch {
      /* already gone */
    }
  };
  process.on("exit", cleanup);

  if (signedIn) {
    const page = await context.newPage();
    await page.goto(`${BASE}/sign-in`, { waitUntil: "networkidle" });
    await page.fill("#auth-email", EMAIL);
    await page.fill("#auth-password", PASSWORD);
    await page.click("button[type=submit]");
    await page.waitForURL("**/search**", { timeout: 15000 });
    await page.close();
    console.log("✓ signed in");
  }

  await shoot(context, "01-landing", `${BASE}/`, { settle: 2000 });
  await shoot(context, "02-search-results", `${BASE}/search?q=late+night+ramen`, { settle: 2500 });
  await shoot(context, "03-search-filtered", `${BASE}/search?q=cozy+italian+dinner&mode=hybrid&city=Philadelphia&price_max=3`, { settle: 2500 });
  await shoot(context, "04-search-empty", `${BASE}/search?q=zzzz+qqqq+xxxx&city=Nowhereville`, { settle: 2000 });
  await shoot(context, "05-search-blank", `${BASE}/search`, { settle: 1500 });
  // auth pages redirect signed-in sessions — capture them anonymously
  const anon = await browser.newContext({ deviceScaleFactor: 1 });
  await shoot(anon, "06-sign-in", `${BASE}/sign-in`, {});
  await shoot(anon, "07-sign-up", `${BASE}/sign-up`, {});
  await anon.close();
  await shoot(context, "08-notfound", `${BASE}/uncharted-nowhere`, {});

  if (signedIn) {
    await shoot(context, "09-profile", `${BASE}/profile`, {});
    await shoot(context, "10-plan-form", `${BASE}/plan`, {});
    await shoot(context, "11-plan-result", `${BASE}/plan`, {
      settle: 1000,
      interact: async (page) => {
        await page.fill("#plan-query", "weekend food tour in Philadelphia");
        await page.selectOption("#plan-days", "2");
        await page.click("form button[type=submit]");
        // pending ends when the submit button re-enables
        await page.waitForFunction(
          () => {
            const button = document.querySelector<HTMLButtonElement>("form button[type=submit]");
            return button !== null && !button.disabled;
          },
          { timeout: 90000 },
        );
        await page.waitForTimeout(1200);
      },
    });
  }

  // phase 10 surfaces
  await shoot(context, "14-browse", `${BASE}/browse`, { settle: 2500 });
  await shoot(
    context,
    "15-browse-filtered",
    `${BASE}/browse?city=Philadelphia&category=Restaurants&min_stars=4&sort=reviews&page=2`,
    { settle: 2500 },
  );
  // visiting listings records views → seeds the For-You feed below
  await shoot(context, "16-listing", `${BASE}/listing/-fs09akgCKv5rTTy7iUHUg`, { settle: 2500 });
  await shoot(context, "17-listing-via-browse", `${BASE}/browse?category=Bookstores`, {
    settle: 2000,
    interact: async (page) => {
      // cards sit in a reveal-on-scroll stagger (opacity 0 until observed),
      // so follow the first card's href instead of clicking it
      const href = await page
        .locator("a[href^='/listing/']")
        .first()
        .getAttribute("href");
      if (href) {
        await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
        await page.waitForTimeout(2000);
      }
    },
  });
  await shoot(context, "18-observatory", `${BASE}/observatory`, { settle: 2000 });

  if (signedIn) {
    await shoot(context, "19-foryou", `${BASE}/foryou`, { settle: 2500 });
    await shoot(context, "20-history", `${BASE}/history`, { settle: 2000 });
  }

  // mobile sweeps
  await shoot(context, "12-m-landing", `${BASE}/`, { width: 390, settle: 2000 });
  await shoot(context, "13-m-search", `${BASE}/search?q=late+night+ramen`, { width: 390, settle: 2500 });
  await shoot(context, "21-m-browse", `${BASE}/browse`, { width: 390, settle: 2500 });
  await shoot(context, "22-m-listing", `${BASE}/listing/-fs09akgCKv5rTTy7iUHUg`, { width: 390, settle: 2500 });
  if (signedIn) {
    await shoot(context, "23-m-foryou", `${BASE}/foryou`, { width: 390, settle: 2500 });
    await shoot(context, "24-m-history", `${BASE}/history`, { width: 390, settle: 2000 });
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
