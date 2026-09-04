import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import gold_recovery, parse_reply
from presets import PRESETS
from sftpack import pack_row


def test_pack_matches_gold_recovery():
    row = PRESETS["missing_file"](0)
    packed = pack_row(row)
    assert packed["messages"][0]["role"] == "system"
    assert packed["messages"][1]["role"] == "user"
    assert packed["messages"][2]["role"] == "assistant"
    user = packed["messages"][1]["content"]
    assert "FAILED_TOOL" in user
    assert "ENOENT" in user or "ERROR" in user or "error" in user.lower()
    pred = parse_reply(packed["messages"][2]["content"])
    tool, args = gold_recovery(row)
    assert pred["tool"] == tool
    assert pred["arguments"] == args
    assert pred["tool"] != packed["meta"]["failed_tool"] or pred["arguments"] != packed["meta"]["failed_args"]


def test_every_preset_packs():
    for name, fn in PRESETS.items():
        packed = pack_row(fn(0))
        pred = parse_reply(packed["messages"][2]["content"])
        assert pred["tool"], name
        json.dumps(packed)
