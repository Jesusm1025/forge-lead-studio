"""
Forge Lead Studio — Zero-Dependency Cloudflare Pages Direct API Deployer
Deploys static demo bundles (index.html + widget.js + _headers) or the
Edge-protected Executive Dashboard (_worker.js with SHA-256 ADMIN_KEY guard)
directly to Cloudflare Pages via the Cloudflare v4 REST API using Python stdlib only.

Credentials resolution order:
  1. Environment variables: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
  2. Local fallback: config/sender_credentials.json (or SENDER_CREDENTIALS_JSON env var)
"""

import argparse
import base64
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDS_PATH = ROOT / "config" / "sender_credentials.json"
PUBLIC_DIR = ROOT / "public"
TRACKING_DIR = ROOT / "tracking"
CF_API_BASE = "https://api.cloudflare.com/client/v4"
DASHBOARD_PROJECT = "forge-lead-dashboard"

DEFAULT_DEMO_HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
/widget.js
  Content-Type: application/javascript; charset=utf-8
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=300
"""

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def load_local_creds() -> dict:
    if CREDS_PATH.exists():
        try:
            return json.loads(CREDS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    raw_env = (os.environ.get("SENDER_CREDENTIALS_JSON") or "").strip()
    if raw_env:
        try:
            return json.loads(raw_env)
        except Exception:
            return {}
    return {}


def load_cloudflare_auth(require_token: bool = True) -> tuple[str, str, str]:
    creds = load_local_creds()
    account_id = (
        os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        or creds.get("cloudflare_account_id")
        or ""
    ).strip()
    api_token = (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or creds.get("cloudflare_api_token")
        or ""
    ).strip()
    source = "env" if (os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN")) else "config/fallback"
    if require_token and (not account_id or not api_token):
        raise SystemExit(
            "[BLOCKED] Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN. "
            "Set them in environment variables (GitHub Actions secrets) or config/sender_credentials.json."
        )
    return account_id, api_token, source


def load_admin_sha256() -> str:
    explicit_hash = (os.environ.get("DASHBOARD_ADMIN_SHA256") or "").strip().lower()
    if len(explicit_hash) == 64:
        return explicit_hash
    creds = load_local_creds()
    admin_key = (
        os.environ.get("TELEMETRY_ADMIN_KEY")
        or creds.get("telemetry_admin_key")
        or ""
    ).strip()
    if not admin_key:
        raise SystemExit(
            "[BLOCKED] Missing TELEMETRY_ADMIN_KEY (or DASHBOARD_ADMIN_SHA256) needed to protect "
            "forge-lead-dashboard /tracking/*.json endpoints."
        )
    return hashlib.sha256(admin_key.encode("utf-8")).hexdigest()


def cf_request(
    method: str,
    path: str,
    token: str,
    body: bytes | dict | list | None = None,
    content_type: str | None = None,
    timeout: int = 45,
) -> tuple[int, dict]:
    url = f"{CF_API_BASE}{path}" if path.startswith("/") else path
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "ForgeLeadStudio-PagesDeployer/1.0",
    }
    data = None
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = content_type or "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body)
        if content_type:
            headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            parsed = {"success": False, "errors": [{"code": e.code, "message": raw[:400]}]}
        return e.code, parsed


def encode_multipart_form(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----ForgeBoundary{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, filename, content, ctype in files:
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {ctype}\r\n\r\n".encode("ascii"))
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def ensure_pages_project(account_id: str, token: str, project_name: str, production_branch: str = "main") -> dict:
    status, payload = cf_request(
        "POST",
        f"/accounts/{account_id}/pages/projects",
        token,
        body={"name": project_name, "production_branch": production_branch},
    )
    if status in (200, 201) and payload.get("success"):
        res = payload.get("result") or {}
        return {"action": "created", "name": project_name, "subdomain": res.get("subdomain") or f"{project_name}.pages.dev"}

    errs = payload.get("errors") or []
    already_exists = status == 409 or any(int(e.get("code") or 0) == 8000007 for e in errs)
    if already_exists:
        g_status, g_payload = cf_request("GET", f"/accounts/{account_id}/pages/projects/{project_name}", token)
        res = (g_payload.get("result") or {}) if g_status == 200 else {}
        return {"action": "existing", "name": project_name, "subdomain": res.get("subdomain") or f"{project_name}.pages.dev"}

    raise RuntimeError(f"Failed creating Cloudflare Pages project '{project_name}' (HTTP {status}): {errs}")


def poll_deployment_success(account_id: str, token: str, project_name: str, dep_id: str, timeout_s: int = 90) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        status, payload = cf_request(
            "GET",
            f"/accounts/{account_id}/pages/projects/{project_name}/deployments/{dep_id}",
            token,
        )
        if status == 200 and payload.get("success"):
            res = payload.get("result") or {}
            stage = (res.get("latest_stage") or {}).get("name")
            st = (res.get("latest_stage") or {}).get("status")
            last = {"id": dep_id, "stage": stage, "status": st, "url": res.get("url"), "modified_on": res.get("modified_on")}
            if stage == "deploy" and st == "success":
                return last
            if st in ("failure", "canceled"):
                raise RuntimeError(f"Cloudflare Pages deployment failed for {project_name}/{dep_id}: {last}")
        time.sleep(2.0)
    raise RuntimeError(f"Timed out waiting for deployment {project_name}/{dep_id}: last={last}")


def compute_pages_asset_hash(raw_bytes: bytes, rel_path: str) -> tuple[str, str]:
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    ext = Path(rel_path).suffix.lstrip(".").lower()
    # 32 lowercase hex characters matching Cloudflare Pages asset key format
    digest = hashlib.blake2b((b64 + ext).encode("utf-8"), digest_size=16).hexdigest()
    return digest, b64


def verify_live_urls(base_url: str, check_widget: bool = True, retries: int = 5) -> dict:
    base = base_url.rstrip("/")
    checks = {"root_status": None, "widget_status": None, "widget_bytes": None}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{base}/", headers={"User-Agent": "ForgeLeadStudio-Verifier/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                checks["root_status"] = r.status
            if check_widget:
                req_w = urllib.request.Request(f"{base}/widget.js", headers={"User-Agent": "ForgeLeadStudio-Verifier/1.0"})
                with urllib.request.urlopen(req_w, timeout=20) as rw:
                    checks["widget_status"] = rw.status
                    checks["widget_bytes"] = len(rw.read())
            if checks["root_status"] == 200 and (not check_widget or checks["widget_status"] == 200):
                return checks
        except Exception:
            pass
        if attempt + 1 < retries:
            time.sleep(2.5)
    return checks


def deploy_static_site(
    project_name: str,
    source_dir: str | Path,
    dry_run: bool = False,
    verify: bool = True,
    production_branch: str = "main",
) -> dict:
    src = Path(source_dir).resolve()
    index_file = src / "index.html"
    widget_file = src / "widget.js"
    if not index_file.exists():
        raise FileNotFoundError(f"Missing required {index_file}")

    assets: list[tuple[str, bytes, str]] = []
    for p in sorted(src.rglob("*")):
        if p.is_file():
            rel = "/" + p.relative_to(src).as_posix()
            ctype = MIME_TYPES.get(p.suffix.lower(), "application/octet-stream")
            if p.name == "_headers":
                ctype = "text/plain; charset=utf-8"
            assets.append((rel, p.read_bytes(), ctype))

    if not any(rel == "/_headers" for rel, _, _ in assets):
        assets.append(("/_headers", DEFAULT_DEMO_HEADERS.encode("utf-8"), "text/plain; charset=utf-8"))

    manifest: dict[str, str] = {}
    upload_payload: list[dict] = []
    hashes: list[str] = []
    file_summary = []

    for rel, raw, ctype in assets:
        key, b64 = compute_pages_asset_hash(raw, rel)
        manifest[rel] = key
        hashes.append(key)
        upload_payload.append({
            "key": key,
            "value": b64,
            "metadata": {"contentType": ctype},
            "base64": True,
        })
        file_summary.append({"path": rel, "bytes": len(raw), "key": key, "contentType": ctype})

    account_id, api_token, auth_src = load_cloudflare_auth(require_token=not dry_run)
    live_url = f"https://{project_name}.pages.dev"

    if dry_run:
        return {
            "mode": "dry_run",
            "project": project_name,
            "account_id": account_id or "(from CLOUDFLARE_ACCOUNT_ID)",
            "token_configured": bool(api_token),
            "auth_source": auth_src,
            "live_url": live_url,
            "live_widget_url": f"{live_url}/widget.js" if widget_file.exists() else None,
            "files": file_summary,
            "manifest": manifest,
            "endpoints": [
                f"POST {CF_API_BASE}/accounts/{{account_id}}/pages/projects",
                f"GET  {CF_API_BASE}/accounts/{{account_id}}/pages/projects/{project_name}/upload-token",
                f"POST {CF_API_BASE}/pages/assets/upload",
                f"POST {CF_API_BASE}/pages/assets/upsert-hashes",
                f"POST {CF_API_BASE}/accounts/{{account_id}}/pages/projects/{project_name}/deployments",
            ],
        }

    # 1. Ensure Pages project exists (ignores 8000007)
    proj_info = ensure_pages_project(account_id, api_token, project_name, production_branch=production_branch)

    # 2. Obtain short-lived Direct Upload JWT
    t_status, t_payload = cf_request(
        "GET",
        f"/accounts/{account_id}/pages/projects/{project_name}/upload-token",
        api_token,
    )
    jwt = (t_payload.get("result") or {}).get("jwt") if t_status == 200 else None
    if not jwt:
        raise RuntimeError(f"Failed to get upload-token for {project_name} (HTTP {t_status}): {t_payload}")

    # 3. Upload asset blobs & register hashes
    u_status, u_payload = cf_request("POST", "/pages/assets/upload", jwt, body=upload_payload)
    if u_status not in (200, 201) or not u_payload.get("success", True):
        raise RuntimeError(f"Failed /pages/assets/upload for {project_name} (HTTP {u_status}): {u_payload}")

    h_status, h_payload = cf_request("POST", "/pages/assets/upsert-hashes", jwt, body={"hashes": hashes})
    if h_status not in (200, 201) or not h_payload.get("success", True):
        raise RuntimeError(f"Failed /pages/assets/upsert-hashes for {project_name} (HTTP {h_status}): {h_payload}")

    # 4. Create Pages deployment via multipart/form-data manifest
    mp_body, mp_ctype = encode_multipart_form(
        fields={"manifest": json.dumps(manifest), "branch": production_branch},
        files=[],
    )
    d_status, d_payload = cf_request(
        "POST",
        f"/accounts/{account_id}/pages/projects/{project_name}/deployments",
        api_token,
        body=mp_body,
        content_type=mp_ctype,
    )
    if d_status not in (200, 201) or not d_payload.get("success"):
        raise RuntimeError(f"Failed creating deployment for {project_name} (HTTP {d_status}): {d_payload}")

    dep_res = d_payload.get("result") or {}
    dep_id = dep_res["id"]
    poll = poll_deployment_success(account_id, api_token, project_name, dep_id)
    subdomain = proj_info.get("subdomain") or f"{project_name}.pages.dev"
    live_url = f"https://{subdomain}" if not subdomain.startswith("http") else subdomain

    verification = verify_live_urls(live_url, check_widget=widget_file.exists()) if verify else {}
    return {
        "mode": "live",
        "project": project_name,
        "project_action": proj_info["action"],
        "deployment_id": dep_id,
        "deployment_url": poll.get("url"),
        "live_url": live_url,
        "live_widget_url": f"{live_url}/widget.js" if widget_file.exists() else None,
        "deployed_at": poll.get("modified_on"),
        "files": file_summary,
        "verification": verification,
    }


def build_protected_dashboard_worker(public_dir: Path, admin_sha256: str) -> tuple[str, dict]:
    html_path = public_dir / "index.html"
    crm_path = public_dir / "tracking" / "crm_pipeline.json"
    if not crm_path.exists():
        crm_path = TRACKING_DIR / "crm_pipeline.json"
    niche_path = public_dir / "tracking" / "niche_intelligence.json"
    if not niche_path.exists():
        niche_path = TRACKING_DIR / "niche_intelligence.json"

    if not html_path.exists() or not crm_path.exists():
        raise FileNotFoundError(f"Missing dashboard assets: html={html_path.exists()}, crm={crm_path.exists()}")

    html_raw = html_path.read_bytes()
    crm_raw = crm_path.read_bytes()
    niche_raw = niche_path.read_bytes() if niche_path.exists() else b"{}"

    html_gz_b64 = base64.b64encode(gzip.compress(html_raw, compresslevel=9)).decode("ascii")
    crm_gz_b64 = base64.b64encode(gzip.compress(crm_raw, compresslevel=9)).decode("ascii")
    niche_gz_b64 = base64.b64encode(gzip.compress(niche_raw, compresslevel=9)).decode("ascii")

    worker_code = f"""
