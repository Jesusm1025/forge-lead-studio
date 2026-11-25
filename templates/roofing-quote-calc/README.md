# White-Label Template: `roofing-quote-calc`

Reusable, zero-dependency, Shadow DOM 4-step **Instant Roof Replacement & Financing Estimator** engineered for high-ticket residential and commercial roofing contractors.

## Architecture
- **`template.js`** — Parameterized ES6+ Shadow DOM widget engine (`<30 KB`, zero frameworks, zero external CDN calls). Decouples `brand_config` from `pricing_engine`.
- **`preview_shell.html`** — Branded executive demo wrapper with copyable 1-line embed bar, conversion upgrade callouts, and a live `trojan:lead_captured` CRM payload inspector.
- **`hydrate.py`** — Zero-dependency Python hydrator that compiles any validated `02_spec.json` into a prospect's self-contained `03_mvp/widget.js` and `03_mvp/index.html`.

## Hydrating a New Prospect
```powershell
python c:\agencia\templates\roofing-quote-calc\hydrate.py `
  c:\agencia\pipeline\<prospect_id>\02_spec.json `
  c:\agencia\pipeline\<prospect_id>\03_mvp
```

## 1-Line Drop-In Client Installation (WordPress, Wix, Squarespace, Webflow, Next.js)
Place this single snippet anywhere on the client's homepage or landing page (or omit the `<div>` and the script auto-mounts directly beneath itself):

```html
<div id="trojan-quote-widget"></div>
<script src="https://widgets.trojanagency.com/<client-slug>/widget.js" defer></script>
```

## CRM / Webhook Lead Routing Hook
Every completed booking dispatches a standard browser `CustomEvent` containing full roof qualification specs and calculated estimate ranges:

```js
window.addEventListener('trojan:lead_captured', (event) => {
  const leadPayload = event.detail;
  // Route leadPayload to GoHighLevel, HubSpot, AccuLynx, JobNimbus, Zapier, or SMS webhook
  fetch('https://your-crm-webhook.example/roof-lead', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(leadPayload)
  });
});
```
