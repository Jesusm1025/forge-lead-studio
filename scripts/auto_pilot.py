"""
Forge Lead Studio — Zero-Token Daily AutoPilot Daemon
1. IMAP Safety Brake (imap.gmail.com:993): detects prospect replies, opt-outs, and MX bounces
   before any automated follow-up runs, updates tracking/crm_pipeline.json, and sends a
   high-priority lead alert email to forgeleadstudio@gmail.com.
2. Scheduled Step 2 / 3 / 4 Follow-Up Dispatcher: executes send_outreach.py strictly within
   the daily Gmail deliverability cap (default 15/day UTC).
3. Full audit trail logged to c:/agencia/tracking/autopilot.log.
"""

import argparse
import email
from email.header import decode_header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, parseaddr
import imaplib
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRM_PATH = os.path.join(ROOT, "tracking", "crm_pipeline.json")
CREDS_PATH = os.path.join(ROOT, "config", "sender_credentials.json")
LOG_PATH = os.path.join(ROOT, "tracking", "autopilot.log")
SEND_SCRIPT = os.path.join(ROOT, "scripts", "send_outreach.py")
DEFAULT_TELEMETRY_URL = "https://forge-lead-router.forge-lead-studio.workers.dev"

SKIP_STATUSES = {"REPLIED", "BOUNCED_MX", "CLOSED_WON", "CLOSED", "UNSUBSCRIBED"}
FREEMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "live.com", "me.com", "msn.com", "protonmail.com", "proton.me",
    "comcast.net", "att.net", "verizon.net", "bellsouth.net", "cox.net",
}
STEP_DELAY_DAYS = {1: 3, 2: 4, 3: 5}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


class Logger:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path

    def log(self, level: str, msg: str):
        line = f"[{utc_iso()}] [{level:<7}] {msg}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_credentials() -> tuple[dict, str]:
    """Load credentials from disk, SENDER_CREDENTIALS_JSON env var, or individual cloud env vars."""
    if os.path.exists(CREDS_PATH):
        creds = load_json(CREDS_PATH)
        source = "file:config/sender_credentials.json"
    elif (os.environ.get("SENDER_CREDENTIALS_JSON") or "").strip():
        raw = os.environ["SENDER_CREDENTIALS_JSON"].strip()
        try:
            creds = json.loads(raw)
        except json.JSONDecodeError as ex:
            raise SystemExit(f"[BLOCKED] Invalid JSON in SENDER_CREDENTIALS_JSON env var: {ex}")
        source = "env:SENDER_CREDENTIALS_JSON"
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
        source = "env:individual_vars"
    else:
        raise SystemExit(
            "[BLOCKED] Missing credentials. Provide config/sender_credentials.json on disk, "
            "or set SENDER_CREDENTIALS_JSON (or GMAIL_USER + GMAIL_APP_PASSWORD) in environment."
        )

    creds.setdefault("daily_send_limit", 15)
    creds.setdefault("sender_name", "Forge Lead Studio")
    creds.setdefault("sender_physical_address", creds["sender_name"])
    if creds.get("telemetry_admin_key") and not creds.get("telemetry_worker_url"):
        creds["telemetry_worker_url"] = DEFAULT_TELEMETRY_URL

    missing = [k for k in ("sender_email", "gmail_app_password") if not str(creds.get(k) or "").strip()]
    if missing:
        raise SystemExit(f"[BLOCKED] Incomplete credentials from {source}; missing: {missing}")

    return creds, source


