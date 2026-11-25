import argparse
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_DIR = os.path.join(ROOT, "pipeline")
CRM_PATH = os.path.join(ROOT, "tracking", "crm_pipeline.json")
CREDS_PATH = os.path.join(ROOT, "config", "sender_credentials.json")
EXAMPLE_CREDS_PATH = os.path.join(ROOT, "config", "sender_credentials.example.json")
DEFAULT_TELEMETRY_URL = "https://forge-lead-router.forge-lead-studio.workers.dev"

DEFAULT_UNSUBSCRIBE = "Reply 'no' and I won't email you again."


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def verify_qa_approved(prospect_id: str) -> dict:
    audit_path = os.path.join(PIPELINE_DIR, prospect_id, "05_qa_audit.json")
    if not os.path.exists(audit_path):
        raise SystemExit(
            f"[BLOCKED] QA Gate Lock: missing {audit_path}. Run scripts/qa_gate.py {prospect_id} first."
        )
    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)
    if audit.get("verdict") != "APPROVED":
        raise SystemExit(
            f"[BLOCKED] QA Gate Lock: {prospect_id} verdict is '{audit.get('verdict')}' (must be APPROVED)."
        )
    return audit


def load_credentials(live_mode: bool) -> tuple[dict, bool]:
    if os.path.exists(CREDS_PATH):
        with open(CREDS_PATH, encoding="utf-8") as f:
            creds = json.load(f)
        using_example = False
    elif (os.environ.get("SENDER_CREDENTIALS_JSON") or "").strip():
        try:
            creds = json.loads(os.environ["SENDER_CREDENTIALS_JSON"].strip())
        except json.JSONDecodeError as ex:
            raise SystemExit(f"[BLOCKED] Invalid JSON in SENDER_CREDENTIALS_JSON env var: {ex}")
        using_example = False
    elif (os.environ.get("GMAIL_USER") or os.environ.get("SENDER_EMAIL")) and os.environ.get("GMAIL_APP_PASSWORD"):
        creds = {
            "sender_name": (os.environ.get("SENDER_NAME") or "Forge Lead Studio").strip(),
            "sender_email": (os.environ.get("GMAIL_USER") or os.environ.get("SENDER_EMAIL") or "").strip(),
            "gmail_app_password": os.environ["GMAIL_APP_PASSWORD"].strip(),
            "sender_physical_address": (os.environ.get("SENDER_PHYSICAL_ADDRESS") or "Forge Lead Studio").strip(),
            "daily_send_limit": int(os.environ.get("DAILY_SEND_LIMIT") or 15),
            "telemetry_worker_url": (os.environ.get("TELEMETRY_WORKER_URL") or DEFAULT_TELEMETRY_URL).strip(),
            "telemetry_admin_key": (os.environ.get("TELEMETRY_ADMIN_KEY") or "").strip(),
        }
        using_example = False
    elif not live_mode and os.path.exists(EXAMPLE_CREDS_PATH):
        with open(EXAMPLE_CREDS_PATH, encoding="utf-8") as f:
            creds = json.load(f)
        using_example = True
    else:
        raise SystemExit(
            f"[BLOCKED] Missing {CREDS_PATH} and no cloud secret env vars found. "
            "Provide config/sender_credentials.json locally or set SENDER_CREDENTIALS_JSON in GitHub Actions Secrets."
        )

    creds.setdefault("daily_send_limit", 15)
    creds.setdefault("sender_name", "Forge Lead Studio")
    creds.setdefault("sender_physical_address", creds["sender_name"])

    required_keys = [
        "sender_name",
        "sender_email",
        "gmail_app_password",
        "sender_physical_address",
        "daily_send_limit",
    ]
    missing = [k for k in required_keys if not creds.get(k)]
    if missing:
        raise SystemExit(f"[BLOCKED] Incomplete sender credentials; missing keys: {missing}")

    if live_mode:
        placeholders = ("your full name", "your-outreach-account@gmail.com", "xxxx xxxx xxxx xxxx", "123 main st")
        low_blob = json.dumps(creds).lower()
        if any(ph in low_blob for ph in placeholders):
            raise SystemExit(
                "[BLOCKED] Refusing --live send: sender credentials still contain example placeholder values."
            )
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", creds["sender_email"].strip()):
            raise SystemExit(f"[BLOCKED] Invalid sender_email: {creds['sender_email']}")

    return creds, using_example


