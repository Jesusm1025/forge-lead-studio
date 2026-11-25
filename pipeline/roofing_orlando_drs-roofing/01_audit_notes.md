# Agent 01 Audit Notes — DRS Roofing (D.R.S. of Central Florida, Inc.)

- **Prospect ID:** `roofing_orlando_drs-roofing`
- **Location:** 6107 Anno Ave., Orlando, FL 32809 (operating since 1995, FL License `CCC-057239`)
- **Website:** https://drs-roofing.com/
- **Decision Maker:** Richard Rao (Owner & President)
- **Public Contact:** `info@drs-roofing.com` | `(407) 240-1225` | https://drs-roofing.com/roofing-estimate/
- **Brand Tokens (Live CSS):** Primary `#B1080B` (crimson red, 55 occurrences), Secondary `#FFCD57` (`--ast-global-color-7` gold).
- **Conversion Leak:** Confirmed `has_instant_quote_tool: false`. Massive 585 KB homepage HTML, 232 images (176 missing `loading="lazy"`, 84 legacy JPG/PNG), and high-friction 14-field `/roofing-estimate/` + 15-field `/contact/` forms with zero instant estimate.
- **Offer Anchor:** $750 setup + $149/mo retainer.
