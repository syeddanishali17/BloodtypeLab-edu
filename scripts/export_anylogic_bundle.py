"""Export the AnyLogic docking bundle for a configuration.

Usage:
    python scripts/export_anylogic_bundle.py --out anylogic_bundle [--config my_config.json]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bloodtypelab.anylogic_bridge import export_anylogic_bundle  # noqa: E402
from bloodtypelab.config import SimulationConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "anylogic_bundle")
    args = ap.parse_args()
    cfg = SimulationConfig.from_json(args.config.read_text()) if args.config else SimulationConfig(initial_population=2000, horizon_steps=100)
    folder = export_anylogic_bundle(cfg, args.out)
    print(f"Bundle written to {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
