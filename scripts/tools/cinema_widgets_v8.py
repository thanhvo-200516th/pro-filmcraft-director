#!/usr/bin/env python3
"""cinema_widgets_v8.py — Deterministic 60fps RGBA Plate Renderer for pro-filmcraft-director v8.

Renders transparent-background .mov plates (qtrle / prores4444 / png RGBA) using Playwright +
/usr/bin/google-chrome (headless, --enable-webgl --ignore-gpu-blocklist), reusing ONE browser
page across batch manifests for fast (~10–25s) multi-plate rendering.

Supported templates:
  Typography (kt13..kt18 — Vietnamese NFC-safe):
    - kt13_dviet_optical_glow_slow
    - kt14_random_letter_stagger
    - kt15_typewriter_glitch_cursor
    - kt16_vertical_echo_stack
    - kt17_behind_subject_3d_bevel
    - kt18_word_highlight_boxes
  3D / Glass / Infographic Widgets (w01..w06):
    - w01_glass_numbered_pill
    - w02_glass_checklist_card
    - w03_animated_bar_chart
    - w04_curved_head_orbit_text
    - w05_3d_floating_badge
    - w06_neon_hollow_backdrop
  Continuous Verbatim Karaoke Caption Rail:
    - rail_karaoke

Usage:
    PY=~/.venvs/video-skills/bin/python3
    # Batch from manifest:
    $PY scripts/tools/cinema_widgets_v8.py --manifest plates_manifest.json --out-dir ./plates --fps 60 --codec qtrle
    # Single plate:
    $PY scripts/tools/cinema_widgets_v8.py --template w01_glass_numbered_pill --props '{"number":"1","label":"PHÂN TÍCH KỊCH BẢN"}' --duration 2.5 --out pill.mov
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

CHROME_EXECUTABLE = "/usr/bin/google-chrome"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 60

SUPPORTED_TEMPLATES = (
    "kt13_dviet_optical_glow_slow",
    "kt14_random_letter_stagger",
    "kt15_typewriter_glitch_cursor",
    "kt16_vertical_echo_stack",
    "kt17_behind_subject_3d_bevel",
    "kt18_word_highlight_boxes",
    "w01_glass_numbered_pill",
    "w02_glass_checklist_card",
    "w03_animated_bar_chart",
    "w04_curved_head_orbit_text",
    "w05_3d_floating_badge",
    "w06_neon_hollow_backdrop",
    "rail_karaoke",
    "rail_dynamic_typo",
)


def _load_typo_v81_presets() -> dict[str, Any]:
    """Load Typography v8.1 presets JSON from presets/typography_v81_presets.json."""
    preset_path = Path(__file__).resolve().parents[2] / "presets" / "typography_v81_presets.json"
    if preset_path.is_file():
        try:
            return json.loads(preset_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"font_pairings": {}, "palettes": {}, "subtitle_modes": {}}


TYPO_V81_PRESETS = _load_typo_v81_presets()


def clamp_to_l_safe_zone(
    x: float,
    y: float,
    w: float,
    h: float,
    W: int = DEFAULT_WIDTH,
    H: int = DEFAULT_HEIGHT,
) -> tuple[float, float, float, float]:
    """Clamp a bounding box (x, y, w, h) into the verified L-shaped TikTok 9:16 safe zone.

    At 1080x1920:
      - Top-right notch rect: x in [120, 960], y in [252, 360]
      - Main body rect:       x in [120, 840], y in [360, 1216]
    Scales proportionally for other 9:16 resolutions; passes through with gentle margin on landscape.
    Returns (clamped_x, clamped_y, clamped_w, clamped_h).
    """
    if H <= W:
        pad_x = W * 0.06
        pad_y = H * 0.06
        cw = min(float(w), W - 2 * pad_x)
        ch = min(float(h), H - 2 * pad_y)
        cx = max(pad_x, min(float(x), W - pad_x - cw))
        cy = max(pad_y, min(float(y), H - pad_y - ch))
        return (round(cx, 2), round(cy, 2), round(cw, 2), round(ch, 2))

    sx = W / 1080.0
    sy = H / 1920.0
    x_min = 120.0 * sx
    y_min = 252.0 * sy
    notch_y_max = 360.0 * sy
    y_max = 1216.0 * sy

    ch = min(float(h), y_max - y_min)
    cy = max(y_min, min(float(y), y_max - ch))

    # Only boxes fully inside the upper notch [252..360] may extend to x=960
    x_max = (960.0 * sx) if (cy + ch <= notch_y_max + 0.5) else (840.0 * sx)
    cw = min(float(w), x_max - x_min)
    cx = max(x_min, min(float(x), x_max - cw))
    return (round(cx, 2), round(cy, 2), round(cw, 2), round(ch, 2))

# 19 crisp built-in SVG icons for w05_3d_floating_badge (24x24 viewBox, stroke-based clean geometry)
SVG_ICONS: dict[str, str] = {
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    "lightbulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
    "sparkles": '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3z"/><path d="M5 3v4"/><path d="M3 5h4"/><path d="M19 17v4"/><path d="M17 19h4"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
    "key": '<circle cx="7.5" cy="15.5" r="4.5"/><path d="M11 12l9-9"/><path d="M16 7l3 3"/><path d="M19 4l2 2"/>',
    "chart": '<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6" rx="1"/><rect x="12" y="8" width="3" height="10" rx="1"/><rect x="17" y="5" width="3" height="13" rx="1"/>',
    "hourglass": '<path d="M5 2h14"/><path d="M5 22h14"/><path d="M6 2v4c0 3 6 4 6 6s-6 3-6 6v4"/><path d="M18 2v4c0 3-6 4-6 6s6 3 6 6v4"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="M8 12.5l2.8 2.8L16.5 9"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 12 12 17 22 12"/><polyline points="2 17 12 22 22 17"/>',
    "aperture": '<circle cx="12" cy="12" r="10"/><line x1="14.31" y1="8" x2="20.05" y2="17.94"/><line x1="9.69" y1="8" x2="21.17" y2="8"/><line x1="7.38" y1="12" x2="13.12" y2="2.06"/><line x1="9.69" y1="16" x2="3.95" y2="6.06"/><line x1="14.31" y1="16" x2="2.83" y2="16"/><line x1="16.62" y1="12" x2="10.88" y2="21.94"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "heart": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "home": '<path d="M3 9.5L12 2l9 7.5V20a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "dollar": '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "wand": '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8L19 13"/><path d="M15 9h.01"/><path d="M17.8 6.2L19 5"/><path d="M3 21l9-9"/><path d="M12.2 6.2L11 5"/>',
}


def nfc_deep(obj: Any) -> Any:
    """Recursively normalize all strings to Unicode NFC for safe Vietnamese rendering."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, list):
        return [nfc_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: nfc_deep(v) for k, v in obj.items()}
    return obj


def _ffmpeg_codec_args(codec: str) -> list[str]:
    if codec == "qtrle":
        return ["-c:v", "qtrle", "-pix_fmt", "argb"]
    if codec == "prores4444":
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    if codec == "png":
        return ["-c:v", "png", "-pix_fmt", "rgba"]
    raise ValueError(f"Unsupported codec: {codec} (qtrle | prores4444 | png)")


def build_stage_html(width: int, height: int) -> str:
    """Self-contained HTML/CSS/JS stage loaded once into the persistent headless Chrome page."""
    icons_json = json.dumps(SVG_ICONS, ensure_ascii=False)
    typo_v81_json = json.dumps(TYPO_V81_PRESETS, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<style>
  *, *::before, *::after {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  html, body {{
    width: {width}px;
    height: {height}px;
    overflow: hidden;
    background: transparent !important;
    -webkit-font-smoothing: antialiased;
    text-rendering: geometricPrecision;
    font-family: "Be Vietnam Pro", "Montserrat", "Inter", "Noto Sans", sans-serif;
  }}
  #stage {{
    position: relative;
    width: {width}px;
    height: {height}px;
    overflow: hidden;
    background: transparent;
  }}
  .font-sans {{
    font-family: "Be Vietnam Pro", "Montserrat", "Inter", "Noto Sans", sans-serif;
  }}
  .font-display {{
    font-family: "Montserrat", "Be Vietnam Pro", "Anton", "Inter", sans-serif;
  }}
  .font-serif {{
    font-family: "Playfair Display", "Fraunces", "Liberation Serif", Georgia, serif;
  }}
  .font-mono {{
    font-family: "JetBrains Mono", "Space Mono", "DejaVu Sans Mono", monospace;
  }}
  .font-script {{
    font-family: "SVN-Aaron Script", "Dancing Script", "Playfair Display", cursive;
  }}
  .font-condensed {{
    font-family: "Barlow Condensed", "Oswald", "Be Vietnam Pro", sans-serif;
  }}
  .font-chunky {{
    font-family: "Unbounded", "Paytone One", "Montserrat", sans-serif;
  }}
</style>
</head>
<body>
<div id="stage"></div>
<script>
const SVG_ICONS = {icons_json};
const TYPO_V81 = {typo_v81_json};
const W = {width};
const H = {height};
const IS_PORTRAIT_9_16 = H > W;
const DIFFUSED_SHADOW = "0 4px 18px rgba(0,0,0,0.75)";

// ---------- Math & Easing ----------
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const easeOutCubic = (u) => 1 - Math.pow(1 - clamp(u, 0, 1), 3);
const easeOutQuart = (u) => 1 - Math.pow(1 - clamp(u, 0, 1), 4);
const easeInOutCubic = (u) => {{
  const t = clamp(u, 0, 1);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}};
const easeOutBack = (u, s = 1.45) => {{
  const t = clamp(u, 0, 1) - 1;
  return 1 + (s + 1) * Math.pow(t, 3) + s * Math.pow(t, 2);
}};

// Verified L-Shaped TikTok 9:16 Safe Zone Clamper
function clampToLSafeZone(x, y, w, h) {{
  if (!IS_PORTRAIT_9_16) {{
    const px = W * 0.06, py = H * 0.06;
    const cw = Math.min(w, W - 2 * px);
    const ch = Math.min(h, H - 2 * py);
    return {{
      x: clamp(x, px, W - px - cw),
      y: clamp(y, py, H - py - ch),
      w: cw,
      h: ch,
    }};
  }}
  const sx = W / 1080, sy = H / 1920;
  const xMin = 120 * sx;
  const yMin = 252 * sy;
  const notchYMax = 360 * sy;
  const yMax = 1216 * sy;
  const ch = Math.min(h, yMax - yMin);
  const cy = clamp(y, yMin, yMax - ch);
  const xMax = (cy + ch <= notchYMax + 0.5) ? (960 * sx) : (840 * sx);
  const cw = Math.min(w, xMax - xMin);
  const cx = clamp(x, xMin, xMax - cw);
  return {{ x: cx, y: cy, w: cw, h: ch }};
}}

function getFontPair(id) {{
  const map = (TYPO_V81 && TYPO_V81.font_pairings) || {{}};
  return map[id] || map.FP1_EDITORIAL_LUXE || {{
    id: "FP1_EDITORIAL_LUXE",
    css_primary: '"Be Vietnam Pro", "Montserrat", sans-serif',
    css_accent: '"Playfair Display", Georgia, serif',
    primary_weight: 800,
    accent_weight: 700,
    accent_style: "italic",
  }};
}}

function getPalette(id) {{
  const map = (TYPO_V81 && TYPO_V81.palettes) || {{}};
  const alias = {{
    gold: "PAL_CHAMPAGNE_GOLD",
    platinum: "PAL_SILVER_CHROME",
    cyan: "PAL_ELECTRIC_CYAN",
    rose: "PAL_CORAL_CRIMSON",
    emerald: "PAL_EMERALD_MINT",
    violet: "PAL_ROYAL_VIOLET",
    amber: "PAL_SOLAR_AMBER",
    duotone: "PAL_DUOTONE_BLUE_ORANGE",
  }};
  const key = map[id] ? id : (alias[id] || "PAL_ELECTRIC_CYAN");
  return map[key] || {{
    id: "PAL_ELECTRIC_CYAN",
    gradient: "linear-gradient(135deg, #F0F9FF 0%, #67E8F9 42%, #0EA5E9 100%)",
    primary_color: "#F8FAFC",
    accent_color: "#38BDF8",
    glow_color: "#0EA5E9",
    extrude_color: "#0C4A6E",
    diffused_shadow: DIFFUSED_SHADOW,
  }};
}}

function makeGhostWatermark(text, pal, sizePx = 220) {{
  const wm = document.createElement("div");
  wm.className = "font-display";
  wm.textContent = String(text);
  wm.style.cssText = `
    position:absolute; left:50%; top:50%;
    transform:translate(-50%, -52%);
    font-size:${{sizePx}}px;
    font-weight:900;
    line-height:0.9;
    letter-spacing:-0.04em;
    color:${{hexToRgba(pal.accent_color || "#38BDF8", 0.22)}};
    filter: blur(5px);
    opacity: 0.22;
    pointer-events:none;
    user-select:none;
    z-index:0;
    white-space:nowrap;
  `;
  return wm;
}}

