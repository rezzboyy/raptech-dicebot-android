"""Parse metadata komentar di top-of-file strategy Lua.

Format yang didukung (longgar):

  --[[
  @name       Martingale Conservative
  @author     Raptech
  @recommend  BTC, DOGE | balance >= 0.0001
  @desc       Doubles after 3 consecutive losses
  @tag        dice cautious
  ]]

Atau baris-baris single-line:

  -- @name Martingale Conservative
  -- @desc Single line description

Caller pakai untuk menampilkan preview di strategy picker.
File tanpa metadata return StrategyMeta dengan field kosong.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StrategyMeta:
    name: str = ""
    author: str = ""
    desc: str = ""
    recommend: str = ""
    tags: tuple[str, ...] = ()


_TAG_RE = re.compile(r"@(\w+)\s+(.+?)\s*$", re.MULTILINE)


def parse_strategy_meta(path: Path) -> StrategyMeta:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return StrategyMeta()

    # Ambil hanya bagian top: sampai --[[]] block pertama selesai, atau
    # 30 baris pertama (whichever shorter), supaya kita tidak men-scan
    # seluruh strategy.
    head = "\n".join(text.splitlines()[:60])
    block_match = re.search(r"--\[\[(.+?)\]\]", head, re.DOTALL)
    if block_match:
        meta_text = block_match.group(1)
    else:
        # Coba kumpulkan single-line `-- @key value`
        meta_text = "\n".join(
            line for line in head.splitlines() if line.lstrip().startswith("--")
        )

    fields: dict[str, str] = {}
    for m in _TAG_RE.finditer(meta_text):
        key = m.group(1).lower().strip()
        value = m.group(2).strip()
        if key in fields:
            fields[key] = fields[key] + " " + value
        else:
            fields[key] = value

    tags_raw = fields.get("tag") or fields.get("tags") or ""
    tags = tuple(t.strip() for t in re.split(r"[\s,]+", tags_raw) if t.strip())

    return StrategyMeta(
        name=fields.get("name", ""),
        author=fields.get("author", ""),
        desc=fields.get("desc") or fields.get("description", ""),
        recommend=fields.get("recommend", ""),
        tags=tags,
    )
