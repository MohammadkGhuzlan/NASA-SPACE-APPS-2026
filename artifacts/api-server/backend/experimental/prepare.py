"""Worker subprocess, so source acquisition has a hard wall-clock limit."""
import argparse
import signal
from pathlib import Path

from ..machine_learning.common import write_json
from ..machine_learning.farm_inputs import prepare_location
from ..machine_learning.budget import ResearchBudget
from .inputs import allow_soil_estimates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--crop", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-estimated-inputs", action="store_true")
    args = parser.parse_args()
    # Also bound an orphaned worker if a dev-server restart kills its parent.
    signal.alarm(295)
    root = Path("generated-artifacts/ml-recovery")
    budget = ResearchBudget(root, seconds=300, max_bytes=1_610_612_736)
    result = prepare_location(args.latitude, args.longitude, args.crop, "LRLM",
        root / "environment", budget=budget)
    result = allow_soil_estimates(result, root / "environment",
                                 allow=args.allow_estimated_inputs, budget=budget)
    write_json(args.output, result)
