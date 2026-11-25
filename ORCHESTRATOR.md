# MASTER ORCHESTRATOR — AUTONOMOUS B2B "TROJAN HORSE" DIGITAL AGENCY

This document defines the end-to-end 6-agent assembly line, strict JSON contracts, CRM state machine, and repeatable batch execution protocol operating inside `c:/agencia/`.

---

## 1. End-to-End 6-Agent Assembly Line

```text
[Agent 01: Scout]      ──► 01_dossier.json + 01_audit_notes.md
       │                          (Status: SCOUTED)
       ▼
[Agent 02: Architect]  ──► 02_spec.json
       │                          (Status: ARCHITECTED)
       ▼
[Agent 03: Builder]    ──► templates/<base>/ ──► 03_mvp/widget.js (<30KB) + index.html
       │                          (Status: BUILT)
       ▼
[Agent 04: Closer]     ──► 04_outreach/sequence.json + copy_pack.md + objections.md
       │                          (Status: OUTREACH_READY)
       ▼
[Agent 05: QA Gate]    ──► 05_qa_audit.json + 05_qa_report.md
       │                          (Status: QA_APPROVED | QA_REJECTED)
       ▼
[Agent 06: Dispatcher] ──► Cloudflare Pages deploy (deploy_demo.py)
       │               ──► Gmail SMTP SSL dispatch (send_outreach.py)
       │                          (Status: SENT -> REPLIED -> CLOSED)
       ▼
[Human Founder]        ──► Handle Replies, Demo Calls & Retainer Onboarding
```

---

## 2. Agent Registry & Strict Data Contracts

| Stage | Agent SOP | Input Contract | Output / Action | Validating Gate | CRM Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `agents/01-scout.md` | Target niche & metro (`config/agency_config.json`) | `pipeline/<id>/01_dossier.json` + `01_audit_notes.md` | `schemas/01_prospect_dossier.schema.json` | `SCOUTED` |
| **02** | `agents/02-architect.md` | `01_dossier.json` + `01_audit_notes.md` | `pipeline/<id>/02_spec.json` | `schemas/02_solution_spec.schema.json` | `ARCHITECTED` |
| **03** | `agents/03-builder.md` | `02_spec.json` + `templates/<template_base>/` | `pipeline/<id>/03_mvp/widget.js` + `index.html` | `<30KB`, Shadow DOM, 0 CDN | `BUILT` |
| **04** | `agents/04-closer.md` | `01_dossier.json` + `02_spec.json` + `03_mvp/` | `pipeline/<id>/04_outreach/sequence.json`, `copy_pack.md`, `objections.md` | `schemas/04_outreach_sequence.schema.json` | `OUTREACH_READY` |
| **05** | `agents/05-qa-auditor.md` | All Stage 01–04 artifacts | `pipeline/<id>/05_qa_audit.json` + `05_qa_report.md` | `schemas/05_qa_audit.schema.json` + `scripts/qa_gate.py` | `QA_APPROVED` / `QA_REJECTED` |
| **06** | `agents/06-dispatcher.md` | `05_qa_audit.json` (`APPROVED`), `03_mvp/`, `04_outreach/`, `config/sender_credentials.json` | Live `https://*.pages.dev` preview + live `widget.js` embed + Gmail SMTP SSL dispatch | Hard QA lock, Email 1 link-free rule, daily quota & anti-duplicate guard | `SENT` → `REPLIED` → `CLOSED` |

---

## 3. Canonical Merge-Tag Standard (Outreach Assets)
All outreach templates and sequences MUST use only these standardized merge tags so automated QA (`scripts/qa_gate.py`) and dispatch (`scripts/send_outreach.py`) operate deterministically:
- `{{sender_name}}` — Human founder display name (`config/sender_credentials.json`)
- `{{sender_address}}` — Valid physical business postal address (`config/sender_credentials.json`)
- `{{unsubscribe_line}}` — Clear plain-text opt-out line (default built into `send_outreach.py`)
- `{{preview_url}}` — Live Cloudflare Pages HTTPS URL saved automatically by `scripts/deploy_demo.py`
- `{{loom_url}}` — Recorded 60-second Loom video walkthrough link (`--loom-url`)