def save_crm(crm: dict):
    crm["updated_at"] = utc_iso()
    with open(CRM_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(crm, f, indent=2)
        f.write("\n")


def decode_mime_header(raw_val: str | None) -> str:
    if not raw_val:
        return ""
    parts = decode_header(raw_val)
    decoded = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(str(chunk))
    return "".join(decoded).strip()


def extract_plain_body(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html_txt = payload.decode(charset, errors="replace")
                        body = re.sub(r"<[^>]+>", " ", html_txt)
                        break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                body = re.sub(r"<[^>]+>", " ", body)

    # Trim quoted thread replies to preserve only the prospect's new message
    clean_lines = []
    for ln in body.splitlines():
        s = ln.strip()
        if re.match(r"^On .+ wrote:$", s) or s.startswith("-----Original Message-----") or s.startswith("From: "):
            break
        if s.startswith(">"):
            continue
        if s:
            clean_lines.append(s)
    snippet = " ".join(clean_lines)
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:380]


def is_bounce_message(from_addr: str, subject: str, body: str) -> bool:
    fa = from_addr.lower()
    sub = subject.lower()
    if any(k in fa for k in ("mailer-daemon", "postmaster", "mail-daemon")):
        return True
    if any(k in sub for k in ("delivery status notification", "undeliverable", "mail delivery failed", "returned mail")):
        return True
    return False


def is_unsubscribe_reply(snippet: str) -> bool:
    low = snippet.lower().strip()
    if re.fullmatch(r"no[.!]?", low):
        return True
    return any(
        phrase in low
        for phrase in ("unsubscribe", "remove me", "stop emailing", "do not email", "take me off", "opt out")
    )


def send_reply_alert(creds: dict, prospect: dict, reply_from: str, reply_subject: str, snippet: str, status_tag: str, logger: Logger):
    sender_email = creds["sender_email"].strip()
    app_pw = creds["gmail_app_password"].replace(" ", "").strip()
    bname = prospect.get("business_name", prospect.get("prospect_id"))
    pid = prospect.get("prospect_id")

    msg = EmailMessage()
    msg["From"] = formataddr((f"{creds['sender_name'].strip()} AutoPilot", sender_email))
    msg["To"] = sender_email
    msg["Subject"] = f"[LEAD {status_tag}] {bname} replied!"
    msg["Date"] = formatdate(localtime=False)
    msg["X-Priority"] = "1"
    msg["Importance"] = "High"

    body = (
        f"HIGH-PRIORITY AUTOPILOT ALERT — {status_tag}\n"
        f"{'=' * 64}\n"
        f"Business      : {bname} ({prospect.get('city')}, {prospect.get('state')})\n"
        f"Decision Maker: {prospect.get('decision_maker')}\n"
        f"Reply From    : {reply_from}\n"
        f"Subject       : {reply_subject}\n"
        f"New CRM Status: {status_tag} (all automated follow-ups HALTED)\n"
        f"Live Demo URL : {prospect.get('live_preview_url') or 'N/A'}\n"
        f"Objection Doc : c:/agencia/pipeline/{pid}/04_outreach/objections.md\n"
        f"{'-' * 64}\n"
        f"MESSAGE SNIPPET:\n{snippet or '(Empty body — inspect inbox directly)'}\n"
        f"{'=' * 64}\n"
    )
    msg.set_content(body, subtype="plain", charset="utf-8")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
        server.login(sender_email, app_pw)
        server.send_message(msg)
    logger.log("ALERT", f"High-priority email alert sent to {sender_email} for {bname} ({status_tag}).")


def send_hot_demo_alert(creds: dict, prospect: dict, views: int, max_step: int, total_leads: int, last_viewed: str, logger: Logger):
    sender_email = creds["sender_email"].strip()
    app_pw = creds["gmail_app_password"].replace(" ", "").strip()
    bname = prospect.get("business_name", prospect.get("prospect_id"))
    pid = prospect.get("prospect_id")

    msg = EmailMessage()
    msg["From"] = formataddr((f"{creds['sender_name'].strip()} Telemetry", sender_email))
    msg["To"] = sender_email
    msg["Subject"] = f"[HOT DEMO VIEW] {bname} opened their prototype! ({views} view{'s' if views != 1 else ''} · Step {max_step}/4)"
    msg["Date"] = formatdate(localtime=False)
    msg["X-Priority"] = "1"
    msg["Importance"] = "High"

    body = (
        f"HOT DEMO ENGAGEMENT ALERT — STRIKE WHILE IRON IS HOT\n"
        f"{'=' * 64}\n"
        f"Business      : {bname} ({prospect.get('city')}, {prospect.get('state')})\n"
        f"Decision Maker: {prospect.get('decision_maker')}\n"
        f"Phone (Call!) : {prospect.get('phone')}\n"
        f"Email         : {prospect.get('email')}\n"
        f"{'-' * 64}\n"
        f"Demo Views    : {views}\n"
        f"Max Step      : Step {max_step} / 4\n"
        f"Leads Tested  : {total_leads}\n"
        f"Last Viewed   : {last_viewed or 'Just now'}\n"
        f"Live Demo URL : {prospect.get('live_preview_url') or 'N/A'}\n"
        f"Objection Doc : c:/agencia/pipeline/{pid}/04_outreach/objections.md\n"
        f"{'=' * 64}\n"
    )
    msg.set_content(body, subtype="plain", charset="utf-8")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
        server.login(sender_email, app_pw)
        server.send_message(msg)
    logger.log("HOT-VIEW", f"Sent [HOT DEMO VIEW] alert to {sender_email} for {bname} (views={views}, step={max_step}/4).")


def run_telemetry_sync(creds: dict, crm: dict, live_mode: bool, sync_write: bool, logger: Logger) -> dict:
    worker_url = (creds.get("telemetry_worker_url") or "").strip().rstrip("/")
    admin_key = (creds.get("telemetry_admin_key") or "").strip()
    stats_out = {"fetched": 0, "updated": 0, "hot_views": []}

    if not worker_url or not admin_key or "REPLACE_WITH" in admin_key:
        logger.log("TELEMETRY", "Telemetry Worker URL or Admin Key not configured in sender_credentials.json; skipping KV sync.")
        return stats_out

    req_url = f"{worker_url}/stats?secret={urllib.parse.quote(admin_key)}"
    req = urllib.request.Request(req_url, headers={"User-Agent": "ForgeAutoPilot/1.0", "X-Admin-Key": admin_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as ex:
        logger.log("WARN", f"Failed to pull KV telemetry from {worker_url}/stats: {ex}")
        return stats_out

    remote_map = data.get("prospects") or {}
    stats_out["fetched"] = len(remote_map)
    crm_dirty = False

    for p in crm.get("prospects", []):
        pid = p.get("prospect_id")
        if pid not in remote_map:
            continue
        r = remote_map[pid]
        new_views = int(r.get("views") or 0)
        new_step = int(r.get("max_step_reached") or 0)
        new_test_leads = int(r.get("test_leads") or 0)
        new_prod_leads = int(r.get("prod_leads") or 0)
        new_last_viewed = r.get("last_viewed_at")
        prev_views = int(p.get("demo_views") or 0)
        prev_alerted_step = int(p.get("last_alerted_step") or 0)
        prev_alerted_leads = int(p.get("last_alerted_leads") or 0)
        total_leads = new_test_leads + new_prod_leads

        changed = (
            new_views != prev_views
            or new_step != int(p.get("max_step_reached") or 0)
            or new_test_leads != int(p.get("test_leads") or 0)
            or new_prod_leads != int(p.get("prod_leads") or 0)
            or new_last_viewed != p.get("last_viewed_at")
        )

        if changed:
            stats_out["updated"] += 1
            logger.log(
                "TELEMETRY",
                f"{p['business_name']} ({pid}): views={new_views} (prev {prev_views}), max_step={new_step}/4, test_leads={new_test_leads}, prod_leads={new_prod_leads}",
            )
            if live_mode or sync_write:
                p["demo_views"] = new_views
                p["max_step_reached"] = new_step
                p["test_leads"] = new_test_leads
                p["prod_leads"] = new_prod_leads
                p["last_viewed_at"] = new_last_viewed
                if r.get("recent_leads"):
                    p["recent_leads"] = r["recent_leads"][:5]
                crm_dirty = True

        # Only trigger [HOT DEMO VIEW] email alerts on genuine human interaction
        # (prevents SSL/CT-log scanner page loads at Step 1 from spamming alerts).
        human_engaged = (new_step >= 2) or (total_leads >= 1)
        new_interaction = (new_step > prev_alerted_step) or (total_leads > prev_alerted_leads)
        if human_engaged and new_interaction:
            stats_out["hot_views"].append((pid, p["business_name"], new_views, new_step))
            if live_mode:
                send_hot_demo_alert(
                    creds, p, new_views, new_step, total_leads, new_last_viewed or "", logger
                )
                p["last_view_alerted_views"] = new_views
                p["last_alerted_step"] = new_step
                p["last_alerted_leads"] = total_leads
                crm_dirty = True
            else:
                logger.log("HOT-VIEW", f"[DRY-RUN] Would send [HOT DEMO VIEW] alert for {p['business_name']} (views={new_views}, step={new_step}/4, leads={total_leads}).")

    if (live_mode or sync_write) and crm_dirty:
        save_crm(crm)
        logger.log("CRM", f"Merged KV telemetry updates for {stats_out['updated']} prospect(s) into {CRM_PATH}.")

    return stats_out


def run_imap_reply_detector(creds: dict, crm: dict, live_mode: bool, lookback_days: int, logger: Logger) -> dict:
    sender_email = creds["sender_email"].strip().lower()
    app_pw = creds["gmail_app_password"].replace(" ", "").strip()

    prospects = crm.get("prospects", [])
    by_email = {}
    by_domain = {}
    for p in prospects:
        em = (p.get("email") or "").strip().lower()
        if not em or "@" not in em:
            continue
        by_email[em] = p
        dom = em.split("@", 1)[1]
        if dom not in FREEMAIL_DOMAINS:
            by_domain.setdefault(dom, []).append(p)

    stats = {"scanned": 0, "replies": [], "unsubscribes": [], "bounces": [], "crm_dirty": False}

    since_str = (utc_now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    logger.log("IMAP", f"Connecting to imap.gmail.com:993 as {sender_email} (lookback {lookback_days}d since {since_str})...")

    ctx = ssl.create_default_context()
    with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx) as imap:
        imap.login(sender_email, app_pw)
        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            raise RuntimeError("Failed to select Gmail INBOX via IMAP")

        typ, data = imap.search(None, "SINCE", since_str)
        if typ != "OK":
            raise RuntimeError("IMAP SINCE search failed")

        msg_ids = data[0].split()
        recent_ids = msg_ids[-150:]
        logger.log("IMAP", f"Login OK. Found {len(msg_ids)} inbox messages since {since_str}; inspecting {len(recent_ids)} recent messages.")

        for mid in recent_ids:
            typ, fetched = imap.fetch(mid, "(RFC822)")
            if typ != "OK" or not fetched or not isinstance(fetched[0], tuple):
                continue
            raw_bytes = fetched[0][1]
            msg = email.message_from_bytes(raw_bytes)
            stats["scanned"] += 1

            _, from_addr = parseaddr(msg.get("From", ""))
            from_low = (from_addr or "").strip().lower()
            subject = decode_mime_header(msg.get("Subject", ""))

            # Skip our own outbound/alert messages
            if from_low == sender_email:
                continue

            body_raw = extract_plain_body(msg)

            # 1) Bounce / DSN check
            if is_bounce_message(from_low, subject, body_raw):
                full_text = (subject + "\n" + raw_bytes.decode("utf-8", errors="ignore")).lower()
                for pem, p in by_email.items():
                    if pem in full_text:
                        st = str(p.get("status", "")).upper()
                        if st not in ("BOUNCED_MX", "REPLIED", "CLOSED_WON", "CLOSED"):
                            stats["bounces"].append((p["prospect_id"], pem, subject))
                            logger.log("BOUNCE", f"Detected DSN bounce for {p['business_name']} ({pem}) — Subject: {subject}")
                            if live_mode:
                                p["status"] = "BOUNCED_MX"
                                p["bounce_reason"] = f"AutoPilot IMAP DSN detected: {subject[:160]}"
                                p["bounce_checked_at"] = utc_iso()
                                stats["crm_dirty"] = True
                continue

            # 2) Prospect reply check (exact email OR corporate domain match)
            matched_prospect = by_email.get(from_low)
            if not matched_prospect and "@" in from_low:
                dom = from_low.split("@", 1)[1]
                cands = by_domain.get(dom, [])
                if len(cands) == 1:
                    matched_prospect = cands[0]

            if not matched_prospect:
                continue

            pid = matched_prospect["prospect_id"]
            cur_st = str(matched_prospect.get("status", "")).upper()
            if cur_st in ("REPLIED", "UNSUBSCRIBED", "CLOSED_WON", "CLOSED"):
                continue

            unsub = is_unsubscribe_reply(body_raw)
            new_status = "UNSUBSCRIBED" if unsub else "REPLIED"
            entry = {
                "prospect_id": pid,
                "business_name": matched_prospect["business_name"],
                "from": from_low,
                "subject": subject,
                "snippet": body_raw,
                "new_status": new_status,
            }
            if unsub:
                stats["unsubscribes"].append(entry)
            else:
                stats["replies"].append(entry)

            logger.log(
                "REPLY",
                f"MATCHED {new_status}: {matched_prospect['business_name']} ({from_low}) | Subj: '{subject}' | Snippet: '{body_raw[:120]}'",
            )

            if live_mode:
                matched_prospect["status"] = new_status
                matched_prospect["replied_at"] = utc_iso()
                matched_prospect["reply_from"] = from_low
                matched_prospect["reply_subject"] = subject
                matched_prospect["reply_snippet"] = body_raw
                stats["crm_dirty"] = True
                send_reply_alert(creds, matched_prospect, from_low, subject, body_raw, new_status, logger)

    if live_mode and stats["crm_dirty"]:
        save_crm(crm)
        logger.log("CRM", f"Saved reply/bounce updates to {CRM_PATH} (safety brake engaged).")

    return stats


def get_step_info(prospect: dict) -> tuple[int, date | None, str | None]:
    history = prospect.get("outreach_history") or []
    cur_step = max(
        int(prospect.get("current_step") or 0),
        int(prospect.get("last_sent_step") or 0),
    )
    last_ts = None

    if cur_step and prospect.get(f"step_{cur_step}_sent_at"):
        last_ts = prospect.get(f"step_{cur_step}_sent_at")
    if not last_ts:
        last_ts = prospect.get("last_sent_at")

    if history:
        latest = max(history, key=lambda h: (int(h.get("step") or 0), h.get("sent_at") or ""))
        hist_step = int(latest.get("step") or 0)
        if hist_step > cur_step:
            cur_step = hist_step
            last_ts = latest.get("sent_at") or last_ts
        elif not last_ts:
            last_ts = latest.get("sent_at")

    if cur_step and not last_ts:
        last_ts = prospect.get(f"step_{cur_step}_sent_at")

    if not last_ts:
        return cur_step, None, None

    try:
        dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        return cur_step, dt.date(), last_ts
    except ValueError:
        return cur_step, None, last_ts


def count_sent_today(crm: dict, today_ymd: str) -> int:
    total = 0
    for p in crm.get("prospects", []):
        for h in (p.get("outreach_history") or []):
            if h.get("date_utc") == today_ymd:
                total += 1
    return total


def run_followup_dispatcher(creds: dict, live_mode: bool, ref_date: date, logger: Logger) -> dict:
    # Always reload fresh CRM after IMAP phase so newly detected REPLIED prospects are strictly skipped
    crm = load_json(CRM_PATH)
    daily_limit = int(creds.get("daily_send_limit", 15))
    today_ymd = ref_date.strftime("%Y-%m-%d")
    sent_today = count_sent_today(crm, today_ymd)

    due_now = []
    upcoming = []
    skipped = []

    for p in crm.get("prospects", []):
        pid = p["prospect_id"]
        st = str(p.get("status", "")).upper()
        if st in SKIP_STATUSES or st != "SENT":
            skipped.append((pid, st))
            continue

        cur_step, sent_date, sent_ts = get_step_info(p)
        if cur_step not in STEP_DELAY_DAYS or sent_date is None:
            skipped.append((pid, f"step={cur_step}"))
            continue

        req_days = STEP_DELAY_DAYS[cur_step]
        next_step = cur_step + 1
        due_date = sent_date + timedelta(days=req_days)
        elapsed_days = (ref_date - sent_date).days

        item = {
            "prospect_id": pid,
            "business_name": p["business_name"],
            "email": p["email"],
            "current_step": cur_step,
            "next_step": next_step,
            "sent_date": sent_date.isoformat(),
            "due_date": due_date.isoformat(),
            "elapsed_days": elapsed_days,
            "req_days": req_days,
            "has_loom": bool((p.get("loom_url") or "").strip()),
            "live_preview_url": p.get("live_preview_url") or "",
        }
        if elapsed_days >= req_days:
            due_now.append(item)
        else:
            upcoming.append(item)

    due_now.sort(key=lambda x: (x["due_date"], x["business_name"]))
    upcoming.sort(key=lambda x: (x["due_date"], x["business_name"]))

    logger.log(
        "QUEUE",
        f"Reference UTC Date: {today_ymd} | Quota used: {sent_today}/{daily_limit} | Due now: {len(due_now)} | Upcoming: {len(upcoming)} | Skipped/Halted: {len(skipped)}",
    )

    dispatched = []
    quota_deferred = []

    for item in due_now:
        if sent_today >= daily_limit:
            quota_deferred.append(item)
            logger.log("QUOTA", f"Daily cap ({daily_limit}/day) reached — deferring {item['business_name']} Step {item['next_step']} to next UTC day.")
            continue

        cmd = [sys.executable, SEND_SCRIPT, item["prospect_id"], "--step", str(item["next_step"])]
        if item["next_step"] == 2 and not item["has_loom"]:
            cmd.append("--allow-no-loom")
        cmd.append("--live" if live_mode else "--dry-run")

        if not live_mode:
            logger.log(
                "DRY-RUN",
                f"WOULD SEND Step {item['next_step']} -> {item['business_name']} <{item['email']}> (sent {item['sent_date']}, due {item['due_date']}) | cmd: {' '.join(cmd)}",
            )
            dispatched.append(item)
            sent_today += 1
            continue

        logger.log("DISPATCH", f"Executing Step {item['next_step']} LIVE -> {item['business_name']} <{item['email']}>...")
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        if res.returncode == 0:
            sent_today += 1
            dispatched.append(item)
            sent_line = next((ln for ln in res.stdout.splitlines() if "[SENT" in ln), "Delivered OK")
            logger.log("SENT", f"{item['prospect_id']} Step {item['next_step']}: {sent_line.strip()} | Quota now {sent_today}/{daily_limit}")
        else:
            err_txt = (res.stderr or res.stdout).strip().splitlines()[-1] if (res.stderr or res.stdout) else f"exit {res.returncode}"
            logger.log("ERROR", f"Failed {item['prospect_id']} Step {item['next_step']}: {err_txt}")

    # Log upcoming follow-up schedule grouped by date
    if upcoming:
        by_due = {}
        for u in upcoming:
            by_due.setdefault(u["due_date"], []).append(u)
        for d_str in sorted(by_due.keys()):
            names = ", ".join(f"{u['business_name']} (Step {u['next_step']})" for u in by_due[d_str])
            logger.log("UPCOMING", f"Scheduled {d_str} ({len(by_due[d_str])} prospect{'s' if len(by_due[d_str]) != 1 else ''}): {names}")

    return {
        "ref_date": today_ymd,
        "due_now": due_now,
        "dispatched": dispatched,
        "quota_deferred": quota_deferred,
        "upcoming": upcoming,
        "skipped": skipped,
        "sent_today_after": sent_today,
        "daily_limit": daily_limit,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Forge Lead Studio — Zero-Token Daily AutoPilot (IMAP Reply Safety Brake + Step 2/3/4 Scheduler)."
    )
    parser.add_argument("--dry-run", action="store_true", help="Scan live IMAP and preview follow-ups without sending or editing CRM (default)")
    parser.add_argument("--live", action="store_true", help="Update CRM on replies/telemetry, send alerts, and dispatch due follow-ups live")
    parser.add_argument("--sync-telemetry", action="store_true", help="Write KV telemetry stats into crm_pipeline.json even during dry-run (no emails sent)")
    parser.add_argument("--as-of", default="", help="Optional UTC date YYYY-MM-DD for dry-run queue simulation (ignored in --live mode)")
    parser.add_argument("--lookback-days", type=int, default=14, help="Days of Gmail INBOX history to scan for replies/bounces (default: 14)")
    args = parser.parse_args()

    live_mode = bool(args.live) and not bool(args.dry_run)
    ref_date = utc_now().date()
    if args.as_of and not live_mode:
        ref_date = date.fromisoformat(args.as_of)

    logger = Logger(LOG_PATH)
    mode_lbl = "LIVE AUTOPILOT" if live_mode else f"DRY-RUN (as-of {ref_date.isoformat()})"
    logger.log("START", f"================ FORGE LEAD STUDIO AUTOPILOT — {mode_lbl} ================")

    creds, cred_source = load_credentials()
    logger.log("AUTH", f"Loaded sender credentials via {cred_source}.")
    crm = load_json(CRM_PATH)

    # Phase 1: Cloudflare KV Telemetry Sync & [HOT DEMO VIEW] Alerts
    tel_stats = run_telemetry_sync(creds, crm, live_mode=live_mode, sync_write=bool(args.sync_telemetry), logger=logger)
    logger.log(
        "TEL-OK",
        f"Worker KV stats pulled: {tel_stats['fetched']} active keys | CRM updated: {tel_stats['updated']} | Hot demo views: {len(tel_stats['hot_views'])}",
    )

    # Phase 2: IMAP Safety Brake (Replies, Opt-Outs, Bounces)
    imap_stats = run_imap_reply_detector(creds, crm, live_mode=live_mode, lookback_days=args.lookback_days, logger=logger)
    logger.log(
        "IMAP-OK",
        f"Scanned {imap_stats['scanned']} messages | New Replies: {len(imap_stats['replies'])} | Unsubscribes: {len(imap_stats['unsubscribes'])} | Bounces: {len(imap_stats['bounces'])}",
    )

    # Phase 3: Scheduled Step 2 / 3 / 4 Dispatcher
    disp_stats = run_followup_dispatcher(creds, live_mode=live_mode, ref_date=ref_date, logger=logger)

    logger.log(
        "DONE",
        f"AutoPilot complete | Mode={mode_lbl} | Dispatched={len(disp_stats['dispatched'])} | Deferred={len(disp_stats['quota_deferred'])} | Quota={disp_stats['sent_today_after']}/{disp_stats['daily_limit']}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
