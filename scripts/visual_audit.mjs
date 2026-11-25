import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SHOT_DIR = 'c:\\agencia\\tracking\\screenshots';
fs.mkdirSync(SHOT_DIR, { recursive: true });

const WAVES = {
  '1': [
    { slug: 'roof-royale', url: 'https://roof-royale-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'austin-roofing-company', url: 'https://austin-roofing-company-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'buddys-roofing', url: 'https://buddys-roofing-demo.pages.dev', expectedMin: '$15,000' },
  ],
  '1b': [
    { slug: 'honestroof', url: 'https://honestroof-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'davis-roofing-solutions', url: 'https://davis-roofing-solutions-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'advantage-roofing', url: 'https://advantage-roofing-demo-340.pages.dev', expectedMin: '$13,800' },
    { slug: 'drs-roofing', url: 'https://drs-roofing-demo.pages.dev', expectedMin: '$15,000' },
    { slug: 'atlantic-roofing', url: 'https://atlantic-roofing-demo.pages.dev', expectedMin: '$15,000' },
  ],
  '1c': [
    { slug: 'allstate-roofing', url: 'https://allstate-roofing-demo.pages.dev', expectedMin: '$13,800' },
    { slug: 'right-way-roofing', url: 'https://right-way-roofing-demo.pages.dev', expectedMin: '$13,800' },
    { slug: 'gryphon-roofing', url: 'https://gryphon-roofing-demo.pages.dev', expectedMin: '$13,800' },
    { slug: 'reset-roofing', url: 'https://reset-roofing-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'atlanta-roofing-restoration', url: 'https://atlanta-roofing-restoration-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'ameristar-roofing', url: 'https://ameristar-roofing-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'evergreen-roofing', url: 'https://evergreen-roofing-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'advanced-roofing', url: 'https://advanced-roofing-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'horizon-roof-restoration', url: 'https://horizon-roof-restoration-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'academy-roofing', url: 'https://academy-roofing-demo.pages.dev', expectedMin: '$14,400' },
    { slug: 'wilson-brothers-roofing', url: 'https://wilson-brothers-roofing-demo.pages.dev', expectedMin: '$14,400' },
    { slug: 'family-roofing', url: 'https://family-roofing-demo.pages.dev', expectedMin: '$14,400' },
  ],
  '1d': [
    { slug: 'decker-roofing', url: 'https://decker-roofing-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'jm-melton-roofing', url: 'https://jm-melton-roofing-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'twin-hammers-roofing', url: 'https://twin-hammers-roofing-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'first-light-roofing', url: 'https://first-light-roofing-demo.pages.dev', expectedMin: '$15,000' },
    { slug: 'townsend-roofing', url: 'https://townsend-roofing-demo.pages.dev', expectedMin: '$15,000' },
    { slug: 'allegiance-roofing', url: 'https://allegiance-roofing-demo.pages.dev', expectedMin: '$15,000' },
    { slug: 'raleigh-residential-exteriors', url: 'https://raleigh-residential-exteriors-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'rex-construction', url: 'https://rex-construction-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'aceline-roofing', url: 'https://aceline-roofing-demo.pages.dev', expectedMin: '$12,600' },
    { slug: 'quality-rrc', url: 'https://quality-rrc-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'mr-goodroof', url: 'https://mr-goodroof-demo.pages.dev', expectedMin: '$13,200' },
    { slug: 'he-parmer', url: 'https://he-parmer-demo.pages.dev', expectedMin: '$13,200' },
  ],
};
const waveArgIdx = process.argv.indexOf('--wave');
const WAVE_KEY = waveArgIdx !== -1 && process.argv[waveArgIdx + 1] ? process.argv[waveArgIdx + 1].toLowerCase() : '1';
const TARGETS = WAVE_KEY === 'all' ? [...WAVES['1'], ...WAVES['1b'], ...WAVES['1c'], ...WAVES['1d']] : (WAVES[WAVE_KEY] || WAVES['1']);

const sleep = ms => new Promise(r => setTimeout(r, ms));

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
  }
  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', ev => {
      const msg = JSON.parse(String(ev.data));
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      } else if (msg.method) {
        for (const fn of this.listeners.get(msg.method) || []) fn(msg.params);
      }
    });
  }
  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(fn);
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const res = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (res.exceptionDetails) throw new Error('JS Eval Error: ' + JSON.stringify(res.exceptionDetails));
    return res.result?.value;
  }
  close() {
    try { this.ws.close(); } catch {}
  }
}

async function waitForDevTools(port, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (res.ok) {
        const list = await res.json();
        const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
        if (page) return page.webSocketDebuggerUrl;
      }
    } catch {}
    await sleep(250);
  }
  throw new Error('Timed out waiting for headless Chrome DevTools endpoint');
}

