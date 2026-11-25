/*!
* Trojan Horse White-Label Roofing Quote Widget (Zero-Dependency Shadow DOM Engine)
* Template: roofing-quote-calc | Mounts into #trojan-quote-widget or auto-creates after <script>
*/
((win, doc) => {
'use strict';
const DEFAULT_CONFIG = {"prospect_id":"roofing_houston_advantage-roofing","telemetry_endpoint":"https://forge-lead-router.forge-lead-studio.workers.dev/event","delivery_mode":"demo","brand_config":{"business_name":"Advantage Roofing","tagline":"3rd-Generation Family-Owned Houston Roofer \u00b7 Hand-Nailed Craftsmanship","primary_hex":"#CF2131","secondary_hex":"#CFBE9C","surface_hex":"#FAF8F4","text_hex":"#1A1A1A","cta_label":"Schedule Free Houston Inspection","phone_display":"(713) 609-9319"},"pricing_engine":{"currency":"USD","base_rates_per_sqft":{"architectural_shingle":{"min":5.75,"max":7.5,"label":"Hand-Nailed Wind-Rated Shingle"},"standing_seam_metal":{"min":11.75,"max":15.5,"label":"Gulf Coast Standing Seam Metal"},"designer_tile":{"min":14.0,"max":18.75,"label":"Coastal Concrete & Clay Tile"}},"story_multipliers":{"one_story":1.0,"two_story":1.12,"three_plus":1.25},"pitch_multipliers":{"low":0.95,"standard":1.0,"steep":1.18},"financing_apr_percent":9.99,"financing_term_months":120}};
const SCRIPT_EL = doc.currentScript;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const hexToRgb = hex => {
const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
return m ? `${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)}` : '186,155,90';
};
const isLight = hex => {
const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
return m ? (0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16)) > 155 : false;
};
const fmt = (n, cur) => `${cur === 'GBP' ? '\u00A3' : cur === 'CAD' ? 'CA$' : cur === 'AUD' ? 'A$' : '$'}${Math.round(n).toLocaleString('en-US')}`;
function calcEstimate(st, eng) {
const rate = eng.base_rates_per_sqft[st.material] || eng.base_rates_per_sqft.architectural_shingle;
const mult = (eng.story_multipliers[st.stories] || 1) * (eng.pitch_multipliers[st.pitch] || 1);
const min_usd = Math.round((st.sqft * rate.min * mult) / 100) * 100;
const max_usd = Math.round((st.sqft * rate.max * mult) / 100) * 100;
const apr = Number(eng.financing_apr_percent) || 0;
const term_months = Number(eng.financing_term_months) || 120;
const r = (apr / 100) / 12;
const monthly_min_usd = apr <= 0
? Math.round(min_usd / term_months)
: Math.round(min_usd * ((r * Math.pow(1 + r, term_months)) / (Math.pow(1 + r, term_months) - 1)));
return { min_usd, max_usd, monthly_min_usd, apr_percent: apr, term_months, currency: eng.currency || 'USD', material_label: rate.label };
}
function validateContact(val) {
const v = (val || '').trim();
if (/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return { ok: true, type: 'email' };
const d = v.replace(/\D/g, '');
return d.length >= 10 && d.length <= 15 ? { ok: true, type: 'phone' } : { ok: false, type: null };
}
const ICONS = {
roof: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5L12 4l9 7.5"/><path d="M5 10.5V20h14v-9.5"/></svg>',
s1: '<svg width="30" height="22" viewBox="0 0 36 26" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 13L18 4l15 9M7 12v11h22V12"/><rect x="15" y="16" width="6" height="7"/></svg>',
s2: '<svg width="30" height="22" viewBox="0 0 36 26" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 10L18 2l14 8M7 9v15h22V9M7 16h22"/><rect x="11" y="11" width="4" height="3"/><rect x="21" y="11" width="4" height="3"/></svg>',
s3: '<svg width="30" height="22" viewBox="0 0 36 26" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 7L18 1.5 30 7M8 7v17h20V7M8 12.5h20M8 18h20"/></svg>',
pLow: '<svg width="36" height="20" viewBox="0 0 40 22" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 17L20 10l17 7"/><line x1="3" y1="19" x2="37" y2="19" stroke-opacity=".35"/></svg>',
pStd: '<svg width="36" height="20" viewBox="0 0 40 22" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 18L20 6l17 12"/><line x1="3" y1="19" x2="37" y2="19" stroke-opacity=".35"/></svg>',
pStp: '<svg width="36" height="20" viewBox="0 0 40 22" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 19L20 2l14 17"/><line x1="3" y1="19" x2="37" y2="19" stroke-opacity=".35"/></svg>',
ok: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
};
const MAT_META = {
architectural_shingle: { short: 'Shingle', badge: 'Most Popular · Class 4 Hail', life: '25–30 yr lifespan · Best value' },
standing_seam_metal: { short: 'Metal', badge: 'Hail Tough · Energy Smart', life: '45–50+ yr lifespan · 24-gauge' },
designer_tile: { short: 'Tile', badge: 'Architectural Luxury', life: '50+ yr lifespan · Heat shield' }
};
const STORY_LBL = { one_story: '1-Story', two_story: '2-Story', three_plus: '3+ Stories' };
const PITCH_LBL = { low: 'Low Pitch', standard: 'Standard Pitch', steep: 'Steep Pitch' };
const COND_LBL = { routine: 'Routine Replacement', storm: 'Storm / Hail Damage', leak: 'Active Leak' };
function buildCss(b) {
const p = b.primary_hex || '#111111';
const s = b.secondary_hex || '#BA9B5A';
const sf = b.surface_hex || '#FAF8F0';
const ink = b.text_hex || '#151515';
const sa = (!isLight(p) && !isLight(s)) ? '#fff' : s;
const sar = (!isLight(p) && !isLight(s)) ? '255,255,255' : hexToRgb(s);
return `:host{all:initial;display:block;width:100%;max-width:560px;margin:0 auto;--p:${p};--s:${s};--sa:${sa};--sar:${sar};--sf:${sf};--ink:${ink};--pr:${hexToRgb(p)};--sr:${hexToRgb(s)};--op:${isLight(p) ? '#111' : '#fff'};--os:${isLight(s) ? '#111' : '#fff'};font-family:"Manrope",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
*,*::before,*::after{box-sizing:border-box}
.card{background:#fff;border:1px solid rgba(var(--pr),.12);border-radius:16px;overflow:hidden;box-shadow:0 20px 48px rgba(0,0,0,.12);max-width:100%}
.hd{background:var(--p);color:var(--op);padding:18px 22px 15px;border-bottom:2px solid var(--s)}
.hd-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.brand{display:flex;align-items:center;gap:10px;min-width:0;flex:1}
.mark{width:34px;height:34px;border-radius:9px;background:rgba(var(--sar),.16);border:1px solid var(--sa);display:flex;align-items:center;justify-content:center;color:var(--sa);flex-shrink:0}
.bname,.q,.sqft-val,.rev-price{font-family:"Barlow Condensed","Oswald","Arial Narrow",sans-serif}
.bname{font-size:20px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bsub{font-size:11px;opacity:.82;letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
.pill{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:5px 10px;border-radius:999px;background:rgba(var(--sar),.2);color:var(--sa);border:1px solid rgba(var(--sar),.48);white-space:nowrap;flex-shrink:0}
.track{height:4px;background:rgba(255,255,255,.18);border-radius:999px;margin-top:13px;overflow:hidden}
.fill{height:100%;background:var(--sa);border-radius:999px;transition:width .26s cubic-bezier(.22,1,.36,1)}
.body{padding:22px}
.pane{animation:fi .2s ease-out}
@keyframes fi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.q{font-size:24px;font-weight:700;line-height:1.15;margin:0 0 4px;color:var(--p)}
.sub{font-size:13px;color:#5a5a5a;margin:0 0 15px;line-height:1.45}
.lbl{display:block;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#444;margin:15px 0 8px}
.sbox{background:var(--sf);border:1px solid rgba(var(--pr),.1);border-radius:12px;padding:14px 16px}
.shead{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.sqft-val{font-size:32px;font-weight:800;color:var(--p);line-height:1}
.sunit{font-size:13px;font-weight:600;color:#5a5a5a;margin-left:4px}
.shint{font-size:11px;font-weight:700;color:var(--s);text-transform:uppercase;letter-spacing:.05em}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:7px;border-radius:999px;outline:none;cursor:pointer;background:#ddd8ce}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:24px;height:24px;border-radius:50%;background:var(--p);border:3px solid var(--s);box-shadow:0 2px 8px rgba(0,0,0,.25);cursor:pointer}
input[type=range]::-moz-range-thumb{width:24px;height:24px;border-radius:50%;background:var(--p);border:3px solid var(--s);box-shadow:0 2px 8px rgba(0,0,0,.25);cursor:pointer}
.presets{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:11px}
.pre,.win{appearance:none;border:1.5px solid #d8d5cd;background:#fff;color:var(--ink);border-radius:8px;padding:8px 5px;font:inherit;font-size:12px;font-weight:700;cursor:pointer;min-height:38px;transition:.14s}
.pre:hover,.win:hover{border-color:var(--s)}
.pre.on{background:var(--p);color:var(--op);border-color:var(--p);box-shadow:inset 0 0 0 1px var(--s)}
.win.on{border-color:var(--p);background:var(--sf);box-shadow:inset 0 0 0 1px var(--s)}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.g1{display:grid;grid-template-columns:1fr;gap:9px}
.opt{appearance:none;width:100%;background:#fff;border:1.5px solid #dfddd6;border-radius:12px;padding:12px 10px;cursor:pointer;font:inherit;color:var(--ink);transition:.15s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;min-height:44px}
.opt:hover,.opt.on{border-color:var(--s);background:var(--sf)}
.opt.on{border-color:var(--p);box-shadow:0 0 0 2px rgba(var(--sr),.45)}
.ico{color:var(--p);display:flex}
.opt.on .ico{color:var(--s)}
.ot{font-size:13px;font-weight:700;line-height:1.2;text-align:center}
.os{font-size:11px;color:#626262;line-height:1.25;text-align:center}
.row{flex-direction:row;justify-content:space-between;padding:13px 14px;gap:10px}
.row .ot,.row .os{text-align:left}
.bdg{font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:999px;background:rgba(var(--sr),.18);color:var(--p);border:1px solid rgba(var(--sr),.5);white-space:nowrap}
.opt.on .bdg{background:var(--s);color:var(--os);border-color:var(--s)}
.mmeta{font-size:11px;font-weight:700;color:#555;margin-top:2px}
.nav{display:flex;align-items:center;gap:10px;margin-top:16px}
.btn{appearance:none;border:0;border-radius:10px;padding:13px 16px;font:inherit;font-size:14px;font-weight:800;cursor:pointer;min-height:46px;display:inline-flex;align-items:center;justify-content:center;gap:6px;transition:.15s;text-decoration:none}
.bp{background:var(--p);color:var(--op);flex:1;box-shadow:0 6px 16px rgba(var(--pr),.22)}
.bg{background:var(--s);color:var(--os);flex:1;box-shadow:0 6px 16px rgba(var(--sr),.32)}
.bp:hover,.bg:hover{filter:brightness(1.06);transform:translateY(-1px)}
.bgh{background:transparent;color:#555;border:1px solid #d8d5cd;padding:12px 14px}
.bgh:hover{color:var(--p);border-color:var(--p)}
.rev{background:var(--p);color:var(--op);border-radius:14px;padding:18px;border:1.5px solid var(--sa)}
.rk{font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--sa);margin-bottom:6px;display:flex;justify-content:space-between;gap:8px}
.rk button{background:none;border:0;color:inherit;font:inherit;text-decoration:underline;cursor:pointer;padding:0;flex-shrink:0}
.rev-price{font-size:40px;font-weight:800;line-height:1.02}
.rfin{margin-top:9px;display:inline-flex;align-items:center;gap:6px;background:rgba(var(--sar),.18);border:1px solid rgba(var(--sar),.55);color:#fff;padding:6px 11px;border-radius:999px;font-size:13px;font-weight:700;flex-wrap:wrap}
.rfin strong{color:var(--sa)}
.rnote{font-size:11px;opacity:.72;margin-top:8px;line-height:1.35}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-size:11px;background:rgba(255,255,255,.1);color:rgba(255,255,255,.92);padding:4px 8px;border-radius:6px}
.mtabs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:11px;padding-top:11px;border-top:1px solid rgba(255,255,255,.14)}
.mtab{appearance:none;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.06);color:rgba(255,255,255,.88);border-radius:8px;padding:7px 5px;font:inherit;font-size:11px;font-weight:700;cursor:pointer;min-height:36px}
.mtab.on{background:var(--s);color:var(--os);border-color:var(--s)}
.storm{margin-top:11px;background:var(--sf);border-left:3px solid var(--s);padding:10px 12px;border-radius:0 8px 8px 0;font-size:12px;line-height:1.4}
.fbox{margin-top:15px;padding-top:15px;border-top:1px solid #e6e3dc}
.fh{font-size:15px;font-weight:800;margin:0 0 3px;color:var(--p)}
.fs{font-size:12px;color:#5a5a5a;margin:0 0 11px}
.flds{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.fld label{display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#444;margin-bottom:4px}
.inp{width:100%;min-height:44px;padding:10px 12px;border:1.5px solid #d5d2ca;border-radius:9px;font:inherit;font-size:14px;color:var(--ink);background:#fff;outline:none}
.inp:focus{border-color:var(--s);box-shadow:0 0 0 3px rgba(var(--sr),.22)}
.inp.err{border-color:#b42318}
.emsg{color:#b42318;font-size:12px;font-weight:600;margin:8px 0 0;min-height:16px}
.prow{text-align:center;margin-top:9px;font-size:12px;color:#5a5a5a}
.prow a{color:var(--p);font-weight:800;text-decoration:none;border-bottom:1px solid var(--s)}
.okb{text-align:center;padding:6px 2px}
.oki{width:52px;height:52px;border-radius:50%;background:rgba(var(--sr),.2);border:2px solid var(--s);color:var(--p);display:flex;align-items:center;justify-content:center;margin:0 auto 10px}
.okref{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;padding:4px 10px;border-radius:999px;background:var(--sf);border:1px solid var(--s);color:var(--p);margin-bottom:8px}
.oksum{text-align:left;background:var(--sf);border:1px solid #e4e0d5;border-radius:12px;padding:13px;margin:13px 0;font-size:13px;line-height:1.5}
.oksum div{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px dashed rgba(0,0,0,.08)}
.oksum div:last-child{border-bottom:0}
.oksum span:first-child{color:#5a5a5a}
.oksum span:last-child{font-weight:700;text-align:right}
.ft{background:var(--sf);padding:10px 22px;border-top:1px solid rgba(var(--pr),.08);display:flex;justify-content:space-between;gap:8px;font-size:11px;color:#5a5a5a}
@media(max-width:480px){.body{padding:16px}.flds,.g3{grid-template-columns:1fr}.presets{grid-template-columns:repeat(2,1fr)}.rev-price{font-size:34px}.ft{flex-direction:column;text-align:center}}`;
}
function mount(cfg, targetEl) {
if (!cfg || !cfg.brand_config || !cfg.pricing_engine) return null;
let host = targetEl || doc.getElementById('trojan-quote-widget') || doc.querySelector('[data-trojan-quote-widget]');
if (!host) {
host = doc.createElement('div');
host.id = 'trojan-quote-widget';
if (SCRIPT_EL && SCRIPT_EL.parentNode) SCRIPT_EL.parentNode.insertBefore(host, SCRIPT_EL.nextSibling);
else if (doc.body) doc.body.appendChild(host);
else return null;
}
if (host.shadowRoot) return host.shadowRoot;
const shadow = host.attachShadow({ mode: 'open' });
const brand = cfg.brand_config;
const eng = cfg.pricing_engine;
const telUrl = cfg.telemetry_endpoint || (host.dataset && host.dataset.telemetryEndpoint) || '';
const delMode = cfg.delivery_mode || (host.dataset && host.dataset.deliveryMode) || 'demo';
const ping = (type, step, pl) => {
if (!telUrl) return;
const body = JSON.stringify({ prospect_id: cfg.prospect_id || 'roofing-quote-calc', event_type: type, step, mode: delMode, payload: pl, ts: new Date().toISOString() });
try {
if (type !== 'lead_captured' && typeof navigator !== 'undefined' && navigator.sendBeacon) {
navigator.sendBeacon(telUrl, new Blob([body], { type: 'application/json' }));
return;
}
if (typeof fetch === 'function') {
fetch(telUrl, { method: 'POST', headers: { 'content-type': 'application/json' }, body, keepalive: true }).catch(() => {});
}
} catch {}
};
const phoneHref = 'tel:' + String(brand.phone_display || '').replace(/[^\d+]/g, '');
const st = {
step: 1, sqft: 2400, stories: 'one_story', pitch: 'standard', condition: 'routine',
material: 'architectural_shingle', name: '', contact: '', windowPref: 'Morning (8am–12pm)',
error: '', submitted: null, raf: 0
};
const styleEl = doc.createElement('style');
styleEl.textContent = buildCss(brand);
const root = doc.createElement('div');
shadow.append(styleEl, root);
const paintSlider = sl => {
if (!sl) return;
const pct = ((Number(sl.value) - 1200) / 3300) * 100;
sl.style.background = `linear-gradient(90deg,${brand.secondary_hex} 0%,${brand.secondary_hex} ${pct}%,#ddd8ce ${pct}%,#ddd8ce 100%)`;
};
function animateEst(est) {
if (st.raf) cancelAnimationFrame(st.raf);
const rEl = shadow.getElementById('rev-range');
const mEl = shadow.getElementById('rev-mo');
const t0 = performance.now();
const tick = now => {
const t = Math.min(1, (now - t0) / 420);
const k = 0.72 + 0.28 * (1 - Math.pow(1 - t, 3));
if (rEl) rEl.textContent = `${fmt(est.min_usd * k, est.currency)} – ${fmt(est.max_usd * k, est.currency)}`;
if (mEl) mEl.textContent = `${fmt(est.monthly_min_usd * k, est.currency)}/mo`;
if (t < 1) st.raf = requestAnimationFrame(tick);
};
st.raf = requestAnimationFrame(tick);
}
const optBtn = (act, val, on, cls, inner) => `<button type="button" role="radio" aria-checked="${on}" class="${cls}${on ? ' on' : ''}" data-act="${act}" data-val="${esc(val)}">${inner}</button>`;
function stepHtml() {
if (st.step === 1) {
const pre = [[1600, '1,600 sq ft'], [2400, '2,400 sq ft'], [3200, '3,200 sq ft'], [4200, '4,200+ sq ft']];
const stories = [['one_story', '1-Story', 'Ranch / Single', ICONS.s1], ['two_story', '2-Story', 'Standard 2-Level', ICONS.s2], ['three_plus', '3+ Stories', 'Tall / Multi-Level', ICONS.s3]];
return `<div class="pane"><h2 class="q">Tell us about your property</h2><p class="sub">Slide or tap your approximate roof footprint for an instant local ballpark.</p><div class="sbox"><div class="shead"><div><span class="sqft-val" id="sqft-read">${st.sqft.toLocaleString('en-US')}${st.sqft >= 4500 ? '+' : ''}</span><span class="sunit">sq. ft.</span></div><span class="shint">Approx. Roof Area</span></div><input id="sqft-slider" type="range" min="1200" max="4500" step="100" value="${st.sqft}" aria-label="Approximate roof square footage"><div class="presets">${pre.map(([v, l]) => `<button type="button" class="pre${st.sqft === v ? ' on' : ''}" data-act="sqft" data-val="${v}">${l}</button>`).join('')}</div></div><span class="lbl">Number of Stories</span><div class="g3" role="radiogroup" aria-label="Number of stories">${stories.map(([k, t, s, i]) => optBtn('story', k, st.stories === k, 'opt', `<span class="ico">${i}</span><span class="ot">${t}</span><span class="os">${s}</span>`)).join('')}</div><div class="nav"><button type="button" class="btn bp" data-act="step" data-val="2">Continue to Roof Details &rarr;</button></div></div>`;
}
if (st.step === 2) {
const pitches = [['low', 'Low Pitch', '2/12 – 4/12', ICONS.pLow], ['standard', 'Standard', '5/12 – 7/12', ICONS.pStd], ['steep', 'Steep Pitch', '8/12+ Slope', ICONS.pStp]];
const conds = [['routine', 'Routine Replacement', 'Aging roof (15+ yrs) or planning ahead', 'Retail / Finance'], ['storm', 'Storm / Hail Damage', 'Recent wind or hail event in your area', 'Insurance Check'], ['leak', 'Active Leak / Urgent', 'Water spots or missing shingles', 'Priority Slot']];
return `<div class="pane"><h2 class="q">Roof slope &amp; current condition</h2><p class="sub">Pitch and storm condition help calibrate labor staging and claim eligibility.</p><span class="lbl" style="margin-top:0">Roof Pitch</span><div class="g3" role="radiogroup" aria-label="Roof pitch">${pitches.map(([k, t, s, i]) => optBtn('pitch', k, st.pitch === k, 'opt', `<span class="ico">${i}</span><span class="ot">${t}</span><span class="os">${s}</span>`)).join('')}</div><span class="lbl">Current Condition / Urgency</span><div class="g1" role="radiogroup" aria-label="Roof condition">${conds.map(([k, t, s, b]) => optBtn('cond', k, st.condition === k, 'opt row', `<div><div class="ot">${t}</div><div class="os">${s}</div></div><span class="bdg">${b}</span>`)).join('')}</div><div class="nav"><button type="button" class="btn bgh" data-act="step" data-val="1">&larr; Back</button><button type="button" class="btn bp" data-act="step" data-val="3">Choose Roof Material &rarr;</button></div></div>`;
}
if (st.step === 3) {
const keys = ['architectural_shingle', 'standing_seam_metal', 'designer_tile'];
return `<div class="pane"><h2 class="q">Select your roofing system</h2><p class="sub">All ranges include full tear-off, synthetic underlayment, installation, and cleanup.</p><div class="g1" role="radiogroup" aria-label="Roofing material">${keys.map(k => {
const r = eng.base_rates_per_sqft[k], m = MAT_META[k] || { badge: 'Installed', life: '' };
return r ? optBtn('mat', k, st.material === k, 'opt row', `<div><div class="ot">${esc(r.label)}</div><div class="os">${esc(m.life)}</div><div class="mmeta">Local avg: ${fmt(r.min, eng.currency)} – ${fmt(r.max, eng.currency)} / sq. ft.</div></div><span class="bdg">${esc(m.badge)}</span>`) : '';
}).join('')}</div><div class="nav"><button type="button" class="btn bgh" data-act="step" data-val="2">&larr; Back</button><button type="button" class="btn bg" data-act="step" data-val="4">Reveal My Instant Estimate &rarr;</button></div></div>`;
}
const est = calcEstimate(st, eng);
if (st.submitted) {
const s = st.submitted;
return `<div class="pane okb"><div class="oki">${ICONS.ok}</div><span class="okref">Inspection Request #${esc(s.reference_id)}</span><h2 class="q">You're on the Priority Schedule, ${esc(s.lead.full_name.split(' ')[0])}!</h2><p class="sub">A local ${esc(brand.business_name)} advisor will confirm your <strong>${esc(s.lead.preferred_window)}</strong> roof inspection shortly.</p><div class="oksum"><div><span>Roofing System</span><span>${esc(s.estimate.material_label)}</span></div><div><span>Property Specs</span><span>${s.roof_profile.sqft.toLocaleString('en-US')} sq ft · ${STORY_LBL[s.roof_profile.stories]} · ${PITCH_LBL[s.roof_profile.pitch]}</span></div><div><span>Instant Ballpark</span><span>${fmt(s.estimate.min_usd, s.estimate.currency)} – ${fmt(s.estimate.max_usd, s.estimate.currency)}</span></div><div><span>Est. Financing</span><span>From ${fmt(s.estimate.monthly_min_usd, s.estimate.currency)}/mo</span></div><div><span>Contact Saved</span><span>${esc(s.lead.contact)}</span></div></div><div class="nav"><button type="button" class="btn bgh" data-act="reset">Run Another Estimate</button><a class="btn bp" href="${esc(phoneHref)}">Call ${esc(brand.phone_display)}</a></div></div>`;
}
const keys = ['architectural_shingle', 'standing_seam_metal', 'designer_tile'];
const wins = ['Morning (8am–12pm)', 'Afternoon (12pm–5pm)', 'ASAP / Storm Urgent'];
return `<div class="pane"><div class="rev"><div class="rk"><span>Instant Estimate · ${esc(est.material_label)}</span><button type="button" data-act="step" data-val="1">Edit Specs</button></div><div class="rev-price" id="rev-range">${fmt(est.min_usd, est.currency)} – ${fmt(est.max_usd, est.currency)}</div><div class="rfin">Est. from <strong id="rev-mo">${fmt(est.monthly_min_usd, est.currency)}/mo</strong> with Roof Financing</div><div class="chips"><span class="chip">${st.sqft.toLocaleString('en-US')} sq ft</span><span class="chip">${STORY_LBL[st.stories]}</span><span class="chip">${PITCH_LBL[st.pitch]}</span><span class="chip">${COND_LBL[st.condition]}</span></div><div class="mtabs" aria-label="Compare material tiers">${keys.map(k => `<button type="button" class="mtab${st.material === k ? ' on' : ''}" data-act="swap" data-val="${k}">${MAT_META[k].short}</button>`).join('')}</div><div class="rnote">Ballpark based on local installed averages &amp; ${est.apr_percent}% APR / ${est.term_months} mos (subject to credit approval). Exact quote confirmed on-site.</div></div>
${st.condition !== 'routine' ? '<div class="storm"><strong>Storm / Leak Priority:</strong> Qualifying storm damage may be covered by your homeowner policy minus deductible. We provide photo documentation free.</div>' : ''}
<form class="fbox" id="lead-form" novalidate><h3 class="fh">Lock in your exact written quote — free inspection</h3><p class="fs">No pressure, no obligation. Two quick details so we can confirm your time.</p><div class="flds"><div class="fld"><label for="f-name">Full Name</label><input id="f-name" class="inp${st.error && st.name.trim().length < 2 ? ' err' : ''}" type="text" autocomplete="name" placeholder="Jordan Ramirez" value="${esc(st.name)}" required></div><div class="fld"><label for="f-contact">Mobile Phone or Email</label><input id="f-contact" class="inp${st.error && !validateContact(st.contact).ok ? ' err' : ''}" type="text" autocomplete="tel" placeholder="(512) 555-0192 or email" value="${esc(st.contact)}" required></div></div><span class="lbl" style="margin-top:11px">Preferred Inspection Window</span><div class="g3" role="radiogroup" aria-label="Preferred inspection window">${wins.map(w => optBtn('win', w, st.windowPref === w, 'win', esc(w))).join('')}</div><div class="emsg" role="alert">${esc(st.error)}</div><div class="nav" style="margin-top:10px"><button type="button" class="btn bgh" data-act="step" data-val="3">&larr; Back</button><button type="submit" class="btn bg">${esc(brand.cta_label || 'Lock In Free Roof Inspection')}</button></div><div class="prow">Prefer to talk now? Call <a href="${esc(phoneHref)}">${esc(brand.phone_display)}</a></div></form></div>`;
}
function render(animate) {
root.innerHTML = `<div class="card" role="region" aria-label="${esc(brand.business_name)} Instant Roof Quote Estimator"><div class="hd"><div class="hd-top"><div class="brand"><div class="mark" aria-hidden="true">${ICONS.roof}</div><div style="min-width:0"><div class="bname">${esc(brand.business_name)}</div><div class="bsub">Instant Roof &amp; Financing Estimator</div></div></div><span class="pill">${st.submitted ? 'Confirmed' : `Step ${st.step} of 4`}</span></div><div class="track" aria-hidden="true"><div class="fill" style="width:${st.step * 25}%"></div></div></div><div class="body">${stepHtml()}</div><div class="ft"><span>${esc(brand.tagline)}</span><span>100% Free · No Credit Pull</span></div></div>`;
paintSlider(shadow.getElementById('sqft-slider'));
if (st.step === 4 && !st.submitted && animate) animateEst(calcEstimate(st, eng));
}
root.addEventListener('input', e => {
const t = e.target;
if (t.id === 'sqft-slider') {
st.sqft = Number(t.value);
const rd = shadow.getElementById('sqft-read');
if (rd) rd.textContent = st.sqft.toLocaleString('en-US') + (st.sqft >= 4500 ? '+' : '');
paintSlider(t);
shadow.querySelectorAll('[data-act="sqft"]').forEach(b => b.classList.toggle('on', Number(b.dataset.val) === st.sqft));
} else if (t.id === 'f-name') st.name = t.value;
else if (t.id === 'f-contact') st.contact = t.value;
});
root.addEventListener('click', e => {
const btn = e.target.closest('[data-act]');
if (!btn) return;
const { act, val } = btn.dataset;
if (act === 'sqft') { st.sqft = Number(val); render(false); }
else if (act === 'story') { st.stories = val; render(false); }
else if (act === 'pitch') { st.pitch = val; render(false); }
else if (act === 'cond') { st.condition = val; if (val !== 'routine') st.windowPref = 'ASAP / Storm Urgent'; render(false); }
else if (act === 'mat') { st.material = val; render(false); }
else if (act === 'swap') { st.material = val; render(true); }
else if (act === 'win') { st.windowPref = val; render(false); }
else if (act === 'step') { st.error = ''; st.step = Number(val); ping('step', st.step); render(st.step === 4); }
else if (act === 'reset') { st.step = 1; st.submitted = null; st.error = ''; render(false); }
});
root.addEventListener('submit', e => {
if (e.target.id !== 'lead-form') return;
e.preventDefault();
const nm = st.name.trim(), ct = validateContact(st.contact);
if (nm.length < 2) { st.error = 'Please enter your full name so our advisor knows who to ask for.'; render(false); shadow.getElementById('f-name')?.focus(); return; }
if (!ct.ok) { st.error = 'Please enter a valid 10-digit phone number or email address.'; render(false); shadow.getElementById('f-contact')?.focus(); return; }
st.error = '';
const pfx = (brand.business_name.match(/\b[A-Za-z]/g) || ['R', 'Q']).slice(0, 2).join('').toUpperCase();
const payload = {
reference_id: pfx + '-' + Math.floor(1000 + Math.random() * 9000),
prospect_id: cfg.prospect_id || 'roofing-quote-calc',
business_name: brand.business_name,
captured_at: new Date().toISOString(),
lead: { full_name: nm, contact: st.contact.trim(), contact_type: ct.type, preferred_window: st.windowPref },
roof_profile: { sqft: st.sqft, stories: st.stories, pitch: st.pitch, condition: st.condition, material: st.material },
estimate: calcEstimate(st, eng)
};
st.submitted = payload;
ping('lead_captured', 4, payload);
win.dispatchEvent(new CustomEvent('trojan:lead_captured', { detail: payload }));
render(false);
});
render(false);
ping('view', 1);
return shadow;
}
win.TrojanRoofCalc = { mount, calculate: calcEstimate };
if (DEFAULT_CONFIG) {
if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', () => mount(DEFAULT_CONFIG));
else mount(DEFAULT_CONFIG);
}
})(window, document);