function getLSafeCenterLayout(yPct, boxW, boxH, enforceLSafe = true) {{
  if (!IS_PORTRAIT_9_16 || !enforceLSafe) {{
    return {{ leftPx: W * 0.5, topPx: (H * yPct) / 100, widthPx: boxW }};
  }}
  const desiredY = (H * yPct) / 100 - boxH * 0.5;
  const desiredX = (120 + (840 - 120) * 0.5) * (W / 1080) - boxW * 0.5;
  const box = clampToLSafeZone(desiredX, desiredY, boxW, boxH);
  return {{
    leftPx: box.x + box.w * 0.5,
    topPx: box.y + box.h * 0.5,
    widthPx: box.w,
  }};
}}

function hexToRgba(hex, alpha = 1) {{
  let h = (hex || "#38BDF8").replace("#", "").trim();
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  const r = parseInt(h.slice(0, 2), 16) || 56;
  const g = parseInt(h.slice(2, 4), 16) || 189;
  const b = parseInt(h.slice(4, 6), 16) || 248;
  return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
}}

function splitGraphemes(str) {{
  const s = (str || "").normalize("NFC");
  if (typeof Intl !== "undefined" && Intl.Segmenter) {{
    const seg = new Intl.Segmenter("vi", {{ granularity: "grapheme" }});
    return Array.from(seg.segment(s), x => x.segment);
  }}
  return Array.from(s);
}}

function seededRandom(seed) {{
  let x = (seed >>> 0) || 1337;
  return () => {{
    x ^= x << 13; x >>>= 0;
    x ^= x >> 17; x >>>= 0;
    x ^= x << 5;  x >>>= 0;
    return (x >>> 0) / 4294967296;
  }};
}}

function escapeHtml(s) {{
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}}

function exitFade(t, dur, fadeOut = 0.22) {{
  if (fadeOut <= 0 || dur <= fadeOut) return 1;
  const rem = dur - t;
  if (rem >= fadeOut) return 1;
  return easeOutCubic(clamp(rem / fadeOut, 0, 1));
}}

// ---------- Active Plate State ----------
let ACTIVE = null;

function mountPlate(template, props, duration) {{
  const stage = document.getElementById("stage");
  stage.innerHTML = "";
  const p = props || {{}};
  const dur = Number(duration || 3.0);

  if (template === "kt13_dviet_optical_glow_slow") {{
    ACTIVE = initKt13(stage, p, dur);
  }} else if (template === "kt14_random_letter_stagger") {{
    ACTIVE = initKt14(stage, p, dur);
  }} else if (template === "kt15_typewriter_glitch_cursor") {{
    ACTIVE = initKt15(stage, p, dur);
  }} else if (template === "kt16_vertical_echo_stack") {{
    ACTIVE = initKt16(stage, p, dur);
  }} else if (template === "kt17_behind_subject_3d_bevel") {{
    ACTIVE = initKt17(stage, p, dur);
  }} else if (template === "kt18_word_highlight_boxes") {{
    ACTIVE = initKt18(stage, p, dur);
  }} else if (template === "w01_glass_numbered_pill") {{
    ACTIVE = initW01(stage, p, dur);
  }} else if (template === "w02_glass_checklist_card") {{
    ACTIVE = initW02(stage, p, dur);
  }} else if (template === "w03_animated_bar_chart") {{
    ACTIVE = initW03(stage, p, dur);
  }} else if (template === "w04_curved_head_orbit_text") {{
    ACTIVE = initW04(stage, p, dur);
  }} else if (template === "w05_3d_floating_badge") {{
    ACTIVE = initW05(stage, p, dur);
  }} else if (template === "w06_neon_hollow_backdrop") {{
    ACTIVE = initW06(stage, p, dur);
  }} else if (template === "rail_karaoke") {{
    const segs = Array.isArray(p.segments) ? p.segments : (Array.isArray(p.cues) ? p.cues : []);
    const hasSubModes = segs.some(s => s && s.sub_mode);
    if (p.dynamic_typo === true || (p.dynamic_typo !== false && hasSubModes)) {{
      ACTIVE = initRailDynamicTypo(stage, p, dur);
    }} else {{
      ACTIVE = initRailKaraoke(stage, p, dur);
    }}
  }} else if (template === "rail_dynamic_typo") {{
    ACTIVE = initRailDynamicTypo(stage, p, dur);
  }} else {{
    throw new Error("Unknown template: " + template);
  }}
  window.__setTime(0);
}}

window.__mountPlate = mountPlate;
window.__setTime = (t) => {{
  if (!ACTIVE) return "none";
  return ACTIVE.update(Number(t));
}};
window.__stateKey = (t) => {{
  if (!ACTIVE || !ACTIVE.stateKey) return null;
  return ACTIVE.stateKey(Number(t));
}};

// ============================================================================
// TYPOGRAPHY TEMPLATES (kt13 .. kt18)
// ============================================================================

// kt13: @__dviet Nov-2026 condensed lowercase, ZERO black stroke, soft colored optical halation, 0.38s opacity+blur ramp
// v8.1: supports font_pair (FP1..FP6), palette (PAL_*), ghost_watermark, and L-safe-zone clamping
function initKt13(stage, p, dur) {{
  const text = (p.text || "không cần làm màu").toLowerCase();
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const pal = p.palette ? getPalette(p.palette) : null;
  const color = p.color || (pal ? pal.primary_color : "#FFFFFF");
  const glow = p.glow || (pal ? pal.glow_color : "#60A5FA");
  const fontSize = p.font_size || Math.round(W * 0.088);
  const yPct = p.y_pct ?? 46;
  const scaleX = p.scale_x ?? 0.82;
  const ramp = p.ramp_sec ?? 0.38;
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 2.4), p.l_safe !== false);

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
    pointer-events:none;
  `;
  if (p.ghost_watermark) {{
    wrap.appendChild(makeGhostWatermark(p.ghost_watermark, pal || {{ accent_color: glow }}, p.watermark_size || 220));
  }}
  const el = document.createElement("div");
  el.className = "font-sans";
  el.textContent = text;
  const useGrad = Boolean(pal && pal.gradient && !p.color);
  el.style.cssText = `
    position:relative; z-index:1;
    display:inline-block;
    font-family:${{fp ? fp.css_primary : '"Be Vietnam Pro", "Montserrat", sans-serif'}};
    font-size:${{fontSize}}px;
    font-weight:${{fp ? fp.primary_weight : 700}};
    line-height:1.12;
    letter-spacing:-0.04em;
    ${{useGrad
      ? `background:${{pal.gradient}}; -webkit-background-clip:text; background-clip:text; color:transparent; filter:drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 22px ${{hexToRgba(glow, 0.58)}});`
      : `color:${{color}}; text-shadow: 0 4px 18px rgba(0,0,0,0.75), 0 0 14px ${{hexToRgba(glow, 0.72)}}, 0 0 34px ${{hexToRgba(glow, 0.45)}}, 0 0 64px ${{hexToRgba(glow, 0.24)}};`
    }}
    transform-origin:center center;
    will-change: transform, opacity, filter;
  `;
  wrap.appendChild(el);
  stage.appendChild(wrap);

  return {{
    stateKey(t) {{
      if (t > ramp + 0.05 && t < dur - 0.25) return "hold";
      return null;
    }},
    update(t) {{
      const u = easeOutCubic(clamp(t / ramp, 0, 1));
      const out = exitFade(t, dur, 0.22);
      const op = u * out;
      const blur = lerp(14, 0, u) + lerp(8, 0, out);
      const sc = lerp(1.045, 1.0, u);
      wrap.style.opacity = op.toFixed(4);
      const baseFilter = useGrad
        ? `drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 22px ${{hexToRgba(glow, 0.58)}})`
        : "";
      el.style.filter = blur > 0.05
        ? `${{baseFilter}} blur(${{blur.toFixed(2)}}px)`.trim()
        : (baseFilter || "none");
      el.style.transform = `scaleX(${{scaleX}}) scale(${{sc.toFixed(4)}})`;
    }}
  }};
}}

// kt14: Vietnamese grapheme-safe random per-character blur + fade entrance (~25ms/char)
// v8.1: supports font_pair (FP1..FP6), palette (PAL_*), ghost_watermark, and L-safe-zone clamping
function initKt14(stage, p, dur) {{
  const text = p.text || "Tư duy hệ thống mới là đòn bẩy";
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const pal = p.palette ? getPalette(p.palette) : null;
  const color = p.color || (pal ? pal.primary_color : "#FFFFFF");
  const glow = p.glow || (pal ? pal.glow_color : "#38BDF8");
  const fontSize = p.font_size || Math.round(W * 0.070);
  const yPct = p.y_pct ?? 46;
  const stagger = p.stagger_sec ?? 0.025;
  const charDur = p.char_dur ?? 0.28;
  const seed = p.seed ?? 42;
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 3.0), p.l_safe !== false);

  const outer = document.createElement("div");
  outer.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
    pointer-events:none;
  `;
  if (p.ghost_watermark) {{
    outer.appendChild(makeGhostWatermark(p.ghost_watermark, pal || {{ accent_color: glow }}, p.watermark_size || 220));
  }}

  const wrap = document.createElement("div");
  wrap.className = "font-sans";
  wrap.style.cssText = `
    position:relative; z-index:1;
    font-family:${{fp ? fp.css_primary : '"Be Vietnam Pro", "Montserrat", sans-serif'}};
    font-size:${{fontSize}}px;
    font-weight:${{fp ? fp.primary_weight : 800}};
    line-height:1.22;
    letter-spacing:-0.02em;
    color:${{color}};
    text-shadow: 0 4px 18px rgba(0,0,0,0.75), 0 0 18px ${{hexToRgba(glow, 0.55)}}, 0 0 38px ${{hexToRgba(glow, 0.28)}};
  `;

  const graphemes = splitGraphemes(text);
  const nonSpaceIdx = [];
  const spans = graphemes.map((g, i) => {{
    const sp = document.createElement("span");
    sp.textContent = g;
    sp.style.display = "inline-block";
    if (g === " ") sp.style.width = "0.28em";
    else nonSpaceIdx.push(i);
    wrap.appendChild(sp);
    return sp;
  }});

  const rng = seededRandom(seed);
  const order = [...nonSpaceIdx];
  for (let i = order.length - 1; i > 0; i--) {{
    const j = Math.floor(rng() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }}
  const delayMap = new Map();
  order.forEach((idx, rank) => delayMap.set(idx, rank * stagger));
  const maxEnd = order.length * stagger + charDur;

  outer.appendChild(wrap);
  stage.appendChild(outer);
  return {{
    stateKey(t) {{
      if (t > maxEnd + 0.05 && t < dur - 0.25) return "hold";
      return null;
    }},
    update(t) {{
      const out = exitFade(t, dur, 0.20);
      outer.style.opacity = out.toFixed(4);
      spans.forEach((sp, i) => {{
        if (!delayMap.has(i)) return;
        const u = easeOutCubic(clamp((t - delayMap.get(i)) / charDur, 0, 1));
        const blur = lerp(12, 0, u);
        const dy = lerp(10, 0, u);
        sp.style.opacity = u.toFixed(4);
        sp.style.filter = blur > 0.05 ? `blur(${{blur.toFixed(2)}}px)` : "none";
        sp.style.transform = `translateY(${{dy.toFixed(2)}}px)`;
      }});
    }}
  }};
}}

