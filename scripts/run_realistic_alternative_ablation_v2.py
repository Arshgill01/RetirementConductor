#!/usr/bin/env python3
"""Run or verify the frozen CP-03 realistic-alternative comparison."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.realistic_alternative_ablation import (  # noqa: E402
    load_object,
    run_foundation_matrix,
    verify_public_evidence,
)
from scripts.realistic_alternative_ablation_oracle import (  # noqa: E402
    oracle_digest,
    verify_frozen_protocol,
)

PROTOCOL = ROOT / "fixtures/realistic-alternative-ablation-v2/FROZEN.json"
PUBLIC = ROOT / "artifacts/public/realistic-alternative-ablation-v2"
RAW = ROOT / ".retirement-conductor/cp03-realistic-ablation/raw-run.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify-freeze", "run", "verify"))
    args = parser.parse_args()
    if args.action == "verify-freeze":
        protocol = load_object(PROTOCOL)
        verify_frozen_protocol(protocol)
        print(
            f"Frozen protocol verified: {len(protocol['scenarios'])} scenarios; "
            f"{protocol['frozen_digest']}; oracle={oracle_digest(protocol)}"
        )
        return 0
    if args.action == "run":
        index = run_foundation_matrix(PROTOCOL, public_root=PUBLIC, raw_path=RAW)
        print(
            f"{index['classification']}: recommendation={index['recommendation']} "
            f"index={index['index_digest']}"
        )
        return 0
    index = verify_public_evidence(PROTOCOL, PUBLIC)
    print(
        f"Public evidence verified: {index['classification']} "
        f"recommendation={index['recommendation']} index={index['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
