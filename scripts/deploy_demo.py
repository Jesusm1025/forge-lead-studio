import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = r"c:\agencia"
PIPELINE_DIR = os.path.join(ROOT, "pipeline")
CRM_PATH = os.path.join(ROOT, "tracking", "crm_pipeline.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_npx() -> str:
    for candidate in ("npx.cmd", "npx"):
        path = shutil.which(candidate)
        if path:
            return path
    return "npx"


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


def sanitize_project_name(slug: str) -> str:
    clean = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
    return f"{clean}-demo"[:58]


def run_wrangler(npx_bin: str, args: list, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [npx_bin, "--yes", "wrangler"] + args
    print(f"[CMD] {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        err_out = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(
            f"[ERROR] Wrangler command failed (exit {proc.returncode}):\n{err_out}\n\n"
            "Hint: Ensure you have authenticated once with: npx wrangler login"
        )
    return proc


def extract_pages_url(output_text: str, project_name: str) -> str:
    # Prefer canonical production domain if returned, else capture first https://*.pages.dev URL
    urls = re.findall(r"https://[a-zA-Z0-9.-]+\.pages\.dev", output_text)
    canonical = f"https://{project_name}.pages.dev"
    if canonical in urls:
        return canonical
    if urls:
        # Wrangler prints deployment URL (e.g. https://<hash>.<project>.pages.dev); production alias is <project>.pages.dev
        for u in urls:
            if u.endswith(f".{project_name}.pages.dev") or u == canonical:
                return canonical
        return urls[0]
    raise SystemExit(
        "[ERROR] Deployment succeeded but no https://*.pages.dev URL was detected in Wrangler output:\n"
        + output_text
    )


def patch_index_embed_url(index_path: str, live_base_url: str) -> bool:
    with open(index_path, encoding="utf-8") as f:
        html_text = f.read()

    live_widget_url = live_base_url.rstrip("/") + "/widget.js"
    # Replace placeholder or prior URL inside the copyable embed snippet code block
    pattern = re.compile(
        r'(<code[^>]*id="embed-snippet"[^>]*>.*?src=")https?://[^"&]+/widget\.js(".*?</code>)',
        flags=re.I | re.S,
    )
    updated, count = pattern.subn(rf"\g<1>{live_widget_url}\g<2>", html_text, count=1)
    if count == 0:
        # Fallback: replace any widgets.trojanagency.com/.../widget.js reference
        updated, count = re.subn(
            r"https://widgets\.trojanagency\.com/[^\"'<\s]+/widget\.js",
            live_widget_url,
            html_text,
        )
    if count > 0 and updated != html_text:
        with open(index_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(updated)
        return True
    return False


def update_crm(prospect_id: str, project_name: str, live_url: str):
    with open(CRM_PATH, encoding="utf-8") as f:
        crm = json.load(f)

    found = False
    now = utc_now()
    for p in crm.get("prospects", []):
        if p.get("prospect_id") == prospect_id:
            p["cloudflare_project"] = project_name
            p["live_preview_url"] = live_url
            p["live_widget_url"] = live_url.rstrip("/") + "/widget.js"
            p["deployed_at"] = now
            found = True
            break
    if not found:
        raise SystemExit(f"[ERROR] Prospect '{prospect_id}' not found in {CRM_PATH}")

    crm["updated_at"] = now
    with open(CRM_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(crm, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Agent 06 — Deploy QA-approved Trojan Horse MVP to Cloudflare Pages."
    )
    parser.add_argument("prospect_id", help="Prospect slug (e.g., roofing_austin_roof-royale)")
    parser.add_argument("--project-name", help="Override Cloudflare Pages project name (default: <slug>-demo)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate QA gate and preview commands without deploying to Cloudflare Pages",
    )
    args = parser.parse_args()

    # 1. Enforce QA Gate Lock
    audit = verify_qa_approved(args.prospect_id)
    mvp_dir = os.path.join(PIPELINE_DIR, args.prospect_id, "03_mvp")
    index_path = os.path.join(mvp_dir, "index.html")
    widget_path = os.path.join(mvp_dir, "widget.js")
    for req in (index_path, widget_path):
        if not os.path.exists(req):
            raise SystemExit(f"[ERROR] Missing MVP artifact: {req}")

    slug = args.prospect_id.split("_")[-1]
    project_name = args.project_name or sanitize_project_name(slug)
    npx_bin = resolve_npx()

    print(f"[QA GATE] PASSED — {args.prospect_id} verdict={audit['verdict']} ({audit['overall_score_100']}/100)")
    print(f"[TARGET ] Cloudflare Pages project: {project_name}")
    print(f"[SOURCE ] {mvp_dir}")

    if args.dry_run:
        print("\n[DRY-RUN] Would execute:")
        print(f"  1. {npx_bin} --yes wrangler pages project create {project_name} --production-branch main")
        print(f"  2. {npx_bin} --yes wrangler pages deploy {mvp_dir} --project-name {project_name} --branch main")
        print(f"  3. Patch 03_mvp/index.html embed snippet -> https://{project_name}.pages.dev/widget.js")
        print(f"  4. Re-deploy {mvp_dir} and save live_preview_url into tracking/crm_pipeline.json")
        return 0

    # 2. Ensure Cloudflare Pages project exists (idempotent)
    create_proc = run_wrangler(
        npx_bin,
        ["pages", "project", "create", project_name, "--production-branch", "main"],
        check=False,
    )
    combined_create = (create_proc.stdout or "") + "\n" + (create_proc.stderr or "")
    if create_proc.returncode != 0 and "already exists" not in combined_create.lower() and "8000002" not in combined_create:
        print(f"[WARN] Project create returned non-zero (continuing to deploy): {combined_create.strip()[:260]}")

    # 3. Initial deploy to capture live *.pages.dev URL
    dep1 = run_wrangler(
        npx_bin,
        ["pages", "deploy", mvp_dir, "--project-name", project_name, "--branch", "main"],
        check=True,
    )
    live_url = extract_pages_url((dep1.stdout or "") + "\n" + (dep1.stderr or ""), project_name)
    print(f"[LIVE   ] Captured Cloudflare Pages URL: {live_url}")

    # 4. Patch embed snippet inside index.html with live URL and re-deploy
    patched = patch_index_embed_url(index_path, live_url)
    if patched:
        print(f"[PATCH  ] Updated 03_mvp/index.html embed snippet -> {live_url}/widget.js")
        run_wrangler(
            npx_bin,
            ["pages", "deploy", mvp_dir, "--project-name", project_name, "--branch", "main"],
            check=True,
        )
        print("[DEPLOY ] Re-deployed patched index.html with live widget.js embed URL.")
    else:
        print("[INFO   ] index.html embed snippet already up to date; skipping second deploy.")

    # 5. Update CRM ledger
    update_crm(args.prospect_id, project_name, live_url)
    print(f"\n[SUCCESS] Saved live_preview_url='{live_url}' to {CRM_PATH}")
    print(f"          Live Demo  : {live_url}")
    print(f"          Embed Tag  : <div id=\"trojan-quote-widget\"></div><script src=\"{live_url}/widget.js\" defer></script>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