// kt15: Scramble-decode typewriter + blinking accent cursor |
// v8.1: supports font_pair (FP1..FP6), palette (PAL_*), ghost_watermark, and L-safe-zone clamping
function initKt15(stage, p, dur) {{
  const text = p.text || "Tự động hoá 100% quy trình";
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const pal = p.palette ? getPalette(p.palette) : null;
  const color = p.color || (pal ? pal.primary_color : "#F8FAFC");
  const accent = p.accent || (pal ? pal.accent_color : "#38BDF8");
  const fontSize = p.font_size || Math.round(W * 0.062);
  const yPct = p.y_pct ?? 46;
  const charStep = p.char_step ?? 0.042;
  const glyphPool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*";
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 3.0), p.l_safe !== false);

  const graphemes = splitGraphemes(text);
  const wrap = document.createElement("div");
  wrap.className = "font-sans";
  wrap.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
    font-family:${{fp ? fp.css_primary : '"Be Vietnam Pro", "Montserrat", sans-serif'}};
    font-size:${{fontSize}}px;
    font-weight:${{fp ? fp.primary_weight : 700}};
    line-height:1.28;
    letter-spacing:-0.015em;
    color:${{color}};
    text-shadow: 0 4px 18px rgba(0,0,0,0.75), 0 0 18px ${{hexToRgba(accent, 0.42)}};
  `;
  if (p.ghost_watermark) {{
    wrap.appendChild(makeGhostWatermark(p.ghost_watermark, pal || {{ accent_color: accent }}, p.watermark_size || 220));
  }}
  const fg = document.createElement("div");
  fg.style.cssText = "position:relative; z-index:1;";
  const textNode = document.createElement("span");
  const cursor = document.createElement("span");
  cursor.textContent = "|";
  cursor.style.cssText = `
    display:inline-block;
    margin-left:4px;
    font-weight:400;
    color:${{accent}};
    text-shadow: 0 0 14px ${{hexToRgba(accent, 0.9)}}, 0 0 28px ${{hexToRgba(accent, 0.55)}};
  `;
  fg.appendChild(textNode);
  fg.appendChild(cursor);
  wrap.appendChild(fg);
  stage.appendChild(wrap);

  return {{
    update(t) {{
      const out = exitFade(t, dur, 0.18);
      wrap.style.opacity = out.toFixed(4);
      const revealedFloat = t / charStep;
      const locked = Math.min(graphemes.length, Math.floor(revealedFloat));
      let shown = graphemes.slice(0, locked).join("");
      if (locked < graphemes.length && t > 0.01) {{
        const g = graphemes[locked];
        if (g !== " ") {{
          const tick = Math.floor(t * 30);
          const idx = (locked * 7 + tick * 13) % glyphPool.length;
          shown += glyphPool[idx];
        }} else {{
          shown += " ";
        }}
      }}
      textNode.textContent = shown;
      const blink = Math.sin(t * Math.PI * 3.6) >= -0.15 ? 1 : 0.08;
      cursor.style.opacity = blink.toFixed(2);
    }}
  }};
}}

// kt16: 3-tier semantic vertical echo stack with motion blur & fade trail
// v8.1: supports font_pair (FP1..FP6), palette (PAL_*), ghost_watermark, and L-safe-zone clamping
function initKt16(stage, p, dur) {{
  const text = (p.text || "CHẤT LƯỢNG").toUpperCase();
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const pal = p.palette ? getPalette(p.palette) : null;
  const color = p.color || (pal ? pal.primary_color : "#FFFFFF");
  const accent = p.accent || (pal ? pal.accent_color : "#38BDF8");
  const fontSize = p.font_size || Math.round(W * 0.095);
  const yPct = p.y_pct ?? 48;
  const spreadPx = p.spread_px ?? Math.round(fontSize * 0.92);
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 3.2), p.l_safe !== false);

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
  `;
  if (p.ghost_watermark) {{
    wrap.appendChild(makeGhostWatermark(p.ghost_watermark, pal || {{ accent_color: accent }}, p.watermark_size || 220));
  }}

  const useGrad = Boolean(pal && pal.gradient && !p.color);
  const makeTier = (isCenter) => {{
    const el = document.createElement("div");
    el.className = "font-display";
    el.textContent = text;
    el.style.cssText = `
      position:${{isCenter ? "relative" : "absolute"}};
      z-index:${{isCenter ? 2 : 1}};
      left:0; right:0; top:0;
      font-family:${{fp ? fp.css_primary : '"Montserrat", "Be Vietnam Pro", sans-serif'}};
      font-size:${{fontSize}}px;
      font-weight:900;
      line-height:1.05;
      letter-spacing:-0.03em;
      ${{isCenter
        ? (useGrad
            ? `background:${{pal.gradient}}; -webkit-background-clip:text; background-clip:text; color:transparent; filter:drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 24px ${{hexToRgba(accent, 0.60)}});`
            : `color:${{color}}; text-shadow: 0 4px 18px rgba(0,0,0,0.75), 0 0 22px ${{hexToRgba(accent, 0.55)}}, 0 0 48px ${{hexToRgba(accent, 0.25)}};`)
        : `color:transparent; -webkit-text-stroke: 2.2px ${{hexToRgba(accent, 0.85)}}; text-shadow: 0 0 24px ${{hexToRgba(accent, 0.45)}};`
      }}
      will-change: transform, opacity, filter;
    `;
    return el;
  }};

  const topEcho = makeTier(false);
  const botEcho = makeTier(false);
  const hero = makeTier(true);
  wrap.appendChild(topEcho);
  wrap.appendChild(botEcho);
  wrap.appendChild(hero);
  stage.appendChild(wrap);

  return {{
    update(t) {{
      const u = easeOutQuart(clamp(t / 0.42, 0, 1));
      const out = exitFade(t, dur, 0.22);
      const drift = Math.sin(t * 2.2) * 4;
      const offset = lerp(0, spreadPx, u) + drift;
      const echoBlur = lerp(12, 2.2, u);
      const heroScale = lerp(0.86, 1.0, easeOutBack(clamp(t / 0.36, 0, 1), 1.1));

      hero.style.opacity = (u * out).toFixed(4);
      hero.style.transform = `scale(${{heroScale.toFixed(4)}})`;
      const gradFilter = useGrad ? `drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 24px ${{hexToRgba(accent, 0.60)}})` : "";
      hero.style.filter = u < 0.9 ? `${{gradFilter}} blur(${{lerp(6, 0, u).toFixed(2)}}px)`.trim() : (gradFilter || "none");

      topEcho.style.opacity = (u * 0.42 * out).toFixed(4);
      topEcho.style.transform = `translateY(${{(-offset).toFixed(2)}}px) scale(${{lerp(0.96, 0.94, u).toFixed(3)}})`;
      topEcho.style.filter = `blur(${{echoBlur.toFixed(2)}}px)`;

      botEcho.style.opacity = (u * 0.34 * out).toFixed(4);
      botEcho.style.transform = `translateY(${{offset.toFixed(2)}}px) scale(${{lerp(0.96, 0.94, u).toFixed(3)}})`;
      botEcho.style.filter = `blur(${{(echoBlur + 0.8).toFixed(2)}}px)`;
    }}
  }};
}}

