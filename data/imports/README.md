# Original environmental inputs

These four CSVs were extracted unchanged from the user-supplied archive. Do not edit them to fix validation findings. The importer compares existing bytes before extraction and refuses to overwrite a changed original. SHA-256 hashes are kept in database ingestion reports.

- `nasa_daily.csv`: 10,228 location-days; five climate parameters. Coordinates are supplied by the project brief, not embedded in this file. Units are mapped from official NASA POWER parameter definitions, checked on 2026-11-14.
- `nasa_monthly.csv`: 336 location-months; used only to cross-check daily-derived statistics. Means use 0.0011 tolerance and precipitation totals 0.011 mm; hot-day comparison is strict `>35°C`.
- `nasa_soil_moisture_daily.csv`: 10,228 location-days. `GWETTOP/GWETROOT` are modeled fractions, explicitly **not SMAP**. `SFMC/RZMC` columns exist but are empty and are not imported as observations.
- `soilgrids_0_5cm_aligned.csv`: four nearby modeled soil proxies with original and sampled coordinates. `PROXY_DEMO_ONLY`; never farm measurements or training labels.

NASA reference: https://power.larc.nasa.gov/api/system/manager/parameters?community=AG&temporal=daily

Official units: T2M/T2M_MAX/T2M_MIN `C`; PRECTOTCORR `mm/day`; RH2M `%`; GWETTOP/GWETROOT `1` (0–1). These are source-definition mappings, not proof of the uploaded climate file's original metadata. Climate time standard and original retrieval dates were not provided. Wetness query URLs specify UTC.

Known input issue: Al Ain's reported offset is **7.073 km**; the supplied coordinates imply **approximately 6.451 km** by haversine. Both are retained in the database, with `distance_discrepancy` quality status.