const ADMIN_SHA256 = {json.dumps(admin_sha256)};
const HTML_GZ_B64 = {json.dumps(html_gz_b64)};
const CRM_GZ_B64 = {json.dumps(crm_gz_b64)};
const NICHE_GZ_B64 = {json.dumps(niche_gz_b64)};

function b64ToBytes(b64) {{
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}}

async function gunzipText(b64) {{
  const ds = new DecompressionStream('gzip');
  const stream = new Blob([b64ToBytes(b64)]).stream().pipeThrough(ds);
  return await new Response(stream).text();
}}

async function sha256Hex(str) {{
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}}

function timingSafeEqual(a, b) {{
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}}

const SEC_HEADERS = {{
  'X-Robots-Tag': 'noindex, nofollow',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-store'
}};

async function requireAdmin(request, url) {{
  const key = (request.headers.get('X-Admin-Key') || url.searchParams.get('secret') || '').trim();
  if (!key) {{
    return new Response(JSON.stringify({{ ok: false, error: 'Unauthorized' }}), {{
      status: 401,
      headers: {{ ...SEC_HEADERS, 'Content-Type': 'application/json; charset=utf-8' }}
    }});
  }}
  const digest = await sha256Hex(key);
  if (!timingSafeEqual(digest, ADMIN_SHA256)) {{
    return new Response(JSON.stringify({{ ok: false, error: 'Forbidden' }}), {{
      status: 401,
      headers: {{ ...SEC_HEADERS, 'Content-Type': 'application/json; charset=utf-8' }}
    }});
  }}
  return null;
}}

