---
name: Suitability validation decisions
description: Scientific acceptance constraints and reasons for crop/domain scope and independent holdouts.
---

Permit independently justified crop/domain acceptance; do not demand that every
crop pass together, or relax accuracy gates merely to enable the website.

**Why:** The recovery brief explicitly permits limited genuine capabilities and
prioritizes scientific reliability over an apparent activation. Sparse global
sampling can make a worldwide claim infeasible even when a limited claim might
eventually be defensible.

**How to apply:** Declare the deployment population from training/validation
evidence before independent testing. Report unsupported regions explicitly.
Keep the five named demonstration locations as operational checks, not an
independent accuracy benchmark. A missing-model refusal is not estimator
execution; a published FAO lookup is not ML inference.

Keep geographic holdout identity stable when datasets, outputs, feature versions
or random seeds change.

**Why:** A dataset checksum changes when rows or feature metadata change, but
that does not make previously evaluated geography scientifically independent.
Deleting or bypassing a reservation would permit repeated selection against
the same final test.

**How to apply:** Preserve shared reservations with research evidence and
require an audited recovery after crashes. Do not evaluate the test just
because MAE passes if R², baseline improvement or support already fails.

For zero-heavy continuous suitability targets, include a training-only median
constant baseline when MAE is the selection metric.

**Why:** The median is the MAE-optimal constant. Improvement over a mean dummy
can otherwise appear meaningful while being worse than a trivial constant
under the stated loss. This does not justify returning zeros as live predictions.

**How to apply:** Fit baselines only on training folds; report mean and median
comparisons, continuous distributions and source-cell counts rather than
pretending repeated crop rows or zeros are independent classes.

Rejected models may run only in a visibly separate experimental research lane
when explicitly requested; this is not a production acceptance override.

**Why:** The experimental-mode brief explicitly requests genuine numerical
inference from failed candidates while preserving every validation threshold
and the untouched final test.

**How to apply:** Keep production readiness disabled, require complete authentic
training-contract features, display failed-validation and out-of-domain warnings,
and never feed experimental results into agricultural recommendations or normal
saved reports. Operator changes to development access must not expose another
browser workspace's farms or enable production.
