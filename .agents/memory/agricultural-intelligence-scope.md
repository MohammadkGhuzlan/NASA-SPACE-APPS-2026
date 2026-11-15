---
name: Agricultural intelligence scope
description: User-defined product objective and sequencing beyond environmental dashboards.
---

Field Shift's intended product is evidence-based agricultural decision support, not just environmental charts or generic chatbot answers. Preserve the existing interface, global map, database, profiles and NASA integration.

**Why:** The user's core architecture clarification explicitly requires practical crop candidates, planting/harvesting windows, current rotation plus two alternatives, and referenced agricultural management advice.

**How to apply:** Finish environmental integration in Phase 2; build verified agricultural knowledge and a separate rule-based planning engine in Phase 3; perform reproducible supervised training and independent validation in Phase 4; add validated environmental-similarity coverage and uncertainty reporting in Phase 5. Do not train on farmer requests.

The initial supervised target is consistent, verified FAO GAEZ crop-suitability assessments, not yield or soil-health outcomes. Preserve preprocessing pipelines and model metadata. Reference-based planning rules and trained predictions must remain distinguishable.

**Why:** Suitability labels do not establish actual yield or management benefits, and geographic proximity alone does not establish validated model coverage.

**How to apply:** Use actual selected-coordinate environmental data and comparable feature structures for training/inference. Only emit supported prediction, similar-region estimate or insufficient evidence when the implemented coverage assessment justifies that status. Never invent confidence numbers. Preserve source and reliability for farmer inputs, including desired season and operational constraints.

Published FAO GAEZ evidence is a separate decision-support workstream that may operate without an accepted Field Shift ML model. It does not replace the existing agricultural rules, future harvest-yield prediction, or future weather forecasting.

**Why:** The user's GAEZ brief explicitly rejects using failed model candidates just to appear AI-powered, while requiring useful source-backed assessments now. Suitability assessments are not observed farm outcomes.

**How to apply:** Keep published FAO assessments and Field Shift model predictions in distinct source lanes. Do not treat agreement as independent validation if a future model learned from the same FAO data. Show scenario and source-period differences rather than inventing corrections, and leave yield/forecast work on its separate roadmap.
