# Agent 01 Audit Notes — Roof Royale

- **Prospect ID:** `roofing_austin_roof-royale`
- **Audited:** 2026-11-22 UTC
- **Location:** 13276 N Hwy 183 Ste 202, Austin, TX 78750 (HQ in Austin; also serves Hutto, Round Rock, Georgetown, Central TX & regional TX metros)
- **Website:** https://roofroyale.com/
- **Decision Makers:** Tony Schlessinger & Jessica Acosta (Owners / Founders — listed as "Anthony & Jessica" on `/meet-the-team`)
- **Public Contact:** `office@roofroyale.com` | `(512) 379-7933` (and `866-8-ROYALE`) | https://roofroyale.com/contact

## Qualification Gate Verification
1. **Active Local Business:** Veteran-owned, family-operated Texas roofing company headquartered in North Austin with a verified local leadership and advisor team listed on `/meet-the-team`. Not a national franchise.
2. **High-Ticket Fit ($10k+):** Full residential & commercial roof replacements, storm/hail restoration, insurance claims assistance, and roof financing.
3. **Conversion Bottleneck:** Confirmed `has_instant_quote_tool: false` across homepage, `/about`, `/meet-the-team`, and `/contact`. Zero embedded Roofr/Roofle/Hover tools.
4. **Contact Channel:** Public business email (`office@roofroyale.com` in schema/contact), named founders, Austin phone, and dedicated `/contact` page.

## Brand Palette & Typography (Extracted Directly from Live CSS `:root`)
- **Primary Obsidian Charcoal (`--navy-900`):** `#111111` (with `--navy-950: #080808` and `--navy-800: #1C1C1C`)
- **Secondary Signature Gold (`--gold`):** `#BA9B5A`
- **Warm Sand Surface (`--sand`):** `#FAF8F0`
- **Typography:** Display `"Barlow Condensed"`, Body `"Manrope"`
- **Vibe:** High-trust veteran-owned, sleek luxury black-and-gold contractor positioning.

## Observed Technical & Conversion Leaks
- **Mobile Accessibility Penalty:** `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1">` blocks user pinch-to-zoom on mobile devices.
- **High-Friction 8-Field Static Form:** Identical 8-field form (Name, Phone, Email, Property address, Service dropdown, City/ZIP, Notes, Consent checkbox) on both homepage and `/contact` with no placeholders on 7 fields and zero instant quote range.
- **Missed Financing Conversion Hook:** Site advertises "Roof Financing" in top nav, making an instant ballpark + monthly financing preview calculator an immediate CRO win.
- **Asset/Speed Gaps:** 9 of 12 homepage images lack `loading="lazy"`, 7 are JPG/PNG, and 1 script is render-blocking in `<head>`.

## Recommended Trojan Horse MVP (`TYPE_A_ROOFING_CALCULATOR`)
Bespoke obsidian-and-gold (`#111111` / `#BA9B5A`) **"Instant Roof Replacement & Financing Range Calculator"** tailored to Roof Royale's `Barlow Condensed` + `Manrope` typography, letting Austin homeowners estimate total replacement range + monthly financing in 30 seconds before requesting a free inspection.
