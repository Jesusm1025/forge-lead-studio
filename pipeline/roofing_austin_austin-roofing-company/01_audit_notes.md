# Agent 01 Audit Notes — Austin Roofing Company LLC

- **Prospect ID:** `roofing_austin_austin-roofing-company`
- **Audited:** 2026-11-22 UTC
- **Location:** 12430 Metric Blvd Suite 2205, Austin, TX 78758 (serves Austin, Round Rock, Cedar Park, Pflugerville, Georgetown)
- **Website:** https://austinroofingcompany.us/
- **Decision Maker:** Abraham Ron (Owner)
- **Public Contact:** `info@austinroofingcompany.us` | `(512) 952-7454` | https://austinroofingcompany.us/contact/

## Qualification Gate Verification
1. **Active Local Business:** Family-owned independent Austin contractor operating since 2007 (19+ years, 1,478+ roofs serviced, 831+ inspections listed on `/about/`). Not a national franchise.
2. **High-Ticket Fit ($10k+):** Full residential & commercial roof replacements across Asphalt Shingle, Metal, Clay Tile, Solar Roofing, Built-Up, Modified Bitumen, and Single-Ply systems, plus Hail & Storm Damage restoration.
3. **Conversion Bottleneck:** Confirmed `has_instant_quote_tool: false` across homepage, `/about/`, and `/contact/`. Zero Roofr, Roofle, Hover, or custom calculators present.
4. **Contact Channel:** Verified public email, phone, named owner, and live contact page.

## Brand Palette (Extracted Directly from Live CSS)
- **Primary Navy (`--arc-content-navy`):** `#08295B`
- **Secondary CTA Gold (`--arc-feed-gold` / `--arc-nav-yellow`):** `#FFCC16`
- **Supporting Brand Blue (`--arc-content-blue`):** `#2F95CE`
- **Dark Hover Navy (`--arc-post-navy-dark`):** `#061F47`
- **Vibe:** Established family-owned Austin roofer; clean navy/gold authority aesthetic.

## Observed Technical & Conversion Leaks
- **Heavy & Slow Initial Load:** `1,935 ms` response time and `419,343 bytes` (419 KB) HTML payload on homepage, with overlapping WordPress/Elementor/Divi footprints and 1 render-blocking `<head>` script.
- **Image Bloat & SEO Gaps:** 58 images on homepage; 33 are unoptimized JPG/PNG and 18 lack descriptive `alt` text.
- **High-Friction Blind Lead Capture:** Clicking "Free Estimate" opens a WordPress Forminator modal (`forminator-module-2859`, initially `display: none` until JS loads) asking immediately for Name, Phone, and Street Address with zero price range, material selector, or qualification flow. `/contact/` adds Date/Time pickers (`forminator-module-2222`) without giving homeowners any cost expectation first.

## Recommended Trojan Horse MVP (`TYPE_A_ROOFING_CALCULATOR`)
Embeddable, zero-bloat (<30KB) **"Austin Instant Roof Cost & Hail-Upgrade Estimator"** styled in `#08295B` / `#FFCC16` / `#2F95CE` covering Austin's top materials (Asphalt Shingle, Standing Seam Metal, Clay Tile, Class 4 Impact-Resistant) with instant ballpark range + monthly financing preview before capturing name/phone/address.
