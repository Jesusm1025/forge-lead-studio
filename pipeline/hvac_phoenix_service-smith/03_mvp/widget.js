/*!
* Trojan Horse White-Label HVAC Replacement Quote Widget (Zero-Dependency Shadow DOM Engine)
* Template: hvac-quote-calc | Mounts into #trojan-quote-widget or auto-creates after <script>
*/
((win, doc) => {
'use strict';
const DEFAULT_CONFIG = {"prospect_id":"hvac_phoenix_service-smith","vertical":"hvac","telemetry_endpoint":"https://forge-lead-router.forge-lead-studio.workers.dev/event","delivery_mode":"demo","brand_config":{"business_name":"Service Smith, L.L.C.","tagline":"Honest Phoenix HVAC Replacements & Diagnostics \u00b7 Locally Owned","primary_hex":"#1B365D","secondary_hex":"#D96838","surface_hex":"#F8FAFC","text_hex":"#132238","cta_label":"Schedule Free Phoenix HVAC Estimate","phone_display":"(480) 478-6425"},"pricing_engine":{"currency":"USD","base_system_prices":{"ac_gas_furnace":{"min":10200,"max":14800,"label":"Central AC + Gas Furnace"},"heat_pump":{"min":10600,"max":15400,"label":"Desert High-Efficiency Heat Pump"},"ac_coil_only":{"min":7600,"max":11200,"label":"AC Condenser & Coil Only"},"ductless_minisplit":{"min":8200,"max":12400,"label":"Ductless Mini-Split System"}},"tonnage_multipliers":{"under_1500":0.85,"1500_2200":1.0,"2200_3000":1.18,"over_3000":1.42},"seer2_multipliers":{"standard_seer2":0.88,"high_seer2":1.0,"variable_seer2":1.24},"ductwork_adder":{"min":1800,"max":3200},"financing_apr_percent":9.99,"financing_term_months":120}};
const SCRIPT_EL = doc.currentScript;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const hexToRgb = hex => {
const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
return m ? `${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)}` : '14,165,233';
};
const isLight = hex => {
const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
return m ? (0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16)) > 155 : false;
};
const fmt = (n, cur) => `${cur === 'GBP' ? '\u00A3' : cur === 'CAD' ? 'CA$' : cur === 'AUD' ? 'A$' : '$'}${Math.round(n).toLocaleString('en-US')}`;
function calcEstimate(st, eng) {
const sys = eng.base_system_prices[st.systemType] || eng.base_system_prices.ac_gas_furnace;
const tMult = Number(eng.tonnage_multipliers[st.homeSize]) || 1;
const sMult = Number(eng.seer2_multipliers[st.seerTier]) || 1;
const duct = st.ductwork === 'needs_mod' ? (eng.ductwork_adder || { min: 1800, max: 3200 }) : { min: 0, max: 0 };
const min_usd = Math.round(((sys.min * tMult * sMult) + duct.min) / 100) * 100;
const max_usd = Math.round(((sys.max * tMult * sMult) + duct.max) / 100) * 100;
const apr = Number(eng.financing_apr_percent) || 0;
const term_months = Number(eng.financing_term_months) || 120;
const r = (apr / 100) / 12;
const monthly_min_usd = apr <= 0
? Math.round(min_usd / term_months)
: Math.round(min_usd * ((r * Math.pow(1 + r, term_months)) / (Math.pow(1 + r, term_months) - 1)));
return {
min_usd,
max_usd,
monthly_min_usd,
apr_percent: apr,
term_months,
currency: eng.currency || 'USD',
material_label: `${sys.label} (${SEER_SHORT[st.seerTier] || 'SEER2'})`,
system_label: sys.label
};
}
function validateContact(val) {
const v = (val || '').trim();
if (/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return { ok: true, type: 'email' };
const d = v.replace(/\D/g, '');
return d.length >= 10 && d.length <= 15 ? { ok: true, type: 'phone' } : { ok: false, type: null };
}
const ICONS = {
hvac: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48 2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48 2.83-2.83"/></svg>',
home: '<svg width="24" height="20" viewBox="0 0 28 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12L14 3l11 9M6 10.5V21h16V10.5"/><rect x="11" y="14" width="6" height="7"/></svg>',
ac: '<svg width="24" height="20" viewBox="0 0 28 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="22" height="16" rx="2"/><circle cx="11" cy="12" r="4.5"/><path d="M19 8h3M19 12h3M19 16h3"/></svg>',
hp: '<svg width="24" height="20" viewBox="0 0 28 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3v18M8 7l6-4 6 4M8 17l6 4 6-4M4 12h20"/></svg>',
mini: '<svg width="24" height="20" viewBox="0 0 28 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="22" height="9" rx="2"/><path d="M6 11h16M8 18c1-1.5 2-1.5 3 0M14 18c1-1.5 2-1.5 3 0M20 18c1-1.5 2-1.5 3 0"/></svg>',
ok: '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
};
const SIZE_META = {
under_1500: { title: '< 1,500 sq ft', sub: '2 – 2.5 Ton System', sqft: 1300 },
'1500_2200': { title: '1,500 – 2,200 sq ft', sub: '3 – 3.5 Ton System', sqft: 1900 },
'2200_3000': { title: '2,200 – 3,000 sq ft', sub: '4 Ton System', sqft: 2600 },
over_3000: { title: '3,000+ sq ft', sub: '5 Ton / Dual Zone', sqft: 3500 }
};
const SYS_META = {
ac_gas_furnace: { desc: 'Complete split cooling & gas heating package', badge: 'Full System', icon: ICONS.ac },
heat_pump: { desc: 'All-electric cooling + efficient winter heating', badge: 'Rebate Eligible', icon: ICONS.hp },
ac_coil_only: { desc: 'Outdoor condenser + matching indoor coil swap', badge: 'Fast Install', icon: ICONS.ac },
ductless_minisplit: { desc: 'Whisper-quiet zoned inverter comfort, no ducts', badge: 'Multi-Zone', icon: ICONS.mini }
};
const SEER_META = {
standard_seer2: { title: 'Standard 14.3–15.2 SEER2', desc: 'Code-compliant single-stage reliability · Lowest upfront', badge: 'Best Value' },
high_seer2: { title: 'High-Efficiency 16–18 SEER2', desc: 'Two-stage humidity control · Strong utility savings', badge: 'Most Popular' },
variable_seer2: { title: 'Variable-Speed 19+ SEER2', desc: 'Inverter precision comfort · Whisper-quiet + max rebates', badge: 'Premium Tier' }
};
const SEER_SHORT = { standard_seer2: '14–15 SEER2', high_seer2: '16–18 SEER2', variable_seer2: '19+ SEER2' };
const DUCT_LBL = { ok: 'Existing Ductwork OK', needs_mod: 'Needs Ductwork Mod' };
function buildCss(b) {
const p = b.primary_hex || '#0F2A47';
const s = b.secondary_hex || '#0EA5E9';
const sf = b.surface_hex || '#F4F8FC';
const ink = b.text_hex || '#142030';
const sa = (!isLight(p) && !isLight(s)) ? '#fff' : s;
const sar = (!isLight(p) && !isLight(s)) ? '255,255,255' : hexToRgb(s);
return `:host{all:initial;display:block;width:100%;max-width:560px;margin:0 auto;--p:${p};--s:${s};--sa:${sa};--sar:${sar};--sf:${sf};--ink:${ink};--pr:${hexToRgb(p)};--sr:${hexToRgb(s)};--op:${isLight(p) ? '#111' : '#fff'};--os:${isLight(s) ? '#111' : '#fff'};font-family:"Manrope",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
*,*::before,*::after{box-sizing:border-box}
.card{background:#fff;border:1px solid rgba(var(--pr),.12);border-radius:16px;overflow:hidden;box-shadow:0 20px 48px rgba(0,0,0,.12);max-width:100%}
.hd{background:var(--p);color:var(--op);padding:18px 22px 15px;border-bottom:2px solid var(--s)}
.hd-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.brand{display:flex;align-items:center;gap:10px;min-width:0;flex:1}
.mark{width:34px;height:34px;border-radius:9px;background:rgba(var(--sar),.16);border:1px solid var(--sa);display:flex;align-items:center;justify-content:center;color:var(--sa);flex-shrink:0}
.bname,.q,.rev-price{font-family:"Barlow Condensed","Oswald","Arial Narrow",sans-serif}
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
.g2{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.g1{display:grid;grid-template-columns:1fr;gap:9px}
.opt{appearance:none;width:100%;background:#fff;border:1.5px solid #dfddd6;border-radius:12px;padding:12px 11px;cursor:pointer;font:inherit;color:var(--ink);transition:.15s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:44px}
.opt:hover,.opt.on{border-color:var(--s);background:var(--sf)}
.opt.on{border-color:var(--p);box-shadow:0 0 0 2px rgba(var(--sr),.42)}
.ico{color:var(--p);display:flex;flex-shrink:0}
.opt.on .ico{color:var(--s)}
.ot{font-size:13px;font-weight:700;line-height:1.2;text-align:center}
.os{font-size:11px;color:#626262;line-height:1.25;text-align:center}
.row{flex-direction:row;justify-content:space-between;align-items:center;padding:12px 13px;gap:10px}
.row-l{display:flex;align-items:center;gap:10px;min-width:0}
.row .ot,.row .os{text-align:left}
.bdg{font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:999px;background:rgba(var(--sr),.18);color:var(--p);border:1px solid rgba(var(--sr),.48);white-space:nowrap;flex-shrink:0}
.opt.on .bdg{background:var(--s);color:var(--os);border-color:var(--s)}
.win{appearance:none;border:1.5px solid #d8d5cd;background:#fff;color:var(--ink);border-radius:8px;padding:8px 5px;font:inherit;font-size:12px;font-weight:700;cursor:pointer;min-height:38px;transition:.14s}
.win:hover{border-color:var(--s)}
.win.on{border-color:var(--p);background:var(--sf);box-shadow:inset 0 0 0 1px var(--s)}
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
.rnote{font-size:11px;opacity:.75;margin-top:8px;line-height:1.35}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-size:11px;background:rgba(255,255,255,.11);color:rgba(255,255,255,.94);padding:4px 8px;border-radius:6px}
.mtabs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:11px;padding-top:11px;border-top:1px solid rgba(255,255,255,.14)}
.mtab{appearance:none;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.06);color:rgba(255,255,255,.88);border-radius:8px;padding:7px 4px;font:inherit;font-size:11px;font-weight:700;cursor:pointer;min-height:36px}
.mtab.on{background:var(--s);color:var(--os);border-color:var(--s)}
.rebate{margin-top:11px;background:var(--sf);border-left:3px solid var(--s);padding:10px 12px;border-radius:0 8px 8px 0;font-size:12px;line-height:1.4}
.fbox{margin-top:15px;padding-top:15px;border-top:1px solid #e6e3dc}
.fh{font-size:15px;font-weight:800;margin:0 0 3px;color:var(--p)}
.fs{font-size:12px;color:#5a5a5a;margin:0 0 11px}
.flds{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.fld-full{grid-column:1 / -1}
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
@media(max-width:480px){.body{padding:16px}.flds,.g2,.g3{grid-template-columns:1fr}.rev-price{font-size:34px}.ft{flex-direction:column;text-align:center}}`;
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
const body = JSON.stringify({ prospect_id: cfg.prospect_id || 'hvac-quote-calc', event_type: type, step, mode: delMode, payload: pl, ts: new Date().toISOString() });
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
step: 1,
homeSize: '1500_2200',
systemType: 'ac_gas_furnace',
seerTier: 'high_seer2',
ductwork: 'ok',
name: '',
contact: '',
address: '',
windowPref: 'Morning (8am–12pm)',
error: '',
submitted: null,
raf: 0
};
const styleEl = doc.createElement('style');
styleEl.textContent = buildCss(brand);
const root = doc.createElement('div');
shadow.append(styleEl, root);
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
const sizes = ['under_1500', '1500_2200', '2200_3000', 'over_3000'];
return `<div class="pane"><h2 class="q">Home size &amp; cooling tonnage</h2><p class="sub">Select your approximate conditioned living space for proper tonnage sizing.</p><div class="g2" role="radiogroup" aria-label="Home square footage and tonnage">${sizes.map(k => {
const m = SIZE_META[k];
return optBtn('size', k, st.homeSize === k, 'opt', `<span class="ico">${ICONS.home}</span><span class="ot">${m.title}</span><span class="os">${m.sub}</span>`);
}).join('')}</div><div class="nav"><button type="button" class="btn bp" data-act="step" data-val="2">Choose System Type &rarr;</button></div></div>`;
}
if (st.step === 2) {
const systems = ['ac_gas_furnace', 'heat_pump', 'ac_coil_only', 'ductless_minisplit'];
return `<div class="pane"><h2 class="q">Select your HVAC system type</h2><p class="sub">Every turnkey range includes removal, new pad/whip, permits, start-up, and warranty.</p><div class="g1" role="radiogroup" aria-label="HVAC system type">${systems.map(k => {
const p = eng.base_system_prices[k], m = SYS_META[k];
return p ? optBtn('sys', k, st.systemType === k, 'opt row', `<div class="row-l"><span class="ico">${m.icon}</span><div><div class="ot">${esc(p.label)}</div><div class="os">${esc(m.desc)}</div></div></div><span class="bdg">${esc(m.badge)}</span>`) : '';
}).join('')}</div><div class="nav"><button type="button" class="btn bgh" data-act="step" data-val="1">&larr; Back</button><button type="button" class="btn bp" data-act="step" data-val="3">Efficiency &amp; Ductwork &rarr;</button></div></div>`;
}
if (st.step === 3) {
const tiers = ['standard_seer2', 'high_seer2', 'variable_seer2'];
const ducts = [['ok', 'Existing Ductwork OK', 'Reuse current supply & return trunk'], ['needs_mod', 'Needs Ductwork Modification', 'Plenum, transitions, or airflow upgrades']];
return `<div class="pane"><h2 class="q">SEER2 efficiency &amp; ductwork</h2><p class="sub">Higher SEER2 tiers cut summer electric bills and unlock federal/utility rebates.</p><div class="g1" role="radiogroup" aria-label="SEER2 efficiency tier">${tiers.map(k => {
const m = SEER_META[k];
return optBtn('seer', k, st.seerTier === k, 'opt row', `<div><div class="ot">${m.title}</div><div class="os">${m.desc}</div></div><span class="bdg">${m.badge}</span>`);
}).join('')}</div><span class="lbl">Ductwork Condition</span><div class="g2" role="radiogroup" aria-label="Ductwork condition">${ducts.map(([k, t, s]) => optBtn('duct', k, st.ductwork === k, 'opt', `<span class="ot">${t}</span><span class="os">${s}</span>`)).join('')}</div><div class="nav"><button type="button" class="btn bgh" data-act="step" data-val="2">&larr; Back</button><button type="button" class="btn bg" data-act="step" data-val="4">Reveal My Instant Quote &rarr;</button></div></div>`;
}
const est = calcEstimate(st, eng);
if (st.submitted) {
const s = st.submitted;
return `<div class="pane okb"><div class="oki">${ICONS.ok}</div><span class="okref">Comfort Estimate #${esc(s.reference_id)}</span><h2 class="q">You're on the Priority Schedule, ${esc(s.lead.full_name.split(' ')[0])}!</h2><p class="sub">A local ${esc(brand.business_name)} comfort advisor will confirm your <strong>${esc(s.lead.preferred_window)}</strong> Manual-J load evaluation shortly.</p><div class="oksum"><div><span>HVAC System</span><span>${esc(s.estimate.material_label)}</span></div><div><span>Home Sizing</span><span>${esc(s.hvac_profile.home_size_label)} · ${esc(s.hvac_profile.tonnage_label)}</span></div><div><span>Ductwork</span><span>${esc(DUCT_LBL[s.hvac_profile.ductwork])}</span></div><div><span>Instant Ballpark</span><span>${fmt(s.estimate.min_usd, s.estimate.currency)} – ${fmt(s.estimate.max_usd, s.estimate.currency)}</span></div><div><span>Est. Financing</span><span>From ${fmt(s.estimate.monthly_min_usd, s.estimate.currency)}/mo</span></div><div><span>Address &amp; Contact</span><span>${esc(s.lead.address || 'On file')} · ${esc(s.lead.contact)}</span></div></div><div class="nav"><button type="button" class="btn bgh" data-act="reset">Run Another Quote</button><a class="btn bp" href="${esc(phoneHref)}">Call ${esc(brand.phone_display)}</a></div></div>`;
}
const tiers = ['standard_seer2', 'high_seer2', 'variable_seer2'];
const wins = ['Morning (8am–12pm)', 'Afternoon (12pm–5pm)', 'Urgent / No AC'];
const sm = SIZE_META[st.homeSize] || SIZE_META['1500_2200'];
return `<div class="pane"><div class="rev"><div class="rk"><span>Turnkey Ballpark · ${esc(est.system_label)}</span><button type="button" data-act="step" data-val="1">Edit Specs</button></div><div class="rev-price" id="rev-range">${fmt(est.min_usd, est.currency)} – ${fmt(est.max_usd, est.currency)}</div><div class="rfin">Est. from <strong id="rev-mo">${fmt(est.monthly_min_usd, est.currency)}/mo</strong> with HVAC Financing</div><div class="chips"><span class="chip">${sm.title}</span><span class="chip">${sm.sub}</span><span class="chip">${SEER_SHORT[st.seerTier]}</span><span class="chip">${DUCT_LBL[st.ductwork]}</span></div><div class="mtabs" aria-label="Compare SEER2 tiers">${tiers.map(k => `<button type="button" class="mtab${st.seerTier === k ? ' on' : ''}" data-act="swap" data-val="${k}">${SEER_SHORT[k]}</button>`).join('')}</div><div class="rnote">Turnkey ballpark based on local installed averages &amp; ${est.apr_percent}% APR / ${est.term_months} mos (subject to credit approval). Final quote confirmed after on-site Manual-J load check.</div></div>
${(st.systemType === 'heat_pump' || st.seerTier !== 'standard_seer2') ? '<div class="rebate"><strong>Rebate &amp; Tax Credit Alert:</strong> Qualifying high-efficiency SEER2 &amp; heat pump upgrades may qualify for up to $2,000 in federal 25C tax credits plus local utility rebates.</div>' : ''}
<form class="fbox" id="lead-form" novalidate><h3 class="fh">Lock in your exact written quote — free in-home load check</h3><p class="fs">No obligation. Share your details so our comfort advisor can confirm your time.</p><div class="flds"><div class="fld"><label for="f-name">Full Name</label><input id="f-name" class="inp${st.error && st.name.trim().length < 2 ? ' err' : ''}" type="text" autocomplete="name" placeholder="Jordan Ramirez" value="${esc(st.name)}" required></div><div class="fld"><label for="f-contact">Mobile Phone or Email</label><input id="f-contact" class="inp${st.error && !validateContact(st.contact).ok ? ' err' : ''}" type="text" autocomplete="tel" placeholder="(480) 555-0192 or email" value="${esc(st.contact)}" required></div><div class="fld fld-full"><label for="f-address">Street Address</label><input id="f-address" class="inp${st.error && st.address.trim().length < 4 ? ' err' : ''}" type="text" autocomplete="street-address" placeholder="1420 Oakridge Dr, Unit / ZIP" value="${esc(st.address)}" required></div></div><span class="lbl" style="margin-top:11px">Preferred Visit Window</span><div class="g3" role="radiogroup" aria-label="Preferred visit window">${wins.map(w => optBtn('win', w, st.windowPref === w, 'win', esc(w))).join('')}</div><div class="emsg" role="alert">${esc(st.error)}</div><div class="nav" style="margin-top:10px"><button type="button" class="btn bgh" data-act="step" data-val="3">&larr; Back</button><button type="submit" class="btn bg">${esc(brand.cta_label || 'Lock In Free HVAC Estimate')}</button></div><div class="prow">Need cooling urgently? Call <a href="${esc(phoneHref)}">${esc(brand.phone_display)}</a></div></form></div>`;
}
function render(animate) {
root.innerHTML = `<div class="card" role="region" aria-label="${esc(brand.business_name)} Instant HVAC Replacement Estimator"><div class="hd"><div class="hd-top"><div class="brand"><div class="mark" aria-hidden="true">${ICONS.hvac}</div><div style="min-width:0"><div class="bname">${esc(brand.business_name)}</div><div class="bsub">Instant HVAC &amp; SEER2 Quote Estimator</div></div></div><span class="pill">${st.submitted ? 'Confirmed' : `Step ${st.step} of 4`}</span></div><div class="track" aria-hidden="true"><div class="fill" style="width:${st.step * 25}%"></div></div></div><div class="body">${stepHtml()}</div><div class="ft"><span>${esc(brand.tagline)}</span><span>100% Free · No Credit Pull</span></div></div>`;
if (st.step === 4 && !st.submitted && animate) animateEst(calcEstimate(st, eng));
}
root.addEventListener('input', e => {
const t = e.target;
if (t.id === 'f-name') st.name = t.value;
else if (t.id === 'f-contact') st.contact = t.value;
else if (t.id === 'f-address') st.address = t.value;
});
root.addEventListener('click', e => {
const btn = e.target.closest('[data-act]');
if (!btn) return;
const { act, val } = btn.dataset;
if (act === 'size') { st.homeSize = val; render(false); }
else if (act === 'sys') { st.systemType = val; render(false); }
else if (act === 'seer') { st.seerTier = val; render(false); }
else if (act === 'duct') { st.ductwork = val; render(false); }
else if (act === 'swap') { st.seerTier = val; render(true); }
else if (act === 'win') { st.windowPref = val; render(false); }
else if (act === 'step') { st.error = ''; st.step = Number(val); ping('step', st.step); render(st.step === 4); }
else if (act === 'reset') { st.step = 1; st.submitted = null; st.error = ''; render(false); }
});
root.addEventListener('submit', e => {
if (e.target.id !== 'lead-form') return;
e.preventDefault();
const nm = st.name.trim(), ct = validateContact(st.contact), addr = st.address.trim();
if (nm.length < 2) { st.error = 'Please enter your full name so our advisor knows who to ask for.'; render(false); shadow.getElementById('f-name')?.focus(); return; }
if (!ct.ok) { st.error = 'Please enter a valid 10-digit phone number or email address.'; render(false); shadow.getElementById('f-contact')?.focus(); return; }
if (addr.length < 4) { st.error = 'Please enter your street address so we can verify equipment sizing.'; render(false); shadow.getElementById('f-address')?.focus(); return; }
st.error = '';
const pfx = (brand.business_name.match(/\b[A-Za-z]/g) || ['H', 'V']).slice(0, 2).join('').toUpperCase();
const sm = SIZE_META[st.homeSize] || SIZE_META['1500_2200'];
const payload = {
reference_id: pfx + '-' + Math.floor(1000 + Math.random() * 9000),
prospect_id: cfg.prospect_id || 'hvac-quote-calc',
vertical: 'hvac',
business_name: brand.business_name,
captured_at: new Date().toISOString(),
lead: { full_name: nm, contact: st.contact.trim(), contact_type: ct.type, address: addr, preferred_window: st.windowPref },
hvac_profile: { home_size: st.homeSize, home_size_label: sm.title, tonnage_label: sm.sub, sqft: sm.sqft, system_type: st.systemType, seer_tier: st.seerTier, ductwork: st.ductwork },
roof_profile: { sqft: sm.sqft, material: st.systemType },
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
win.TrojanHvacCalc = { mount, calculate: calcEstimate };
win.TrojanQuoteCalc = win.TrojanHvacCalc;
if (DEFAULT_CONFIG) {
if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', () => mount(DEFAULT_CONFIG));
else mount(DEFAULT_CONFIG);
}
})(window, document);