---

## 4. Repeatable Single-Command Build, QA & Dispatch Protocol

### A. Hydrate Any Architected Prospect (`Agent 03`)
```powershell
python c:\agencia\templates\roofing-quote-calc\hydrate.py `
  c:\agencia\pipeline\<prospect_id>\02_spec.json `
  c:\agencia\pipeline\<prospect_id>\03_mvp
```

### B. Run Deterministic 5-Point Pre-Flight QA Gate (`Agent 05`)
```powershell
python c:\agencia\scripts\qa_gate.py <prospect_id>
```

### C. Deploy Live Preview to Cloudflare Pages (`Agent 06`)
```powershell
# Safe preview check
python c:\agencia\scripts\deploy_demo.py <prospect_id> --dry-run

# Live Cloudflare Pages deploy + embed snippet auto-patch + CRM update
python c:\agencia\scripts\deploy_demo.py <prospect_id>
```

### D. Dry-Run & Dispatch Cold Outreach via Gmail SMTP SSL (`Agent 06`)
```powershell
# Default --dry-run preview (verifies QA gate, merge tags, link-free Step 1 rule & quota)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 1

# Live Step 1 send (zero external links for maximum inbox deliverability)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 1 --live

# Live Step 2 send (injects live_preview_url from CRM + recorded Loom link)
python c:\agencia\scripts\send_outreach.py <prospect_id> --step 2 --loom-url "https://www.loom.com/share/..." --live
```

### E. Batch Hydrate + QA Across Multiple Prospects
```powershell
foreach ($id in @('roofing_austin_roof-royale', 'roofing_austin_austin-roofing-company', 'roofing_tampa_buddys-roofing')) {
  if (Test-Path "c:\agencia\pipeline\$id\02_spec.json") {
    python c:\agencia\templates\roofing-quote-calc\hydrate.py "c:\agencia\pipeline\$id\02_spec.json" "c:\agencia\pipeline\$id\03_mvp"
  }
  if (Test-Path "c:\agencia\pipeline\$id\04_outreach\sequence.json") {
    python c:\agencia\scripts\qa_gate.py $id
  }
}
```

---

## 5. Single-Prompt Autonomous Run Protocol (Operator Command)
To run a new or already-scouted prospect autonomously through Stages 01–05 and ready for Stage 06 dispatch:

> **Prompt Template:**  
> *"Execute `ORCHESTRATOR.md` end-to-end for `<prospect_id>` (or scout N new `<niche>` prospects in `<city, state>`). Advance sequentially through Agents 01 -> 02 -> 03 -> 04 -> 05, validate every JSON artifact against `schemas/`, run `scripts/qa_gate.py`, update `tracking/crm_pipeline.json`, and run `scripts/send_outreach.py <prospect_id> --step 1` in dry-run mode ready for my `--live` go-ahead."*

---

## 6. Scaling Beyond Wave 1 (Multi-Niche SaaS Productization)
1. **Complete Wave 1 Queue:** Promote the remaining two already-scouted Wave 1 roofers (`roofing_austin_austin-roofing-company` and `roofing_tampa_buddys-roofing`) through Agents 02 → 06 using `templates/roofing-quote-calc/`.
2. **Wave 2 Niche Expansion:** Clone `templates/roofing-quote-calc/` into:
   - `templates/hvac-replacement-calc/` (Good/Better/Best SEER2 + federal/utility rebate estimator)
   - `templates/remodeling-budget-planner/` (Kitchen/Bath/Deck scope & tire-kicker budget qualifier)
3. **Paid Client Webhook Routing:** Connect `trojan:lead_captured` to a Cloudflare Worker / Make / Zapier webhook for live SMS + CRM routing included in the monthly retainer.
