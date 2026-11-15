---
name: Scientific source boundaries
description: User-required scientific interpretation constraints for future Field Shift phases.
---

Keep environmental estimates, farmer assertions, verified outcomes and training labels conceptually separate, even when an input is chosen in preference to another source.

**Why:** The Phase 2 brief explicitly prioritizes scientific integrity over complete-looking dashboards. POWER wetness must not become SMAP, nearby SoilGrids proxies must not become farm ground truth, and a farmer's claimed laboratory result must not imply independent verification.

**How to apply:** Future recommendation or model work must preserve the original evidence and its uncertainty. Missing source metadata does not become verified merely because values pass physical screening. Do not silently switch scientific products or create suitability labels from environmental inputs.

Do not assume a SoilGrids WCS GeoTIFF preserves the native missing-value mask.

**Why:** Inspected official WCS subsets returned integer pixels with no GeoTIFF NoData tag and empty coverage nilValues, while the native WebDAV VRT explicitly declared a missing-value sentinel. Treating those untagged zeros as soil measurements would silently change the evidence.

**How to apply:** Recheck the actual response metadata. Reject ambiguous masks; use documented native VRT/tile masks or an independently verified equivalent instead of guessing that zero is either valid or missing. HTTP 200 and plausible average values are not sufficient validation.

Keep raw response integrity separate from scientific feature agreement when
reacquiring provider data.

**Why:** NASA POWER responses can contain runtime timing metadata. Re-requested
raw hashes differed during recovery even though a saved feature example and
the original pooled validation results were numerically reproduced. Missing
original raw bytes prevent attributing every byte difference to timing alone.

**How to apply:** Preserve new raw hashes and request/header provenance rather
than pretending original bytes were recovered. Compare actual units, periods,
daily values/features and reproducible model results separately; a differing
payload hash alone neither proves a preprocessing defect nor permits silently
overwriting scientific source identity.