export default {{
  async fetch(request) {{
    const url = new URL(request.url);
    const p = url.pathname;

    if (p === '/tracking/crm_pipeline.json') {{
      const denied = await requireAdmin(request, url);
      if (denied) return denied;
      const crmText = await gunzipText(CRM_GZ_B64);
      return new Response(crmText, {{
        status: 200,
        headers: {{ ...SEC_HEADERS, 'Content-Type': 'application/json; charset=utf-8' }}
      }});
    }}

    if (p === '/tracking/niche_intelligence.json') {{
      const denied = await requireAdmin(request, url);
      if (denied) return denied;
      const nicheText = await gunzipText(NICHE_GZ_B64);
      return new Response(nicheText, {{
        status: 200,
        headers: {{ ...SEC_HEADERS, 'Content-Type': 'application/json; charset=utf-8' }}
      }});
    }}

    if (p === '/' || p === '/index.html') {{
      const htmlText = await gunzipText(HTML_GZ_B64);
      return new Response(htmlText, {{
        status: 200,
        headers: {{ ...SEC_HEADERS, 'Content-Type': 'text/html; charset=utf-8' }}
      }});
    }}

    return new Response('Not Found', {{ status: 404, headers: SEC_HEADERS }});
  }}
}};
"""
    stats = {
        "html_raw_bytes": len(html_raw),
        "html_gz_b64_len": len(html_gz_b64),
        "crm_raw_bytes": len(crm_raw),
        "crm_gz_b64_len": len(crm_gz_b64),
        "niche_raw_bytes": len(niche_raw),
        "niche_gz_b64_len": len(niche_gz_b64),
        "worker_bytes": len(worker_code.encode("utf-8")),
        "admin_sha256_prefix": admin_sha256[:12] + "...",
    }
    return worker_code, stats


def deploy_protected_dashboard(
    public_dir: str | Path = PUBLIC_DIR,
    project_name: str = DASHBOARD_PROJECT,
    dry_run: bool = False,
    verify: bool = True,
) -> dict:
    pub = Path(public_dir).resolve()
    admin_sha256 = load_admin_sha256()
    worker_code, stats = build_protected_dashboard_worker(pub, admin_sha256)
    account_id, api_token, auth_src = load_cloudflare_auth(require_token=not dry_run)
    live_url = f"https://{project_name}.pages.dev"

    if dry_run:
        return {
            "mode": "dry_run",
            "target": "protected_dashboard",
            "project": project_name,
            "account_id": account_id or "(from CLOUDFLARE_ACCOUNT_ID)",
            "token_configured": bool(api_token),
            "auth_source": auth_src,
            "live_url": live_url,
            "edge_protected_routes": ["/tracking/crm_pipeline.json", "/tracking/niche_intelligence.json"],
            "bundle_stats": stats,
            "endpoints": [
                f"POST {CF_API_BASE}/accounts/{{account_id}}/pages/projects",
                f"POST {CF_API_BASE}/accounts/{{account_id}}/pages/projects/{project_name}/deployments (_worker.js)",
            ],
        }

    proj_info = ensure_pages_project(account_id, api_token, project_name, production_branch="main")
    mp_body, mp_ctype = encode_multipart_form(
        fields={"manifest": "{}", "branch": "main"},
        files=[("_worker.js", "_worker.js", worker_code.encode("utf-8"), "application/javascript+module")],
    )
    d_status, d_payload = cf_request(
        "POST",
        f"/accounts/{account_id}/pages/projects/{project_name}/deployments",
        api_token,
        body=mp_body,
        content_type=mp_ctype,
        timeout=60,
    )
    if d_status not in (200, 201) or not d_payload.get("success"):
        raise RuntimeError(f"Failed deploying protected dashboard '{project_name}' (HTTP {d_status}): {d_payload}")

    dep_id = d_payload["result"]["id"]
    poll = poll_deployment_success(account_id, api_token, project_name, dep_id)

    verif = {}
    if verify:
        verif = verify_live_urls(live_url, check_widget=False)
        for route in ("/tracking/crm_pipeline.json", "/tracking/niche_intelligence.json"):
            try:
                req = urllib.request.Request(f"{live_url}{route}", headers={"User-Agent": "ForgeLeadStudio-Verifier/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    verif[f"anon_{route}"] = r.status
            except urllib.error.HTTPError as e:
                verif[f"anon_{route}"] = e.code

    return {
        "mode": "live",
        "target": "protected_dashboard",
        "project": project_name,
        "project_action": proj_info["action"],
        "deployment_id": dep_id,
        "deployment_url": poll.get("url"),
        "live_url": live_url,
        "deployed_at": poll.get("modified_on"),
        "bundle_stats": stats,
        "verification": verif,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forge Lead Studio — Direct Cloudflare Pages REST API Deployer (Zero External Dependencies)"
    )
    parser.add_argument("--project", default="", help="Cloudflare Pages project name (e.g. acme-hvac-demo)")
    parser.add_argument("--dir", default="", help="Directory containing index.html and widget.js")
    parser.add_argument("--deploy-dashboard", action="store_true", help="Deploy Edge-protected public/ executive dashboard to forge-lead-dashboard.pages.dev")
    parser.add_argument("--dry-run", action="store_true", help="Validate bundle and print API plan without deploying")
    parser.add_argument("--no-verify", action="store_true", help="Skip post-deploy HTTP 200/401 live probe")
    args = parser.parse_args()

    if args.deploy_dashboard:
        res = deploy_protected_dashboard(
            public_dir=PUBLIC_DIR,
            project_name=args.project or DASHBOARD_PROJECT,
            dry_run=args.dry_run,
            verify=not args.no_verify,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.dry_run and not args.project and not args.dir:
        # Convenience smoke check: validate protected dashboard bundle + sample HVAC demo
        sample_dir = ROOT / "pipeline" / "hvac_phoenix_service-smith" / "03_mvp"
        out = {
            "dashboard_dry_run": deploy_protected_dashboard(public_dir=PUBLIC_DIR, dry_run=True),
        }
        if sample_dir.exists():
            out["sample_demo_dry_run"] = deploy_static_site(
                project_name="service-smith-hvac-demo",
                source_dir=sample_dir,
                dry_run=True,
            )
        print(json.dumps(out, indent=2))
        return 0

    if not args.project or not args.dir:
        parser.error("Provide --project <name> --dir <path>, or --deploy-dashboard (or --dry-run for smoke check).")

    res = deploy_static_site(
        project_name=args.project,
        source_dir=args.dir,
        dry_run=args.dry_run,
        verify=not args.no_verify,
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
