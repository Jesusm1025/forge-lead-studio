# Agent 01 Audit Notes — Buddy's Roofing & Repairs, Inc.

- **Prospect ID:** `roofing_tampa_buddys-roofing`
- **Audited:** 2026-11-22 UTC
- **Location:** Tampa Bay Metro — Office at 12933 Thonotosassa Road, Dover, FL 33527 (actively targets Tampa, Brandon, Carrollwood, Apollo Beach, Plant City & Hillsborough County)
- **Website:** https://buddysroofing.com/
- **Decision Maker:** Buddy Cheaves (Owner & President — verified on `/meet-our-team.html`)
- **Public Contact:** `info@buddysroofing.com` | `(813) 690-3296` (hero/CTA line) & `(813) 982-0218` (main office) | https://buddysroofing.com/contact.html

## Qualification Gate Verification
1. **Active Local Business:** Multi-decade family-owned Tampa Bay roofing contractor founded in 1994 (37+ years roofing experience, 126+ 5-star reviews across platforms, direct-hire crews — zero subcontractors). Not a national franchise.
2. **High-Ticket Fit ($10k+):** Full residential & commercial roof replacements across Shingle, Metal, Clay Tile, Flat, TPO, PVC, and Built-Up systems, plus Wind Mitigation Inspections and Storm/Insurance claim support.
3. **Conversion Bottleneck:** Confirmed `has_instant_quote_tool: false` across homepage, `/about.html`, `/meet-our-team.html`, and `/contact.html`. Zero embedded calculators or instant quoting tools.
4. **Contact Channel:** Public business email (`info@buddysroofing.com`), named Owner & President on site, phone numbers, and dedicated `/contact.html`.

## Brand Palette (Extracted Directly from Live `brand.css` & `styles.css`)
- **Primary Brand Crimson (`--accent` / `--logo-mark`):** `#B20000` (hover `#A0100B`)
- **Secondary Deep Slate Navy (`--ink`):** `#102B35` (dark charcoal `#090C0B` in `brand.css`)
- **Call Accent Green (`.header-call-icon`):** `#33A867`
- **Soft Accent Tint (`--accent-soft`):** `#F0D2CA`
- **Vibe:** Heritage 37-year family-owned Tampa contractor; clean, trustworthy, direct-hire craftsmanship.

## Observed Technical & Conversion Leaks
- **Zero Homepage Lead Form:** Homepage has `0` `<form>` elements. Every "Book service online" button redirects visitors off the homepage to `/contact.html` into a static 7-field form (`Full name`, `Phone`, `Email`, `ZIP`, `Service address`, `Desired service`, `Notes`) with zero ballpark pricing.
- **Image Optimization & Accessibility Gaps:** Header logo serves a massive `1395x1117` PNG (`/media/d5d1053f85b43589.png`) with `alt=""`; 13 of 23 homepage images have empty/missing `alt` text; 6 images lack `loading="lazy"`.
- **Geo-Copy & Phone Inconsistency:** Hero targets "Tampa, FL", while service cards immediately below repeat "in Dover", and contact details split across two different 813 numbers (`(813) 690-3296` vs `(813) 982-0218`).

## Recommended Trojan Horse MVP (`TYPE_A_ROOFING_CALCULATOR`)
Embeddable Tampa Bay **"Instant Roof Replacement & Hurricane-Ready Material Estimator"** matched to `#B20000` / `#102B35` covering Florida's core roof systems (Architectural Shingle, Standing Seam Metal, Clay/Concrete Tile, Commercial Flat/TPO) + Wind Mitigation insurance-savings note directly on the homepage—turning passive visitors into pre-qualified Tampa inspection bookings.