// kt17: @tng.vinhomes8 / @xuanart.visual giant 3D metallic/gradient beveled display title + tilted italic script accent
// v8.1: supports font_pair (FP1..FP6), palette (PAL_* or gold/platinum/cyan/rose), ghost_watermark, and L-safe-zone clamping
function initKt17(stage, p, dur) {{
  const title = (p.title || p.text || "ĐẲNG CẤP").toUpperCase();
  const scriptAccent = p.script_accent || p.subtitle || "chuẩn điện ảnh";
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const palObj = getPalette(p.palette || "gold");
  const yPct = p.y_pct ?? 24;
  const fontSize = p.font_size || Math.round(W * 0.13);
  const accentSize = p.accent_size || Math.round(fontSize * 0.44);
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 2.2), p.l_safe !== false);

  const pal = {{
    grad: palObj.gradient,
    extrude: palObj.extrude_color || "#78350F",
    glow: palObj.glow_color || "#F59E0B",
    script: palObj.accent_color || "#FEF08A",
  }};

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
    perspective: 900px;
  `;
  if (p.ghost_watermark) {{
    wrap.appendChild(makeGhostWatermark(p.ghost_watermark, palObj, p.watermark_size || 220));
  }}

  const titleBox = document.createElement("div");
  titleBox.style.cssText = `position:relative; z-index:1; display:inline-block; transform-style:preserve-3d;`;

  const titleFontCss = fp ? fp.css_primary : '"Be Vietnam Pro", "Montserrat", sans-serif';
  const accentFontCss = fp ? fp.css_accent : '"Playfair Display", Georgia, serif';

  const depthLayers = [];
  for (let d = 7; d >= 1; d--) {{
    const layer = document.createElement("div");
    layer.className = "font-sans";
    layer.textContent = title;
    layer.style.cssText = `
      position:absolute; left:0; right:0; top:0;
      font-family:${{titleFontCss}};
      font-size:${{fontSize}}px;
      font-weight:900;
      line-height:1.02;
      letter-spacing:-0.025em;
      color:${{pal.extrude}};
      transform: translate(${{(d * 1.1).toFixed(1)}}px, ${{(d * 1.8).toFixed(1)}}px);
      opacity:${{(0.55 + (7 - d) * 0.06).toFixed(2)}};
      pointer-events:none;
    `;
    if (d === 7) {{
      layer.style.filter = `drop-shadow(0 14px 28px ${{hexToRgba(pal.glow, 0.35)}})`;
    }}
    titleBox.appendChild(layer);
    depthLayers.push(layer);
  }}

  const face = document.createElement("div");
  face.className = "font-sans";
  face.textContent = title;
  face.style.cssText = `
    position:relative;
    font-family:${{titleFontCss}};
    font-size:${{fontSize}}px;
    font-weight:900;
    line-height:1.02;
    letter-spacing:-0.025em;
    background:${{pal.grad}};
    -webkit-background-clip:text;
    background-clip:text;
    color:transparent;
    filter: drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 22px ${{hexToRgba(pal.glow, 0.55)}});
  `;
  titleBox.appendChild(face);
  wrap.appendChild(titleBox);

  let scriptEl = null;
  if (scriptAccent) {{
    scriptEl = document.createElement("div");
    scriptEl.className = "font-serif";
    scriptEl.textContent = scriptAccent;
    scriptEl.style.cssText = `
      position:relative; z-index:2;
      margin-top:${{-Math.round(fontSize * 0.22)}}px;
      font-family:${{accentFontCss}};
      font-size:${{accentSize}}px;
      font-style:${{fp ? (fp.accent_style || "italic") : "italic"}};
      font-weight:${{fp ? (fp.accent_weight || 700) : 700}};
      letter-spacing:0.01em;
      color:${{pal.script}};
      text-shadow:
        0 4px 18px rgba(0,0,0,0.75),
        0 0 16px ${{hexToRgba(pal.glow, 0.8)}},
        0 0 36px ${{hexToRgba(pal.glow, 0.45)}};
      transform-origin:center center;
    `;
    wrap.appendChild(scriptEl);
  }}

  stage.appendChild(wrap);
  return {{
    update(t) {{
      const u = easeOutQuart(clamp(t / 0.48, 0, 1));
      const out = exitFade(t, dur, 0.25);
      const bob = Math.sin(t * 1.8) * 3.5;
      const rotX = lerp(24, 0, u);
      const sc = lerp(0.84, 1.0, u);

      titleBox.style.opacity = (u * out).toFixed(4);
      titleBox.style.transform = `translateY(${{(lerp(28, 0, u) + bob).toFixed(2)}}px) rotateX(${{rotX.toFixed(2)}}deg) scale(${{sc.toFixed(4)}})`;

      if (scriptEl) {{
        const su = easeOutBack(clamp((t - 0.16) / 0.40, 0, 1), 1.3);
        scriptEl.style.opacity = (clamp((t - 0.16) / 0.25, 0, 1) * out).toFixed(4);
        scriptEl.style.transform = `translateY(${{lerp(18, 0, su).toFixed(2)}}px) rotate(-5.5deg) scale(${{lerp(0.85, 1.0, su).toFixed(4)}})`;
      }}
    }}
  }};
}}

// kt18: @xuanart.visual staggered glowing accent rectangular highlight blocks popping behind individual words
// v8.1: supports font_pair (FP1..FP6), palette (PAL_*), ghost_watermark, and L-safe-zone clamping
function initKt18(stage, p, dur) {{
  const text = p.text || "Không cần phức tạp, chỉ cần đúng hệ thống";
  const fp = p.font_pair ? getFontPair(p.font_pair) : null;
  const pal = p.palette ? getPalette(p.palette) : null;
  const highlights = (p.highlight_words || p.highlights || ["đúng", "hệ", "thống"]).map(w => w.toLowerCase());
  const accent = p.accent || (pal ? pal.accent_color : "#F43F5E");
  const color = p.color || (pal ? pal.primary_color : "#FFFFFF");
  const fontSize = p.font_size || Math.round(W * 0.064);
  const yPct = p.y_pct ?? 46;
  const stagger = p.stagger_sec ?? 0.10;
  const lay = getLSafeCenterLayout(yPct, Math.round(W * 0.66), Math.round(fontSize * 3.2), p.l_safe !== false);

  const outer = document.createElement("div");
  outer.style.cssText = `
    position:absolute; left:${{lay.leftPx.toFixed(1)}}px; top:${{lay.topPx.toFixed(1)}}px;
    width:${{Math.round(lay.widthPx)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
  `;
  if (p.ghost_watermark) {{
    outer.appendChild(makeGhostWatermark(p.ghost_watermark, pal || {{ accent_color: accent }}, p.watermark_size || 220));
  }}

  const wrap = document.createElement("div");
  wrap.className = "font-sans";
  wrap.style.cssText = `
    position:relative; z-index:1;
    display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
    gap: 14px 14px;
    font-family:${{fp ? fp.css_primary : '"Be Vietnam Pro", "Montserrat", sans-serif'}};
    font-size:${{fontSize}}px;
    font-weight:${{fp ? fp.primary_weight : 800}};
    line-height:1.18;
    color:${{color}};
  `;

  const words = text.split(/\\s+/).filter(Boolean);
  let hlCount = 0;
  const items = words.map((w, i) => {{
    const clean = w.toLowerCase().replace(/[.,!?;:()\\u201c\\u201d\\u2018\\u2019"']/g, "");
    const isHl = highlights.length === 0 ? true : highlights.includes(clean);
    const box = document.createElement("span");
    box.style.cssText = `
      position:relative; display:inline-block;
      padding: 6px 16px;
      border-radius: 14px;
    `;
    const bg = document.createElement("span");
    bg.style.cssText = `
      position:absolute; inset:0;
      border-radius:14px;
      background:${{isHl
        ? `linear-gradient(135deg, ${{hexToRgba(accent, 0.94)}}, ${{hexToRgba(accent, 0.76)}})`
        : "rgba(15,23,42,0.45)"}};
      border: 1.5px solid ${{isHl ? "rgba(255,255,255,0.42)" : "rgba(255,255,255,0.12)"}};
      box-shadow: ${{isHl
        ? `0 0 24px ${{hexToRgba(accent, 0.65)}}, 0 8px 24px rgba(0,0,0,0.35)`
        : "0 4px 16px rgba(0,0,0,0.25)"}};
      transform-origin: left center;
      z-index: 0;
    `;
    const label = document.createElement("span");
    label.textContent = w;
    label.style.cssText = `position:relative; z-index:1; text-shadow: 0 4px 18px rgba(0,0,0,0.75);`;
    box.appendChild(bg);
    box.appendChild(label);
    wrap.appendChild(box);
    const delay = isHl ? 0.12 + (hlCount++) * stagger : i * 0.03;
    return {{ box, bg, isHl, delay }};
  }});

  outer.appendChild(wrap);
  stage.appendChild(outer);
  const maxEnd = 0.12 + Math.max(hlCount, words.length) * stagger + 0.35;
  return {{
    stateKey(t) {{
      if (t > maxEnd && t < dur - 0.25) return "hold";
      return null;
    }},
    update(t) {{
      const out = exitFade(t, dur, 0.20);
      outer.style.opacity = out.toFixed(4);
      items.forEach(({{ box, bg, isHl, delay }}) => {{
        const u = easeOutBack(clamp((t - delay) / 0.28, 0, 1), 1.35);
        const op = easeOutCubic(clamp((t - delay) / 0.18, 0, 1));
        box.style.opacity = op.toFixed(4);
        if (isHl) {{
          bg.style.transform = `scaleX(${{clamp(u, 0, 1.06).toFixed(4)}}) scaleY(${{lerp(0.86, 1.0, clamp(u, 0, 1)).toFixed(4)}})`;
        }} else {{
          bg.style.transform = `scale(${{lerp(0.92, 1.0, op).toFixed(4)}})`;
        }}
      }});
    }}
  }};
}}

// ============================================================================
// 3D / GLASS / INFOGRAPHIC WIDGETS (w01 .. w06)
// ============================================================================

// w01: @xuanart.visual frosted dark-glass pill with glowing accent circular number badge + uppercase label + specular rim
function initW01(stage, p, dur) {{
  const num = String(p.number ?? p.step ?? "1");
  const label = (p.label || p.text || "BƯỚC ĐẦU TIÊN").toUpperCase();
  const sublabel = p.sublabel || "";
  const accent = p.accent || "#38BDF8";
  const xPct = p.x_pct ?? 50;
  const yPct = p.y_pct ?? 22;

  const pill = document.createElement("div");
  pill.style.cssText = `
    position:absolute; left:${{xPct}}%; top:${{yPct}}%;
    transform:translate(-50%, -50%);
    display:inline-flex; align-items:center; gap:24px;
    padding: 18px 40px 18px 20px;
    max-width:${{Math.round(W * 0.88)}}px;
    border-radius: 999px;
    background: linear-gradient(155deg, rgba(18,24,38,0.88) 0%, rgba(9,13,22,0.92) 100%);
    border: 2px solid rgba(255,255,255,0.22);
    box-shadow:
      inset 0 2px 1px rgba(255,255,255,0.34),
      inset 0 -2px 10px ${{hexToRgba(accent, 0.22)}},
      0 18px 46px rgba(0,0,0,0.52),
      0 0 32px ${{hexToRgba(accent, 0.34)}};
    will-change: transform, opacity;
  `;

  const badge = document.createElement("div");
  badge.className = "font-display";
  badge.textContent = num;
  badge.style.cssText = `
    width: 78px; height: 78px; flex: 0 0 78px;
    border-radius: 50%;
    display:flex; align-items:center; justify-content:center;
    font-size: 40px; font-weight: 900; color: #FFFFFF;
    background: radial-gradient(circle at 32% 28%, #FFFFFF 0%, ${{accent}} 38%, ${{hexToRgba(accent, 0.85)}} 100%);
    border: 2px solid rgba(255,255,255,0.65);
    box-shadow:
      0 0 22px ${{hexToRgba(accent, 0.85)}},
      0 0 44px ${{hexToRgba(accent, 0.42)}},
      inset 0 2px 6px rgba(255,255,255,0.6);
  `;

  const textWrap = document.createElement("div");
  textWrap.style.cssText = `display:flex; flex-direction:column; gap:4px;`;
  const titleEl = document.createElement("div");
  titleEl.className = "font-sans";
  titleEl.textContent = label;
  titleEl.style.cssText = `
    font-size: ${{label.length > 16 ? 32 : 38}}px; font-weight: 800; letter-spacing: 0.03em;
    color: #F8FAFC; line-height: 1.15;
    white-space: nowrap;
    text-shadow: 0 2px 12px rgba(0,0,0,0.45);
  `;
  textWrap.appendChild(titleEl);
  if (sublabel) {{
    const subEl = document.createElement("div");
    subEl.className = "font-sans";
    subEl.textContent = sublabel;
    subEl.style.cssText = `font-size: 24px; font-weight: 500; color: rgba(226,232,240,0.82);`;
    textWrap.appendChild(subEl);
  }}

  pill.appendChild(badge);
  pill.appendChild(textWrap);
  stage.appendChild(pill);

  return {{
    update(t) {{
      const u = easeOutBack(clamp(t / 0.40, 0, 1), 1.35);
      const op = easeOutCubic(clamp(t / 0.22, 0, 1)) * exitFade(t, dur, 0.22);
      const floatY = Math.sin(t * 2.6) * 4.5;
      const dy = lerp(32, 0, u) + floatY;
      const sc = lerp(0.84, 1.0, u);
      pill.style.opacity = op.toFixed(4);
      pill.style.transform = `translate(-50%, calc(-50% + ${{dy.toFixed(2)}}px)) scale(${{sc.toFixed(4)}})`;
    }}
  }};
}}

// w02: @vuotaiai / @tng.vinhomes8 translucent frosted dark-glass progressive checklist card with animated glowing checkmarks
function initW02(stage, p, dur) {{
  const heading = (p.title || "QUY TRÌNH CHUẨN").toUpperCase();
  const items = p.items || [
    "Tách kịch bản A-Roll & B-Roll",
    "Đồng bộ nhịp giọng nói 60fps",
    "Xuất master chuẩn nền tảng",
  ];
  const accent = p.accent || "#22C55E";
  const yPct = p.y_pct ?? 48;
  const itemDelay = p.item_delay ?? 0.36;

  const card = document.createElement("div");
  card.style.cssText = `
    position:absolute; left:50%; top:${{yPct}}%;
    width:${{Math.round(W * 0.84)}}px;
    padding: 36px 40px 40px 40px;
    border-radius: 34px;
    background: linear-gradient(160deg, rgba(15,23,42,0.88) 0%, rgba(7,11,20,0.94) 100%);
    border: 2px solid rgba(255,255,255,0.18);
    box-shadow:
      inset 0 2px 1px rgba(255,255,255,0.28),
      0 24px 60px rgba(0,0,0,0.58),
      0 0 36px ${{hexToRgba(accent, 0.20)}};
    transform:translate(-50%, -50%);
  `;

  const headEl = document.createElement("div");
  headEl.className = "font-display";
  headEl.textContent = heading;
  headEl.style.cssText = `
    font-size: 30px; font-weight: 800; letter-spacing: 0.08em;
    color: ${{accent}};
    margin-bottom: 26px;
    padding-bottom: 18px;
    border-bottom: 1.5px solid rgba(255,255,255,0.12);
    text-shadow: 0 0 18px ${{hexToRgba(accent, 0.55)}};
  `;
  card.appendChild(headEl);

  const rows = items.map((txt, i) => {{
    const row = document.createElement("div");
    row.style.cssText = `
      display:flex; align-items:center; gap:22px;
      padding: 18px 20px;
      margin-bottom: ${{i === items.length - 1 ? 0 : 14}}px;
      border-radius: 20px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
    `;
    const iconBox = document.createElement("div");
    iconBox.style.cssText = `
      width: 48px; height: 48px; flex: 0 0 48px;
      border-radius: 14px;
      display:flex; align-items:center; justify-content:center;
      background: ${{hexToRgba(accent, 0.16)}};
      border: 2px solid ${{hexToRgba(accent, 0.72)}};
      box-shadow: 0 0 18px ${{hexToRgba(accent, 0.45)}};
    `;
    iconBox.innerHTML = `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="${{accent}}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path class="chk-path" d="M5 13l4.2 4.2L19 7.5" stroke-dasharray="28" stroke-dashoffset="28"/></svg>`;
    const pathEl = iconBox.querySelector(".chk-path");

    const label = document.createElement("div");
    label.className = "font-sans";
    label.textContent = txt;
    label.style.cssText = `
      font-size: 33px; font-weight: 600; color: #F1F5F9; line-height: 1.25;
    `;
    row.appendChild(iconBox);
    row.appendChild(label);
    card.appendChild(row);
    return {{ row, pathEl, delay: 0.22 + i * itemDelay }};
  }});

  stage.appendChild(card);
  return {{
    update(t) {{
      const u = easeOutQuart(clamp(t / 0.36, 0, 1));
      const out = exitFade(t, dur, 0.24);
      card.style.opacity = (u * out).toFixed(4);
      card.style.transform = `translate(-50%, calc(-50% + ${{lerp(28, 0, u).toFixed(2)}}px)) scale(${{lerp(0.92, 1.0, u).toFixed(4)}})`;

      rows.forEach(({{ row, pathEl, delay }}) => {{
        const ru = easeOutCubic(clamp((t - delay) / 0.28, 0, 1));
        const cu = easeOutCubic(clamp((t - delay - 0.10) / 0.26, 0, 1));
        row.style.opacity = ru.toFixed(4);
        row.style.transform = `translateX(${{lerp(-24, 0, ru).toFixed(2)}}px)`;
        pathEl.setAttribute("stroke-dashoffset", (28 * (1 - cu)).toFixed(2));
      }});
    }}
  }};
}}

