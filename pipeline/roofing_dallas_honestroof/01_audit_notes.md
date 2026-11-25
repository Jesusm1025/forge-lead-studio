# Agent 01 Audit Notes — HonestRoof.com

- **Prospect ID:** `roofing_dallas_honestroof`
- **Location:** Dallas–Fort Worth Metro, TX (operating 60–70+ years since 1954)
- **Website:** https://www.honestroof.com/
- **Decision Maker:** Dennis B. Harrison (President & CEO)
- **Public Contact:** `info@honestroof.com` | `(817) 809-7000` | https://www.honestroof.com/contact-us
- **Brand Tokens (Live CSS):** Primary `#9F0712` (`bg-red-800` / `--color-red-800`), Secondary `#0F172A` (dark slate navy).
- **Conversion Leak:** Confirmed `has_instant_quote_tool: false`. Positioning centers on transparent, honest pricing by the square, yet homeowners hit a static 9-field form asking for full address, city, state, ZIP, email, and phone blind. 317 KB HTML payload + 1 render-blocking `<head>` script.
- **Offer Anchor:** $750 setup + $149/mo retainer for a DFW Instant Roof & Hail Replacement Estimator.
