# SPDX-License-Identifier: Apache-2.0
"""Validate resource-session claims. Print counts/diagnostic codes only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.claim_provenance_resource_20261003 import (FORBIDDEN_PARTS, ProvenanceError, safe_source_path, strict_json_loads, validate_provenance)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--provenance", required=True, help="Workspace-relative manuscript CLAIM_PROVENANCE JSON")
    parser.add_argument("--receipt", help="Optional new workspace-relative results JSON; refuses overwrite")
    args = parser.parse_args()
    try:
        source = safe_source_path(args.root, args.provenance)
        document = strict_json_loads(source.read_text(encoding="utf-8-sig"))
        receipt = validate_provenance(document, args.root)
    except (ProvenanceError, OSError, UnicodeError):
        receipt = {"valid": False, "claims_total": 0, "claims_verified": 0, "errors": [{"claim_index": None, "code": "provenance_input_unreadable_or_forbidden"}]}
    receipt["validated_utc"] = datetime.now(timezone.utc).isoformat()
    if args.receipt:
        relative = Path(args.receipt)
        root = args.root.resolve()
        target = root / relative
        if relative.is_absolute() or ".." in relative.parts or any(part.casefold() in FORBIDDEN_PARTS or part.startswith(".") for part in relative.parts) or "\\" in args.receipt or ":" in args.receipt or not relative.parts or relative.parts[0] != "results" or target.suffix != ".json" or target.exists() or not target.resolve().is_relative_to(root):
            print(json.dumps({"valid": False, "errors": [{"claim_index": None, "code": "receipt_path_unsafe_or_existing"}]}))
            return 2
        if any(root.joinpath(*relative.parts[:index]).is_symlink() or (hasattr(Path, "is_junction") and root.joinpath(*relative.parts[:index]).is_junction()) for index in range(1, len(relative.parts) + 1)):
            print(json.dumps({"valid": False, "errors": [{"claim_index": None, "code": "receipt_link_requires_review"}]}))
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
