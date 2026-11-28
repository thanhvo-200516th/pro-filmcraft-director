#!/usr/bin/env python3
"""local_3d_props.py — Offline WebGL2 PBR 3D Prop Renderer & 17-Industry Catalog Matcher.

Renders true 3D shaded, PBR-lit rotating/bobbing RGBA .mov (qtrle argb) props with
transparent background using Playwright + /usr/bin/google-chrome (--enable-webgl
--ignore-gpu-blocklist) and an inline zero-CDN WebGL2 Cook-Torrance PBR engine.

Usage:
    PY=~/.venvs/video-skills/bin/python3
    $PY scripts/tools/local_3d_props.py match --text "Ống kính quay phim sắc nét" --industry creative_media_agency --top 5
    $PY scripts/tools/local_3d_props.py render --prop 3d_camera_lens_glass --out lens.mov --dur 3.0 --fps 30 --size 320
    $PY scripts/tools/local_3d_props.py render --manifest props_manifest.json --out-dir ./props_out
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

CHROME_EXECUTABLE = "/usr/bin/google-chrome"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "presets" / "assets_3d_catalog.json"
DEFAULT_FPS = 30
DEFAULT_SIZE = 320
DEFAULT_DUR = 3.0


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _strip_accents(text: str) -> str:
    s = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _norm_text(text: str) -> str:
    t = _nfc(text).lower().replace("_", " ").replace("-", " ")
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def load_catalog(catalog_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"3D asset catalog not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def match_props(
    text: str,
    industry: str = "",
    top: int = 5,
    engine: str = "all",
    catalog_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Rank props from assets_3d_catalog.json against Vietnamese/English cue text & industry."""
    cat = load_catalog(catalog_path)
    props: dict[str, dict[str, Any]] = cat.get("props") or {}
    norm_q = _norm_text(text)
    ascii_q = _norm_text(_strip_accents(text))
    tokens_q = set(norm_q.split()) | set(ascii_q.split())
    ind = (industry or "").strip().lower()

    # Legacy alias support matching industry_profiles.json
    aliases = {
        "ecom": "tactile_review",
        "beauty_spa": "luxury_skincare",
        "real_estate": "real_estate_interior",
        "tech_saas": "b2b_saas_realestate",
        "education": "course_edtech",
    }
    ind = aliases.get(ind, ind)

    scored: list[dict[str, Any]] = []
    for pid, spec in props.items():
        prop_engine = str(spec.get("engine") or "local_3d")
        if engine != "all" and prop_engine != engine:
            continue

        score = 0.0
        matched_kws: list[str] = []

        # Industry affinity
        prop_inds = [str(x).lower() for x in (spec.get("industries") or [])]
        if ind and ind in prop_inds:
            score += 4.5 if prop_inds[0] == ind else 3.2

        # Keyword matching (Vietnamese + English, exact phrase & accent-stripped fallback)
        all_kws = list(spec.get("keywords_vi") or []) + list(spec.get("keywords_en") or [])
        for kw in all_kws:
            kw_n = _norm_text(kw)
            kw_a = _norm_text(_strip_accents(kw))
            if not kw_n:
                continue
            if kw_n in norm_q:
                pts = 6.0 + min(3.0, len(kw_n.split()) * 1.2)
                score += pts
                matched_kws.append(kw)
            elif kw_a and kw_a in ascii_q:
                pts = 4.2 + min(2.0, len(kw_a.split()) * 0.8)
                score += pts
                matched_kws.append(kw)
            else:
                kw_toks = set(kw_a.split())
                overlap = kw_toks & tokens_q
                if overlap and len(overlap) == len(kw_toks):
                    score += 2.5
                    matched_kws.append(kw)

        # Label & prop ID token bonus
        label_blob = _norm_text(_strip_accents(f"{pid} {spec.get('label_vi', '')} {spec.get('label_en', '')}"))
        for tok in tokens_q:
            if len(tok) >= 3 and tok in label_blob:
                score += 1.0

        # Slight preference for instant offline local_3d when tied
        if prop_engine == "local_3d":
            score += 0.35

        scored.append({
            "prop_id": pid,
            "engine": prop_engine,
            "score": round(score, 2),
            "matched_keywords": matched_kws[:8],
            "industries": prop_inds,
            "label_vi": spec.get("label_vi", ""),
            "label_en": spec.get("label_en", ""),
            "material_preset": spec.get("material_preset", "gold_polished"),
            "default_slot": spec.get("default_slot", "upper_right"),
            "size_pct_w": spec.get("size_pct_w", 0.28),
            "geometry": spec.get("geometry", pid.replace("3d_", "")),
        })

    scored.sort(key=lambda x: (-x["score"], 0 if x["engine"] == "local_3d" else 1, x["prop_id"]))
    return scored[: max(1, int(top))]


def _ffmpeg_codec_args(codec: str) -> list[str]:
    if codec == "prores4444":
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    if codec == "png":
        return ["-c:v", "png", "-pix_fmt", "rgba"]
    return ["-c:v", "qtrle", "-pix_fmt", "argb"]


# ==============================================================================
# Inline Self-Contained WebGL2 PBR 3D Studio Renderer (Zero CDN, 100% Offline)
# ==============================================================================
STAGE_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  html, body {
    margin: 0; padding: 0; width: 100%; height: 100%;
    overflow: hidden; background: transparent !important;
  }
  canvas {
    display: block; width: 100%; height: 100%;
    background: transparent !important;
  }
