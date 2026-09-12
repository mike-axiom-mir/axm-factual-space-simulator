import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const base = process.env.AXM_ATLAS_URL || 'http://127.0.0.1:8765/output/persistent_atlas_demo/atlas.html';
const artifactDir = path.resolve('artifacts/atlas-map-experience');
fs.mkdirSync(artifactDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const pageErrors = [];
const consoleErrors = [];
const failedRequests = [];
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on('pageerror', error => pageErrors.push(String(error)));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`));
  await page.goto(base, { waitUntil: 'load' });
  const nodes = page.locator('svg#map g[data-id]');
  const count = await nodes.count();
  if (count < 2) throw new Error(`expected at least 2 atlas nodes, got ${count}`);
  const initialSelected = await page.locator('svg#map g[aria-pressed="true"]').count();
  if (initialSelected !== 1) throw new Error(`expected one selected map node, got ${initialSelected}`);
  const target = nodes.nth(1);
  const targetId = await target.getAttribute('data-id');
  await target.focus();
  if (await target.getAttribute('role') !== 'button') throw new Error('map node lacks button role');
  await page.keyboard.press('Enter');
  const selected = page.locator(`svg#map g[data-id="${targetId}"]`);
  if (await selected.getAttribute('aria-pressed') !== 'true') throw new Error('keyboard selection did not become aria-pressed');
  if (await selected.locator('.selected-ring').count() !== 1) throw new Error('selected map node lacks visible selection ring');
  const activeButton = page.locator(`#locations button[data-id="${targetId}"].active`);
  if (await activeButton.count() !== 1) throw new Error('list and map selection diverged');
  const selectedName = (await page.locator('#name').textContent())?.trim();
  if (!selectedName) throw new Error('selected location details did not update');
  const desktopWidths = await page.evaluate(() => ({ viewport: innerWidth, scroll: document.documentElement.scrollWidth }));
  if (desktopWidths.viewport !== desktopWidths.scroll) throw new Error(`desktop overflow ${JSON.stringify(desktopWidths)}`);
  await page.screenshot({ path: path.join(artifactDir, 'atlas-map-desktop.png'), fullPage: true });

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  mobile.on('pageerror', error => pageErrors.push(String(error)));
  mobile.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  mobile.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`));
  await mobile.goto(base, { waitUntil: 'load' });
  const mobileTarget = mobile.locator('svg#map g[data-id]').nth(1);
  await mobileTarget.focus();
  await mobile.keyboard.press(' ');
  if (await mobileTarget.getAttribute('aria-pressed') !== 'true') throw new Error('mobile-size keyboard selection did not persist');
  const mobileWidths = await mobile.evaluate(() => ({ viewport: innerWidth, scroll: document.documentElement.scrollWidth }));
  if (mobileWidths.viewport !== mobileWidths.scroll) throw new Error(`mobile overflow ${JSON.stringify(mobileWidths)}`);
  await mobile.screenshot({ path: path.join(artifactDir, 'atlas-map-mobile.png'), fullPage: true });

  if (pageErrors.length || consoleErrors.length || failedRequests.length) throw new Error(JSON.stringify({ pageErrors, consoleErrors, failedRequests }));
  const evidence = {
    schema: 'axm.atlas-map-experience-evidence/v1',
    selectedLocationId: targetId,
    selectedLocationName: selectedName,
    mapNodeCount: count,
    desktopWidths,
    mobileWidths,
    pageErrors,
    consoleErrors,
    failedRequests,
    authority: 'PRESENTATION_ONLY',
    canonicalStateChangedBySelection: false
  };
  fs.writeFileSync(path.join(artifactDir, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify(evidence));
} finally {
  await browser.close();
}