// w03: @vuotaiai / @tng.vinhomes8 dark glass infographic card with ruler ticks, smoothly animating bars & numeric badges
function initW03(stage, p, dur) {{
  const heading = (p.title || "HIỆU SUẤT TĂNG TRƯỞNG").toUpperCase();
  const unit = p.unit || "%";
  const accent = p.accent || "#38BDF8";
  const highlightAccent = p.highlight_accent || "#FACC15";
  const orientation = p.orientation || "horizontal"; // horizontal | vertical
  const yPct = p.y_pct ?? 50;
  const bars = p.bars || [
    {{ label: "Thủ công", value: 28 }},
    {{ label: "Bán tự động", value: 62 }},
    {{ label: "Hệ thống AI", value: 96, highlight: true }},
  ];
  const maxVal = p.max_value || Math.max(...bars.map(b => Number(b.value) || 0), 100);

  const card = document.createElement("div");
  card.style.cssText = `
    position:absolute; left:50%; top:${{yPct}}%;
    width:${{Math.round(W * 0.86)}}px;
    padding: 36px 40px 42px 40px;
    border-radius: 34px;
    background: linear-gradient(160deg, rgba(13,20,36,0.90) 0%, rgba(6,10,20,0.95) 100%);
    border: 2px solid rgba(255,255,255,0.18);
    box-shadow:
      inset 0 2px 1px rgba(255,255,255,0.28),
      0 26px 64px rgba(0,0,0,0.60),
      0 0 38px ${{hexToRgba(accent, 0.22)}};
    transform:translate(-50%, -50%);
  `;

  const headEl = document.createElement("div");
  headEl.className = "font-display";
  headEl.textContent = heading;
  headEl.style.cssText = `
    font-size: 30px; font-weight: 800; letter-spacing: 0.06em;
    color: #F8FAFC; margin-bottom: 22px;
  `;
  card.appendChild(headEl);

  // Ruler ticks header
  const ruler = document.createElement("div");
  ruler.style.cssText = `
    display:flex; justify-content:space-between; align-items:flex-end;
    height: 22px; margin-bottom: 24px;
    border-bottom: 1px solid rgba(255,255,255,0.18);
    padding-bottom: 6px;
    font-size: 18px; color: rgba(148,163,184,0.85);
  `;
  for (let k = 0; k <= 4; k++) {{
    const tick = document.createElement("span");
    tick.className = "font-mono";
    tick.textContent = `${{Math.round((maxVal * k) / 4)}}${{unit}}`;
    ruler.appendChild(tick);
  }}
  card.appendChild(ruler);

  const barEls = [];
  if (orientation === "vertical") {{
    const cols = document.createElement("div");
    cols.style.cssText = `
      display:flex; align-items:flex-end; justify-content:space-around;
      height: 360px; gap: 24px; padding-top: 30px;
    `;
    bars.forEach((b, i) => {{
      const colColor = b.color || (b.highlight ? highlightAccent : accent);
      const col = document.createElement("div");
      col.style.cssText = `display:flex; flex-direction:column; align-items:center; flex:1; height:100%; justify-content:flex-end; gap:12px;`;
      const badge = document.createElement("div");
      badge.className = "font-mono";
      badge.style.cssText = `
        padding: 4px 14px; border-radius: 999px; font-size: 24px; font-weight: 800;
        color: #0F172A; background: ${{colColor}};
        box-shadow: 0 0 18px ${{hexToRgba(colColor, 0.7)}};
      `;
      const track = document.createElement("div");
      track.style.cssText = `
        width: 78px; height: 240px; border-radius: 18px;
        background: rgba(255,255,255,0.06);
        display:flex; align-items:flex-end; overflow:hidden;
        border: 1px solid rgba(255,255,255,0.10);
      `;
      const fill = document.createElement("div");
      fill.style.cssText = `
        width:100%; height:0%;
        border-radius: 16px;
        background: linear-gradient(180deg, #FFFFFF 0%, ${{colColor}} 26%, ${{hexToRgba(colColor, 0.72)}} 100%);
        box-shadow: 0 0 24px ${{hexToRgba(colColor, 0.65)}};
      `;
      track.appendChild(fill);
      const lbl = document.createElement("div");
      lbl.className = "font-sans";
      lbl.textContent = b.label;
      lbl.style.cssText = `font-size: 24px; font-weight: 700; color: #E2E8F0; text-align:center;`;
      col.appendChild(badge);
      col.appendChild(track);
      col.appendChild(lbl);
      cols.appendChild(col);
      barEls.push({{ fill, badge, target: Number(b.value) || 0, delay: 0.20 + i * 0.14 }});
    }});
    card.appendChild(cols);
  }} else {{
    bars.forEach((b, i) => {{
      const colColor = b.color || (b.highlight ? highlightAccent : accent);
      const row = document.createElement("div");
      row.style.cssText = `margin-bottom: ${{i === bars.length - 1 ? 0 : 24}}px;`;
      const topLine = document.createElement("div");
      topLine.style.cssText = `display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;`;
      const lbl = document.createElement("span");
      lbl.className = "font-sans";
      lbl.textContent = b.label;
      lbl.style.cssText = `font-size: 28px; font-weight: 700; color: #F1F5F9;`;
      const badge = document.createElement("span");
      badge.className = "font-mono";
      badge.style.cssText = `
        padding: 4px 16px; border-radius: 999px; font-size: 24px; font-weight: 800;
        color: #0B1120; background: ${{colColor}};
        box-shadow: 0 0 18px ${{hexToRgba(colColor, 0.65)}};
      `;
      topLine.appendChild(lbl);
      topLine.appendChild(badge);

      const track = document.createElement("div");
      track.style.cssText = `
        width:100%; height: 34px; border-radius: 999px;
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.10);
        overflow:hidden;
      `;
      const fill = document.createElement("div");
      fill.style.cssText = `
        height:100%; width:0%; border-radius:999px;
        background: linear-gradient(90deg, ${{hexToRgba(colColor, 0.72)}} 0%, ${{colColor}} 75%, #FFFFFF 100%);
        box-shadow: 0 0 22px ${{hexToRgba(colColor, 0.65)}};
      `;
      track.appendChild(fill);
      row.appendChild(topLine);
      row.appendChild(track);
      card.appendChild(row);
      barEls.push({{ fill, badge, target: Number(b.value) || 0, delay: 0.20 + i * 0.14 }});
    }});
  }}

  stage.appendChild(card);
  return {{
    update(t) {{
      const u = easeOutQuart(clamp(t / 0.36, 0, 1));
      const out = exitFade(t, dur, 0.24);
      card.style.opacity = (u * out).toFixed(4);
      card.style.transform = `translate(-50%, calc(-50% + ${{lerp(26, 0, u).toFixed(2)}}px)) scale(${{lerp(0.92, 1.0, u).toFixed(4)}})`;

      barEls.forEach(({{ fill, badge, target, delay }}) => {{
        const bu = easeOutQuart(clamp((t - delay) / 0.58, 0, 1));
        const pct = clamp((target / maxVal) * 100 * bu, 0, 100);
        if (orientation === "vertical") fill.style.height = `${{pct.toFixed(2)}}%`;
        else fill.style.width = `${{pct.toFixed(2)}}%`;
        badge.textContent = `${{Math.round(target * bu)}}${{unit}}`;
      }});
    }}
  }};
}}

// w04: @vuotaiai / @__dviet SVG <textPath> curved arc halo text orbiting above the speaker's head
function initW04(stage, p, dur) {{
  const text = (p.text || "TƯ DUY HỆ THỐNG  •  CHUẨN ĐIỆN ẢNH").toUpperCase();
  const cx = p.cx ?? Math.round(W * 0.5);
  const cy = p.cy ?? Math.round(H * 0.36);
  const radius = p.radius ?? Math.round(W * 0.34);
  const fontSize = p.font_size ?? Math.round(W * 0.044);
  const color = p.color || "#F8FAFC";
  const glow = p.glow || "#38BDF8";
  const orbitDeg = p.orbit_deg ?? 12;

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("width", String(W));
  svg.setAttribute("height", String(H));
  svg.setAttribute("viewBox", `0 0 ${{W}} ${{H}}`);
  svg.style.cssText = `position:absolute; inset:0; overflow:visible;`;

  // Top semicircle arc from left to right above (cx, cy)
  const dPath = `M ${{cx - radius}},${{cy}} A ${{radius}},${{radius}} 0 0,1 ${{cx + radius}},${{cy}}`;
  svg.innerHTML = `
    <defs>
      <path id="orbitArc" d="${{dPath}}" />
      <filter id="arcGlow" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="7" result="b1" />
        <feFlood flood-color="${{glow}}" flood-opacity="0.85" result="c1" />
        <feComposite in="c1" in2="b1" operator="in" result="g1" />
        <feMerge>
          <feMergeNode in="g1" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    <g id="arcGroup" transform-origin="${{cx}}px ${{cy}}px" filter="url(#arcGlow)">
      <text class="font-display" fill="${{color}}" font-size="${{fontSize}}" font-weight="800" letter-spacing="0.14em">
        <textPath id="arcTextPath" href="#orbitArc" startOffset="50%" text-anchor="middle">${{escapeHtml(text)}}</textPath>
      </text>
    </g>
  `;
  stage.appendChild(svg);
  const grp = svg.querySelector("#arcGroup");

  return {{
    update(t) {{
      const u = easeOutCubic(clamp(t / 0.44, 0, 1));
      const out = exitFade(t, dur, 0.24);
      const rot = lerp(-orbitDeg * 0.8, orbitDeg * 0.4, clamp(t / Math.max(dur, 0.5), 0, 1)) + Math.sin(t * 1.6) * 2.5;
      const sc = lerp(0.90, 1.0, u);
      grp.style.opacity = (u * out).toFixed(4);
      grp.style.transform = `rotate(${{rot.toFixed(2)}}deg) scale(${{sc.toFixed(4)}})`;
    }}
  }};
}}

// w05: @tng.vinhomes8 / @vuotaiai CSS-3D perspective-tilted glossy floating icon + label badge with bobbing + sheen
function initW05(stage, p, dur) {{
  const iconName = (p.icon || "sparkles").toLowerCase();
  const label = p.label || "AI Studio";
  const accent = p.accent || "#38BDF8";
  const xPct = p.x_pct ?? 76;
  const yPct = p.y_pct ?? 28;
  const tiltY = p.tilt_y ?? -14;
  const tiltX = p.tilt_x ?? 8;
  const iconSvg = SVG_ICONS[iconName] || SVG_ICONS.sparkles;

  const scene = document.createElement("div");
  scene.style.cssText = `
    position:absolute; left:${{xPct}}%; top:${{yPct}}%;
    transform:translate(-50%, -50%);
    perspective: 750px;
  `;

  const card = document.createElement("div");
  card.style.cssText = `
    position:relative; overflow:hidden;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px;
    min-width: 210px; padding: 26px 30px;
    border-radius: 30px;
    background: linear-gradient(145deg, rgba(22,32,54,0.92) 0%, rgba(10,15,28,0.96) 100%);
    border: 2px solid rgba(255,255,255,0.28);
    box-shadow:
      inset 0 2px 2px rgba(255,255,255,0.42),
      inset 0 -4px 14px ${{hexToRgba(accent, 0.28)}},
      0 22px 48px rgba(0,0,0,0.55),
      0 0 34px ${{hexToRgba(accent, 0.42)}};
    transform-style: preserve-3d;
  `;

  const sheen = document.createElement("div");
  sheen.style.cssText = `
    position:absolute; top:-40%; left:-60%;
    width: 65%; height: 180%;
    background: linear-gradient(105deg, transparent 20%, rgba(255,255,255,0.28) 50%, transparent 80%);
    transform: rotate(18deg);
    pointer-events:none;
  `;

  const iconRing = document.createElement("div");
  iconRing.style.cssText = `
    width: 84px; height: 84px; border-radius: 24px;
    display:flex; align-items:center; justify-content:center;
    background: radial-gradient(circle at 30% 25%, ${{hexToRgba(accent, 0.42)}}, ${{hexToRgba(accent, 0.14)}});
    border: 1.5px solid ${{hexToRgba(accent, 0.72)}};
    box-shadow: 0 0 24px ${{hexToRgba(accent, 0.55)}};
  `;
  iconRing.innerHTML = `<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" style="filter:drop-shadow(0 0 10px ${{hexToRgba(accent, 0.9)}})">${{iconSvg}}</svg>`;

  const lbl = document.createElement("div");
  lbl.className = "font-sans";
  lbl.textContent = label;
  lbl.style.cssText = `
    font-size: 28px; font-weight: 800; color: #F8FAFC;
    letter-spacing: 0.02em; text-align:center;
    text-shadow: 0 2px 10px rgba(0,0,0,0.45);
  `;

  card.appendChild(sheen);
  card.appendChild(iconRing);
  card.appendChild(lbl);
  scene.appendChild(card);
  stage.appendChild(scene);

  return {{
    update(t) {{
      const u = easeOutBack(clamp(t / 0.42, 0, 1), 1.4);
      const op = easeOutCubic(clamp(t / 0.22, 0, 1)) * exitFade(t, dur, 0.22);
      const bobY = Math.sin(t * 2.8) * 8;
      const ry = tiltY + Math.sin(t * 1.9) * 5;
      const rx = tiltX + Math.cos(t * 2.1) * 3.5;
      const sc = lerp(0.75, 1.0, u);
      card.style.opacity = op.toFixed(4);
      card.style.transform = `translateY(${{bobY.toFixed(2)}}px) rotateY(${{ry.toFixed(2)}}deg) rotateX(${{rx.toFixed(2)}}deg) scale(${{sc.toFixed(4)}})`;

      // Periodic glossy sheen sweep every 2.4s
      const sweepPhase = (t % 2.4) / 0.9;
      const sheenX = sweepPhase <= 1 ? lerp(-80, 220, easeInOutCubic(sweepPhase)) : 240;
      sheen.style.left = `${{sheenX.toFixed(1)}}%`;
    }}
  }};
}}

