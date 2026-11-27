#!/usr/bin/env python3
"""
Vietnamese glyph coverage of the font chain in `presets/dviet_style_tokens.json` -> `fonts.roles` (references/26_dviet_fonts.md).

For every role flagged `vietnamese: true`, each installed font of its chain (primary + fallbacks) must carry ạ ầ ữ ơ ư ẫ ẳ ỡ đ.
A font that is not installed is SKIPPED (never failed); a font that IS installed and routed Vietnamese text but lacks a glyph FAILS.
Roles flagged `vietnamese: false` (English labels only) must not route Vietnamese text, and the banned Anton / Bebas fonts must not
appear anywhere in the chain or in `scripts/env_status.py`'s fallbacks. Resolution uses `fc-match` (+ its charset); no font is copied.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOKENS = SKILL_ROOT / "presets" / "dviet_style_tokens.json"
VI_SAMPLE = "ạ ầ ữ ơ ư ẫ ẳ ỡ đ"
VI_CODEPOINTS = sorted({ord(c) for c in unicodedata.normalize("NFC", VI_SAMPLE) if not c.isspace()})
BANNED = ("anton", "bebas")
CREATOR_STATED = {("SF Pro Display", "Regular"), ("Playfair Display", "Italic"), ("Whisper", "Regular")}
SKILL_PRESET = {"SVN-Aaron Script", "DFVN West West Condensed", "LigaSFMono"}


def _roles() -> dict:
    return json.loads(TOKENS.read_text(encoding="utf-8"))["fonts"]["roles"]


def _chain(role: dict) -> list[dict]:
    return [role["primary"], *role["fallbacks"]]


def _parse_charset(text: str) -> set[int]:
    cps: set[int] = set()
    for part in text.split():
        lo, _, hi = part.partition("-")
        cps.update(range(int(lo, 16), int(hi or lo, 16) + 1))
    return cps


def resolve(family: str, style: str) -> dict | None:
    """Installed font for family+style via fc-match, or None. fc-match always answers with *something*, so the family must match."""
    out = subprocess.run(["fc-match", "-f", "%{family}|%{style}|%{file}|%{charset}", f"{family}:style={style}"],
                         capture_output=True, text=True, timeout=30, check=False).stdout
    fam, sty, file, charset = (out.split("|", 3) + ["", "", "", ""])[:4]
    names = {n.strip().lower() for n in fam.split(",")}
    if family.lower() not in names or not file:
        return None
    return {"file": file, "style": sty, "charset": _parse_charset(charset)}


def test_tokens_chain_shape_and_provenance() -> None:
    roles = _roles()
    assert {"lead_sans", "hero_sans", "hero_condensed", "serif_accent", "hero_script", "mono"} <= set(roles)
    stated = set()
    for name, role in roles.items():
        assert isinstance(role["vietnamese"], bool) and isinstance(role["fallbacks"], list) and role["fallbacks"], name
        for ent in _chain(role):
            assert ent["family"] and ent["style"] and ent["provenance"], (name, ent)
            assert not any(b in ent["family"].lower() for b in BANNED), f"{name}: banned font {ent['family']} (references/04)"
            if ent["provenance"] == "creator-stated":
                stated.add((ent["family"], ent["style"]))
            if ent["family"] in SKILL_PRESET:
                assert ent["provenance"] == "skill-preset, no evidence", (name, ent)
    assert stated == CREATOR_STATED, f"creator-stated must be exactly SF Pro Display Regular + Playfair Display Italic + Whisper Regular, got {stated}"
    cond = [e["family"] for e in _chain(roles["hero_condensed"])]
    assert "Barlow Condensed" in cond and cond.index("Barlow Condensed") < cond.index("Be Vietnam Pro")
    inter = next(e for e in roles["lead_sans"]["fallbacks"] if e["family"] == "Inter")
    assert inter["provenance"] == "free stand-in"
    jb = next(e for e in roles["mono"]["fallbacks"] if e["family"] == "JetBrains Mono")
    assert jb["provenance"] == "free stand-in"
    assert not any(e["family"] == "Instrument Serif" for r in roles.values() if r["vietnamese"] for e in _chain(r)), \
        "Instrument Serif has 2/90 Vietnamese glyphs: English labels only"
    spec = roles["specimen_serif_en"]
    assert spec["vietnamese"] is False and "English labels only" in spec["primary"]["note"]
    doc = json.loads(TOKENS.read_text(encoding="utf-8"))
    assert "font_roles" in doc and "caption" in doc["font_roles"], "the fonts chain is additive: font_roles must remain"
    print("[PASS] tokens: fonts chain shape, provenance tags and bans")


def test_env_status_fallbacks_match_the_chain() -> None:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))
    import env_status
    fb = env_status.FONT_FALLBACKS
    assert fb["DFVN West West Condensed"].startswith("Barlow Condensed"), "the recommended fallback must be Barlow Condensed, not Anton/Bebas"
    for fam in ("Whisper", "Arimo", "Instrument Serif"):
        assert fam in fb, fam
    assert "english labels only" in fb["Instrument Serif"].lower() or "2/90" in fb["Instrument Serif"]
    print("[PASS] env_status: DFVN fallback is Barlow Condensed (no Anton/Bebas), Whisper/Arimo/Instrument Serif listed")


def test_vietnamese_glyph_coverage() -> None:
    if not shutil.which("fc-match"):
        print("[SKIP] glyph coverage: fc-match not installed")
        return
    roles = _roles()
    checked, skipped, failures = [], [], []
    for name, role in roles.items():
        if not role["vietnamese"]:
            continue
        for ent in _chain(role):
            label = f"{name}: {ent['family']} {ent['style']}"
            font = resolve(ent["family"], ent["style"])
            if font is None:
                skipped.append(label)
                continue
            missing = [chr(cp) for cp in VI_CODEPOINTS if cp not in font["charset"]]
            (failures if missing else checked).append(f"{label} -> {Path(font['file']).name} missing {missing}" if missing else label)
    for s in skipped:
        print(f"[SKIP] not installed: {s}")
    assert not failures, "fonts routed Vietnamese text but lack glyphs:\n  " + "\n  ".join(failures)
    assert checked or skipped, "no font was examined"
    print(f"[PASS] Vietnamese glyphs ({VI_SAMPLE}): {len(checked)} installed font(s) complete, {len(skipped)} skipped as absent")


def test_non_vietnamese_roles_are_really_english_only_or_complete() -> None:
    """A role marked `vietnamese: false` is allowed to lack glyphs; Instrument Serif must indeed lack them (else the flag is stale)."""
    if not shutil.which("fc-match"):
        print("[SKIP] english-only roles: fc-match not installed")
        return
    font = resolve("Instrument Serif", "Regular")
    if font is None:
        print("[SKIP] Instrument Serif not installed")
        return
    missing = [chr(cp) for cp in VI_CODEPOINTS if cp not in font["charset"]]
    assert missing, "Instrument Serif now covers the Vietnamese sample: update references/26 and the `vietnamese` flag"
    print(f"[PASS] Instrument Serif lacks {len(missing)}/{len(VI_CODEPOINTS)} sample glyphs: English labels only is still right")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (fonts_vi v7.4.0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