async function auditSite(cdp, target) {
  const result = {
    slug: target.slug,
    url: target.url,
    http_root: null,
    http_widget: null,
    console_errors: [],
    failed_requests: [],
    desktop: {},
    mobile: {},
  };

  // Direct HTTP 200 verification for / and /widget.js
  const rRoot = await fetch(target.url);
  result.http_root = rRoot.status;
  const rWidget = await fetch(`${target.url}/widget.js`);
  result.http_widget = rWidget.status;
  const widgetSize = (await rWidget.arrayBuffer()).byteLength;
  result.widget_live_bytes = widgetSize;

  let activeConsoleErrors = [];
  let activeFailedReqs = [];
  const reqMap = new Map();

  cdp.listeners.clear();
  cdp.on('Runtime.consoleAPICalled', p => {
    if (p.type === 'error') activeConsoleErrors.push(p.args?.map(a => a.value ?? a.description).join(' ') || 'console.error');
  });
  cdp.on('Runtime.exceptionThrown', p => {
    activeConsoleErrors.push(p.exceptionDetails?.text || 'Uncaught exception');
  });
  cdp.on('Network.requestWillBeSent', p => reqMap.set(p.requestId, p.request.url));
  cdp.on('Network.loadingFailed', p => {
    const u = reqMap.get(p.requestId) || p.requestId;
    if (!u.endsWith('/favicon.ico')) activeFailedReqs.push(`${u} (${p.errorText})`);
  });
  cdp.on('Network.responseReceived', p => {
    if (p.response.status >= 400 && !p.response.url.endsWith('/favicon.ico')) {
      activeFailedReqs.push(`${p.response.url} (HTTP ${p.response.status})`);
    }
  });

  async function navigateAndWait(url) {
    let loaded = false;
    const onLoad = () => { loaded = true; };
    cdp.on('Page.loadEventFired', onLoad);
    await cdp.send('Page.navigate', { url });
    const t0 = Date.now();
    while (!loaded && Date.now() - t0 < 15000) await sleep(100);
    await sleep(600);
  }

  // ---------- 1. DESKTOP (1440x900) ----------
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440, height: 900, deviceScaleFactor: 1, mobile: false,
  });
  await navigateAndWait(target.url);

  const deskMetrics = await cdp.eval(`(() => {
    const host = document.getElementById('trojan-quote-widget');
    const sr = host && host.shadowRoot;
    const card = sr && sr.querySelector('.card');
    const rect = card ? card.getBoundingClientRect() : null;
    return {
      title: document.title,
      shadowMounted: Boolean(sr && card),
      cardWidth: rect ? Math.round(rect.width) : 0,
      cardHeight: rect ? Math.round(rect.height) : 0,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      embedText: (document.getElementById('embed-snippet')?.textContent || '').trim()
    };
  })()`);

  const deskShot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  const deskPath = path.join(SHOT_DIR, `${target.slug}_desktop.png`);
  fs.writeFileSync(deskPath, Buffer.from(deskShot.data, 'base64'));
  result.desktop = { ...deskMetrics, screenshot: deskPath };

  // ---------- 2. MOBILE (390x844, iPhone scale) ----------
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 390, height: 844, deviceScaleFactor: 2, mobile: true,
  });
  await navigateAndWait(target.url);

  const mobStep1 = await cdp.eval(`(() => {
    const vp = document.querySelector('meta[name="viewport"]')?.getAttribute('content') || '';
    const host = document.getElementById('trojan-quote-widget');
    const sr = host && host.shadowRoot;
    const els = sr ? Array.from(sr.querySelectorAll('button, input')) : [];
    const clipped = els.filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && (r.left < -1 || r.right > 391);
    }).map(el => el.textContent?.trim() || el.id || el.tagName);
    return {
      viewport: vp,
      pinchZoomOk: vp.includes('width=device-width') && !vp.toLowerCase().includes('maximum-scale=1'),
      shadowMounted: Boolean(sr),
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflowStep1: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      clippedStep1: clipped,
      step1Text: sr?.querySelector('.pill')?.textContent?.trim() || ''
    };
  })()`);

  // Click through Steps 1 -> 2 -> 3 -> 4 in mobile viewport
  const flowCheck = await cdp.eval(`(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const sr = document.getElementById('trojan-quote-widget').shadowRoot;
    const stepsSeen = [];
    const overflows = [];
    const checkClip = () => Array.from(sr.querySelectorAll('button, input')).filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && (r.left < -1 || r.right > 391);
    }).length;

    // Step 1 -> 2
    sr.querySelector('[data-act="step"][data-val="2"]')?.click();
    await wait(120);
    stepsSeen.push(sr.querySelector('.pill')?.textContent?.trim());
    overflows.push({ step: 2, docOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth, clipped: checkClip() });

    // Select Storm on Step 2, go -> 3
    sr.querySelector('[data-act="cond"][data-val="storm"]')?.click();
    await wait(80);
    sr.querySelector('[data-act="step"][data-val="3"]')?.click();
    await wait(120);
    stepsSeen.push(sr.querySelector('.pill')?.textContent?.trim());
    overflows.push({ step: 3, docOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth, clipped: checkClip() });

    // Step 3 -> 4 (ungated reveal)
    sr.querySelector('[data-act="step"][data-val="4"]')?.click();
    await wait(600);
    stepsSeen.push(sr.querySelector('.pill')?.textContent?.trim());
    overflows.push({ step: 4, docOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth, clipped: checkClip() });

    return {
      stepsSeen,
      overflows,
      revealedPrice: sr.getElementById('rev-range')?.textContent?.trim() || '',
      revealedMonthly: sr.getElementById('rev-mo')?.textContent?.trim() || '',
      hasBookingForm: Boolean(sr.getElementById('lead-form')),
      hasStormBanner: Boolean(sr.querySelector('.storm'))
    };
  })()`);

  // Capture full-page mobile screenshot (on Step 4 showing live estimate reveal + 2-field form inside 390px)
  const mobShot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  const mobPath = path.join(SHOT_DIR, `${target.slug}_mobile.png`);
  fs.writeFileSync(mobPath, Buffer.from(mobShot.data, 'base64'));

  result.console_errors = activeConsoleErrors;
  result.failed_requests = activeFailedReqs;
  result.mobile = { ...mobStep1, ...flowCheck, screenshot: mobPath };
  result.passed = (
    result.http_root === 200 &&
    result.http_widget === 200 &&
    result.console_errors.length === 0 &&
    result.failed_requests.length === 0 &&
    result.desktop.shadowMounted &&
    !result.desktop.overflow &&
    result.mobile.pinchZoomOk &&
    !result.mobile.overflowStep1 &&
    result.mobile.clippedStep1.length === 0 &&
    result.mobile.stepsSeen.join('|') === 'Step 2 of 4|Step 3 of 4|Step 4 of 4' &&
    result.mobile.overflows.every(o => !o.docOverflow && o.clipped === 0) &&
    result.mobile.revealedPrice.includes(target.expectedMin) &&
    result.mobile.hasBookingForm
  );
  return result;
}