def count_sent_today(crm: dict, today_str: str) -> int:
    total = 0
    for p in crm.get("prospects", []):
        for entry in p.get("outreach_history", []):
            if entry.get("date_utc") == today_str:
                total += 1
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Agent 06 — Send QA-approved B2B cold outreach via Gmail SMTP SSL (defaults to --dry-run)."
    )
    parser.add_argument("prospect_id", help="Prospect slug (e.g., roofing_austin_roof-royale)")
    parser.add_argument("--step", type=int, required=True, choices=[1, 2, 3, 4], help="Email sequence step (1–4)")
    parser.add_argument("--variant", choices=["a", "b"], default="a", help="Subject line A/B variant (default: a)")
    parser.add_argument("--loom-url", default="", help="Optional recorded 60-second Loom share URL")
    parser.add_argument("--allow-no-loom", action="store_true", help="Gracefully omit optional Loom video line if loom_url is not yet recorded")
    parser.add_argument("--dry-run", action="store_true", help="Preview resolved SMTP payload without sending (default)")
    parser.add_argument("--live", action="store_true", help="Explicitly transmit email via smtp.gmail.com:465 SSL")
    parser.add_argument("--force", action="store_true", help="Override duplicate-step guard (not recommended)")
    args = parser.parse_args()

    live_mode = bool(args.live) and not bool(args.dry_run)

    # 1. QA Gate Lock
    audit = verify_qa_approved(args.prospect_id)

    # 2. Load CRM, Dossier, Outreach Sequence, and Credentials
    pdir = os.path.join(PIPELINE_DIR, args.prospect_id)
    with open(os.path.join(pdir, "01_dossier.json"), encoding="utf-8") as f:
        dossier = json.load(f)
    with open(os.path.join(pdir, "04_outreach", "sequence.json"), encoding="utf-8") as f:
        seq = json.load(f)
    with open(CRM_PATH, encoding="utf-8") as f:
        crm = json.load(f)

    prospect = next((p for p in crm.get("prospects", []) if p.get("prospect_id") == args.prospect_id), None)
    if not prospect:
        raise SystemExit(f"[ERROR] Prospect '{args.prospect_id}' not found in {CRM_PATH}")

    recipient = (dossier.get("contact_info", {}).get("email") or "").strip()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", recipient):
        raise SystemExit(f"[BLOCKED] No valid public recipient email in 01_dossier.json: '{recipient}'")

    email_item = next((e for e in seq.get("emails", []) if e.get("step") == args.step), None)
    if not email_item:
        raise SystemExit(f"[ERROR] Step {args.step} not found in 04_outreach/sequence.json")

    creds, using_example = load_credentials(live_mode=live_mode)

    # 3. Duplicate Send & Daily Send Limit Guards
    history = prospect.get("outreach_history", [])
    already_sent = any(h.get("step") == args.step for h in history)
    if already_sent and not args.force:
        raise SystemExit(
            f"[BLOCKED] Duplicate guard: Step {args.step} was already sent to {args.prospect_id} ({recipient})."
        )

    today_str = utc_today()
    sent_today = count_sent_today(crm, today_str)
    daily_limit = int(creds.get("daily_send_limit", 15))
    if live_mode and sent_today >= daily_limit:
        raise SystemExit(
            f"[BLOCKED] Daily send limit reached ({sent_today}/{daily_limit} sent on {today_str} UTC)."
        )

    # 4. Merge-Tag Resolution
    preview_url = (prospect.get("live_preview_url") or "").strip()
    loom_url = (args.loom_url or prospect.get("loom_url") or "").strip()
    unsubscribe_line = (creds.get("unsubscribe_line") or DEFAULT_UNSUBSCRIBE).strip()

    subject_key = "subject_line_a" if args.variant == "a" else "subject_line_b"
    raw_subject = email_item[subject_key]
    raw_body = email_item["body_text"]

    needs_preview = "{{preview_url}}" in raw_body or "{{preview_url}}" in raw_subject
    needs_loom = "{{loom_url}}" in raw_body or "{{loom_url}}" in raw_subject

    if live_mode and needs_preview and not preview_url:
        raise SystemExit(
            f"[BLOCKED] Step {args.step} requires {{{{preview_url}}}} but live_preview_url is not set. "
            f"Run: python c:/agencia/scripts/deploy_demo.py {args.prospect_id}"
        )
    if needs_loom and not loom_url:
        if args.allow_no_loom:
            # Cleanly remove optional Loom walkthrough mention & line while keeping the live Cloudflare demo front-and-center
            raw_body = re.sub(r"\r?\n60-sec video:\s*\{\{loom_url\}\}", "", raw_body, flags=re.I)
            raw_body = re.sub(r"\s+(?:along with|plus)\s+a\s+(?:quick\s+)?60-second\s+walkthrough", "", raw_body, flags=re.I)
            needs_loom = False
        elif live_mode:
            raise SystemExit(
                f"[BLOCKED] Step {args.step} requires {{{{loom_url}}}}. Pass --loom-url \"https://www.loom.com/share/...\" (or --allow-no-loom for demo-only autopilot)"
            )

    replacements = {
        "{{sender_name}}": creds["sender_name"].strip(),
        "{{sender_address}}": creds["sender_physical_address"].strip(),
        "{{unsubscribe_line}}": unsubscribe_line,
        "{{preview_url}}": preview_url or "[PENDING — run scripts/deploy_demo.py first]",
        "{{loom_url}}": loom_url or "[PENDING — pass --loom-url]",
    }

    resolved_subject = raw_subject
    resolved_body = raw_body
    for tag, val in replacements.items():
        resolved_subject = resolved_subject.replace(tag, val)
        resolved_body = resolved_body.replace(tag, val)

    unresolved = sorted(set(re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", resolved_subject + "\n" + resolved_body)))
    if unresolved:
        raise SystemExit(f"[BLOCKED] Unresolved merge tags remaining: {unresolved}")

    # 5. Strict Email 1 Link-Free Deliverability Gate
    links_found = re.findall(r"https?://\S+", resolved_subject + "\n" + resolved_body, flags=re.I)
    if args.step == 1 and links_found:
        raise SystemExit(
            f"[BLOCKED] Email 1 Link-Free Rule violated — external links detected in Step 1: {links_found}"
        )

    # 6. Build RFC-5322 Plain-Text EmailMessage
    msg = EmailMessage()
    msg["From"] = formataddr((creds["sender_name"].strip(), creds["sender_email"].strip()))
    msg["To"] = recipient
    msg["Reply-To"] = creds["sender_email"].strip()
    msg["Subject"] = resolved_subject
    msg["Date"] = formatdate(localtime=False)
    msg.set_content(resolved_body, subtype="plain", charset="utf-8")

    # 7. Output Pre-Flight Summary
    mode_label = "LIVE SMTP" if live_mode else "DRY-RUN (NO PACKET SENT)"
    print("=" * 76)
    print(f"AGENT 06 OUTREACH DISPATCHER — MODE: {mode_label}")
    print("=" * 76)
    if using_example:
        print("[NOTICE ] Using config/sender_credentials.example.json (dry-run preview only).")
    print(f"[QA GATE] PASSED — {args.prospect_id} verdict={audit['verdict']} ({audit['overall_score_100']}/100)")
    print(f"[QUOTA  ] Daily sends today ({today_str} UTC): {sent_today}/{daily_limit}")
    print(f"[LINKS  ] External URLs in Step {args.step}: {len(links_found)} {'(PASS: Step 1 link-free)' if args.step == 1 else ''}")
    print(f"[SMTP   ] Host: smtp.gmail.com:465 (SSL) | Auth User: {creds['sender_email']}")
    print("-" * 76)
    print(f"From    : {msg['From']}")
    print(f"To      : {msg['To']}")
    print(f"Reply-To: {msg['Reply-To']}")
    print(f"Subject : {msg['Subject']}  (Step {args.step} / Variant {args.variant.upper()})")
    print("-" * 76)
    print(resolved_body)
    print("=" * 76)

    if not live_mode:
        print("[DRY-RUN OK] Merge tags resolved cleanly and SMTP payload validated. Re-run with --live to send.")
        return 0

    # 8. Live Dispatch via Gmail SMTP SSL (465)
    app_password = creds["gmail_app_password"].replace(" ", "").strip()
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
        server.login(creds["sender_email"].strip(), app_password)
        server.send_message(msg)

    # 9. Update CRM Pipeline Ledger
    now = utc_now()
    if prospect.get("status") not in ("REPLIED", "CLOSED"):
        prospect["status"] = "SENT"
    if loom_url:
        prospect["loom_url"] = loom_url
    prospect.setdefault("outreach_history", []).append(
        {
            "step": args.step,
            "variant": args.variant,
            "subject": resolved_subject,
            "to": recipient,
            "sent_at": now,
            "date_utc": today_str,
        }
    )
    prospect["last_sent_at"] = now
    prospect["last_sent_step"] = args.step
    crm["updated_at"] = now

    with open(CRM_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(crm, f, indent=2)
        f.write("\n")

    print(f"[SENT   ] Email Step {args.step} delivered to {recipient} at {now} and recorded in {CRM_PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
