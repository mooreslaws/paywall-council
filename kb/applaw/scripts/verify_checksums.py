#!/usr/bin/env python3
"""Write or verify SHA256SUMS.txt for a portable package."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from _kb import print_result, resolve_kb_root


MANIFEST = "SHA256SUMS.txt"
LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def package_files(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.rglob("*") if p.is_file() and p.name != MANIFEST and p.suffix != ".pyc" and "__pycache__" not in p.parts),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def package_symlinks(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_manifest(root: Path) -> int:
    links = package_symlinks(root)
    if links:
        return print_result(
            "Checksum verification",
            [
                f"refusing to hash symlink: {path.relative_to(root).as_posix()}"
                for path in links
            ],
            [],
        )
    lines = [f"{digest(path)}  {path.relative_to(root).as_posix()}" for path in package_files(root)]
    (root / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST}: {len(lines)} entries")
    return 0


def verify_manifest(root: Path) -> int:
    issues: list[str] = []
    warnings: list[str] = []
    for link in package_symlinks(root):
        issues.append(f"package contains symlink: {link.relative_to(root).as_posix()}")
    path = root / MANIFEST
    if not path.is_file():
        return print_result("Checksum verification", [f"missing {MANIFEST}"], [])
    entries: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = LINE_RE.fullmatch(line)
        if not match:
            issues.append(f"{MANIFEST}:{number}: malformed entry")
            continue
        expected, rel = match.groups()
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or "\\" in rel:
            issues.append(f"{MANIFEST}:{number}: unsafe or non-portable path: {rel}")
            continue
        if rel in entries:
            issues.append(f"{MANIFEST}:{number}: duplicate path: {rel}")
            continue
        entries[rel] = expected

    actual_paths = {p.relative_to(root).as_posix(): p for p in package_files(root)}
    for rel in sorted(set(entries) - set(actual_paths)):
        issues.append(f"manifest references missing file: {rel}")
    for rel in sorted(set(actual_paths) - set(entries)):
        issues.append(f"file missing from manifest: {rel}")
    for rel in sorted(set(entries) & set(actual_paths)):
        if digest(actual_paths[rel]) != entries[rel]:
            issues.append(f"checksum mismatch: {rel}")
    warnings.append(f"checksum summary: {len(entries)} manifest entries, {len(actual_paths)} package files")
    return print_result("Checksum verification", issues, warnings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    if Path.cwd().resolve() != root.resolve():
        return print_result("Checksum verification", ["run checksum operations from the package root"], [])
    return write_manifest(root) if args.write else verify_manifest(root)


if __name__ == "__main__":
    raise SystemExit(main())
