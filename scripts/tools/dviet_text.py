#!/usr/bin/env python3
"""
dviet_text.py — stateless role planner for @__dviet text (v7.4.0)

Turns a list of role-tagged text events into text tracks, taking every y %, size, font, colour and
entrance from `presets/dviet_style_tokens.json` (nothing is hard-coded here).

    python3 scripts/tools/dviet_text.py --events events.json \
        --tokens presets/dviet_style_tokens.json --out tracks.json

events.json:
{
  "accent": "yellow_bright",                     // optional: name in palette.accents or "#RRGGBB"
  "events": [
    {"role": "caption",       "text": "với hiệu ứng này", "at": 1.0, "dur": 1.2, "layout": "talking"},   // talking | panel | hero
    {"role": "keyword_sans",  "text": "tạo ra",           "at": 2.4, "dur": 0.8},
    {"role": "script_accent", "text": "chuyên nghiệp",    "at": 3.2, "dur": 1.0},
    {"role": "number",        "text": "3",                "at": 4.2, "dur": 1.5},
    {"role": "header",        "text": "bước một",         "at": 6.0, "dur": 2.0},
    {"role": "cta",           "text": "Lưu lại",          "at": 8.5, "dur": 1.5},
    {"role": "bilingual_sub", "text": "video editing is tiring.", "at": 10.0, "dur": 1.5},
    {"role": "lockup_sub",    "text": "mình không",       "at": 12.0, "dur": 2.0},
    {"role": "lockup_hero",   "text": "nổi tiếng",        "at": 12.0, "dur": 0.9},
    {"role": "constellation", "text": "Sợ", "satellites": ["chẳng", "mãi thì", "bao"], "at": 15.0, "dur": 2.5},
    {"role": "font_specimen", "text": "Instrument Serif", "font": "Instrument Serif", "at": 18.0, "dur": 1.5}
  ]
}
Every role accepts `y_pct` (override, % of canvas height) and `accent`.

Out: {"profile", "tokens_version", "canvas", "tracks": [{"name", "clips": [...]}], "warnings": [...]}.
Each clip carries role, text (NFC), at, dur, y_pct, position [x, y] px, size_px, font {family, style, status},
color, entrance {name, dur_s, ...} and lighting.

Rules: text is normalised to NFC; an unknown role or layout is an error; a missing font is a WARNING (printed
to stderr and listed under "warnings"), never an error; fonts banned for Vietnamese by
`visual_archetypes_catalog.json` (`forbidden_fonts_vi`) are rejected unless the role is `font_specimen` and the
token allows that font (decision (b), references/23_dviet_profile_decisions_and_backlog.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parents[1]
DEFAULT_TOKENS = SKILL_ROOT / "presets" / "dviet_style_tokens.json"
ARCHETYPES = SKILL_ROOT / "presets" / "visual_archetypes_catalog.json"

ROLES = (
    "caption", "keyword_sans", "script_accent", "number", "header", "cta",
    "bilingual_sub", "lockup_sub", "lockup_hero", "constellation", "font_specimen",
)
TRACK_NAMES = ("T1 Phụ đề", "T2 Chữ nhỏ", "T3 Chữ lớn", "T4 Chữ nhấn")
LOCKUP_GAP_PX = 6


def nfc(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value))


# ---------------------------------------------------------------------------
# Fonts: reuse the skill's existing resolver (typography_composer), never fail on a missing font
# ---------------------------------------------------------------------------

def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(maxsize=1)
def _resolver():
    """Return the typography_composer module, or None if it cannot be imported (never raises)."""
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        import typography_composer as tc  # type: ignore

        return tc
    except Exception:  # noqa: BLE001 - a broken sibling module must not break this tool
        return None


@lru_cache(maxsize=128)
def _family_file(family: str, style: str) -> str | None:
    """File name of a font that really belongs to `family`, else None (the resolver silently falls back)."""
    tc = _resolver()
    fam_key = _alnum(family)
    if tc is not None:
        try:
            path = Path(tc._resolve_typo_font_path(family, style))
            if fam_key in _alnum(path.stem):
                return path.name
        except (OSError, ValueError, TypeError, ImportError) as exc:
            print(f"WARNING: font resolver failed for {family!r}/{style!r} ({type(exc).__name__}: {exc}); scanning font dirs", file=sys.stderr)
        dirs = list(getattr(tc, "FONT_SEARCH_DIRS", []))
    else:
        dirs = [Path.home() / ".local/share/fonts"]
    sty = style.replace(" ", "")
    names = [f"{family.replace(' ', '')}-{sty}", f"{family.replace(' ', '')}-Variable", f"{family.replace(' ', '')}-Regular",
             family, f"{family}-{sty}"]
    for d in dirs:
        for n in names:
            for ext in (".ttf", ".otf"):
                if (Path(d) / f"{n}{ext}").is_file():
                    return f"{n}{ext}"
    return None


def check_font(family: str, style: str, fallback_family: str, warnings: list[str]) -> dict[str, Any]:
    """Resolve a font for a role. A missing font adds a warning and falls back; it never raises."""
    found = _family_file(family, style)
    if found:
        return {"family": family, "style": style, "status": "ok", "file": found}
    fb = _family_file(fallback_family, style)
    msg = (f"font '{family}' ({style}) not found; falling back to '{fallback_family}'"
           if fb else f"font '{family}' ({style}) and fallback '{fallback_family}' not found; the renderer will use its default")
    if msg not in warnings:
        warnings.append(msg)
    return {"family": fallback_family, "requested_family": family, "style": style,
            "status": "fallback" if fb else "missing", "file": fb}


@lru_cache(maxsize=1)
def _banned_fonts() -> tuple[str, ...]:
    try:
        data = json.loads(ARCHETYPES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()

    def find(o: Any) -> list[str]:
        if isinstance(o, dict):
            if isinstance(o.get("forbidden_fonts_vi"), list):
                return [str(x) for x in o["forbidden_fonts_vi"]]
            for v in o.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find(v)
                if r:
                    return r
        return []

    return tuple(find(data))


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _color(tokens: dict[str, Any], spec: str, accent_hex: str) -> str:
    pal = tokens["palette"]
    if spec == "accent":
        return accent_hex
    if spec in ("text", "light", "dark"):
        return pal[spec]
    if spec in pal["accents"]:
        return pal["accents"][spec]
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", spec):
        return spec
    raise ValueError(f"unknown colour {spec!r}")


def _accent(tokens: dict[str, Any], name: str | None) -> str:
    acc = tokens["palette"]["accents"]
    if not name:
        return acc[tokens["palette"]["default_accent"]]
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", name):
        return name
    if name not in acc:
        raise ValueError(f"unknown accent {name!r}; known: {', '.join(acc)}")
    return acc[name]


def _entrance(tokens: dict[str, Any], name: str) -> dict[str, Any]:
    anim = tokens["animations"]
    if name not in anim:
        raise ValueError(f"entrance {name!r} is not defined in tokens.animations")
    return {"name": name, **anim[name]}


def _lighting(tokens: dict[str, Any], color: str, mode: str | None) -> dict[str, Any]:
    pol = tokens["shadow_policy"]
    mode = mode or pol["mode"]
    if mode == "halation":
        h = pol["halation"]
        return {"mode": "halation", "radius_px": round(sum(h["radius_px"]) / 2), "intensity_pct": round(sum(h["intensity_pct"]) / 2), "color": color}
    if mode == "drop_shadow":
        d = pol["drop_shadow"]
        return {"mode": "drop_shadow", "color": d["color"], "opacity_pct": d["opacity_pct"], "blur_px": d["blur_px"], "distance_px": d["distance_px"]}
    raise ValueError(f"unknown lighting mode {mode!r}")


class _Planner:
    def __init__(self, tokens: dict[str, Any], accent_name: str | None):
        self.t = tokens
        self.w = int(tokens["canvas"]["w"])
        self.h = int(tokens["canvas"]["h"])
        self.accent_hex = _accent(tokens, accent_name)
        self.warnings: list[str] = []

    # -- y rules, all read from tokens ------------------------------------------------
    def role_y(self, ev: dict[str, Any]) -> float:
        role = ev["role"]
        if "y_pct" in ev and ev["y_pct"] is not None:
            return float(ev["y_pct"])
        cy = self.t["caption_y_pct"]
        tier = self.t["tiers"][role]
        if role == "caption":
            layout = ev.get("layout", "talking")
            if layout not in ("talking", "panel", "hero"):
                raise ValueError(f"caption layout must be talking | panel | hero, got {layout!r}")
            return float(cy[layout]["value"])
        if role == "bilingual_sub":
            return float(cy["bilingual_en"]["value"])
        if "y_pct" in tier:
            return float(tier["y_pct"])
        return float(cy["talking"]["value"])  # chest line for keyword / script / lock-up / constellation

    def font_for(self, role: str, ev: dict[str, Any], satellite: bool = False) -> dict[str, Any]:
        spec = self.t["font_roles"][role]
        family = spec["satellite_family"] if satellite else spec["family"]
        style = spec["satellite_style"] if satellite else spec["style"]
        if role == "font_specimen" and ev.get("font"):
            family = nfc(ev["font"])
        banned = _banned_fonts()
        if family in banned:
            allowed = spec.get("allow_banned_fonts", [])
            text = nfc(ev.get("text", ""))
            if role != "font_specimen" or family not in allowed:
                raise ValueError(f"font {family!r} is banned for Vietnamese text and not allowed for role {role!r}")
            if not text.isascii():
                raise ValueError(f"font {family!r} is only allowed for ASCII font names (role font_specimen), got {text!r}")
        return check_font(family, style, spec.get("fallback_family", "Be Vietnam Pro"), self.warnings)

    def clip(self, role: str, ev: dict[str, Any], text: str, at: float, dur: float, y_pct: float, x_pct: float = 50.0,
             size_px: float | None = None, color_spec: str | None = None, entrance: str | None = None,
             satellite: bool = False, clip_role: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        tier = self.t["tiers"][role]
        spec = self.t["font_roles"][role]
        color_name = color_spec or ev.get("color") or tier["color"]
        accent_hex = _accent(self.t, ev.get("accent")) if ev.get("accent") else self.accent_hex
        color = _color(self.t, color_name, accent_hex)
        ent = entrance or tier["entrance"]
        out: dict[str, Any] = {
            "role": clip_role or role,
            "track": TRACK_NAMES[int(tier["track"])],
            "text": text,
            "at": round(float(at), 3),
            "dur": round(float(dur), 3),
            "y_pct": round(float(y_pct), 3),
            "position": [round(self.w * x_pct / 100.0), round(self.h * y_pct / 100.0)],
            "align": "center",
            "size_px": round(float(size_px if size_px else tier["size_px"])),
            "font": self.font_for(role, ev, satellite=satellite),
            "color": color,
            "italic": bool(tier.get("italic", spec.get("italic", False))),
            "case": spec.get("case"),
            "tracking": spec.get("tracking"),
            "swash_hybrid": bool(spec.get("swash_hybrid", False)) and not satellite,
            "entrance": _entrance(self.t, ent),
            "lighting": _lighting(self.t, color, ev.get("lighting")),
        }
        if extra:
            out.update(extra)
        return out

    # -- one event -> clips ------------------------------------------------------------
    def plan(self, ev: dict[str, Any]) -> list[dict[str, Any]]:
        role = ev.get("role")
        if role not in ROLES:
            raise ValueError(f"unsupported role {role!r}; supported: {', '.join(ROLES)}")
        if "text" not in ev or not isinstance(ev["text"], str):
            raise ValueError(f"event {role!r} needs a string 'text'")
        at, dur = float(ev["at"]), float(ev["dur"])
        if dur <= 0:
            raise ValueError(f"event {role!r} at {at}: dur must be > 0")
        raw = ev["text"]
        text = nfc(raw)
        if text != raw and f"text normalised to NFC: {text!r}" not in self.warnings:
            self.warnings.append(f"text normalised to NFC: {text!r}")
        y = self.role_y(ev)
        tiers = self.t["tiers"]

        if role == "lockup_hero":
            return [self.clip(role, ev, text, at, dur, y)]
        if role == "lockup_sub":
            hero_px = tiers["lockup_hero"]["size_px"]
            sub_px = tiers["lockup_sub"]["size_px"]
            hero_y = float(ev["hero_y_pct"]) if ev.get("hero_y_pct") is not None else float(self.t["caption_y_pct"]["talking"]["value"])
            offset_px = hero_px * 0.5 + LOCKUP_GAP_PX + sub_px * 0.5
            y_sub = float(ev["y_pct"]) if ev.get("y_pct") is not None else hero_y - 100.0 * offset_px / self.h
            return [self.clip(role, ev, text, at + self.t["lockup"]["two_tier"]["lead_stagger_s"], dur, y_sub,
                              extra={"derived_y": ev.get("y_pct") is None, "anchored_to": "lockup_hero"})]
        if role == "constellation":
            c = self.t["constellation"]
            hero_y = float(ev["y_pct"]) if ev.get("y_pct") is not None else float(c["hero_y_pct"])
            hero_x = float(c["hero_x_pct"])
            clips = [self.clip(role, ev, text, at, dur, hero_y, x_pct=hero_x, extra={"accumulate": True})]
            slots = c["satellite_slots_pct"]
            for i, sat in enumerate(ev.get("satellites", [])):
                dx, dy = slots[i % len(slots)]
                sat_at = at + (i + 1) * float(c["stagger_s"])
                if sat_at >= at + dur:
                    self.warnings.append(f"constellation satellite {sat!r} starts after the phrase ends; skipped")
                    continue
                clips.append(self.clip(role, ev, nfc(sat), sat_at, at + dur - sat_at, hero_y + dy, x_pct=hero_x + dx,
                                       size_px=tiers["constellation"]["satellite_px"], color_spec="text",
                                       entrance=c["entrance_satellite"], satellite=True, clip_role="constellation_satellite",
                                       extra={"accumulate": bool(c["accumulate"])}))
            return clips
        return [self.clip(role, ev, text, at, dur, y)]


def build_tracks(events_doc: dict[str, Any], tokens: dict[str, Any]) -> dict[str, Any]:
    """Pure function: events + tokens -> tracks. Raises ValueError for unknown roles / layouts / banned fonts."""
    events = events_doc.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json needs an 'events' list")
    planner = _Planner(tokens, events_doc.get("accent"))
    by_track: dict[str, list[dict[str, Any]]] = {n: [] for n in TRACK_NAMES}
    for ev in sorted(events, key=lambda e: float(e["at"])):
        for clip in planner.plan(ev):
            by_track[clip["track"]].append(clip)
    for clips in by_track.values():  # same track must not overlap in time, except accumulating clips (constellation)
        plain = [c for c in clips if not c.get("accumulate")]
        for a, b in zip(plain, plain[1:]):
            if a["at"] + a["dur"] > b["at"]:
                a["dur"] = round(max(0.05, b["at"] - a["at"]), 3)
    return {
        "profile": tokens.get("profile", "dviet"),
        "tokens_version": tokens.get("version"),
        "canvas": dict(tokens["canvas"]),
        "tracks": [{"name": n, "clips": by_track[n]} for n in TRACK_NAMES if by_track[n]],
        "warnings": planner.warnings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="dviet_text: role-tagged text events -> @__dviet text tracks (tokens in, tracks out)")
    ap.add_argument("--events", required=True, help="events.json (see module docstring)")
    ap.add_argument("--tokens", default=str(DEFAULT_TOKENS), help="presets/dviet_style_tokens.json")
    ap.add_argument("--out", required=True, help="tracks.json to write")
    args = ap.parse_args(argv)
    try:
        tokens = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
        events = json.loads(Path(args.events).read_text(encoding="utf-8"))
        out = build_tracks(events, tokens)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for w in out["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(len(t["clips"]) for t in out["tracks"])
    print(f"{n} clips on {len(out['tracks'])} tracks -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
