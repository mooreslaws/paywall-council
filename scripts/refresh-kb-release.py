#!/usr/bin/env python3
"""Refresh the KB release artifacts after editing KB content.

Any edit inside kb/applaw invalidates three derived values, and the
KB then fails validation with stale-digest errors that say nothing about what
you actually changed:

  * RELEASE_PROFILE.json case_semantic_sha256  (aggregate over case cards)
  * RELEASE_PROFILE.json package file/byte counts
  * SHA256SUMS.txt                             (per-file manifest)

This recomputes all three with the KB's own helpers, so the values can never
drift from what the validators expect. Run it from anywhere:

    python3 -B scripts/refresh-kb-release.py
    python3 -B kb/applaw/scripts/validate_core.py --kb kb/applaw
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "kb" / "applaw"
sys.path.insert(0, str(KB / "scripts"))

import validate_refs  # noqa: E402
import verify_checksums  # noqa: E402
from _kb import artifact_semantic_aggregate, case_card_records  # noqa: E402


def main() -> int:
    profile_path = KB / "RELEASE_PROFILE.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    before = dict(profile)

    profile["case_semantic_sha256"] = artifact_semantic_aggregate(case_card_records(KB))
    file_count, byte_count = validate_refs.package_totals(KB)
    profile["package_file_count_before_checksum"] = file_count
    profile["package_bytes_before_checksum"] = byte_count

    changed = {k: (before.get(k), v) for k, v in profile.items() if before.get(k) != v}
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for key, (old, new) in changed.items():
        print(f"RELEASE_PROFILE.{key}: {old} -> {new}")
    if not changed:
        print("RELEASE_PROFILE.json already current")

    # write_manifest prints its own summary line and returns an exit status.
    return verify_checksums.write_manifest(KB)


if __name__ == "__main__":
    sys.exit(main())
