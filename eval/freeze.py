"""Write eval/holdout.jsonl from current presets. Run once, then stop touching it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presets import PRESETS  # noqa: E402

OUT = Path(__file__).resolve().parent / "holdout.jsonl"


def rows() -> list[dict]:
    out = [fn(0) for fn in PRESETS.values()]
    if "missing_file" in PRESETS:
        out.append(PRESETS["missing_file"](1))
        out.append(PRESETS["missing_file"](2))
    for row in out:
        row["split"] = "holdout"
    return out


def main() -> int:
    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows()) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(rows())} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