</style>
</head>
<body>
<canvas id="gl"></canvas>
<script>
(() => {
  const canvas = document.getElementById('gl');
  const gl = canvas.getContext('webgl2', {
    alpha: true,
    antialias: true,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance'
  });
  if (!gl) {
    throw new Error('WebGL2 context unavailable');
  }

  // ---- Shaders: Cook-Torrance PBR + 3-Point Studio Softbox Env Reflection ----
  const VS = `#version 300 es
  precision highp float;
  layout(location=0) in vec3 aPos;
  layout(location=1) in vec3 aNorm;
  layout(location=2) in vec3 aColor;
  layout(location=3) in vec4 aMat; // x=metal, y=rough, z=emissive, w=ao

  uniform mat4 uMVP;
  uniform mat4 uModel;
  uniform mat3 uNormalMat;

  out vec3 vWorldPos;
  out vec3 vNormal;
  out vec3 vColor;
  out vec4 vMat;

  void main() {
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorldPos = wp.xyz;
    vNormal = normalize(uNormalMat * aNorm);
    vColor = aColor;
    vMat = aMat;
    gl_Position = uMVP * vec4(aPos, 1.0);
  }`;

  const FS = `#version 300 es
  precision highp float;

  in vec3 vWorldPos;
  in vec3 vNormal;
  in vec3 vColor;
  in vec4 vMat;

  uniform vec3 uCamPos;
  uniform float uOpacity;
  uniform vec3 uRimColor;
  uniform float uGlassMode;

  out vec4 fragColor;

  const float PI = 3.14159265359;

  float D_GGX(float NdotH, float rough) {
    float a = rough * rough;
    float a2 = a * a;
    float d = (NdotH * NdotH) * (a2 - 1.0) + 1.0;
    return a2 / max(PI * d * d, 0.0001);
  }

  float G_SchlickGGX(float NdotV, float rough) {
    float r = rough + 1.0;
    float k = (r * r) / 8.0;
    return NdotV / max(NdotV * (1.0 - k) + k, 0.0001);
  }

  float G_Smith(float NdotV, float NdotL, float rough) {
    return G_SchlickGGX(NdotV, rough) * G_SchlickGGX(NdotL, rough);
  }

  vec3 F_Schlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
  }

  // Procedural 3-point studio softbox environment reflection
  vec3 studioEnv(vec3 R, float rough) {
    vec3 dir = normalize(R);
    float sharpness = mix(22.0, 2.2, rough);

    // Dark neutral studio cyclorama base
    vec3 env = mix(vec3(0.06, 0.07, 0.10), vec3(0.16, 0.19, 0.25), clamp(dir.y * 0.5 + 0.5, 0.0, 1.0));

    // Overhead main softbox panel (warm-white)
    vec3 keyDir = normalize(vec3(-0.48, 0.72, 0.52));
    float keyBox = pow(max(dot(dir, keyDir), 0.0), sharpness);
    env += vec3(2.6, 2.45, 2.25) * keyBox;

    // Right cool fill softbox
    vec3 fillDir = normalize(vec3(0.76, 0.26, 0.58));
    float fillBox = pow(max(dot(dir, fillDir), 0.0), sharpness * 0.65);
    env += vec3(0.95, 1.35, 1.85) * fillBox;

    // Back-top rim kicker strip
    vec3 rimDir = normalize(vec3(0.32, 0.62, -0.72));
    float rimBox = pow(max(dot(dir, rimDir), 0.0), sharpness * 0.9);
    env += uRimColor * 2.1 * rimBox;

    // Subtle floor bounce
    float floorBounce = pow(max(dot(dir, vec3(0.0, -1.0, 0.2)), 0.0), 3.0);
    env += vec3(0.22, 0.24, 0.30) * floorBounce;

    return env;
  }

  vec3 evalLight(vec3 Ldir, vec3 Lcol, vec3 N, vec3 V, vec3 albedo, float metal, float rough, vec3 F0) {
    vec3 L = normalize(Ldir);
    vec3 H = normalize(V + L);
    float NdotL = max(dot(N, L), 0.0);
    float NdotV = max(dot(N, V), 0.001);
    float NdotH = max(dot(N, H), 0.0);
    float HdotV = max(dot(H, V), 0.0);

    float D = D_GGX(NdotH, rough);
    float G = G_Smith(NdotV, NdotL, rough);
    vec3 F = F_Schlick(HdotV, F0);

    vec3 spec = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);
    vec3 kD = (vec3(1.0) - F) * (1.0 - metal);
    return (kD * albedo / PI + spec) * Lcol * NdotL;
  }

  vec3 acesToneMap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
  }

  void main() {
    vec3 N = normalize(vNormal);
    if (!gl_FrontFacing) N = -N;
    vec3 V = normalize(uCamPos - vWorldPos);

    vec3 albedo = pow(max(vColor, vec3(0.0001)), vec3(2.2));
    vec3 rimLin = pow(max(uRimColor, vec3(0.0001)), vec3(2.2));
    float metal = clamp(vMat.x, 0.0, 1.0);
    float rough = clamp(vMat.y, 0.06, 0.96);
    float emiss = clamp(vMat.z, 0.0, 2.0);
    float ao = clamp(vMat.w, 0.25, 1.0);

    vec3 F0 = mix(vec3(0.04), albedo, metal);

    // 3-Point Studio Softbox Direct Lights
    vec3 Lo = vec3(0.0);
    Lo += evalLight(vec3(-2.6, 3.4, 3.0), vec3(2.45, 2.35, 2.18), N, V, albedo, metal, rough, F0);
    Lo += evalLight(vec3(3.4, 1.1, 2.4),  vec3(0.85, 1.08, 1.38), N, V, albedo, metal, rough, F0);
    Lo += evalLight(vec3(1.2, 2.8, -3.4), rimLin * 1.85,          N, V, albedo, metal, rough, F0);

    // Image-based studio softbox reflection + subtle clearcoat
    vec3 R = reflect(-V, N);
    float NdotV = max(dot(N, V), 0.001);
    vec3 Fenv = F_Schlick(NdotV, F0);
    vec3 envSpec = studioEnv(R, rough) * Fenv * mix(0.45, 1.05, metal);
    vec3 envDiff = studioEnv(N, 0.92) * albedo * (1.0 - metal) * 0.24;

    // Fresnel studio rim pop so 3D prop separates crisply from footage
    float fresnel = pow(1.0 - NdotV, 3.8);
    vec3 rimGlow = rimLin * fresnel * (0.18 + 0.28 * (1.0 - rough));

    // Clearcoat crisp highlight for glossy materials
    vec3 coat = vec3(0.0);
    if (rough < 0.28) {
      vec3 Hkey = normalize(V + normalize(vec3(-2.6, 3.4, 3.0)));
      float cSpec = pow(max(dot(N, Hkey), 0.0), 120.0) * (0.28 - rough) * 2.8;
      coat = vec3(1.0, 0.99, 0.96) * cSpec;
    }

    vec3 color = (envDiff + envSpec + Lo) * ao + rimGlow + coat + albedo * emiss * 1.10;
    color = acesToneMap(color);
    color = pow(color, vec3(1.0 / 2.2));

    float alpha = uOpacity;
    if (uGlassMode > 0.5 && metal < 0.45 && rough < 0.22) {
      alpha *= clamp(0.66 + fresnel * 0.34, 0.0, 1.0);
    }
    fragColor = vec4(color, alpha);
  }`;

  function compileShader(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(s));
    }
    return s;
  }

  const prog = gl.createProgram();
  gl.attachShader(prog, compileShader(gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, compileShader(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(prog));
  }
  gl.useProgram(prog);

  const uMVP = gl.getUniformLocation(prog, 'uMVP');
  const uModel = gl.getUniformLocation(prog, 'uModel');
  const uNormalMat = gl.getUniformLocation(prog, 'uNormalMat');
  const uCamPos = gl.getUniformLocation(prog, 'uCamPos');
  const uOpacity = gl.getUniformLocation(prog, 'uOpacity');
  const uRimColor = gl.getUniformLocation(prog, 'uRimColor');
  const uGlassMode = gl.getUniformLocation(prog, 'uGlassMode');

  // ---- Minimal Math Helpers ----
  function hexToRgb(hex) {
    const h = (hex || '#F5C451').replace('#', '');
    const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }
  function mix3(a, b, t) {
    return [a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t, a[2]*(1-t)+b[2]*t];
  }
  function mat4Identity() {
    return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
  }
  function mat4Mul(a, b) {
    const o = new Float32Array(16);
    for (let c = 0; c < 4; c++) {
      for (let r = 0; r < 4; r++) {
        o[c*4+r] = a[0*4+r]*b[c*4+0] + a[1*4+r]*b[c*4+1] + a[2*4+r]*b[c*4+2] + a[3*4+r]*b[c*4+3];
      }
    }
    return o;
  }
  function mat4Perspective(fovRad, aspect, near, far) {
    const f = 1.0 / Math.tan(fovRad / 2);
    const nf = 1 / (near - far);
    return new Float32Array([
      f/aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far+near)*nf, -1,
      0, 0, (2*far*near)*nf, 0
    ]);
  }
  function mat4Translate(x, y, z) {
    return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, x,y,z,1]);
  }
  function mat4Scale(sx, sy, sz) {
    return new Float32Array([sx,0,0,0, 0,sy,0,0, 0,0,sz,0, 0,0,0,1]);
  }
  function mat4RotX(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]);
  }
  function mat4RotY(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]);
  }
  function mat4RotZ(a) {
    const c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([c,s,0,0, -s,c,0,0, 0,0,1,0, 0,0,0,1]);
  }
  function mat3NormalFromMat4(m) {
    // Upper-left 3x3 inverse-transpose (valid for uniform scale + rotation)
    const a00=m[0], a01=m[1], a02=m[2];
    const a10=m[4], a11=m[5], a12=m[6];
    const a20=m[8], a21=m[9], a22=m[10];
    const b01 = a22*a11 - a12*a21;
    const b11 = -a22*a10 + a12*a20;
    const b21 = a21*a10 - a11*a20;
    let det = a00*b01 + a01*b11 + a02*b21;
    if (Math.abs(det) < 1e-8) return new Float32Array([1,0,0, 0,1,0, 0,0,1]);
    det = 1.0 / det;
    return new Float32Array([
      b01*det, (-a22*a01 + a02*a21)*det, (a12*a01 - a02*a11)*det,
      b11*det, (a22*a00 - a02*a20)*det, (-a12*a00 + a02*a10)*det,
      b21*det, (-a21*a00 + a01*a20)*det, (a11*a00 - a01*a10)*det
    ]);
  }

  function xformPoint(m, p) {
    return [
      m[0]*p[0] + m[4]*p[1] + m[8]*p[2] + m[12],
      m[1]*p[0] + m[5]*p[1] + m[9]*p[2] + m[13],
      m[2]*p[0] + m[6]*p[1] + m[10]*p[2] + m[14]
    ];
  }
  function xformNorm(m, n) {
    const x = m[0]*n[0] + m[4]*n[1] + m[8]*n[2];
    const y = m[1]*n[0] + m[5]*n[1] + m[9]*n[2];
    const z = m[2]*n[0] + m[6]*n[1] + m[10]*n[2];
    const l = Math.hypot(x, y, z) || 1;
    return [x/l, y/l, z/l];
  }

  // ---- Procedural 3D Mesh Builder ----
  class MeshBuilder {
    constructor() {
      this.pos = [];
      this.norm = [];
      this.col = [];
      this.mat = []; // metal, rough, emiss, ao
    }

    pushTri(p0, p1, p2, n0, n1, n2, color, mat, xform = null) {
      let a = p0, b = p1, c = p2;
      let na = n0, nb = n1, nc = n2;
      if (xform) {
        a = xformPoint(xform, p0); b = xformPoint(xform, p1); c = xformPoint(xform, p2);
        na = xformNorm(xform, n0); nb = xformNorm(xform, n1); nc = xformNorm(xform, n2);
      }
      this.pos.push(...a, ...b, ...c);
      this.norm.push(...na, ...nb, ...nc);
      this.col.push(...color, ...color, ...color);
      this.mat.push(...mat, ...mat, ...mat);
    }

    pushFlatTri(p0, p1, p2, color, mat, xform = null) {
      let a = p0, b = p1, c = p2;
      if (xform) {
        a = xformPoint(xform, p0); b = xformPoint(xform, p1); c = xformPoint(xform, p2);
      }
      const ux = b[0]-a[0], uy = b[1]-a[1], uz = b[2]-a[2];
      const vx = c[0]-a[0], vy = c[1]-a[1], vz = c[2]-a[2];
      let nx = uy*vz - uz*vy, ny = uz*vx - ux*vz, nz = ux*vy - uy*vx;
      const l = Math.hypot(nx, ny, nz) || 1;
      const n = [nx/l, ny/l, nz/l];
      this.pos.push(...a, ...b, ...c);
      this.norm.push(...n, ...n, ...n);
      this.col.push(...color, ...color, ...color);
      this.mat.push(...mat, ...mat, ...mat);
    }

    addBox(w, h, d, color, mat, xform = null) {
      const hw = w/2, hh = h/2, hd = d/2;
      const faces = [
        { n:[0,0,1],  v:[[-hw,-hh,hd],[hw,-hh,hd],[hw,hh,hd],[-hw,hh,hd]] },
        { n:[0,0,-1], v:[[hw,-hh,-hd],[-hw,-hh,-hd],[-hw,hh,-hd],[hw,hh,-hd]] },
        { n:[1,0,0],  v:[[hw,-hh,hd],[hw,-hh,-hd],[hw,hh,-hd],[hw,hh,hd]] },
        { n:[-1,0,0], v:[[-hw,-hh,-hd],[-hw,-hh,hd],[-hw,hh,hd],[-hw,hh,-hd]] },
        { n:[0,1,0],  v:[[-hw,hh,hd],[hw,hh,hd],[hw,hh,-hd],[-hw,hh,-hd]] },
        { n:[0,-1,0], v:[[-hw,-hh,-hd],[hw,-hh,-hd],[hw,-hh,hd],[-hw,-hh,hd]] }
      ];
      for (const f of faces) {
        this.pushTri(f.v[0], f.v[1], f.v[2], f.n, f.n, f.n, color, mat, xform);
        this.pushTri(f.v[0], f.v[2], f.v[3], f.n, f.n, f.n, color, mat, xform);
      }
    }

    addCylinder(rTop, rBot, h, segs, color, mat, xform = null, open = false) {
      const hh = h / 2;
      const slope = (rBot - rTop) / Math.max(h, 0.0001);
      for (let i = 0; i < segs; i++) {
        const a0 = (i / segs) * Math.PI * 2;
        const a1 = ((i + 1) / segs) * Math.PI * 2;
        const c0 = Math.cos(a0), s0 = Math.sin(a0);
        const c1 = Math.cos(a1), s1 = Math.sin(a1);
        const p00 = [rBot*c0, -hh, rBot*s0];
        const p10 = [rBot*c1, -hh, rBot*s1];
        const p11 = [rTop*c1,  hh, rTop*s1];
        const p01 = [rTop*c0,  hh, rTop*s0];
        const nLen = Math.hypot(1, slope);
        const n0 = [c0/nLen, slope/nLen, s0/nLen];
        const n1 = [c1/nLen, slope/nLen, s1/nLen];
        this.pushTri(p00, p10, p11, n0, n1, n1, color, mat, xform);
        this.pushTri(p00, p11, p01, n0, n1, n0, color, mat, xform);
        if (!open) {
          if (rTop > 0.0001) {
            this.pushTri([0,hh,0], p11, p01, [0,1,0], [0,1,0], [0,1,0], color, mat, xform);
          }
          if (rBot > 0.0001) {
            this.pushTri([0,-hh,0], p00, p10, [0,-1,0], [0,-1,0], [0,-1,0], color, mat, xform);
          }
        }
      }
    }

    addSphere(r, segW, segH, color, mat, xform = null, flat = false) {
      for (let y = 0; y < segH; y++) {
        const v0 = (y / segH) * Math.PI;
        const v1 = ((y + 1) / segH) * Math.PI;
        for (let x = 0; x < segW; x++) {
          const u0 = (x / segW) * Math.PI * 2;
          const u1 = ((x + 1) / segW) * Math.PI * 2;
          const pt = (u, v) => [Math.sin(v)*Math.cos(u), Math.cos(v), Math.sin(v)*Math.sin(u)];
          const n00 = pt(u0, v0), n10 = pt(u1, v0), n11 = pt(u1, v1), n01 = pt(u0, v1);
          const p00 = n00.map(k => k*r), p10 = n10.map(k => k*r);
          const p11 = n11.map(k => k*r), p01 = n01.map(k => k*r);
          if (flat) {
            if (y > 0) this.pushFlatTri(p00, p10, p11, color, mat, xform);
            if (y < segH - 1) this.pushFlatTri(p00, p11, p01, color, mat, xform);
          } else {
            if (y > 0) this.pushTri(p00, p10, p11, n00, n10, n11, color, mat, xform);
            if (y < segH - 1) this.pushTri(p00, p11, p01, n00, n11, n01, color, mat, xform);
          }
        }
      }
    }

    addTorus(R, r, segU, segV, color, mat, xform = null) {
      for (let i = 0; i < segU; i++) {
        const u0 = (i / segU) * Math.PI * 2;
        const u1 = ((i + 1) / segU) * Math.PI * 2;
        for (let j = 0; j < segV; j++) {
          const v0 = (j / segV) * Math.PI * 2;
          const v1 = ((j + 1) / segV) * Math.PI * 2;
          const fn = (u, v) => {
            const cu = Math.cos(u), su = Math.sin(u), cv = Math.cos(v), sv = Math.sin(v);
            const p = [(R + r*cv)*cu, r*sv, (R + r*cv)*su];
            const n = [cv*cu, sv, cv*su];
            return { p, n };
          };
          const a = fn(u0, v0), b = fn(u1, v0), c = fn(u1, v1), d = fn(u0, v1);
          this.pushTri(a.p, b.p, c.p, a.n, b.n, c.n, color, mat, xform);
          this.pushTri(a.p, c.p, d.p, a.n, c.n, d.n, color, mat, xform);
        }
      }
    }

    addLathe(profile, segs, color, mat, xform = null, flat = false) {
      // profile: array of [r, y] from bottom to top
      const nP = profile.length;
      const pNorms = [];
      for (let i = 0; i < nP; i++) {
        const prev = profile[Math.max(0, i - 1)];
        const next = profile[Math.min(nP - 1, i + 1)];
        const dr = next[0] - prev[0];
        const dy = next[1] - prev[1];
        const len = Math.hypot(dy, -dr) || 1;
        pNorms.push([dy / len, -dr / len]);
      }
      for (let i = 0; i < nP - 1; i++) {
        const [r0, y0] = profile[i];
        const [r1, y1] = profile[i + 1];
        const [nr0, ny0] = pNorms[i];
        const [nr1, ny1] = pNorms[i + 1];
        for (let s = 0; s < segs; s++) {
          const a0 = (s / segs) * Math.PI * 2;
          const a1 = ((s + 1) / segs) * Math.PI * 2;
          const c0 = Math.cos(a0), s0 = Math.sin(a0);
          const c1 = Math.cos(a1), s1 = Math.sin(a1);
          const p00 = [r0*c0, y0, r0*s0];
          const p10 = [r0*c1, y0, r0*s1];
          const p11 = [r1*c1, y1, r1*s1];
          const p01 = [r1*c0, y1, r1*s0];
          if (flat) {
            if (r0 > 0.0001 || r1 > 0.0001) {
              this.pushFlatTri(p00, p10, p11, color, mat, xform);
              this.pushFlatTri(p00, p11, p01, color, mat, xform);
            }
          } else {
            const n00 = [nr0*c0, ny0, nr0*s0];
            const n10 = [nr0*c1, ny0, nr0*s1];
            const n11 = [nr1*c1, ny1, nr1*s1];
            const n01 = [nr1*c0, ny1, nr1*s0];
            this.pushTri(p00, p10, p11, n00, n10, n11, color, mat, xform);
            this.pushTri(p00, p11, p01, n00, n11, n01, color, mat, xform);
          }
        }
      }
    }

    addExtrudedPoly(pts2d, depth, color, mat, xform = null, center = [0, 0]) {
      // pts2d ordered CCW in XY plane, extruded along Z in [-depth/2, +depth/2]
      const hz = depth / 2;
      const n = pts2d.length;
      for (let i = 0; i < n; i++) {
        const p0 = pts2d[i];
        const p1 = pts2d[(i + 1) % n];
        // Front cap
        this.pushTri(
          [center[0], center[1], hz], [p0[0], p0[1], hz], [p1[0], p1[1], hz],
          [0,0,1], [0,0,1], [0,0,1], color, mat, xform
        );
        // Back cap
        this.pushTri(
          [center[0], center[1], -hz], [p1[0], p1[1], -hz], [p0[0], p0[1], -hz],
          [0,0,-1], [0,0,-1], [0,0,-1], color, mat, xform
        );
        // Side quad
        const dx = p1[0] - p0[0], dy = p1[1] - p0[1];
        const l = Math.hypot(dx, dy) || 1;
        const sn = [dy / l, -dx / l, 0];
        this.pushTri([p0[0],p0[1],-hz], [p1[0],p1[1],-hz], [p1[0],p1[1],hz], sn, sn, sn, color, mat, xform);
        this.pushTri([p0[0],p0[1],-hz], [p1[0],p1[1],hz], [p0[0],p0[1],hz], sn, sn, sn, color, mat, xform);
      }
    }

    addStar3D(rOuter, rInner, thickness, color, mat, xform = null) {
      // Faceted high-relief 5-point star with peaked centers on +Z and -Z
      const pts = [];
      for (let i = 0; i < 10; i++) {
        const a = Math.PI / 2 + (i / 10) * Math.PI * 2;
        const r = (i % 2 === 0) ? rOuter : rInner;
        pts.push([Math.cos(a) * r, Math.sin(a) * r]);
      }
      const peakF = [0, 0, thickness];
      const peakB = [0, 0, -thickness];
      const edgeZ = thickness * 0.22;
      for (let i = 0; i < 10; i++) {
        const a = pts[i], b = pts[(i + 1) % 10];
        this.pushFlatTri(peakF, [a[0], a[1], edgeZ], [b[0], b[1], edgeZ], color, mat, xform);
        this.pushFlatTri(peakB, [b[0], b[1], -edgeZ], [a[0], a[1], -edgeZ], color, mat, xform);
        this.pushFlatTri([a[0], a[1], -edgeZ], [b[0], b[1], -edgeZ], [b[0], b[1], edgeZ], color, mat, xform);
        this.pushFlatTri([a[0], a[1], -edgeZ], [b[0], b[1], edgeZ], [a[0], a[1], edgeZ], color, mat, xform);
      }
    }

    upload() {
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      const makeBuf = (loc, data, size) => {
        const buf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(loc);
        gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
        return buf;
      };
      const bufs = [
        makeBuf(0, this.pos, 3),
        makeBuf(1, this.norm, 3),
        makeBuf(2, this.col, 3),
        makeBuf(3, this.mat, 4)
      ];
      return { vao, bufs, count: this.pos.length / 3 };
    }
  }

  // ---- 28 Studio-Grade 3D Prop Geometry Builders ----
  function buildPropMesh(geometryId, matSpec) {
    const mb = new MeshBuilder();
    const baseC = hexToRgb(matSpec.base_color || '#F5C451');
    const accC = hexToRgb(matSpec.accent_color || '#FFFFFF');
    const secC = hexToRgb(matSpec.secondary_color || '#334155');
    const metal = matSpec.metalness ?? 0.7;
    const rough = matSpec.roughness ?? 0.25;
    let glassMode = 0.0;

    const M = (m, r, e = 0.0, ao = 1.0) => [m, r, e, ao];

    switch (geometryId) {
      case 'camera_lens_glass': {
        // Multi-ring cinema lens barrel aligned along Z (rotated from Y-axis cylinder)
        const rotZ = mat4RotX(Math.PI / 2);
        const bodyC = [0.11, 0.13, 0.17];
        const darkMetal = [0.06, 0.07, 0.09];
        const silverC = [0.85, 0.88, 0.93];
        const redStripe = [0.90, 0.16, 0.22];
        const cyanGlass = [0.12, 0.65, 0.92];
        const violetGlass = [0.42, 0.26, 0.88];

        // Rear mount & stepped barrel
        mb.addCylinder(0.46, 0.42, 0.24, 36, silverC, M(0.95, 0.18, 0, 0.88), mat4Mul(mat4Translate(0, 0, -0.58), rotZ));
        mb.addCylinder(0.62, 0.56, 0.34, 40, bodyC, M(0.55, 0.42, 0, 0.92), mat4Mul(mat4Translate(0, 0, -0.32), rotZ));
        // Knurled focus ring
        mb.addCylinder(0.68, 0.68, 0.34, 44, darkMetal, M(0.35, 0.58, 0, 0.96), mat4Mul(mat4Translate(0, 0, 0.02), rotZ));
        for (let i = 0; i < 28; i++) {
          const a = (i / 28) * Math.PI * 2;
          const x = Math.cos(a) * 0.685, y = Math.sin(a) * 0.685;
          const xf = mat4Mul(mat4Translate(x, y, 0.02), mat4RotZ(a));
          mb.addBox(0.028, 0.022, 0.30, [0.16, 0.18, 0.22], M(0.45, 0.48, 0, 0.9), xf);
        }
        // Signature red cinema ring + open front barrel
        mb.addTorus(0.685, 0.026, 40, 14, redStripe, M(0.65, 0.20, 0.12, 1.0), mat4Mul(mat4Translate(0, 0, 0.22), rotZ));
        mb.addCylinder(0.74, 0.68, 0.28, 44, bodyC, M(0.65, 0.30, 0, 0.96), mat4Mul(mat4Translate(0, 0, 0.35), rotZ), true);
        // Outer metallic rim bevel + inner stepped ring
        mb.addTorus(0.71, 0.055, 44, 16, silverC, M(0.92, 0.16, 0, 1.0), mat4Mul(mat4Translate(0, 0, 0.49), rotZ));
        mb.addTorus(0.60, 0.032, 40, 14, darkMetal, M(0.55, 0.35, 0, 0.80), mat4Mul(mat4Translate(0, 0, 0.45), rotZ));
        // Recessed dark interior baffle behind optical glass
        mb.addCylinder(0.64, 0.54, 0.16, 36, [0.02, 0.03, 0.05], M(0.2, 0.75, 0, 0.45), mat4Mul(mat4Translate(0, 0, 0.24), rotZ));
        // Multi-coated curved optical glass elements (outer deep cyan-blue dome + inner violet-magenta reflection core)
        mb.addSphere(0.58, 36, 20, [0.06, 0.44, 0.78], M(0.45, 0.06, 0.22, 1.0), mat4Mul(mat4Translate(0, 0, 0.26), mat4Scale(1.0, 1.0, 0.42)));
        mb.addSphere(0.36, 28, 16, violetGlass, M(0.55, 0.06, 0.34, 1.0), mat4Mul(mat4Translate(0, 0, 0.34), mat4Scale(1.0, 1.0, 0.44)));
        mb.addTorus(0.46, 0.016, 36, 10, [0.35, 0.88, 1.0], M(0.85, 0.1, 0.45, 1.0), mat4Mul(mat4Translate(0, 0, 0.45), rotZ));
        mb.addSphere(0.16, 20, 12, [0.05, 0.08, 0.16], M(0.9, 0.06, 0.1, 1.0), mat4Mul(mat4Translate(0, 0, 0.44), mat4Scale(1.0, 1.0, 0.45)));
        break;
      }

      case 'trophy_star_gold': {
        // @hoangsangcreator-inspired beveled crimson-and-gold studio star medal
        const rotZ = mat4RotX(Math.PI / 2);
        const gold = [0.96, 0.76, 0.24];
        const goldDeep = [0.78, 0.52, 0.12];
        const crimson = [0.84, 0.10, 0.14];

        // Thick beveled outer gold coin rim
        mb.addTorus(0.76, 0.10, 48, 20, gold, M(0.96, 0.16, 0.02, 1.0), rotZ);
        mb.addCylinder(0.76, 0.76, 0.17, 48, goldDeep, M(0.92, 0.22, 0, 0.92), rotZ);
        // Decorative milled coin notches around outer edge
        for (let i = 0; i < 24; i++) {
          const a = (i / 24) * Math.PI * 2;
          const xf = mat4Mul(mat4Translate(Math.cos(a)*0.84, Math.sin(a)*0.84, 0), mat4RotZ(a));
          mb.addBox(0.05, 0.045, 0.13, gold, M(0.95, 0.18, 0, 0.95), xf);
        }
        // Deep glossy crimson enamel inner face (dielectric lacquer for rich saturation)
        mb.addCylinder(0.67, 0.67, 0.21, 44, [0.76, 0.05, 0.09], M(0.06, 0.24, 0.04, 0.96), rotZ);
        // Inner gold accent ring
        mb.addTorus(0.61, 0.022, 40, 12, gold, M(0.96, 0.14, 0.05, 1.0), mat4Mul(mat4Translate(0, 0, 0.105), rotZ));
        mb.addTorus(0.61, 0.022, 40, 12, gold, M(0.96, 0.14, 0.05, 1.0), mat4Mul(mat4Translate(0, 0, -0.105), rotZ));
        // High-relief 3D faceted golden 5-point star on both sides
        mb.addStar3D(0.50, 0.21, 0.24, gold, M(0.96, 0.16, 0.04, 1.0));
        break;
      }

      case 'gold_coin_spin': {
        const rotZ = mat4RotX(Math.PI / 2);
        const gold = [0.97, 0.78, 0.26];
        const goldBright = [1.0, 0.88, 0.42];
        const goldRim = [0.85, 0.60, 0.14];
        mb.addTorus(0.75, 0.09, 48, 18, goldBright, M(0.96, 0.15, 0, 1.0), rotZ);
        mb.addCylinder(0.74, 0.74, 0.14, 48, gold, M(0.95, 0.20, 0, 0.92), rotZ);
        mb.addTorus(0.60, 0.025, 40, 12, goldRim, M(0.94, 0.22, 0, 0.95), mat4Mul(mat4Translate(0,0,0.075), rotZ));
        mb.addTorus(0.60, 0.025, 40, 12, goldRim, M(0.94, 0.22, 0, 0.95), mat4Mul(mat4Translate(0,0,-0.075), rotZ));
        mb.addStar3D(0.42, 0.18, 0.16, goldBright, M(0.97, 0.14, 0.05, 1.0));
        break;
      }

      case 'clapperboard_matte': {
        const slate = [0.11, 0.13, 0.16];
        const white = [0.95, 0.96, 0.98];
        const amber = [0.96, 0.68, 0.16];
        const steel = [0.82, 0.85, 0.90];
        // Main slate board
        mb.addBox(1.36, 0.92, 0.11, slate, M(0.18, 0.56, 0, 0.96), mat4Translate(0, -0.18, 0));
        // Subtle white horizontal guide lines on front & back
        for (const zSide of [0.058, -0.058]) {
          mb.addBox(1.16, 0.026, 0.01, white, M(0.1, 0.5, 0.05, 1.0), mat4Translate(0, -0.02, zSide));
          mb.addBox(1.16, 0.026, 0.01, white, M(0.1, 0.5, 0.05, 1.0), mat4Translate(0, -0.26, zSide));
          mb.addBox(0.32, 0.045, 0.012, amber, M(0.4, 0.3, 0.1, 1.0), mat4Translate(-0.36, -0.44, zSide));
        }
        // Lower fixed striped bar
        mb.addBox(1.36, 0.18, 0.13, slate, M(0.22, 0.45, 0, 0.98), mat4Translate(0, 0.34, 0));
        for (let i = -2; i <= 2; i++) {
          const xf = mat4Mul(mat4Translate(i * 0.25, 0.34, 0), mat4RotZ(-0.35));
          mb.addBox(0.11, 0.175, 0.138, white, M(0.12, 0.35, 0, 1.0), xf);
        }
        // Hinged top clapper arm angled open at +18 deg
        const pivot = mat4Mul(mat4Translate(-0.62, 0.45, 0), mat4Mul(mat4RotZ(0.32), mat4Translate(0.62, 0.11, 0)));
        mb.addBox(1.36, 0.18, 0.13, slate, M(0.22, 0.45, 0, 1.0), pivot);
        for (let i = -2; i <= 2; i++) {
          const xf = mat4Mul(pivot, mat4Mul(mat4Translate(i * 0.25, 0, 0), mat4RotZ(0.35)));
          mb.addBox(0.11, 0.175, 0.138, white, M(0.12, 0.35, 0, 1.0), xf);
        }
        // Metallic hinge bolt
        mb.addCylinder(0.08, 0.08, 0.18, 18, steel, M(0.95, 0.18, 0, 1.0), mat4Mul(mat4Translate(-0.62, 0.44, 0), mat4RotX(Math.PI/2)));
        break;
      }

      case 'alarm_clock_chrome': {
        const rotZ = mat4RotX(Math.PI / 2);
        const chrome = [0.88, 0.91, 0.95];
        const red = [0.90, 0.16, 0.20];
        const face = [0.97, 0.97, 0.95];
        const dark = [0.10, 0.12, 0.16];
        // Main body + chrome bezel
        mb.addCylinder(0.64, 0.64, 0.34, 40, red, M(0.55, 0.16, 0, 0.96), rotZ);
        mb.addTorus(0.62, 0.065, 40, 16, chrome, M(0.96, 0.12, 0, 1.0), mat4Mul(mat4Translate(0,0,0.16), rotZ));
        mb.addCylinder(0.56, 0.56, 0.04, 36, face, M(0.08, 0.35, 0.05, 1.0), mat4Mul(mat4Translate(0,0,0.17), rotZ));
        // Clock hands
        mb.addBox(0.055, 0.32, 0.03, dark, M(0.3, 0.3, 0, 1.0), mat4Mul(mat4Translate(0,0.12,0.21), mat4RotZ(-0.2)));
        mb.addBox(0.045, 0.42, 0.03, dark, M(0.3, 0.3, 0, 1.0), mat4Mul(mat4Translate(0.13,0.08,0.22), mat4RotZ(-1.1)));
        mb.addSphere(0.055, 14, 10, red, M(0.85, 0.15, 0, 1.0), mat4Translate(0,0,0.23));
        // Twin top bells
        for (const s of [-1, 1]) {
          const bXf = mat4Mul(mat4Translate(s*0.46, 0.58, 0), mat4RotZ(-s*0.65));
          mb.addSphere(0.24, 24, 14, chrome, M(0.96, 0.12, 0, 1.0), mat4Mul(bXf, mat4Scale(1.0, 0.75, 1.0)));
          mb.addCylinder(0.04, 0.04, 0.24, 12, chrome, M(0.95, 0.15, 0, 1.0), mat4Mul(mat4Translate(s*0.34, 0.45, 0), mat4RotZ(-s*0.65)));
          // Feet
          mb.addCylinder(0.05, 0.065, 0.26, 14, chrome, M(0.95, 0.14, 0, 1.0), mat4Mul(mat4Translate(s*0.40, -0.60, 0), mat4RotZ(s*0.45)));
        }
        // Top hammer
        mb.addCylinder(0.03, 0.03, 0.22, 12, chrome, M(0.95, 0.14, 0, 1.0), mat4Translate(0, 0.72, 0));
        mb.addSphere(0.07, 14, 10, chrome, M(0.96, 0.12, 0, 1.0), mat4Translate(0, 0.84, 0));
        break;
      }

      case 'house_key_gold': {
        const gold = [0.96, 0.77, 0.24];
        const goldLight = [1.0, 0.88, 0.45];
        const rotZ = mat4RotX(Math.PI / 2);
        const tilt = mat4RotZ(-0.45);
        // Ornate bow (ring head)
        mb.addTorus(0.38, 0.10, 36, 16, gold, M(0.96, 0.16, 0, 1.0), mat4Mul(tilt, mat4Mul(mat4Translate(-0.48, 0, 0), rotZ)));
        mb.addTorus(0.22, 0.04, 28, 12, goldLight, M(0.96, 0.14, 0.04, 1.0), mat4Mul(tilt, mat4Mul(mat4Translate(-0.48, 0, 0), rotZ)));
        // Collar + cylindrical shaft
        mb.addCylinder(0.11, 0.11, 0.12, 20, goldLight, M(0.95, 0.16, 0, 1.0), mat4Mul(tilt, mat4Mul(mat4Translate(-0.06, 0, 0), mat4RotZ(Math.PI/2))));
        mb.addCylinder(0.075, 0.075, 0.92, 20, gold, M(0.95, 0.18, 0, 1.0), mat4Mul(tilt, mat4Mul(mat4Translate(0.38, 0, 0), mat4RotZ(Math.PI/2))));
        // Stepped key teeth
        mb.addBox(0.11, 0.24, 0.09, goldLight, M(0.95, 0.18, 0, 1.0), mat4Mul(tilt, mat4Translate(0.46, -0.14, 0)));
        mb.addBox(0.10, 0.17, 0.09, gold, M(0.95, 0.18, 0, 1.0), mat4Mul(tilt, mat4Translate(0.60, -0.11, 0)));
        mb.addBox(0.12, 0.27, 0.09, goldLight, M(0.95, 0.18, 0, 1.0), mat4Mul(tilt, mat4Translate(0.75, -0.16, 0)));
        break;
      }

      case 'location_pin_glass': {
        const ruby = [0.92, 0.14, 0.30];
        const white = [0.97, 0.98, 1.0];
        const gold = [0.96, 0.78, 0.30];
        const profile = [
          [0.01, -0.88], [0.16, -0.58], [0.36, -0.26], [0.54, 0.06],
          [0.60, 0.28], [0.56, 0.50], [0.42, 0.68], [0.22, 0.78], [0.01, 0.82]
        ];
        mb.addLathe(profile, 36, ruby, M(0.35, 0.10, 0.08, 1.0), mat4Scale(1.0, 1.0, 0.65));
        mb.addTorus(0.28, 0.055, 32, 14, gold, M(0.94, 0.16, 0, 1.0), mat4Mul(mat4Translate(0, 0.25, 0.32), mat4RotX(Math.PI/2)));
        mb.addSphere(0.24, 24, 16, white, M(0.15, 0.08, 0.14, 1.0), mat4Translate(0, 0.25, 0.26));
        mb.addSphere(0.24, 24, 16, white, M(0.15, 0.08, 0.14, 1.0), mat4Translate(0, 0.25, -0.26));
        break;
      }

      case 'water_droplet_glass': {
        glassMode = 1.0;
        const crystal = [0.22, 0.76, 0.98];
        const bright = [0.82, 0.96, 1.0];
        const profile = [
          [0.01, -0.78], [0.26, -0.74], [0.48, -0.58], [0.58, -0.34],
          [0.56, -0.06], [0.44, 0.22], [0.26, 0.50], [0.10, 0.74], [0.01, 0.88]
        ];
        mb.addLathe(profile, 40, crystal, M(0.25, 0.06, 0.12, 1.0));
        mb.addSphere(0.16, 18, 14, bright, M(0.1, 0.06, 0.35, 1.0), mat4Translate(-0.16, -0.24, 0.18));
        mb.addSphere(0.08, 14, 10, bright, M(0.1, 0.06, 0.42, 1.0), mat4Translate(0.14, -0.40, 0.14));
        break;
      }

      case 'shield_check': {
        const emerald = [0.06, 0.72, 0.50];
        const rim = [0.88, 0.95, 0.98];
        const checkC = [0.98, 0.99, 1.0];
        const pts = [
          [0, 0.84], [-0.66, 0.60], [-0.60, -0.08], [-0.34, -0.56],
          [0, -0.84], [0.34, -0.56], [0.60, -0.08], [0.66, 0.60]
        ];
        mb.addExtrudedPoly(pts, 0.20, emerald, M(0.38, 0.14, 0.06, 1.0));
        const rimPts = pts.map(p => [p[0]*1.08, p[1]*1.07]);
        mb.addExtrudedPoly(rimPts, 0.13, rim, M(0.92, 0.16, 0, 0.96));
        // Raised 3D checkmark on front & back
        for (const z of [0.125, -0.125]) {
          mb.addBox(0.32, 0.11, 0.06, checkC, M(0.2, 0.18, 0.2, 1.0), mat4Mul(mat4Translate(-0.13, -0.06, z), mat4RotZ(-0.78)));
          mb.addBox(0.56, 0.11, 0.06, checkC, M(0.2, 0.18, 0.2, 1.0), mat4Mul(mat4Translate(0.12, 0.04, z), mat4RotZ(0.78)));
        }
        break;
      }

      case 'bar_chart_rising': {
        const basePlate = [0.16, 0.20, 0.28];
        const c1 = [0.12, 0.62, 0.88];
        const c2 = [0.08, 0.76, 0.68];
        const c3 = [0.10, 0.82, 0.48];
        const c4 = [0.96, 0.78, 0.24];
        mb.addBox(1.42, 0.10, 0.54, basePlate, M(0.65, 0.30, 0, 0.95), mat4Translate(0, -0.58, 0));
        mb.addBox(0.24, 0.42, 0.26, c1, M(0.42, 0.16, 0.05, 1.0), mat4Translate(-0.46, -0.32, 0));
        mb.addBox(0.24, 0.72, 0.26, c2, M(0.42, 0.16, 0.06, 1.0), mat4Translate(-0.15, -0.17, 0));
        mb.addBox(0.24, 1.02, 0.26, c3, M(0.42, 0.16, 0.08, 1.0), mat4Translate(0.16, -0.02, 0));
        mb.addBox(0.24, 1.32, 0.26, c4, M(0.92, 0.16, 0.10, 1.0), mat4Translate(0.47, 0.13, 0));
        break;
      }

      case 'delivery_box_kraft': {
        const kraft = [0.76, 0.58, 0.39];
        const tape = [0.93, 0.84, 0.68];
        const label = [0.97, 0.97, 0.95];
        const accent = [0.90, 0.34, 0.22];
        mb.addBox(1.06, 0.94, 1.06, kraft, M(0.06, 0.76, 0, 0.98));
        // Packing tape strips
        mb.addBox(1.08, 0.03, 0.20, tape, M(0.12, 0.42, 0, 1.0), mat4Translate(0, 0.475, 0));
        mb.addBox(0.20, 0.03, 1.08, tape, M(0.12, 0.42, 0, 1.0), mat4Translate(0, 0.475, 0));
        mb.addBox(0.20, 0.34, 1.08, tape, M(0.12, 0.42, 0, 1.0), mat4Translate(0, 0.31, 0));
        // Shipping label tile
        mb.addBox(0.36, 0.24, 0.02, label, M(0.05, 0.65, 0, 1.0), mat4Translate(0.26, -0.14, 0.535));
        mb.addBox(0.24, 0.05, 0.025, accent, M(0.1, 0.5, 0, 1.0), mat4Translate(0.26, -0.10, 0.54));
        break;
      }

      case 'diamond_gem': {
        glassMode = 1.0;
        const gemC = [0.36, 0.84, 1.0];
        const innerC = [0.76, 0.94, 1.0];
        // Brilliant-cut flat-shaded crystal lathe (8-sided facets)
        const profile = [
          [0.001, -0.78],
          [0.74, 0.14],
          [0.76, 0.22],
          [0.46, 0.58],
          [0.001, 0.58]
        ];
        mb.addLathe(profile, 8, gemC, M(0.35, 0.06, 0.14, 1.0), null, true);
        mb.addLathe([[0.001,-0.46],[0.42,0.14],[0.26,0.36],[0.001,0.36]], 8, innerC, M(0.5, 0.06, 0.30, 1.0), null, true);
        break;
      }

      case 'lightning_gold': {
        const gold = [0.98, 0.80, 0.18];
        const pts = [
          [0.14, 0.88], [-0.46, 0.02], [-0.04, 0.02],
          [-0.24, -0.88], [0.48, 0.08], [0.06, 0.08]
        ];
        mb.addExtrudedPoly(pts, 0.22, gold, M(0.95, 0.15, 0.12, 1.0), null, [0.02, 0.04]);
        break;
      }

      case 'gear_brushed_steel': {
        const rotZ = mat4RotX(Math.PI / 2);
        const steel = [0.68, 0.74, 0.82];
        const dark = [0.32, 0.38, 0.46];
        mb.addTorus(0.54, 0.14, 36, 14, steel, M(0.92, 0.24, 0, 0.98), rotZ);
        mb.addTorus(0.24, 0.08, 28, 12, dark, M(0.90, 0.28, 0, 0.92), rotZ);
        // 4 spokes
        for (let i = 0; i < 4; i++) {
          const a = (i / 4) * Math.PI * 2;
          mb.addBox(0.58, 0.12, 0.16, dark, M(0.88, 0.28, 0, 0.9), mat4RotZ(a));
        }
        // 12 precision teeth
        for (let i = 0; i < 12; i++) {
          const a = (i / 12) * Math.PI * 2;
          const xf = mat4Mul(mat4RotZ(a), mat4Translate(0.73, 0, 0));
          mb.addBox(0.20, 0.16, 0.24, steel, M(0.94, 0.22, 0, 1.0), xf);
        }
        break;
      }

      case 'coffee_cup_clay': {
        const clay = [0.85, 0.46, 0.33];
        const sleeve = [0.76, 0.58, 0.40];
        const lid = [0.97, 0.95, 0.92];
        mb.addCylinder(0.48, 0.34, 1.12, 36, clay, M(0.08, 0.38, 0, 0.96), mat4Translate(0, -0.10, 0));
        mb.addCylinder(0.455, 0.405, 0.44, 36, sleeve, M(0.06, 0.72, 0, 0.98), mat4Translate(0, -0.06, 0));
        // Domed lid + rim
        mb.addCylinder(0.53, 0.53, 0.10, 36, lid, M(0.10, 0.26, 0, 1.0), mat4Translate(0, 0.50, 0));
        mb.addCylinder(0.47, 0.51, 0.14, 36, lid, M(0.10, 0.24, 0, 1.0), mat4Translate(0, 0.61, 0));
        mb.addBox(0.14, 0.08, 0.12, lid, M(0.10, 0.24, 0, 1.0), mat4Translate(0.26, 0.69, 0));
        break;
      }

      case 'dumbbell_matte': {
        const bar = [0.82, 0.86, 0.92];
        const plate = [0.14, 0.16, 0.20];
        const accent = [0.96, 0.76, 0.24];
        const tilt = mat4RotZ(0.28);
        const rotH = mat4RotZ(Math.PI / 2);
        mb.addCylinder(0.085, 0.085, 1.38, 20, bar, M(0.95, 0.22, 0, 1.0), mat4Mul(tilt, rotH));
        for (const s of [-1, 1]) {
          mb.addCylinder(0.38, 0.38, 0.22, 6, plate, M(0.45, 0.46, 0, 0.96), mat4Mul(tilt, mat4Mul(mat4Translate(s*0.44, 0, 0), rotH)));
          mb.addCylinder(0.32, 0.32, 0.18, 6, plate, M(0.45, 0.46, 0, 0.96), mat4Mul(tilt, mat4Mul(mat4Translate(s*0.64, 0, 0), rotH)));
          mb.addCylinder(0.13, 0.13, 0.08, 16, accent, M(0.94, 0.18, 0, 1.0), mat4Mul(tilt, mat4Mul(mat4Translate(s*0.76, 0, 0), rotH)));
        }
        break;
      }

      case 'book_hardcover': {
        const cover = [0.12, 0.32, 0.78];
        const pages = [0.96, 0.94, 0.88];
        const gold = [0.96, 0.78, 0.26];
        const tilt = mat4Mul(mat4RotZ(-0.18), mat4RotY(0.25));
        // Pages block
        mb.addBox(0.94, 1.24, 0.28, pages, M(0.05, 0.72, 0, 0.94), mat4Mul(tilt, mat4Translate(0.04, 0, 0)));
        // Front & back covers
        mb.addBox(1.02, 1.32, 0.045, cover, M(0.18, 0.46, 0, 1.0), mat4Mul(tilt, mat4Translate(0, 0, 0.165)));
        mb.addBox(1.02, 1.32, 0.045, cover, M(0.18, 0.46, 0, 1.0), mat4Mul(tilt, mat4Translate(0, 0, -0.165)));
        // Curved spine
        mb.addCylinder(0.19, 0.19, 1.32, 20, cover, M(0.20, 0.44, 0, 0.98), mat4Mul(tilt, mat4Translate(-0.50, 0, 0)));
        // Gold spine bands & cover emblem
        for (const y of [-0.42, 0.42]) {
          mb.addCylinder(0.20, 0.20, 0.05, 20, gold, M(0.95, 0.18, 0, 1.0), mat4Mul(tilt, mat4Translate(-0.50, y, 0)));
        }
        mb.addBox(0.46, 0.10, 0.02, gold, M(0.95, 0.18, 0.05, 1.0), mat4Mul(tilt, mat4Translate(0.06, 0.26, 0.195)));
        mb.addBox(0.32, 0.06, 0.02, gold, M(0.95, 0.18, 0.05, 1.0), mat4Mul(tilt, mat4Translate(0.06, 0.08, 0.195)));
        break;
      }

      case 'microphone_studio': {
        const steel = [0.76, 0.80, 0.86];
        const dark = [0.14, 0.16, 0.21];
        const gold = [0.95, 0.76, 0.28];
        // Condenser grille head
        mb.addSphere(0.34, 24, 16, steel, M(0.92, 0.26, 0, 1.0), mat4Mul(mat4Translate(0, 0.36, 0), mat4Scale(1.0, 1.35, 1.0)));
        mb.addTorus(0.34, 0.032, 32, 12, gold, M(0.95, 0.16, 0, 1.0), mat4Translate(0, 0.36, 0));
        // Lower body
        mb.addCylinder(0.26, 0.22, 0.62, 28, dark, M(0.55, 0.36, 0, 0.96), mat4Translate(0, -0.24, 0));
        // Stand yoke & base
        mb.addCylinder(0.07, 0.07, 0.26, 16, steel, M(0.92, 0.20, 0, 1.0), mat4Translate(0, -0.66, 0));
        mb.addCylinder(0.34, 0.38, 0.09, 28, dark, M(0.75, 0.28, 0, 1.0), mat4Translate(0, -0.80, 0));
        break;
      }

      case 'speaker_oak_wood': {
        const rotZ = mat4RotX(Math.PI / 2);
        const oak = [0.70, 0.49, 0.30];
        const baffle = [0.11, 0.13, 0.17];
        const cone = [0.92, 0.74, 0.26];
        const chrome = [0.82, 0.86, 0.92];
        mb.addBox(0.96, 1.32, 0.84, oak, M(0.14, 0.56, 0, 0.98));
        mb.addBox(0.84, 1.20, 0.05, baffle, M(0.25, 0.45, 0, 0.95), mat4Translate(0, 0, 0.41));
        // Woofer
        mb.addTorus(0.30, 0.045, 32, 12, chrome, M(0.90, 0.20, 0, 1.0), mat4Mul(mat4Translate(0, -0.22, 0.44), rotZ));
        mb.addCylinder(0.27, 0.14, 0.12, 28, cone, M(0.65, 0.30, 0, 0.92), mat4Mul(mat4Translate(0, -0.22, 0.40), rotZ));
        mb.addSphere(0.10, 16, 12, baffle, M(0.4, 0.25, 0, 1.0), mat4Translate(0, -0.22, 0.44));
        // Tweeter
        mb.addTorus(0.15, 0.03, 28, 10, chrome, M(0.92, 0.18, 0, 1.0), mat4Mul(mat4Translate(0, 0.34, 0.44), rotZ));
        mb.addSphere(0.11, 16, 12, [0.22, 0.25, 0.32], M(0.5, 0.22, 0, 1.0), mat4Translate(0, 0.34, 0.43));
        break;
      }

      case 'lightbulb_glow': {
        glassMode = 1.0;
        const glass = [1.0, 0.90, 0.52];
        const filament = [1.0, 0.72, 0.12];
        const brass = [0.80, 0.84, 0.90];
        const profile = [
          [0.24, -0.34], [0.28, -0.14], [0.48, 0.10], [0.56, 0.34],
          [0.50, 0.58], [0.32, 0.76], [0.01, 0.84]
        ];
        mb.addLathe(profile, 36, glass, M(0.18, 0.08, 0.32, 1.0));
        // Warm glowing inner core
        mb.addSphere(0.22, 18, 14, filament, M(0.1, 0.2, 1.15, 1.0), mat4Translate(0, 0.30, 0));
        // Ribbed metallic Edison screw base
        mb.addCylinder(0.24, 0.22, 0.34, 24, brass, M(0.94, 0.20, 0, 0.98), mat4Translate(0, -0.52, 0));
        for (const y of [-0.44, -0.54, -0.64]) {
          mb.addTorus(0.23, 0.025, 24, 10, brass, M(0.95, 0.18, 0, 1.0), mat4Translate(0, y, 0));
        }
        mb.addSphere(0.14, 16, 10, [0.16, 0.18, 0.22], M(0.4, 0.4, 0, 0.9), mat4Translate(0, -0.72, 0));
        break;
      }

      case 'tooth_enamel_pearl': {
        const pearl = [0.97, 0.98, 1.0];
        const crown = [
          [0.01, 0.68], [0.34, 0.66], [0.56, 0.46], [0.58, 0.12],
          [0.48, -0.22], [0.22, -0.36], [0.01, -0.34]
        ];
        mb.addLathe(crown, 36, pearl, M(0.10, 0.12, 0.08, 1.0), mat4Scale(1.0, 1.0, 0.78));
        // Dual roots
        for (const s of [-1, 1]) {
          mb.addCylinder(0.22, 0.06, 0.56, 20, pearl, M(0.10, 0.16, 0.05, 0.96),
            mat4Mul(mat4Translate(s*0.24, -0.46, 0), mat4RotZ(s*0.18)));
        }
        break;
      }

      case 'medical_cross_crystal': {
        const porcelain = [0.96, 0.98, 1.0];
        const ice = [0.12, 0.68, 0.95];
        mb.addBox(1.26, 0.42, 0.30, porcelain, M(0.18, 0.14, 0.06, 1.0));
        mb.addBox(0.42, 1.26, 0.30, porcelain, M(0.18, 0.14, 0.06, 1.0));
        mb.addBox(1.12, 0.26, 0.33, ice, M(0.35, 0.12, 0.12, 1.0));
        mb.addBox(0.26, 1.12, 0.33, ice, M(0.35, 0.12, 0.12, 1.0));
        break;
      }

      case 'serum_dropper_bottle': {
        const amber = [0.85, 0.45, 0.06];
        const gold = [0.96, 0.78, 0.28];
        const cap = [0.14, 0.13, 0.14];
        mb.addCylinder(0.44, 0.44, 0.88, 36, amber, M(0.30, 0.10, 0.08, 1.0), mat4Translate(0, -0.26, 0));
        mb.addCylinder(0.24, 0.44, 0.16, 36, amber, M(0.30, 0.10, 0.08, 1.0), mat4Translate(0, 0.26, 0));
        mb.addCylinder(0.25, 0.25, 0.16, 28, gold, M(0.95, 0.16, 0, 1.0), mat4Translate(0, 0.42, 0));
        mb.addCylinder(0.15, 0.18, 0.34, 24, cap, M(0.15, 0.45, 0, 1.0), mat4Translate(0, 0.66, 0));
        mb.addSphere(0.15, 18, 12, cap, M(0.15, 0.45, 0, 1.0), mat4Translate(0, 0.82, 0));
        break;
      }

      case 'hanger_velvet_gold': {
        const rose = [0.90, 0.60, 0.54];
        const gold = [0.96, 0.78, 0.30];
        mb.addBox(1.36, 0.11, 0.10, rose, M(0.86, 0.22, 0, 1.0), mat4Translate(0, -0.34, 0));
        mb.addBox(0.80, 0.11, 0.10, rose, M(0.86, 0.22, 0, 1.0), mat4Mul(mat4Translate(-0.34, -0.04, 0), mat4RotZ(0.72)));
        mb.addBox(0.80, 0.11, 0.10, rose, M(0.86, 0.22, 0, 1.0), mat4Mul(mat4Translate(0.34, -0.04, 0), mat4RotZ(-0.72)));
        mb.addCylinder(0.045, 0.045, 0.26, 14, gold, M(0.95, 0.16, 0, 1.0), mat4Translate(0, 0.34, 0));
        mb.addTorus(0.16, 0.042, 24, 12, gold, M(0.95, 0.16, 0, 1.0), mat4Mul(mat4Translate(0, 0.56, 0), mat4RotX(Math.PI/2)));
        break;
      }

      case 'compass_brass_glass': {
        const rotZ = mat4RotX(Math.PI / 2);
        const brass = [0.94, 0.75, 0.26];
        const dial = [0.10, 0.16, 0.26];
        const red = [0.92, 0.16, 0.22];
        const white = [0.96, 0.97, 0.99];
        mb.addTorus(0.68, 0.09, 44, 18, brass, M(0.95, 0.16, 0, 1.0), rotZ);
        mb.addCylinder(0.66, 0.66, 0.16, 44, dial, M(0.30, 0.22, 0, 0.96), rotZ);
        mb.addTorus(0.16, 0.04, 24, 10, brass, M(0.95, 0.16, 0, 1.0), mat4Mul(mat4Translate(0, 0.84, 0), rotZ));
        // Compass needle
        const needle = mat4RotZ(-0.55);
        mb.addBox(0.14, 0.46, 0.06, red, M(0.6, 0.18, 0.1, 1.0), mat4Mul(needle, mat4Translate(0, 0.22, 0.10)));
        mb.addBox(0.14, 0.46, 0.06, white, M(0.6, 0.18, 0.05, 1.0), mat4Mul(needle, mat4Translate(0, -0.22, 0.10)));
        mb.addSphere(0.09, 16, 12, brass, M(0.96, 0.14, 0, 1.0), mat4Translate(0, 0, 0.12));
        break;
      }

      case 'chef_cloche_silver': {
        const silver = [0.90, 0.93, 0.97];
        const dome = [
          [0.74, -0.22], [0.72, -0.02], [0.64, 0.20],
          [0.48, 0.40], [0.26, 0.54], [0.01, 0.60]
        ];
        mb.addLathe(dome, 40, silver, M(0.96, 0.11, 0, 1.0));
        mb.addCylinder(0.84, 0.78, 0.08, 44, silver, M(0.96, 0.12, 0, 1.0), mat4Translate(0, -0.26, 0));
        mb.addCylinder(0.05, 0.08, 0.10, 16, silver, M(0.96, 0.12, 0, 1.0), mat4Translate(0, 0.64, 0));
        mb.addSphere(0.13, 20, 14, silver, M(0.96, 0.10, 0, 1.0), mat4Translate(0, 0.74, 0));
        break;
      }

      case 'nail_polish_bottle': {
        const ruby = [0.88, 0.12, 0.30];
        const cap = [0.12, 0.11, 0.14];
        const gold = [0.96, 0.78, 0.30];
        mb.addBox(0.76, 0.74, 0.54, ruby, M(0.32, 0.09, 0.08, 1.0), mat4Translate(0, -0.32, 0));
        mb.addCylinder(0.20, 0.22, 0.10, 24, gold, M(0.95, 0.16, 0, 1.0), mat4Translate(0, 0.10, 0));
        mb.addCylinder(0.15, 0.20, 0.68, 24, cap, M(0.22, 0.30, 0, 1.0), mat4Translate(0, 0.48, 0));
        break;
      }

      case 'piston_wheel_alloy': {
        const rotZ = mat4RotX(Math.PI / 2);
        const alloy = [0.80, 0.84, 0.90];
        const tire = [0.14, 0.15, 0.18];
        const caliper = [0.92, 0.16, 0.18];
        mb.addTorus(0.66, 0.16, 40, 18, tire, M(0.18, 0.62, 0, 0.96), rotZ);
        mb.addTorus(0.54, 0.065, 36, 14, alloy, M(0.95, 0.16, 0, 1.0), rotZ);
        mb.addCylinder(0.18, 0.18, 0.22, 24, alloy, M(0.95, 0.18, 0, 1.0), rotZ);
        for (let i = 0; i < 5; i++) {
          const a = (i / 5) * Math.PI * 2;
          mb.addBox(0.52, 0.11, 0.14, alloy, M(0.94, 0.18, 0, 1.0), mat4Mul(mat4RotZ(a), mat4Translate(0.28, 0, 0)));
        }
        mb.addBox(0.18, 0.26, 0.20, caliper, M(0.65, 0.22, 0.08, 1.0), mat4Translate(0.36, 0.0, -0.06));
        break;
      }

      default: {
        // Clean parametric studio emblem fallback for any future catalog entry
        const rotZ = mat4RotX(Math.PI / 2);
        mb.addTorus(0.68, 0.10, 40, 16, baseC, M(metal, rough, 0, 1.0), rotZ);
        mb.addSphere(0.46, 20, 14, accC, M(Math.min(1, metal + 0.1), Math.max(0.1, rough - 0.08), 0.08, 1.0), null, true);
        mb.addTorus(0.50, 0.04, 32, 12, secC, M(0.85, 0.22, 0, 1.0), mat4RotY(Math.PI / 4));
        break;
      }
    }

    return { mesh: mb.upload(), glassMode };
  }

  // ---- Runtime Scene State ----
  let current = null;
  let duration = 3.0;
  let rimRgb = [1.0, 0.92, 0.72];

  function springPopScale(t) {
    // 0.26s spring overshoot pop-in: 0.72 -> 1.05 -> 1.0
    const dIn = 0.26;
    if (t <= 0) return 0.72;
    if (t < dIn) {
      const u = t / dIn;
      // Critically underdamped spring curve hitting ~1.052 peak around u=0.62
      const ease = 1.0 - Math.exp(-6.2 * u) * Math.cos(u * Math.PI * 1.45);
      return 0.72 + 0.28 * ease;
    }
    return 1.0;
  }

  function exitScaleAndAlpha(t, dur) {
    const dOut = 0.18;
    const rem = dur - t;
    if (rem < dOut) {
      const u = Math.max(0, Math.min(1, rem / dOut));
      const e = u * u * (3 - 2 * u);
      return { scale: 0.68 + 0.32 * e, alpha: e };
    }
    const alphaIn = Math.min(1.0, t / 0.10);
    return { scale: 1.0, alpha: alphaIn };
  }

  window.__mountProp = (geometryId, matSpec, durSec, sizePx) => {
    const dpr = 2; // 2x internal supersampling for razor-sharp alpha edges
    canvas.width = sizePx * dpr;
    canvas.height = sizePx * dpr;
    gl.viewport(0, 0, canvas.width, canvas.height);

    if (current && current.mesh) {
      gl.deleteVertexArray(current.mesh.vao);
      for (const b of current.mesh.bufs) gl.deleteBuffer(b);
    }
    current = buildPropMesh(geometryId, matSpec || {});
    duration = Math.max(0.4, Number(durSec) || 3.0);
    rimRgb = hexToRgb((matSpec && matSpec.rim_color) || '#FDE68A');

    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.enable(gl.BLEND);
    gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  };

  window.__renderFrame = (tSec) => {
    if (!current) return;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    const t = Math.max(0, Math.min(duration, Number(tSec) || 0));
    const popS = springPopScale(t);
    const ex = exitScaleAndAlpha(t, duration);
    const s = popS * ex.scale;

    // Turntable Y rotation (45 deg/s) + gentle sine bob + subtle pitch tilt
    const rotY = -0.35 + (t * 45.0 * Math.PI) / 180.0;
    const pitchX = (10.0 * Math.PI) / 180.0 + Math.sin(t * 2.4) * 0.055;
    const rollZ = Math.cos(t * 1.9) * 0.04;
    const bobY = Math.sin(t * Math.PI * 2.0 * 0.65) * 0.065;

    let model = mat4Translate(0, bobY, 0);
    model = mat4Mul(model, mat4RotX(pitchX));
    model = mat4Mul(model, mat4RotY(rotY));
    model = mat4Mul(model, mat4RotZ(rollZ));
    model = mat4Mul(model, mat4Scale(s, s, s));

    const view = mat4Translate(0, 0, -3.55);
    const proj = mat4Perspective((34 * Math.PI) / 180, 1.0, 0.1, 20.0);
    const mvp = mat4Mul(proj, mat4Mul(view, model));
    const nMat = mat3NormalFromMat4(model);

    gl.useProgram(prog);
    gl.uniformMatrix4fv(uMVP, false, mvp);
    gl.uniformMatrix4fv(uModel, false, model);
    gl.uniformMatrix3fv(uNormalMat, false, nMat);
    gl.uniform3f(uCamPos, 0, 0, 3.55);
    gl.uniform1f(uOpacity, ex.alpha);
    gl.uniform3f(uRimColor, rimRgb[0], rimRgb[1], rimRgb[2]);
    gl.uniform1f(uGlassMode, current.glassMode || 0.0);

    gl.bindVertexArray(current.mesh.vao);
    gl.drawArrays(gl.TRIANGLES, 0, current.mesh.count);
    gl.finish();
  };
})();
</script>
</body>
</html>
"""


class Local3DPropRenderer:
    """Persistent Playwright + Chrome WebGL2 renderer for transparent 3D PBR .mov props."""

    def __init__(self, size: int = DEFAULT_SIZE, executable_path: str = CHROME_EXECUTABLE) -> None:
        self.size = int(size)
        self.executable_path = executable_path
        self._pw = None
        self._browser = None
        self._page = None

    def __enter__(self) -> "Local3DPropRenderer":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        launch_args = [
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--disable-gpu-sandbox",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        kwargs: dict[str, Any] = {"headless": True, "args": launch_args}
        if Path(self.executable_path).is_file():
            kwargs["executable_path"] = self.executable_path
        self._browser = self._pw.chromium.launch(**kwargs)
        context = self._browser.new_context(
            viewport={"width": self.size, "height": self.size},
            device_scale_factor=1,
        )
        self._page = context.new_page()
        self._page.set_content(STAGE_HTML_TEMPLATE, wait_until="load")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def render_prop(
        self,
        prop_id: str,
        out_mov: str | Path,
        duration: float = DEFAULT_DUR,
        fps: int = DEFAULT_FPS,
        size: int | None = None,
        codec: str = "qtrle",
        still_out: str | Path | None = None,
        still_at: float | None = None,
        catalog: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self._page is not None
        t0 = time.perf_counter()
        cat = catalog or load_catalog()
        props = cat.get("props") or {}
        materials = cat.get("material_presets") or {}

        prop_spec = props.get(prop_id) or {}
        geometry_id = str(prop_spec.get("geometry") or prop_id.replace("3d_", ""))
        mat_name = str(prop_spec.get("material_preset") or "gold_polished")
        mat_spec = materials.get(mat_name) or materials.get("gold_polished") or {}

        render_size = int(size or self.size)
        if render_size != self.size:
            self._page.set_viewport_size({"width": render_size, "height": render_size})
            self.size = render_size

        self._page.evaluate(
            "([g, m, d, s]) => window.__mountProp(g, m, d, s)",
            [geometry_id, mat_spec, float(duration), render_size],
        )

        out_path = Path(out_mov)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        total_frames = max(2, int(round(float(duration) * int(fps))))

        still_idx: int | None = None
        if still_out is not None:
            at_sec = float(still_at) if still_at is not None else min(float(duration) * 0.45, max(0.35, float(duration) - 0.35))
            still_idx = int(max(0, min(total_frames - 1, round(at_sec * int(fps)))))

        cmd = [
            "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-vcodec", "png", "-framerate", str(int(fps)),
            "-i", "-",
            *_ffmpeg_codec_args(codec),
            str(out_path),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None

        try:
            for f in range(total_frames):
                t_sec = f / float(fps)
                self._page.evaluate("(t) => window.__renderFrame(t)", t_sec)
                png_bytes = self._page.screenshot(type="png", omit_background=True, animations="disabled")
                proc.stdin.write(png_bytes)
                if still_idx is not None and f == still_idx and still_out is not None:
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
            "prop_id": prop_id,
            "geometry": geometry_id,
            "material_preset": mat_name,
            "out": str(out_path),
            "frames": total_frames,
            "fps": int(fps),
            "size": render_size,
            "codec": codec,
            "elapsed_sec": elapsed,
        }


def render_manifest(
    manifest_path: Path,
    out_dir: Path,
    fps_override: int | None = None,
    size_override: int | None = None,
    codec_override: str | None = None,
    catalog_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        items = raw
        meta: dict[str, Any] = {}
    else:
        meta = raw
        items = raw.get("props") or raw.get("items") or []

    cat = load_catalog(catalog_path)
    default_fps = int(fps_override or meta.get("fps") or DEFAULT_FPS)
    default_size = int(size_override or meta.get("size") or DEFAULT_SIZE)
    default_codec = str(codec_override or meta.get("codec") or "qtrle")
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with Local3DPropRenderer(size=default_size) as renderer:
        for idx, item in enumerate(items, start=1):
            pid = str(item.get("prop") or item.get("prop_id") or "")
            if not pid:
                continue
            item_id = str(item.get("id") or f"{idx:02d}_{pid}")
            out_file = Path(item["out"]) if item.get("out") else (out_dir / f"{item_id}.mov")
            still_file = Path(item["still_out"]) if item.get("still_out") else None
            res = renderer.render_prop(
                prop_id=pid,
                out_mov=out_file,
                duration=float(item.get("dur") or item.get("duration") or DEFAULT_DUR),
                fps=int(item.get("fps") or default_fps),
                size=int(item.get("size") or default_size),
                codec=str(item.get("codec") or default_codec),
                still_out=still_file,
                still_at=item.get("still_at"),
                catalog=cat,
            )
            results.append(res)
            print(f"[3D PROP OK] {pid} -> {out_file.name} ({res['frames']}f @ {res['fps']}fps, {res['size']}px, {res['elapsed_sec']}s)")
    return results


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Offline WebGL2 PBR 3D Prop Renderer & 17-Industry Matcher")
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="Path to assets_3d_catalog.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_match = sub.add_parser("match", help="Match transcript text & industry against 3D prop catalog")
    p_match.add_argument("--text", required=True, help="Vietnamese/English transcript line or visual cue")
    p_match.add_argument("--industry", default="", help="Industry skin ID from industry_profiles.json")
    p_match.add_argument("--top", type=int, default=5, help="Number of top props to return (default 5)")
    p_match.add_argument("--engine", choices=("all", "local_3d", "google_flow"), default="all")

    p_render = sub.add_parser("render", help="Render single 3D prop or batch manifest to transparent RGBA .mov")
    p_render.add_argument("--prop", help="Prop ID from assets_3d_catalog.json (e.g. 3d_camera_lens_glass)")
    p_render.add_argument("--out", help="Output .mov path for single prop")
    p_render.add_argument("--dur", type=float, default=DEFAULT_DUR, help="Duration in seconds (default 3.0)")
    p_render.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Frame rate (default 30)")
    p_render.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Square render size in px (default 320)")
    p_render.add_argument("--codec", choices=("qtrle", "prores4444", "png"), default="qtrle")
    p_render.add_argument("--still-out", help="Optional PNG frame output path for visual QA")
    p_render.add_argument("--still-at", type=float, default=None, help="Timestamp (sec) for --still-out")
    p_render.add_argument("--manifest", help="Batch props_manifest.json path (reuses 1 browser page)")
    p_render.add_argument("--out-dir", help="Output directory for --manifest batch mode")

    p_list = sub.add_parser("list", help="List available props in catalog")
    p_list.add_argument("--engine", choices=("all", "local_3d", "google_flow"), default="all")
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()

    if args.cmd == "match":
        hits = match_props(
            text=args.text,
            industry=args.industry,
            top=args.top,
            engine=args.engine,
            catalog_path=args.catalog,
        )
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "list":
        cat = load_catalog(args.catalog)
        for pid, spec in (cat.get("props") or {}).items():
            eng = spec.get("engine", "local_3d")
            if args.engine != "all" and eng != args.engine:
                continue
            print(f"{pid}\t{eng}\t{','.join(spec.get('industries') or [])}")
        return 0

    if args.cmd == "render":
        if args.manifest:
            mpath = Path(args.manifest)
            if not mpath.is_file():
                print(f"[3D PROP FAIL] Manifest not found: {mpath}", file=sys.stderr)
                return 2
            odir = Path(args.out_dir) if args.out_dir else (mpath.parent / "props_3d")
            res = render_manifest(
                mpath,
                odir,
                fps_override=args.fps,
                size_override=args.size,
                codec_override=args.codec,
                catalog_path=args.catalog,
            )
            print(f"[BATCH DONE] {len(res)} 3D props rendered -> {odir}")
            return 0

        if not args.prop or not args.out:
            ap.error("Provide either --manifest or both --prop and --out")

        cat = load_catalog(args.catalog)
        with Local3DPropRenderer(size=args.size) as renderer:
            res = renderer.render_prop(
                prop_id=args.prop,
                out_mov=args.out,
                duration=args.dur,
                fps=args.fps,
                size=args.size,
                codec=args.codec,
                still_out=args.still_out,
                still_at=args.still_at,
                catalog=cat,
            )
        print(json.dumps(res, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
