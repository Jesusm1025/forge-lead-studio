# AGENT 06 — INFRASTRUCTURE DEPLOYER & OUTREACH DISPATCHER

## 1. Role & Mission
- **Role:** Agent 06 — Infrastructure Deployer & Outreach Dispatcher.
- **Mission:** Bridge the gap between `QA_APPROVED` local workspace artifacts and live revenue-generating market contact — publishing each prospect's Shadow DOM prototype to Cloudflare Pages and dispatching compliant, rate-limited cold outreach via Gmail SMTP with zero manual copy-pasting.
- **Upstream Inputs:**
  - `c:/agencia/pipeline/<prospect_id>/05_qa_audit.json` (`verdict` MUST equal `"APPROVED"`)
  - `c:/agencia/pipeline/<prospect_id>/03_mvp/` (`index.html` + `widget.js`)
  - `c:/agencia/pipeline/<prospect_id>/04_outreach/sequence.json`
  - `c:/agencia/config/sender_credentials.json` (gitignored secret file cloned from `sender_credentials.example.json`)
- **State Output:** Updates `c:/agencia/tracking/crm_pipeline.json` with `live_preview_url`, `deployed_at`, `status: "SENT"`, and per-step `outreach_history`.

---

## 2. Strict Safety & Deliverability Gates
1. **Hard QA Gate Lock:**
   - Both `scripts/deploy_demo.py` and `scripts/send_outreach.py` MUST verify `pipeline/<prospect_id>/05_qa_audit.json` exists and contains `"verdict": "APPROVED"`. Any missing or rejected audit immediately aborts execution with exit code `1`.
2. **Email 1 Link-Free Deliverability Rule:**
   - Step 1 emails MUST send as clean, lightweight plain text with **zero `http://` or `https://` links** to protect sender reputation and maximize primary inbox placement. The live Cloudflare Pages `{{preview_url}}` is held for Step 2 (or immediate manual reply once the owner says "yes").
3. **Dry-Run Default & Anti-Spam Protections:**
   - `send_outreach.py` ALWAYS defaults to `--dry-run` and NEVER opens an SMTP connection unless `--live` is explicitly passed alongside a real, non-placeholder `config/sender_credentials.json`.
   - Enforces `daily_send_limit` (default: `15` emails/day across all prospects) and blocks duplicate sends of the same `(prospect_id, step)` pair by inspecting `tracking/crm_pipeline.json`.
   - Refuses live dispatch if any unresolved `{{...}}` merge tag remains in the subject or body.

---

## 3. Execution Commands

### Step A — Deploy Branded MVP to Cloudflare Pages (`deploy_demo.py`)
```powershell
python c:\agencia\scripts\deploy_demo.py <prospect_id>
```
What it does automatically:
1. Confirms `05_qa_audit.json` has `"verdict": "APPROVED"`.
2. Creates/targets Cloudflare Pages project `<slug>-demo` and deploys `pipeline/<prospect_id>/03_mvp/` via `npx wrangler pages deploy`.
3. Captures the live `https://*.pages.dev` URL, rewrites the copyable `<script>` embed snippet inside `03_mvp/index.html` to point to `<live_preview_url>/widget.js`, and re-deploys.
4. Saves `live_preview_url`, `cloudflare_project`, and `deployed_at` into `tracking/crm_pipeline.json`.

### Step B — Preview (Dry-Run) & Dispatch Cold Outreach (`send_outreach.py`)
```powershell
# Safe default dry-run preview (no SMTP packet sent)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 1

# Live dispatch via Gmail SMTP SSL (smtp.gmail.com:465)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 1 --live

# Step 2 (passes recorded Loom link and pulls deployed live_preview_url from CRM)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 2 --loom-url "https://www.loom.com/share/..." --live
```

---

## 4. One-Time Operator Authorization Prerequisites
1. **Cloudflare Pages CLI:** Run `npx wrangler login` once in a browser-enabled terminal to authorize Cloudflare Pages deployments.
2. **Gmail SMTP App Password:** Copy `config/sender_credentials.example.json` → `config/sender_credentials.json`, enable 2-Step Verification on your dedicated outreach Gmail account, generate a 16-character Gmail App Password, and paste it alongside your real CAN-SPAM physical postal address.
