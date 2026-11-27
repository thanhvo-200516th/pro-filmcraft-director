#!/usr/bin/env python3
"""style_profile — nạp hồ sơ phong cách tuỳ chọn (P6–P12 'minimal-edu') cho mọi script dùng chung.

Bật hồ sơ: ghi `<thư mục work>/profile.json` = {"profile": "minimal-edu"} (chỉ khi người dùng gọi tên kiểu
minimal / Brooks / Joseph). Không có file → None → mọi script giữ hành vi mặc định (luật chung không đổi).

    from style_profile import load, active
    prof = load(spec_path)          # dict thông số (references/<tên>-style.json) hoặc None
    if active(prof, "minimal-edu"): ...
"""
from __future__ import annotations

import json
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "references"
KNOWN = {"minimal-edu": REF / "minimal-edu-style.json"}


def _profile_file(path: str | Path | None) -> Path | None:
    """Tìm profile.json cạnh file spec / trong thư mục work được chỉ ra."""
    if path is None:
        return None
    p = Path(path)
    for d in ([p] if p.is_dir() else [p.parent]):
        f = d / "profile.json"
        if f.is_file():
            return f
    return None


def load(path: str | Path | None = None, name: str | None = None) -> dict | None:
    """Trả thông số hồ sơ đang bật, hoặc None. `name` ép tên hồ sơ (bỏ qua profile.json)."""
    if name is None:
        f = _profile_file(path)
        if f is None:
            return None
        try:
            name = json.loads(f.read_text(encoding="utf-8")).get("profile")
        except (OSError, ValueError) as e:
            raise SystemExit(f"profile.json hỏng ({f}): {e}")
        if not name:
            return None
    src = KNOWN.get(name)
    if src is None:
        raise SystemExit(f"hồ sơ lạ '{name}' — có: {', '.join(sorted(KNOWN))}")
    return json.loads(src.read_text(encoding="utf-8"))


def active(prof: dict | None, name: str) -> bool:
    return bool(prof) and prof.get("name") == name


def get(prof: dict | None, dotted: str, default=None):
    """Lấy thông số theo đường chấm, vd get(prof, 'cuts.cut_lead_max_s', 0.09)."""
    cur = prof
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