async function main() {
  const port = 9231;
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'agencia-cdp-'));
  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ], { stdio: 'ignore' });

  let cdp;
  try {
    const wsUrl = await waitForDevTools(port);
    cdp = new CDPClient(wsUrl);
    await cdp.connect();
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Network.enable');

    const report = [];
    for (const target of TARGETS) {
      const r = await auditSite(cdp, target);
      report.push(r);
      console.log(`\n[${r.passed ? 'PASS' : 'FAIL'}] ${r.slug} (${r.url})`);
      console.log(`  HTTP: /=${r.http_root}, /widget.js=${r.http_widget} (${r.widget_live_bytes} B) | ConsoleErr=${r.console_errors.length} | FailedNet=${r.failed_requests.length}`);
      console.log(`  Desktop 1440x900: shadow=${r.desktop.shadowMounted} card=${r.desktop.cardWidth}x${r.desktop.cardHeight} overflow=${r.desktop.overflow} (${r.desktop.scrollWidth}/${r.desktop.clientWidth}) -> ${r.desktop.screenshot}`);
      console.log(`  Mobile  390x844 : pinchZoom=${r.mobile.pinchZoomOk} overflowS1=${r.mobile.overflowStep1} (${r.mobile.scrollWidth}/${r.mobile.clientWidth}) clippedS1=${r.mobile.clippedStep1.length}`);
      console.log(`  Mobile Flow     : ${r.mobile.stepsSeen.join(' -> ')} | Price='${r.mobile.revealedPrice}' (${r.mobile.revealedMonthly}) | Form=${r.mobile.hasBookingForm} | Storm=${r.mobile.hasStormBanner} -> ${r.mobile.screenshot}`);
      if (r.console_errors.length) console.log('  Console Errors:', r.console_errors);
      if (r.failed_requests.length) console.log('  Failed Requests:', r.failed_requests);
    }

    const reportFile = WAVE_KEY === '1' ? 'visual_audit_report.json' : `visual_audit_wave${WAVE_KEY}_report.json`;
    const reportPath = path.join(SHOT_DIR, reportFile);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.log(`\nReport saved to: ${reportPath}`);
    if (!report.every(r => r.passed)) process.exitCode = 1;
  } finally {
    if (cdp) cdp.close();
    try { chrome.kill(); } catch {}
    await sleep(400);
    try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch {}
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
