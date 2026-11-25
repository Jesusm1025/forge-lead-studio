import html
import json
import os
import re
import sys

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))


def hydrate(spec_path: str, out_dir: str):
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    os.makedirs(out_dir, exist_ok=True)

    # 1. Build lean widget config payload (brand_config + pricing_engine + first-party telemetry)
    tel_endpoint = spec.get("telemetry_endpoint") or "https://forge-lead-router.forge-lead-studio.workers.dev/event"
    del_mode = spec.get("delivery_mode") or "demo"
    widget_cfg = {
        "prospect_id": spec["prospect_id"],
        "telemetry_endpoint": tel_endpoint,
        "delivery_mode": del_mode,
        "brand_config": spec["brand_config"],
        "pricing_engine": spec["pricing_engine"],
    }
    cfg_json = json.dumps(widget_cfg, separators=(",", ":"))

    with open(os.path.join(TEMPLATE_DIR, "template.js"), encoding="utf-8") as f:
        tpl_js = f.read()

    placeholder = "/*__TROJAN_CONFIG__*/null/*__END_TROJAN_CONFIG__*/"
    if placeholder not in tpl_js:
        raise RuntimeError("Missing config injection placeholder in template.js")

    hydrated_js = tpl_js.replace(placeholder, cfg_json, 1)
    # Compact leading indentation and empty lines cleanly without altering logic or string semantics
    compact_lines = [line.strip() for line in hydrated_js.splitlines() if line.strip()]
    hydrated_js = "\n".join(compact_lines) + "\n"
    hydrated_js = re.sub(r">\n<", "><", hydrated_js)
    widget_out = os.path.join(out_dir, "widget.js")
    with open(widget_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(hydrated_js)

    # 2. Build branded preview wrapper index.html
    with open(os.path.join(TEMPLATE_DIR, "preview_shell.html"), encoding="utf-8") as f:
        shell_html = f.read()

    b = spec["brand_config"]
    pw = spec["preview_wrapper_spec"]
    slug = spec["prospect_id"].split("_")[-1]
    phone_digits = re.sub(r"[^\d+]", "", b["phone_display"])
    pain_items = "\n          ".join(
        f"<li>{html.escape(item)}</li>" for item in pw["pain_points_solved_callouts"]
    )

    def hex_luminance(hx: str) -> float:
        h = hx.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, bl = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r * 299 + g * 587 + bl * 114) / 1000.0

    light_sec = hex_luminance(b["secondary_hex"]) > 155
    on_secondary = "#111111" if light_sec else "#FFFFFF"
    copy_border = b["secondary_hex"] if light_sec else "rgba(255, 255, 255, 0.35)"

    replacements = {
        "{{BUSINESS_NAME}}": html.escape(b["business_name"]),
        "{{TAGLINE}}": html.escape(b["tagline"]),
        "{{PRIMARY_HEX}}": b["primary_hex"],
        "{{SECONDARY_HEX}}": b["secondary_hex"],
        "{{ON_SECONDARY_HEX}}": on_secondary,
        "{{COPY_BORDER}}": copy_border,
        "{{SURFACE_HEX}}": b["surface_hex"],
        "{{TEXT_HEX}}": b["text_hex"],
        "{{CTA_LABEL}}": html.escape(b["cta_label"]),
        "{{PHONE_DISPLAY}}": html.escape(b["phone_display"]),
        "{{PHONE_DIGITS}}": phone_digits,
        "{{HERO_HEADLINE}}": html.escape(pw["hero_headline"]),
        "{{HERO_SUBHEADLINE}}": html.escape(pw["hero_subheadline"]),
        "{{PAIN_POINT_ITEMS}}": pain_items,
        "{{EMBED_SCRIPT_SRC}}": f"https://widgets.trojanagency.com/{slug}/widget.js",
        "{{TELEMETRY_ENDPOINT}}": tel_endpoint,
        "{{DELIVERY_MODE}}": del_mode,
    }
    hydrated_html = shell_html
    for k, v in replacements.items():
        hydrated_html = hydrated_html.replace(k, v)

    index_out = os.path.join(out_dir, "index.html")
    with open(index_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(hydrated_html)

    w_bytes = os.path.getsize(widget_out)
    h_bytes = os.path.getsize(index_out)
    print(f"Hydrated {spec['prospect_id']} -> {out_dir}")
    print(f"  widget.js : {w_bytes:,} bytes ({w_bytes/1024:.2f} KB)")
    print(f"  index.html: {h_bytes:,} bytes ({h_bytes/1024:.2f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python hydrate.py <path/to/02_spec.json> <output/03_mvp_dir>")
        sys.exit(1)
    hydrate(sys.argv[1], sys.argv[2])
