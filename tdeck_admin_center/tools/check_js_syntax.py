#!/usr/bin/env python3
"""Local JavaScript syntax gate for Admin Center frontend assets."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def check_with_node(target: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["node", "--check", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, ""
    detail = (result.stderr or result.stdout or "node --check failed").strip()
    return False, detail


def check_with_esprima(target: Path) -> tuple[bool, str]:
    try:
        import esprima  # type: ignore
    except Exception as err:  # pragma: no cover - env dependent
        return False, f"esprima unavailable: {err}"

    try:
        source = target.read_text(encoding="utf-8")
        esprima.parseScript(source, tolerant=False)
        return True, ""
    except Exception as err:  # pragma: no cover - parser-specific
        return False, str(err)


def check_with_quickjs(target: Path) -> tuple[bool, str]:
    try:
        import quickjs  # type: ignore
    except Exception as err:  # pragma: no cover - env dependent
        return False, f"quickjs unavailable: {err}"

    try:
        source = target.read_text(encoding="utf-8")
        ctx = quickjs.Context()
        # Parse-only gate: new Function compiles the source without executing it.
        ctx.eval(f"new Function({json.dumps(source)});")
        return True, ""
    except Exception as err:  # pragma: no cover - parser-specific
        return False, str(err)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check JavaScript syntax for one or more files.")
    parser.add_argument("targets", nargs="+", help="JS files to validate.")
    args = parser.parse_args()

    failures: list[str] = []
    node_path = shutil.which("node")
    parser_name = "node" if node_path else "quickjs"

    for raw in args.targets:
        target = Path(raw).resolve()
        if not target.exists():
            failures.append(f"{target}: file not found")
            continue
        if node_path:
            ok, detail = check_with_node(target)
        else:
            ok, detail = check_with_quickjs(target)
            if not ok:
                parser_name = "esprima"
                ok, detail = check_with_esprima(target)
        if ok:
            print(f"[ok] {target}")
        else:
            failures.append(f"{target}: {detail}")

    if failures:
        print(f"[error] JS syntax gate failed using {parser_name}.", file=sys.stderr)
        for item in failures:
            print(f" - {item}", file=sys.stderr)
        if not node_path:
            print("Install Node.js (preferred) or python quickjs/esprima to run this gate.", file=sys.stderr)
        return 1

    print(f"[ok] JS syntax gate passed using {parser_name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