// w06: @vuotaiai / @xuanart.visual giant neon-stroked hollow display word for dark stage behind a glowing squircle PiP
function initW06(stage, p, dur) {{
  const text = (p.text || "FOCUS").toUpperCase();
  const accent = p.accent || "#38BDF8";
  const fontSize = p.font_size || Math.round(W * 0.21);
  const yPct = p.y_pct ?? 46;
  const strokePx = p.stroke_px ?? 4.5;

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    position:absolute; left:50%; top:${{yPct}}%;
    width:${{Math.round(W * 0.98)}}px;
    transform:translate(-50%, -50%);
    text-align:center;
  `;

  const el = document.createElement("div");
  el.className = "font-display";
  el.textContent = text;
  el.style.cssText = `
    font-size:${{fontSize}}px;
    font-weight:900;
    line-height:0.96;
    letter-spacing:-0.02em;
    color: transparent;
    -webkit-text-stroke: ${{strokePx}}px ${{accent}};
    filter:
      drop-shadow(0 0 12px ${{hexToRgba(accent, 0.9)}})
      drop-shadow(0 0 34px ${{hexToRgba(accent, 0.55)}});
  `;
  wrap.appendChild(el);
  stage.appendChild(wrap);

  return {{
    update(t) {{
      const u = easeOutQuart(clamp(t / 0.45, 0, 1));
      const out = exitFade(t, dur, 0.25);
      const pulse = 0.88 + 0.12 * Math.sin(t * 3.2);
      const sc = lerp(1.08, 1.0, u);
      el.style.opacity = (u * out * pulse).toFixed(4);
      el.style.transform = `scale(${{sc.toFixed(4)}})`;
    }}
  }};
}}

// ============================================================================
// CONTINUOUS VERBATIM KARAOKE CAPTION RAIL (rail_karaoke)
// ============================================================================

function initRailKaraoke(stage, p, dur) {{
  // Accepts either segments: [{{start, end, words: [{{text, start, end}}]}}]
  // or flat words: [{{text, start, end}}] (auto-chunked into clean 4-6 word lines).
  const styleMode = p.style || "dark_pill"; // dark_pill | optical_glow
  const dockMode = p.dock_mode || "normal"; // normal | compact_bottom
  const accent = p.accent || "#FACC15";
  const textColor = p.color || "#FFFFFF";
  const fontSize = p.font_size || (dockMode === "compact_bottom" ? 40 : 48);
  const bottomPx = dockMode === "compact_bottom" ? Math.round(H * 0.085) : Math.round(H * 0.165);

  let segments = Array.isArray(p.segments) ? p.segments : (Array.isArray(p.cues) ? p.cues : []);
  if (!segments.length && Array.isArray(p.words) && p.words.length) {{
    const chunkSize = dockMode === "compact_bottom" ? 7 : 5;
    for (let i = 0; i < p.words.length; i += chunkSize) {{
      const chunk = p.words.slice(i, i + chunkSize);
      segments.push({{
        start: Number(chunk[0].start ?? 0),
        end: Number(chunk[chunk.length - 1].end ?? (chunk[0].start + 1.5)),
        words: chunk,
      }});
    }}
  }}

  const container = document.createElement("div");
  const railBox = clampToLSafeZone(120 * (W / 1080), (H - bottomPx - 140), 720 * (W / 1080), 140);
  container.style.cssText = IS_PORTRAIT_9_16 && p.l_safe !== false
    ? `
      position:absolute; left:${{railBox.x.toFixed(1)}}px; top:${{railBox.y.toFixed(1)}}px;
      width:${{railBox.w.toFixed(1)}}px; height:${{railBox.h.toFixed(1)}}px;
      display:flex; justify-content:center; align-items:flex-end;
      pointer-events:none;
    `
    : `
      position:absolute; left:50%; bottom:${{bottomPx}}px;
      transform:translateX(-50%);
      width:${{Math.round(W * 0.90)}}px;
      display:flex; justify-content:center;
      pointer-events:none;
    `;

  const pill = document.createElement("div");
  pill.className = "font-sans";
  pill.style.cssText = `
    display:inline-flex; flex-wrap:wrap; justify-content:center; align-items:center;
    gap: 8px 13px;
    max-width: 100%;
    padding: ${{styleMode === "dark_pill" ? (dockMode === "compact_bottom" ? "14px 26px" : "18px 30px") : "8px 16px"}};
    border-radius: 26px;
    background: ${{styleMode === "dark_pill" ? "rgba(8,12,22,0.82)" : "transparent"}};
    border: ${{styleMode === "dark_pill" ? "1.5px solid rgba(255,255,255,0.16)" : "none"}};
    box-shadow: ${{styleMode === "dark_pill" ? "0 14px 36px rgba(0,0,0,0.48)" : "none"}};
    font-size: ${{fontSize}}px;
    font-weight: 800;
    line-height: 1.24;
    text-align: center;
  `;
  container.appendChild(pill);
  stage.appendChild(container);

  let renderedSegIdx = -1;
  let wordSpans = [];

  function findState(t) {{
    for (let i = 0; i < segments.length; i++) {{
      const s = segments[i];
      if (t >= s.start - 0.02 && t <= s.end + 0.04) {{
        const ws = s.words || [];
        let activeWord = -1;
        for (let j = 0; j < ws.length; j++) {{
          const wStart = Number(ws[j].start ?? s.start);
          const wEnd = Number(ws[j].end ?? s.end);
          if (t >= wStart - 0.01 && t <= wEnd + 0.02) {{
            activeWord = j;
            break;
          }}
          if (t > wEnd) activeWord = j;
        }}
        return {{ segIdx: i, activeWord }};
      }}
    }}
    return {{ segIdx: -1, activeWord: -1 }};
  }}

  return {{
    stateKey(t) {{
      const st = findState(t);
      return `${{st.segIdx}}:${{st.activeWord}}`;
    }},
    update(t) {{
      const {{ segIdx, activeWord }} = findState(t);
      if (segIdx < 0) {{
        pill.style.opacity = "0";
        return;
      }}
      pill.style.opacity = "1";
      if (segIdx !== renderedSegIdx) {{
        renderedSegIdx = segIdx;
        pill.innerHTML = "";
        const ws = segments[segIdx].words || [];
        wordSpans = ws.map((w) => {{
          const sp = document.createElement("span");
          sp.textContent = w.text || w.word || "";
          sp.style.cssText = `
            display:inline-block;
            transition: none;
            transform-origin: center center;
          `;
          pill.appendChild(sp);
          return sp;
        }});
      }}
      wordSpans.forEach((sp, j) => {{
        const isActive = j === activeWord;
        const isPast = j < activeWord;
        if (isActive) {{
          sp.style.color = accent;
          sp.style.transform = "scale(1.10) translateY(-2px)";
          sp.style.textShadow = `0 0 18px ${{hexToRgba(accent, 0.85)}}, 0 0 36px ${{hexToRgba(accent, 0.45)}}`;
        }} else {{
          sp.style.color = isPast ? textColor : "rgba(248,250,252,0.74)";
          sp.style.transform = "scale(1.0)";
          sp.style.textShadow = styleMode === "optical_glow"
            ? `0 0 14px rgba(15,23,42,0.65), 0 0 26px ${{hexToRgba(accent, 0.25)}}`
            : "0 2px 8px rgba(0,0,0,0.4)";
        }}
      }});
    }}
  }};
}}

// ============================================================================
// DYNAMIC MULTI-STYLE TYPOGRAPHY SUBTITLE RAIL v8.1 (rail_dynamic_typo)
// Renders all 10 distinct sub_01..sub_10 multi-font, multi-color, zero-black-stroke
// subtitle styles strictly inside TikTok L-Safe-Zone (x: 120..840, y: 980..1216).
// ============================================================================

function initRailDynamicTypo(stage, p, dur) {{
  let segments = Array.isArray(p.segments) ? p.segments : (Array.isArray(p.cues) ? p.cues : []);
  if (!segments.length && Array.isArray(p.words) && p.words.length) {{
    for (let i = 0; i < p.words.length; i += 4) {{
      const chunk = p.words.slice(i, i + 4);
      segments.push({{
        start: Number(chunk[0].start ?? 0),
        end: Number(chunk[chunk.length - 1].end ?? (chunk[0].start + 1.5)),
        words: chunk,
        sub_mode: "sub_01",
        font_pair: "FP1_EDITORIAL_LUXE",
        palette: "PAL_ELECTRIC_CYAN",
        highlight_idx: Math.max(0, chunk.length - 1),
      }});
    }}
  }}

  // Strict TikTok L-Safe-Zone subtitle box: x in [120, 840], y in [980, 1216]
  const sx = W / 1080;
  const sy = H / 1920;
  const boxH = Math.round(236 * sy);
  const boxW = Math.round(720 * sx);
  const safeBox = clampToLSafeZone(120 * sx, 980 * sy, boxW, boxH);

  const root = document.createElement("div");
  root.style.cssText = `
    position:absolute;
    left:${{safeBox.x.toFixed(1)}}px;
    top:${{safeBox.y.toFixed(1)}}px;
    width:${{safeBox.w.toFixed(1)}}px;
    height:${{safeBox.h.toFixed(1)}}px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    pointer-events:none;
    overflow:visible;
  `;
  stage.appendChild(root);

  let renderedSegIdx = -1;
  let activeUpdater = null;

  function findCue(t) {{
    for (let i = 0; i < segments.length; i++) {{
      const s = segments[i];
      if (t >= Number(s.start) - 0.015 && t <= Number(s.end) + 0.03) {{
        return i;
      }}
    }}
    return -1;
  }}

  function activeWordIndex(seg, t) {{
    const ws = seg.words || [];
    let active = 0;
    for (let j = 0; j < ws.length; j++) {{
      const ws0 = Number(ws[j].start ?? seg.start);
      const ws1 = Number(ws[j].end ?? seg.end);
      if (t >= ws0 - 0.01 && t <= ws1 + 0.02) return j;
      if (t > ws1) active = j;
    }}
    return active;
  }}

  function wordText(w) {{
    return String(w.word ?? w.text ?? "").normalize("NFC");
  }}

  function glowTextShadow(glowHex, strong = false) {{
    return strong
      ? `0 4px 18px rgba(0,0,0,0.75), 0 0 18px ${{hexToRgba(glowHex, 0.85)}}, 0 0 40px ${{hexToRgba(glowHex, 0.45)}}`
      : `0 4px 18px rgba(0,0,0,0.75), 0 0 14px ${{hexToRgba(glowHex, 0.42)}}`;
  }}

  function gradFilter(glowHex) {{
    return `drop-shadow(0 4px 18px rgba(0,0,0,0.75)) drop-shadow(0 0 22px ${{hexToRgba(glowHex, 0.65)}})`;
  }}

  function mountCue(seg) {{
    root.innerHTML = "";
    const mode = seg.sub_mode || "sub_01";
    const fp = getFontPair(seg.font_pair || "FP1_EDITORIAL_LUXE");
    const pal = getPalette(seg.palette || "PAL_ELECTRIC_CYAN");
    const ws = seg.words || [];
    const tokens = ws.length ? ws.map(wordText) : String(seg.text || "").split(/\\s+/).filter(Boolean);
    const hlIdx = clamp(Number(seg.highlight_idx ?? (tokens.length - 1)), 0, Math.max(0, tokens.length - 1));
    const cStart = Number(seg.start ?? 0);
    const cEnd = Number(seg.end ?? (cStart + 1.0));
    const cDur = Math.max(0.12, cEnd - cStart);

    // Helper for smooth cue fade-out at end
    const cueFade = (localT) => {{
      const outWin = Math.min(0.12, cDur * 0.25);
      const rem = cDur - localT;
      if (rem >= outWin) return 1;
      return easeOutCubic(clamp(rem / Math.max(0.02, outWin), 0, 1));
    }};

    // ---- sub_01: 2-Tier Micro-Lead + Neon Keyword ----
    if (mode === "sub_01") {{
      const leadTokens = tokens.filter((_, i) => i !== hlIdx);
      const heroTok = (tokens[hlIdx] || tokens[0] || "").toUpperCase();
      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex; flex-direction:column; align-items:center; gap:2px; width:100%; text-align:center;";

      let leadEl = null;
      if (leadTokens.length) {{
        leadEl = document.createElement("div");
        leadEl.textContent = leadTokens.join(" ");
        leadEl.style.cssText = `
          font-family:${{fp.css_accent}};
          font-size:32px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;
          color:rgba(248,250,252,0.92);
          text-shadow:${{glowTextShadow(pal.glow_color, false)}};
        `;
        wrap.appendChild(leadEl);
      }}

      const heroEl = document.createElement("div");
      heroEl.textContent = heroTok;
      heroEl.style.cssText = `
        font-family:${{fp.css_primary}};
        font-size:${{heroTok.length > 10 ? 56 : 68}}px; font-weight:900; line-height:1.06;
        letter-spacing:-0.015em;
        background:${{pal.gradient}};
        -webkit-background-clip:text; background-clip:text; color:transparent;
        filter:${{gradFilter(pal.glow_color)}};
      `;
      wrap.appendChild(heroEl);
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutBack(clamp(lt / 0.24, 0, 1), 1.3);
        const out = cueFade(lt);
        wrap.style.opacity = (easeOutCubic(clamp(lt / 0.14, 0, 1)) * out).toFixed(4);
        heroEl.style.transform = `translateY(${{lerp(18, 0, clamp(u, 0, 1.08)).toFixed(2)}}px) scale(${{lerp(0.86, 1.0, clamp(u, 0, 1.06)).toFixed(4)}})`;
        if (leadEl) {{
          const lu = easeOutCubic(clamp(lt / 0.18, 0, 1));
          leadEl.style.transform = `translateY(${{lerp(10, 0, lu).toFixed(2)}}px)`;
        }}
      }};
    }}

    // ---- sub_02: Mixed-Font Inline Emphasis (Sans + Playfair BoldItalic keyword) ----
    if (mode === "sub_02") {{
      const wrap = document.createElement("div");
      wrap.style.cssText = `
        display:flex; flex-wrap:wrap; justify-content:center; align-items:baseline;
        gap: 6px 14px; width:100%; text-align:center; line-height:1.22;
      `;
      const spans = tokens.map((tok, i) => {{
        const isHl = i === hlIdx;
        const sp = document.createElement("span");
        sp.textContent = tok;
        if (isHl) {{
          sp.style.cssText = `
            display:inline-block;
            font-family:"Playfair Display", ${{fp.css_accent}};
            font-style:italic; font-weight:700; font-size:58px;
            background:${{pal.gradient}};
            -webkit-background-clip:text; background-clip:text; color:transparent;
            filter:${{gradFilter(pal.glow_color)}};
            padding:0 4px;
          `;
        }} else {{
          sp.style.cssText = `
            display:inline-block;
            font-family:${{fp.css_primary}};
            font-weight:700; font-size:44px;
            color:${{pal.primary_color || "#F8FAFC"}};
            text-shadow:${{glowTextShadow(pal.glow_color, false)}};
          `;
        }}
        wrap.appendChild(sp);
        return {{ sp, isHl }};
      }});
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutCubic(clamp(lt / 0.22, 0, 1));
        const out = cueFade(lt);
        const act = activeWordIndex(seg, t);
        wrap.style.opacity = (u * out).toFixed(4);
        wrap.style.transform = `translateY(${{lerp(14, 0, u).toFixed(2)}}px)`;
        spans.forEach(({{ sp, isHl }}, i) => {{
          const sc = (i === act) ? 1.08 : (isHl ? 1.03 : 1.0);
          sp.style.transform = `scale(${{sc.toFixed(3)}})`;
        }});
      }};
    }}

    // ---- sub_03: Brushed Script Accent Word (clip-path reveal) ----
    if (mode === "sub_03") {{
      const lead = tokens.filter((_, i) => i !== hlIdx).join(" ");
      const scriptTok = tokens[hlIdx] || tokens[0] || "";
      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex; flex-direction:column; align-items:center; gap:0px; width:100%; text-align:center;";

      let leadEl = null;
      if (lead) {{
        leadEl = document.createElement("div");
        leadEl.textContent = lead;
        leadEl.style.cssText = `
          font-family:${{fp.css_primary}};
          font-size:36px; font-weight:800; color:#F8FAFC;
          text-shadow:${{glowTextShadow(pal.glow_color, false)}};
        `;
        wrap.appendChild(leadEl);
      }}

      const scriptEl = document.createElement("div");
      scriptEl.textContent = scriptTok;
      scriptEl.style.cssText = `
        font-family:"SVN-Aaron Script", "Dancing Script", "Playfair Display", cursive;
        font-size:${{scriptTok.length > 9 ? 62 : 76}}px;
        font-weight:700; line-height:1.15;
        color:${{pal.accent_color}};
        text-shadow:${{glowTextShadow(pal.glow_color, true)}};
        padding: 4px 18px;
        transform: rotate(-3deg);
      `;
      wrap.appendChild(scriptEl);
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const wipe = easeOutQuart(clamp(lt / 0.34, 0, 1));
        const out = cueFade(lt);
        wrap.style.opacity = (easeOutCubic(clamp(lt / 0.14, 0, 1)) * out).toFixed(4);
        const rightClip = ((1 - wipe) * 100).toFixed(1);
        scriptEl.style.clipPath = `inset(-10% ${{rightClip}}% -10% -5%)`;
      }};
    }}

    // ---- sub_04: Cursor-Pin Highlight Bar (glowing vertical pins parting outward) ----
    if (mode === "sub_04") {{
      const row = document.createElement("div");
      row.style.cssText = `
        position:relative; display:inline-flex; align-items:center; justify-content:center;
        padding: 14px 32px; max-width:100%;
      `;
      const ribbon = document.createElement("div");
      ribbon.style.cssText = `
        position:absolute; inset:0; border-radius:14px;
        background:linear-gradient(90deg, ${{hexToRgba(pal.glow_color, 0.24)}}, rgba(15,23,42,0.52), ${{hexToRgba(pal.glow_color, 0.24)}});
        border-top:1.5px solid ${{hexToRgba(pal.accent_color, 0.55)}};
        border-bottom:1.5px solid ${{hexToRgba(pal.accent_color, 0.55)}};
        box-shadow: 0 8px 28px rgba(0,0,0,0.45), 0 0 24px ${{hexToRgba(pal.glow_color, 0.32)}};
        transform-origin:center center;
      `;
      const leftPin = document.createElement("div");
      const rightPin = document.createElement("div");
      const pinCss = `
        position:absolute; top:4px; bottom:4px; width:5px; border-radius:4px;
        background:${{pal.accent_color}};
        box-shadow: 0 0 14px ${{hexToRgba(pal.accent_color, 0.95)}}, 0 0 28px ${{hexToRgba(pal.glow_color, 0.65)}};
      `;
      leftPin.style.cssText = pinCss + "left:0;";
      rightPin.style.cssText = pinCss + "right:0;";

      const textEl = document.createElement("div");
      textEl.style.cssText = `
        position:relative; z-index:1;
        display:flex; flex-wrap:wrap; justify-content:center; gap:6px 12px;
        font-family:${{fp.css_primary}};
        font-size:40px; font-weight:800; line-height:1.2; text-align:center;
      `;
      const spans = tokens.map((tok, i) => {{
        const sp = document.createElement("span");
        sp.textContent = tok;
        sp.style.cssText = `
          color:${{i === hlIdx ? pal.accent_color : "#F8FAFC"}};
          text-shadow:${{glowTextShadow(pal.glow_color, i === hlIdx)}};
        `;
        textEl.appendChild(sp);
        return sp;
      }});
      row.appendChild(ribbon);
      row.appendChild(leftPin);
      row.appendChild(rightPin);
      row.appendChild(textEl);
      root.appendChild(row);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutQuart(clamp(lt / 0.28, 0, 1));
        const out = cueFade(lt);
        const act = activeWordIndex(seg, t);
        row.style.opacity = (clamp(lt / 0.10, 0, 1) * out).toFixed(4);
        ribbon.style.transform = `scaleX(${{lerp(0.08, 1.0, u).toFixed(4)}})`;
        const pinShift = lerp(120, 0, u);
        leftPin.style.transform = `translateX(${{pinShift.toFixed(1)}}px)`;
        rightPin.style.transform = `translateX(${{(-pinShift).toFixed(1)}}px)`;
        textEl.style.clipPath = `inset(0 ${{(50 * (1 - u)).toFixed(1)}}% 0 ${{(50 * (1 - u)).toFixed(1)}}%)`;
        spans.forEach((sp, i) => {{
          sp.style.color = (i === act || i === hlIdx) ? pal.accent_color : "#F8FAFC";
        }});
      }};
    }}

    // ---- sub_05: 3-Tier Asymmetric Sandwich (top-left / center giant / bottom-right) ----
    if (mode === "sub_05") {{
      const pre = tokens.slice(0, hlIdx).join(" ");
      const mid = (tokens[hlIdx] || tokens[0] || "").toUpperCase();
      const post = tokens.slice(hlIdx + 1).join(" ");

      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex; flex-direction:column; width:100%; gap:2px; padding:0 12px;";

      const topEl = document.createElement("div");
      topEl.textContent = pre;
      topEl.style.cssText = `
        align-self:flex-start;
        font-family:${{fp.css_accent}}; font-size:32px; font-weight:600;
        color:rgba(248,250,252,0.90);
        text-shadow:${{glowTextShadow(pal.glow_color, false)}};
        min-height:${{pre ? "36px" : "0"}};
      `;

      const midEl = document.createElement("div");
      midEl.textContent = mid;
      midEl.style.cssText = `
        align-self:center;
        font-family:${{fp.css_primary}};
        font-size:${{mid.length > 9 ? 54 : 66}}px; font-weight:900; line-height:1.04;
        background:${{pal.gradient}};
        -webkit-background-clip:text; background-clip:text; color:transparent;
        filter:${{gradFilter(pal.glow_color)}};
      `;

      const botEl = document.createElement("div");
      botEl.textContent = post;
      botEl.style.cssText = `
        align-self:flex-end;
        font-family:${{fp.css_accent}}; font-size:32px; font-weight:600;
        color:rgba(248,250,252,0.90);
        text-shadow:${{glowTextShadow(pal.glow_color, false)}};
        min-height:${{post ? "36px" : "0"}};
      `;

      if (pre) wrap.appendChild(topEl);
      wrap.appendChild(midEl);
      if (post) wrap.appendChild(botEl);
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutQuart(clamp(lt / 0.28, 0, 1));
        const out = cueFade(lt);
        wrap.style.opacity = (u * out).toFixed(4);
        topEl.style.transform = `translateX(${{lerp(-28, 0, u).toFixed(1)}}px)`;
        midEl.style.transform = `scale(${{lerp(0.88, 1.0, easeOutBack(clamp(lt / 0.26, 0, 1), 1.2)).toFixed(4)}})`;
        botEl.style.transform = `translateX(${{lerp(28, 0, u).toFixed(1)}}px)`;
      }};
    }}

    // ---- sub_06: Overlap Feather Kiss (top white feathered + bottom glowing bold) ----
    if (mode === "sub_06") {{
      const splitAt = Math.max(1, Math.ceil(tokens.length / 2));
      const line1 = tokens.slice(0, splitAt).join(" ");
      const line2 = tokens.slice(splitAt).join(" ");

      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex; flex-direction:column; align-items:center; width:100%; text-align:center;";

      const topEl = document.createElement("div");
      topEl.textContent = line1;
      topEl.style.cssText = `
        font-family:${{fp.css_accent}}; font-style:italic; font-weight:600;
        font-size:40px; line-height:1.15; color:rgba(255,255,255,0.92);
        text-shadow: 0 4px 18px rgba(0,0,0,0.75), 0 0 18px rgba(255,255,255,0.45);
      `;
      wrap.appendChild(topEl);

      let botEl = null;
      if (line2) {{
        botEl = document.createElement("div");
        botEl.textContent = line2.toUpperCase();
        botEl.style.cssText = `
          margin-top:-10px;
          font-family:${{fp.css_primary}}; font-weight:900;
          font-size:54px; line-height:1.08; letter-spacing:-0.015em;
          background:${{pal.gradient}};
          -webkit-background-clip:text; background-clip:text; color:transparent;
          filter:${{gradFilter(pal.glow_color)}};
        `;
        wrap.appendChild(botEl);
      }}
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u1 = easeOutCubic(clamp(lt / 0.24, 0, 1));
        const u2 = easeOutQuart(clamp((lt - 0.06) / 0.26, 0, 1));
        const out = cueFade(lt);
        wrap.style.opacity = out.toFixed(4);
        topEl.style.opacity = u1.toFixed(4);
        topEl.style.filter = u1 < 0.95 ? `blur(${{lerp(6, 0, u1).toFixed(2)}}px)` : "none";
        topEl.style.transform = `translateY(${{lerp(-10, 0, u1).toFixed(1)}}px)`;
        if (botEl) {{
          botEl.style.opacity = u2.toFixed(4);
          botEl.style.transform = `translateY(${{lerp(14, 0, u2).toFixed(1)}}px) scale(${{lerp(0.94, 1.0, u2).toFixed(4)}})`;
        }}
      }};
    }}

    // ---- sub_07: Soft Blur-Bloom Crystallize (italic serif focus rack) ----
    if (mode === "sub_07") {{
      const el = document.createElement("div");
      el.style.cssText = `
        width:100%; text-align:center;
        font-family:"Fraunces", "Lora", "Playfair Display", Georgia, serif;
        font-style:italic; font-weight:700; font-size:48px; line-height:1.22;
        color:${{pal.primary_color || "#F8FAFC"}};
        text-shadow:${{glowTextShadow(pal.glow_color, true)}};
      `;
      tokens.forEach((tok, i) => {{
        const sp = document.createElement("span");
        sp.textContent = (i > 0 ? " " : "") + tok;
        if (i === hlIdx) {{
          sp.style.color = pal.accent_color;
        }}
        el.appendChild(sp);
      }});
      root.appendChild(el);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutQuart(clamp(lt / 0.34, 0, 1));
        const out = cueFade(lt);
        const blur = lerp(14, 0, u);
        el.style.opacity = (easeOutCubic(clamp(lt / 0.20, 0, 1)) * out).toFixed(4);
        el.style.filter = blur > 0.08 ? `blur(${{blur.toFixed(2)}}px)` : "none";
        el.style.letterSpacing = `${{lerp(0.10, 0.01, u).toFixed(3)}}em`;
        el.style.transform = `scale(${{lerp(1.06, 1.0, u).toFixed(4)}})`;
      }};
    }}

    // ---- sub_08: Elastic Wave Pop (chunky spring overshoot) ----
    if (mode === "sub_08") {{
      const wrap = document.createElement("div");
      wrap.style.cssText = `
        display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
        gap: 8px 16px; width:100%; text-align:center;
      `;
      const spans = tokens.map((tok, i) => {{
        const sp = document.createElement("span");
        sp.textContent = tok;
        sp.style.cssText = `
          display:inline-block;
          font-family:"Unbounded", "Paytone One", "Montserrat", sans-serif;
          font-weight:800; font-size:${{tokens.length <= 2 ? 52 : 42}}px;
          line-height:1.18;
          color:${{i === hlIdx ? pal.accent_color : "#FFFFFF"}};
          text-shadow:${{glowTextShadow(pal.glow_color, i === hlIdx)}};
          transform-origin:center bottom;
        `;
        wrap.appendChild(sp);
        return sp;
      }});
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const out = cueFade(lt);
        const act = activeWordIndex(seg, t);
        wrap.style.opacity = out.toFixed(4);
        spans.forEach((sp, i) => {{
          const wStart = ws[i] ? Number(ws[i].start ?? (cStart + i * 0.06)) : (cStart + i * 0.06);
          const wt = Math.max(0, t - Math.min(wStart, cStart + i * 0.06));
          const u = easeOutBack(clamp(wt / 0.24, 0, 1), 1.75);
          const isAct = i === act;
          const baseSc = clamp(u, 0, 1.18);
          const actBoost = isAct ? 1.12 : 1.0;
          const dy = lerp(22, 0, clamp(u, 0, 1)) + (isAct ? -4 : 0);
          sp.style.opacity = clamp(wt / 0.10, 0, 1).toFixed(4);
          sp.style.transform = `translateY(${{dy.toFixed(1)}}px) scale(${{(baseSc * actBoost).toFixed(4)}})`;
        }});
      }};
    }}

    // ---- sub_09: Negation Laser Strike (crimson bar slice for warnings/myths) ----
    if (mode === "sub_09") {{
      const crim = getPalette("PAL_CORAL_CRIMSON");
      const wrap = document.createElement("div");
      wrap.style.cssText = `
        display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
        gap: 6px 14px; width:100%; text-align:center;
      `;
      let strikeBar = null;
      const spans = tokens.map((tok, i) => {{
        const isHl = i === hlIdx;
        const box = document.createElement("span");
        box.style.cssText = "position:relative; display:inline-block; padding: 0 4px;";
        const lbl = document.createElement("span");
        lbl.textContent = tok.toUpperCase();
        lbl.style.cssText = `
          font-family:"Barlow Condensed", "Oswald", "Be Vietnam Pro", sans-serif;
          font-weight:800; font-size:${{isHl ? 60 : 50}}px; line-height:1.1;
          letter-spacing:0.01em;
          color:${{isHl ? crim.accent_color : "#FFF5F5"}};
          text-shadow:${{glowTextShadow(crim.glow_color, isHl)}};
        `;
        box.appendChild(lbl);
        if (isHl) {{
          strikeBar = document.createElement("span");
          strikeBar.style.cssText = `
            position:absolute; left:-6px; right:-6px; top:52%; height:6px;
            border-radius:4px;
            background:linear-gradient(90deg, #FFE4E6 0%, #F43F5E 45%, #E11D48 100%);
            box-shadow: 0 0 16px rgba(244,63,94,0.95), 0 0 32px rgba(225,29,72,0.75);
            transform-origin:left center;
            transform: rotate(-2.5deg) scaleX(0);
          `;
          box.appendChild(strikeBar);
        }}
        wrap.appendChild(box);
        return box;
      }});
      root.appendChild(wrap);

      return (t) => {{
        const lt = Math.max(0, t - cStart);
        const u = easeOutCubic(clamp(lt / 0.18, 0, 1));
        const slashU = easeOutQuart(clamp((lt - 0.10) / 0.24, 0, 1));
        const out = cueFade(lt);
        // Subtle kinetic impact shake when laser finishes slicing
        const shake = (lt > 0.12 && lt < 0.34) ? Math.sin(lt * 55) * 2.8 * (1 - (lt - 0.12) / 0.22) : 0;
        wrap.style.opacity = (u * out).toFixed(4);
        wrap.style.transform = `translateX(${{shake.toFixed(2)}}px)`;
        if (strikeBar) {{
          strikeBar.style.transform = `rotate(-2.5deg) scaleX(${{slashU.toFixed(4)}})`;
        }}
      }};
    }}

    // ---- sub_10: Quiet Whisper Karaoke Rail (minimal breathing room) ----
    const wrap = document.createElement("div");
    wrap.style.cssText = `
      display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
      gap: 6px 11px; width:100%; text-align:center; padding-top:36px;
    `;
    const spans = tokens.map((tok) => {{
      const sp = document.createElement("span");
      sp.textContent = tok;
      sp.style.cssText = `
        display:inline-block;
        font-family:${{fp.css_accent}};
        font-size:36px; font-weight:600; letter-spacing:0.02em; line-height:1.25;
        color:rgba(248,250,252,0.76);
        text-shadow: 0 4px 18px rgba(0,0,0,0.75);
      `;
      wrap.appendChild(sp);
      return sp;
    }});
    root.appendChild(wrap);

    return (t) => {{
      const lt = Math.max(0, t - cStart);
      const u = easeOutCubic(clamp(lt / 0.20, 0, 1));
      const out = cueFade(lt);
      const act = activeWordIndex(seg, t);
      wrap.style.opacity = (u * out).toFixed(4);
      spans.forEach((sp, i) => {{
        if (i === act) {{
          sp.style.color = "#FFFFFF";
          sp.style.textShadow = glowTextShadow(pal.glow_color, true);
          sp.style.transform = "translateY(-1.5px)";
        }} else {{
          sp.style.color = i < act ? "rgba(248,250,252,0.92)" : "rgba(248,250,252,0.68)";
          sp.style.textShadow = "0 4px 18px rgba(0,0,0,0.75)";
          sp.style.transform = "none";
        }}
      }});
    }};
  }}

  return {{
    stateKey(t) {{
      const idx = findCue(t);
      if (idx < 0) return "empty";
      // Quantize animations smoothly at frame level during active cues
      return null;
    }},
    update(t) {{
      const idx = findCue(t);
      if (idx < 0) {{
        root.style.opacity = "0";
        return;
      }}
      root.style.opacity = "1";
      if (idx !== renderedSegIdx) {{
        renderedSegIdx = idx;
        activeUpdater = mountCue(segments[idx]);
      }}
      if (activeUpdater) activeUpdater(t);
    }}
  }};
}}
</script>
</body>
</html>
"""


class CinemaWidgetRenderer:
    """Persistent single-browser Playwright renderer for deterministic RGBA .mov plates."""

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, executable_path: str = CHROME_EXECUTABLE):
        self.width = int(width)
        self.height = int(height)
        self.executable_path = executable_path
        self._pw = None
        self._browser = None
        self._page = None

    def __enter__(self) -> "CinemaWidgetRenderer":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        launch_args = [
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--disable-gpu-sandbox",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--font-render-hinting=none",
        ]
        kwargs: dict[str, Any] = {"headless": True, "args": launch_args}
        if Path(self.executable_path).is_file():
            kwargs["executable_path"] = self.executable_path
        self._browser = self._pw.chromium.launch(**kwargs)
        context = self._browser.new_context(
            viewport={"width": self.width, "height": self.height},
            device_scale_factor=1,
        )
        self._page = context.new_page()
        self._page.set_content(build_stage_html(self.width, self.height), wait_until="load")
        self._page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def render_plate(
        self,
        template: str,
        props: dict[str, Any],
        out_mov: str | Path,
        duration: float = 3.0,
        fps: int = DEFAULT_FPS,
        codec: str = "qtrle",
        still_at: float | None = None,
        still_out: str | Path | None = None,
    ) -> dict[str, Any]:
        """Render a single transparent RGBA .mov plate deterministically."""
        if template not in SUPPORTED_TEMPLATES:
            raise ValueError(f"Unknown template {template!r}. Supported: {', '.join(SUPPORTED_TEMPLATES)}")
        assert self._page is not None

        t0 = time.perf_counter()
        out_path = Path(out_mov)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        norm_props = nfc_deep(props or {})

        # If rail_karaoke or rail_dynamic_typo points to a caption_rail_json file, load it
        if template in ("rail_karaoke", "rail_dynamic_typo") and norm_props.get("caption_rail_json"):
            rail_path = Path(norm_props["caption_rail_json"])
            rail_data = nfc_deep(json.loads(rail_path.read_text(encoding="utf-8")))
            if isinstance(rail_data, dict):
                if "cues" in rail_data and "segments" not in rail_data:
                    rail_data["segments"] = rail_data["cues"]
                norm_props = {**rail_data, **norm_props}
            elif isinstance(rail_data, list):
                norm_props["segments"] = rail_data

        self._page.evaluate(
            "([tpl, pr, dur]) => window.__mountPlate(tpl, pr, dur)",
            [template, norm_props, float(duration)],
        )

        total_frames = max(2, int(round(float(duration) * fps)))
        cmd = [
            "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-vcodec", "png", "-framerate", str(fps),
            "-i", "-",
            *_ffmpeg_codec_args(codec),
            str(out_path),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None

        still_frame_idx = None
        if still_out is not None:
            at_sec = float(still_at) if still_at is not None else min(float(duration) * 0.55, max(0.0, float(duration) - 0.3))
            still_frame_idx = int(max(0, min(total_frames - 1, round(at_sec * fps))))

        last_key: str | None = None
        last_png: bytes | None = None
        rendered_unique = 0

        try:
            for f in range(total_frames):
                t_sec = f / float(fps)
                key = self._page.evaluate("(t) => window.__stateKey(t)", t_sec)
                if key is not None and key == last_key and last_png is not None:
                    png_bytes = last_png
                else:
                    self._page.evaluate("(t) => window.__setTime(t)", t_sec)
                    png_bytes = self._page.screenshot(type="png", omit_background=True, animations="disabled")
                    last_key = key
                    last_png = png_bytes
                    rendered_unique += 1
                proc.stdin.write(png_bytes)
                if still_frame_idx is not None and f == still_frame_idx and still_out is not None:
                    sp = Path(still_out)
                    sp.parent.mkdir(parents=True, exist_ok=True)
                    sp.write_bytes(png_bytes)
        finally:
            proc.stdin.close()
            rc = proc.wait()
            if rc != 0:
                raise RuntimeError(f"ffmpeg failed (rc={rc}) encoding {out_path}")

        elapsed = round(time.perf_counter() - t0, 2)
        return {
            "template": template,
            "out": str(out_path),
            "frames": total_frames,
            "unique_frames": rendered_unique,
            "fps": fps,
            "codec": codec,
            "size": [self.width, self.height],
            "elapsed_sec": elapsed,
        }


def render_manifest(
    manifest_path: Path,
    out_dir: Path,
    fps_override: int | None = None,
    codec_override: str | None = None,
    width_override: int | None = None,
    height_override: int | None = None,
) -> list[dict[str, Any]]:
    """Batch-render all plates declared in a manifest JSON using one persistent browser page."""
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        plates = raw
        meta: dict[str, Any] = {}
    else:
        meta = raw
        plates = raw.get("plates") or []

    w = int(width_override or meta.get("width") or DEFAULT_WIDTH)
    h = int(height_override or meta.get("height") or DEFAULT_HEIGHT)
    default_fps = int(fps_override or meta.get("fps") or DEFAULT_FPS)
    default_codec = str(codec_override or meta.get("codec") or "qtrle")
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with CinemaWidgetRenderer(width=w, height=h) as renderer:
        for idx, item in enumerate(plates, start=1):
            tpl = str(item["template"])
            pid = str(item.get("id") or f"plate_{idx:02d}_{tpl}")
            out_file = Path(item["out"]) if item.get("out") else (out_dir / f"{pid}.mov")
            still_file = Path(item["still_out"]) if item.get("still_out") else None
            res = renderer.render_plate(
                template=tpl,
                props=item.get("props") or {},
                out_mov=out_file,
                duration=float(item.get("duration") or 3.0),
                fps=int(item.get("fps") or default_fps),
                codec=str(item.get("codec") or default_codec),
                still_at=item.get("still_at"),
                still_out=still_file,
            )
            results.append(res)
            print(
                f"[WIDGET OK] {tpl} -> {out_file.name} "
                f"({res['frames']}f, {res['unique_frames']} unique @ {res['fps']}fps, {res['elapsed_sec']}s)"
            )
    return results


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Deterministic 60fps RGBA plate renderer (Playwright + Chrome)")
    ap.add_argument("--manifest", help="Path to plates_manifest.json for batch rendering")
    ap.add_argument("--out-dir", help="Output directory for batch manifest rendering")
    ap.add_argument("--template", choices=SUPPORTED_TEMPLATES, help="Single-plate template name")
    ap.add_argument("--props", default="{}", help="JSON props string for single-plate mode")
    ap.add_argument("--props-file", help="Path to JSON props file for single-plate mode")
    ap.add_argument("--out", help="Output .mov path for single-plate mode")
    ap.add_argument("--still-out", help="Optional mid-frame RGBA PNG output path")
    ap.add_argument("--still-at", type=float, default=None, help="Timestamp (sec) to capture --still-out")
    ap.add_argument("--duration", type=float, default=2.5, help="Plate duration in seconds (default 2.5)")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Canvas width (default 1080)")
    ap.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Canvas height (default 1920)")
    ap.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Frame rate (default 60)")
    ap.add_argument("--codec", choices=("qtrle", "prores4444", "png"), default="qtrle", help="Alpha MOV codec")
    ap.add_argument("--list-templates", action="store_true", help="Print supported templates and exit")
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()

    if args.list_templates:
        for t in SUPPORTED_TEMPLATES:
            print(t)
        return 0

    if args.manifest:
        mpath = Path(args.manifest)
        if not mpath.is_file():
            print(f"[WIDGET FAIL] Manifest not found: {mpath}", file=sys.stderr)
            return 2
        odir = Path(args.out_dir) if args.out_dir else (mpath.parent / "plates")
        results = render_manifest(
            mpath,
            odir,
            fps_override=args.fps,
            codec_override=args.codec,
            width_override=args.width,
            height_override=args.height,
        )
        print(f"[BATCH DONE] {len(results)} plates rendered -> {odir}")
        return 0

    if not args.template or not args.out:
        ap.error("Provide either --manifest or both --template and --out")

    props = json.loads(Path(args.props_file).read_text(encoding="utf-8")) if args.props_file else json.loads(args.props)
    with CinemaWidgetRenderer(width=args.width, height=args.height) as renderer:
        res = renderer.render_plate(
            template=args.template,
            props=props,
            out_mov=args.out,
            duration=args.duration,
            fps=args.fps,
            codec=args.codec,
            still_at=args.still_at,
            still_out=args.still_out,
        )
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
