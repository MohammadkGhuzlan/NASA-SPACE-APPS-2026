from datetime import date

START, END = date(2019, 1, 1), date(2025, 12, 31)
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
METADATA_URL = "https://power.larc.nasa.gov/api/system/manager/parameters?community=AG&temporal=daily"
WETNESS = "NASA_POWER_WETNESS_FRACTION_NOT_SMAP"
CLIMATE = "NASA_POWER_GRIDDED_NOT_FIELD_SENSOR"
LOCATIONS = {
    "irbid": ("Irbid, Jordan", 32.55696, 35.84790),
    "al_ain": ("Al Ain, Abu Dhabi, UAE", 24.2249, 55.7452),
    "colusa": ("Colusa, California, USA", 39.2146, -122.0094),
    "stuttgart": ("Stuttgart, Arkansas, USA", 34.5004, -91.5526),
}
PARAMETERS = {
    "T2M": ("C", -100, 70), "T2M_MAX": ("C", -100, 80),
    "T2M_MIN": ("C", -100, 70), "PRECTOTCORR": ("mm/day", 0, 3000),
    "RH2M": ("%", 0, 100), "GWETTOP": ("1", 0, 1), "GWETROOT": ("1", 0, 1),
}
WARNINGS = [
    "NASA POWER provides gridded environmental estimates, not precise farm or sensor measurements. Meteorological inputs are approximately 0.5° × 0.625°; local conditions may differ.",
    "2019–2025 is a seven-year historical reference, not a standard 30-year climate normal.",
    "GWETTOP and GWETROOT are dimensionless NASA POWER modeled wetness fractions, not SMAP or volumetric soil moisture.",
    "Temperature thresholds describe heat exposure, not crop damage. Rainfall and modeled wetness do not determine irrigation demand or optimal rotation.",
    "Incomplete aggregates remain missing. Seasonal groups are calendar quarters DJF/MAM/JJA/SON, not locally defined growing seasons.",
]
SOIL_NOTICE = "These soil properties are modeled estimates from a nearby location. They have not been measured or validated for your specific farm. Actual soil conditions may differ."


def location_key(lat, lon):
    # No guessed grid-cell boundary or nearest-city matching. Cache exact points
    # to five decimal places (~1 m), far finer than POWER meteorological grids.
    return f"{lat:.5f},{lon:.5f}"
