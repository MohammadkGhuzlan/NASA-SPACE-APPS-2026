# Durable final-test reservations

The recovery runner writes a small `reservation-<identity>.json` here **before**
any final-test prediction. These files are scientific evidence and belong in
version control with evaluation reports, unlike the large raw research cache.

Do not delete or edit a reservation to rerun a test, change a dataset hash,
change an output directory, change a split seed or recover from a crash.
An aborted reservation requires an explicit audited scientific recovery
decision. Preserve these files when moving research workspaces.

No genuine final holdout had been consumed when this ledger was introduced.
Synthetic software tests always use temporary ledger directories.
