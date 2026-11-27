#!/usr/bin/env python3
"""Đặt và kiểm độ to âm thanh theo luật người dùng chốt 2026-11-13 (rules.json → params.audio). Chỉ đọc âm thanh và ghi
JSON / spec; KHÔNG dựng hay xuất video. Mọi số lấy từ rules.json, thiếu khoá thì dừng (không có số mặc định).

    audio_levels.py plan SPEC.craft.json [-o OUT] [--rules rules.json]
    audio_levels.py stems SPEC.craft.json OUT_DIR [--bgm-chain] [--rules rules.json]  # voice.wav bgm.wav sfx.wav (xấp xỉ từ spec)
    audio_levels.py check MIX.wav|mp4 [--voice STEM --bgm STEM --sfx STEM | --stems OUT_DIR] [--allow-skip] [--rules rules.json]
        # exit 1 nếu có FAIL · exit 2 nếu có luật SKIP ("CHƯA KIỂM") · 0 khi mọi luật đạt (--allow-skip: SKIP không tính)
        # WARN (chỉ báo, không đổi exit code; chỉ khi rules.json có khoá tuỳ chọn): bgm_no_voice_lu, lra_warn_lu, short_term_max_lufs

plan: phân loại clip trên các track audio rồi gán gain_db (clip không có "src" bị bỏ qua):
  - voice : đỉnh mẫu dBFS của đoạn clip (in … in+dur) → voice_peak_dbfs.target.
  - bgm   : LUFS tích hợp của đoạn clip → (LUFS giọng − bgm_below_voice_lu.target). LUFS giọng = trung bình năng lượng
            (theo thời lượng) của các clip voice sau gain, xấp xỉ không có cổng.
  - sfx   : đỉnh dBFS → sfx_peak_dbfs.tier[clip["tier"]] nếu clip khai báo tier (A/B/C), không thì .target.
  Phân loại (khớp không phân biệt hoa thường, tên clip ưu tiên hơn tên track): chứa "sfx" → sfx; chứa "nhạc" / "music" /
  "bgm" → bgm; chứa "giọng" / "voice" / "vo" từ đầu → voice. Không khớp được thì dừng, báo tên clip.
  gain_db đang là danh sách khoá (ví dụ hạ nhạc ở chuyển cảnh, giảm dần cuối SFX) thì giữ hình dạng: cả danh sách dời
  đều để khoá lớn nhất = gain tính được. Đo trên file nguồn gốc (gain cũ bị bỏ qua). Spec gốc không bị sửa; ghi bản sao.

  Clip SFX chồng nhau ([at, at+dur] giao nhau, nối chuỗi) tạo thành một cụm: trộn cụm với gain đã tính, nếu đỉnh P của cụm
  > mức đích lớn nhất của cụm + 0,05 dB thì hạ MỌI clip trong cụm đúng (P − mức đích) một lần (overlap_reduction_db trong
  báo cáo). Khoá "tier" bị bỏ khỏi clip ở spec ghi ra (FilmCraft không nhận khoá này); báo cáo giữ tier và dropped_tier.

stems: dựng ba stem 48 kHz stereo float32, dài đúng spec.duration, từ các clip audio của spec: giải mã đoạn in … in+dur×speed,
  speed → atempo, gain_db (số hoặc khoá, nội suy tuyến tính theo dB), đặt tại at, cộng theo vai trò (như plan). Mặc định KHÔNG qua
  bgm_chain (plan đo nhạc không qua chuỗi, FilmCraft không tự áp nó; đo trên OPA05 chuỗi này hạ nhạc thêm 4,2 LU). --bgm-chain
  = nhạc nền qua rules.params.audio.bgm_chain (HPF, EQ, fade vào/ra mỗi clip) khi bản mix thật đã có chuỗi đó. Đây là stem XẤP XỈ TỪ SPEC; mix.wav FilmCraft xuất mới là
  chuẩn cho LUFS / true peak.

check: đo bản mix (LUFS tích hợp, true peak) và các stem nếu có. Luật không có stem để đo thì ghi SKIP.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

DEFAULT_RULES = Path(__file__).resolve().parents[1] / "rules.json"
REQUIRED = {
    "voice_peak_dbfs": ("min", "max", "target"),
    "bgm_below_voice_lu": ("min", "max", "target"),
    "sfx_peak_dbfs": ("min", "max", "target", "tier"),
    "master_lufs": ("final", "tol_lu"),
    "master_true_peak_dbtp": (),
    "bgm_speech_floor_lu": (),
    "bgm_chain": ("hpf_hz", "eq_hz", "eq_q", "eq_db", "fade_in_s", "fade_out_s"),
}
# Khoá TUỲ CHỌN (v7.5.0), chỉ phát WARN, không bao giờ FAIL: vắng mặt = không kiểm (hồ sơ `platform` giữ nguyên);
# có mặt nhưng thiếu khoá con = lấy mặc định dưới đây. Khoá phẳng: `lra_warn_lu` (LRA > ngưỡng), `short_term_max_lufs` (S tối đa > ngưỡng).
OPTIONAL_DEFAULTS = {"bgm_no_voice_lu": {"min": 4.0, "max": 8.0, "target": 6.0, "min_gap_s": 1.5}}
SPEECH_GATE_LU = 10.0      #cửa sổ "có lời" = S của giọng ≥ LUFS tích hợp giọng − 10 LU
S_WARMUP = 3.0             # ebur128 short-term cần 3 s mới đầy cửa sổ
SR = 48000                 # tần số lấy mẫu của stem
OVERLAP_TOL_DB = 0.05      # đỉnh cụm SFX vượt mức đích quá ngưỡng này mới hạ


class RuleError(SystemExit):
    pass


def load_rules(path: Path | str = DEFAULT_RULES) -> dict:
    audio = json.loads(Path(path).read_text(encoding="utf-8")).get("params", {}).get("audio")
    if not isinstance(audio, dict):
        raise RuleError(f"{path}: thiếu params.audio")
    for key, subs in REQUIRED.items():
        if key not in audio:
            raise RuleError(f"{path}: thiếu params.audio.{key}")
        for s in subs:
            if s not in audio[key]:
                raise RuleError(f"{path}: thiếu params.audio.{key}.{s}")
    for key, defaults in OPTIONAL_DEFAULTS.items():
        if isinstance(audio.get(key), dict):
            audio[key] = {**defaults, **audio[key]}
    return audio


# ---------- đo ----------
def _ffmpeg(args: list[str]) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode:
        raise SystemExit(f"ffmpeg lỗi: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode}")
    return r.stderr


def _num(s: str) -> float:
    return -math.inf if "inf" in s else float(s)


def measure(path: str | Path, start: float = 0.0, dur: float | None = None) -> dict:
    """Đoạn [start, start+dur] của file → {"peak": dBFS mẫu, "lufs": tích hợp, "tp": true peak dBTP}."""
    cut = ["-ss", f"{start:.3f}"] + (["-t", f"{dur:.3f}"] if dur else [])
    err = _ffmpeg([*cut, "-i", str(path), "-vn", "-af", "astats=measure_perchannel=none,ebur128=peak=true:framelog=quiet",
                   "-f", "null", "-"])
    try:
        peak = _num(re.search(r"Overall.*?Peak level dB:\s+(-?[\d.]+|-?inf)", err, re.S).group(1))
        sm = err[err.rfind("Summary:"):]
        lufs = _num(re.search(r"I:\s+(-?[\d.]+|-?inf) LUFS", sm).group(1))
        tp = _num(re.search(r"Peak:\s+(-?[\d.]+|-?inf) dBFS", sm).group(1))
    except AttributeError:
        raise SystemExit(f"không đo được {path} (không có luồng âm thanh?)")
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", sm)  # chỉ để tham khảo (EBU R128 s1: LRA không có nghĩa với clip ngắn)
    return {"peak": peak, "lufs": lufs, "tp": tp, "lra": float(lra.group(1)) if lra else None}


def short_term(path: str | Path) -> list[tuple[float, float]]:
    """[(giây, LUFS ngắn hạn)] mỗi 0,1 s, bỏ 3 s đầu (cửa sổ chưa đầy)."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", str(path), "-vn", "-af",
                          "ebur128=metadata=1:framelog=quiet,ametadata=mode=print:key=lavfi.r128.S:file=-", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800).stdout
    out, t = [], 0.0
    for line in err.splitlines():
        if "pts_time:" in line:
            t = float(re.search(r"pts_time:(-?[\d.]+)", line).group(1))
        elif "lavfi.r128.S=" in line and t >= S_WARMUP:
            out.append((round(t, 2), _num(line.split("=")[1])))
    return out


# ---------- phân loại ----------
def classify(track_name: str, clip: dict) -> str:
    for text in (clip.get("name", ""), track_name):
        s = text.lower()
        if "sfx" in s:
            return "sfx"
        if any(k in s for k in ("nhạc", "music", "bgm")):
            return "bgm"
        if "giọng" in s or "voice" in s or re.match(r"\s*(vo|a1)\b", s):
            return "voice"
    raise SystemExit(f"không phân loại được clip audio '{clip.get('name', '')}' trên track '{track_name}' "
                     f"(cần tên chứa SFX / Nhạc|Music|BGM / Giọng|Voice)")


def energy_mean(items: list[tuple[float, float]]) -> float:
    """[(LUFS, thời lượng)] → LUFS trung bình năng lượng theo thời lượng."""
    tot = sum(d for _, d in items)
    return 10 * math.log10(sum(d * 10 ** (v / 10) for v, d in items) / tot)


def apply_gain(clip: dict, gain: float) -> None:
    g = clip.get("gain_db")
    if isinstance(g, list) and g:
        top = max(k[1] for k in g)
        clip["gain_db"] = [[k[0], round(k[1] + gain - top, 2), *k[2:]] for k in g]
    else:
        clip["gain_db"] = round(gain, 2)


def in_range(v: float, rule: dict) -> bool:
    return rule["min"] <= v <= rule["max"]


# ---------- dựng stem ----------
def _atempo(f: float) -> str:
    parts = []
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    return ",".join(f"atempo={x:g}" for x in [*parts, f])


def _is_mono(path: str | Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of",
                        "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return r.stdout.strip() == "1"


def decode(path: str | Path, start: float, src_dur: float, speed: float = 1.0, chain: str = "") -> np.ndarray:
    """Đoạn [start, start+src_dur] của file → float32 [n, 2] ở 48 kHz; speed ≠ 1 → atempo; chain = bộ lọc ffmpeg thêm.
    Nguồn mono → hai kênh giống hệt (pan, không bị hạ 3 dB như upmix mặc định của ffmpeg)."""
    af = ",".join(x for x in ("pan=stereo|c0=c0|c1=c0" if _is_mono(path) else "", _atempo(speed) if speed != 1.0 else "", chain) if x)
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-ss", f"{start:.4f}", "-t", f"{src_dur:.4f}", "-i", str(path),
           "-vn", *(["-af", af] if af else []), "-f", "f32le", "-ar", str(SR), "-ac", "2", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=1800)
    if r.returncode:
        raise SystemExit(f"ffmpeg lỗi khi giải mã {path}: {r.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(r.stdout, dtype="<f4").reshape(-1, 2)


def gain_curve(gain, n: int) -> np.ndarray:
    """gain_db (số hoặc [[giây, dB, …], …] tính từ đầu clip) → hệ số tuyến tính [n]; khoá nội suy tuyến tính theo dB."""
    if not isinstance(gain, list) or not gain:
        return np.full(n, 10 ** ((gain or 0.0) / 20), dtype=np.float32)
    keys = sorted((float(k[0]), float(k[1])) for k in gain)
    db = np.interp(np.arange(n) / SR, [k[0] for k in keys], [k[1] for k in keys])
    return (10 ** (db / 20)).astype(np.float32)


def render_clip(clip: dict, src: Path, role: str, bgm_chain: dict | None = None) -> np.ndarray:
    """Một clip audio → float32 [round(dur×48k), 2] (chưa đặt vào timeline), đã có speed, gain_db, và chuỗi nhạc nền nếu role=bgm."""
    n, speed = int(round(clip["dur"] * SR)), float(clip.get("speed", 1.0))
    chain = ""
    if role == "bgm" and bgm_chain:
        b = bgm_chain
        chain = f"highpass=f={b['hpf_hz']:g},equalizer=f={b['eq_hz']:g}:t=q:w={b['eq_q']:g}:g={b['eq_db']:g}"
    x = decode(src, clip.get("in", 0.0), clip["dur"] * speed, speed, chain)[:n]
    x = np.pad(x, ((0, n - len(x)), (0, 0)))
    x = x * gain_curve(clip.get("gain_db", 0.0), n)[:, None]
    if role == "bgm" and bgm_chain:
        i = np.arange(n)
        fi, fo = max(1, int(bgm_chain["fade_in_s"] * SR)), max(1, int(bgm_chain["fade_out_s"] * SR))
        x = x * (np.minimum(1.0, i / fi) * np.minimum(1.0, (n - 1 - i) / fo)).astype(np.float32)[:, None]
    return x


def place(buf: np.ndarray, x: np.ndarray, at: float) -> None:
    """Cộng x vào buf tại giây at (phần ngoài buf bị cắt). Sửa buf tại chỗ — buf là bộ đệm cục bộ của người gọi."""
    n0 = int(round(at * SR))
    if n0 < 0:
        x, n0 = x[-n0:], 0
    x = x[: max(0, len(buf) - n0)]
    buf[n0:n0 + len(x)] += x


def render_stems(spec: dict, spec_dir: Path, rules: dict, bgm_chain: bool = False) -> dict[str, np.ndarray]:
    if "duration" not in spec:
        raise SystemExit("spec thiếu khoá duration")
    n = int(round(spec["duration"] * SR))
    stems = {k: np.zeros((n, 2), dtype=np.float32) for k in ("voice", "bgm", "sfx")}
    for tr in spec.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        for c in tr.get("clips", []):
            if "src" not in c:
                continue
            src = Path(c["src"])
            src = src if src.is_absolute() else spec_dir / src
            role = classify(tr.get("name", ""), c)
            place(stems[role], render_clip(c, src, role, rules["bgm_chain"] if bgm_chain else None), c["at"])
    return stems


def write_wav(path: Path, x: np.ndarray) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                        "-i", "-", "-c:a", "pcm_f32le", str(path)], input=x.astype("<f4").tobytes(), capture_output=True, timeout=1800)
    if r.returncode:
        raise SystemExit(f"không ghi được {path}: {r.stderr.decode(errors='replace').strip()}")


def stems(spec_path: Path, out_dir: Path, rules: dict, bgm_chain: bool = False) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = {"note": "stem xấp xỉ từ spec — mix.wav FilmCraft vẫn là chuẩn cho LUFS / true peak", "bgm_chain": bgm_chain, "stems": {}}
    for role, x in render_stems(spec, spec_path.parent, rules, bgm_chain).items():
        path = out_dir / f"{role}.wav"
        write_wav(path, x)
        rep["stems"][role] = {"file": str(path), "duration": round(len(x) / SR, 3)}
    return rep


# ---------- plan ----------
def sfx_clusters(sfx: list[dict]) -> list[list[dict]]:
    """Gộp clip SFX có [at, at+dur] giao nhau (nối chuỗi) thành cụm, theo thứ tự thời gian."""
    out, end = [], -math.inf
    for it in sorted(sfx, key=lambda i: i["clip"]["at"]):
        a = it["clip"]["at"]
        if out and a < end:
            out[-1].append(it)
            end = max(end, a + it["clip"]["dur"])
        else:
            out.append([it])
            end = a + it["clip"]["dur"]
    return out


def reduce_overlaps(items: list[dict], spec_dir: Path) -> list[dict]:
    """Cụm SFX chồng nhau: trộn với gain đã tính; đỉnh P > mức đích lớn nhất + OVERLAP_TOL_DB → hạ cả cụm (P − mức đích), một lượt."""
    report = []
    for cl in (c for c in sfx_clusters([i for i in items if i["role"] == "sfx"]) if len(c) > 1):
        t0 = min(i["clip"]["at"] for i in cl)
        buf = np.zeros((int(round((max(i["clip"]["at"] + i["clip"]["dur"] for i in cl) - t0) * SR)) + 1, 2), dtype=np.float32)
        for i in cl:
            src = Path(i["clip"]["src"])
            place(buf, render_clip(i["clip"], src if src.is_absolute() else spec_dir / src, "sfx"), i["clip"]["at"] - t0)
        peak, cap = 20 * math.log10(max(float(np.abs(buf).max()), 1e-9)), max(i["target"] for i in cl)
        cut = max(0.0, peak - cap) if peak > cap + OVERLAP_TOL_DB else 0.0
        for i in cl:
            i["gain"] -= cut
            i["overlap_db"] = -cut
            apply_gain(i["clip"], i["gain"])
        report.append({"at": round(t0, 3), "clips": [i["name"] for i in cl], "peak_dbfs": round(peak, 2), "cap_dbfs": cap,
                       "overlap_reduction_db": round(-cut, 2)})
    return report


def plan(spec_path: Path, out: Path, rules: dict) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    new = copy.deepcopy(spec)
    items = []
    for tr in new.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        for c in tr.get("clips", []):
            if "src" not in c:
                continue
            src = Path(c["src"])
            src = src if src.is_absolute() else spec_path.parent / src
            m = measure(src, c.get("in", 0.0), c["dur"] * float(c.get("speed", 1.0)))
            if not math.isfinite(m["peak"]) or not math.isfinite(m["lufs"]):
                raise SystemExit(f"clip '{c.get('name', src.name)}' im lặng ở đoạn in={c.get('in', 0.0)} dur={c['dur']}")
            items.append({"clip": c, "role": classify(tr.get("name", ""), c), "m": m, "dur": c["dur"],
                          "name": c.get("name", src.name)})
    for role, key in (("voice", "voice_peak_dbfs"), ("sfx", "sfx_peak_dbfs")):
        for it in (i for i in items if i["role"] == role):
            tier = it["clip"].get("tier") if role == "sfx" else None
            if tier is not None and tier not in rules[key]["tier"]:
                raise SystemExit(f"clip '{it['name']}': tier '{tier}' không có trong {key}.tier")
            target = rules[key]["tier"][tier] if tier is not None else rules[key]["target"]
            if not in_range(target, rules[key]):
                raise SystemExit(f"{key}: mức đích {target} nằm ngoài {rules[key]['min']}…{rules[key]['max']}")
            it["gain"], it["target"], it["tier"] = target - it["m"]["peak"], target, tier
    voice = [i for i in items if i["role"] == "voice"]
    voice_i = energy_mean([(i["m"]["lufs"] + i["gain"], i["dur"]) for i in voice]) if voice else None
    bgm = [i for i in items if i["role"] == "bgm"]
    if bgm and voice_i is None:
        raise SystemExit("có clip nhạc nền nhưng không có clip giọng để làm mốc LUFS")
    for it in bgm:
        it["target"] = voice_i - rules["bgm_below_voice_lu"]["target"]
        it["gain"], it["tier"] = it["target"] - it["m"]["lufs"], None
    for it in items:
        apply_gain(it["clip"], it["gain"])
        it["overlap_db"] = 0.0
    clusters = reduce_overlaps(items, spec_path.parent)
    dropped = 0
    for it in items:
        dropped += it["clip"].pop("tier", None) is not None
    out.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = [{"name": i["name"], "role": i["role"], "tier": i["tier"], "src_peak_dbfs": round(i["m"]["peak"], 2),
             "src_lufs": round(i["m"]["lufs"], 2), "target": round(i["target"], 2), "gain_db": round(i["gain"], 2),
             "overlap_reduction_db": round(i["overlap_db"], 2)} for i in items]
    return {"spec": str(out), "voice_lufs": None if voice_i is None else round(voice_i, 2), "dropped_tier": dropped,
            "sfx_overlap_clusters": clusters, "clips": rows}


def print_plan(rep: dict) -> None:
    print(f"{'vai trò':<7} {'tier':<4} {'đỉnh nguồn':>10} {'LUFS nguồn':>10} {'đích':>7} {'gain_db':>8}  clip")
    for r in rep["clips"]:
        print(f"{r['role']:<7} {r['tier'] or '-':<4} {r['src_peak_dbfs']:>10.1f} {r['src_lufs']:>10.1f} "
              f"{r['target']:>7.1f} {r['gain_db']:>8.1f}  {r['name']}")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


# ---------- check ----------
def verdict(rid: str, ok: bool | None, value, rule: str, soft: bool = False) -> dict:
    """soft=True: không đạt → WARN (chỉ báo, không làm exit 1)."""
    bad = "WARN" if soft else "FAIL"
    return {"id": rid, "status": "SKIP" if ok is None else "PASS" if ok else bad, "value": value, "rule": rule}


def no_voice_gap(sv: dict, sb: dict, voice_lufs: float, rule: dict) -> float | None:
    """Trung vị (LU) giữa LUFS tích hợp giọng và S của nhạc ở các cửa sổ KHÔNG có lời. S của giọng phủ 3 s gần nhất, nên cửa sổ
    nào có S giọng dưới ngưỡng nói là cả 3 s đó đều không có lời (nhạc không lẫn đoạn ép). Dưới `min_gap_s` cửa sổ → None (không đo)."""
    gaps = sorted(voice_lufs - sb[t] for t in sv if t in sb and sv[t] < voice_lufs - SPEECH_GATE_LU and math.isfinite(sb[t]))
    if len(gaps) < max(1, round(rule["min_gap_s"] * 10)):
        return None
    return gaps[len(gaps) // 2] if len(gaps) % 2 else (gaps[len(gaps) // 2 - 1] + gaps[len(gaps) // 2]) / 2


def check(mix: Path, rules: dict, voice: Path | None, bgm: Path | None, sfx: Path | None) -> list[dict]:
    mx, res = measure(mix), []
    ml = rules["master_lufs"]
    res.append(verdict("master_lufs", abs(mx["lufs"] - ml["final"]) <= ml["tol_lu"], round(mx["lufs"], 2),
                       f"{ml['final']} ± {ml['tol_lu']} LUFS"))
    res.append(verdict("true_peak", mx["tp"] <= rules["master_true_peak_dbtp"], round(mx["tp"], 2),
                       f"≤ {rules['master_true_peak_dbtp']} dBTP"))
    v = measure(voice) if voice else None
    b = measure(bgm) if bgm else None
    s = measure(sfx) if sfx else None
    vr, br, sr = rules["voice_peak_dbfs"], rules["bgm_below_voice_lu"], rules["sfx_peak_dbfs"]
    res.append(verdict("voice_peak", None if v is None else in_range(v["peak"], vr),
                       None if v is None else round(v["peak"], 2), f"{vr['min']} … {vr['max']} dBFS"))
    res.append(verdict("sfx_peak", None if s is None else in_range(s["peak"], sr),
                       None if s is None else round(s["peak"], 2), f"{sr['min']} … {sr['max']} dBFS"))
    gap = None if v is None or b is None else v["lufs"] - b["lufs"]
    res.append(verdict("bgm_below_voice", None if gap is None else in_range(gap, br),
                       None if gap is None else round(gap, 2), f"{br['min']} … {br['max']} LU dưới giọng"))
    floor, sv, sb = None, {}, {}
    if voice and bgm:
        sv, sb = dict(short_term(voice)), dict(short_term(bgm))
        gaps = [sv[t] - sb[t] for t in sv if t in sb and sv[t] >= v["lufs"] - SPEECH_GATE_LU]
        floor = min(gaps) if gaps else None
    res.append(verdict("speech_floor", None if floor is None else floor >= rules["bgm_speech_floor_lu"],
                       None if floor is None else round(floor, 2), f"≥ {rules['bgm_speech_floor_lu']} LU mọi cửa sổ có lời"))
    # --- chỉ báo (WARN), và chỉ khi luật có khoá: hồ sơ `platform` không có nên danh sách verdict giữ nguyên ---
    nv = rules.get("bgm_no_voice_lu")
    if nv and sv:
        g = no_voice_gap(sv, sb, v["lufs"], nv)
        if g is not None:
            res.append(verdict("bgm_no_voice", nv["min"] <= g <= nv["max"], round(g, 2),
                               f"{nv['min']} … {nv['max']} LU dưới giọng khi không có lời (mục tiêu {nv['target']})", soft=True))
    if rules.get("lra_warn_lu") is not None and mx.get("lra") is not None:
        res.append(verdict("lra", mx["lra"] <= rules["lra_warn_lu"], round(mx["lra"], 2),
                           f"LRA ≤ {rules['lra_warn_lu']} LU (tham khảo, EBU R128 s1)", soft=True))
    if rules.get("short_term_max_lufs") is not None:
        st = [x for _, x in short_term(mix) if math.isfinite(x)]
        if st:
            res.append(verdict("short_term_max", max(st) <= rules["short_term_max_lufs"], round(max(st), 2),
                               f"S tối đa ≤ {rules['short_term_max_lufs']} LUFS", soft=True))
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("plan")
    p.add_argument("spec")
    p.add_argument("-o", "--out")
    c = sub.add_parser("check")
    c.add_argument("mix")
    for k in ("voice", "bgm", "sfx"):
        c.add_argument(f"--{k}")
    c.add_argument("--stems", help="thư mục do `stems` ghi ra (voice.wav bgm.wav sfx.wav)")
    c.add_argument("--allow-skip", action="store_true", help="luật SKIP không làm exit 2")
    t = sub.add_parser("stems")
    t.add_argument("spec")
    t.add_argument("out_dir")
    t.add_argument("--bgm-chain", action="store_true", help="cho nhạc nền qua params.audio.bgm_chain (HPF, EQ, fade); mặc định tắt")
    for sp in (p, c, t):
        sp.add_argument("--rules", default=str(DEFAULT_RULES))
    a = ap.parse_args()
    rules = load_rules(a.rules)
    if a.mode == "stems":
        print(json.dumps(stems(Path(a.spec), Path(a.out_dir), rules, a.bgm_chain), ensure_ascii=False, indent=1))
        return 0
    if a.mode == "plan":
        spec = Path(a.spec)
        out = Path(a.out) if a.out else spec.with_name(spec.name.replace(".craft.json", "") + ".levels.craft.json")
        print_plan(plan(spec, out, rules))
        return 0
    paths = [a.voice, a.bgm, a.sfx]
    if a.stems:
        paths = [str(Path(a.stems) / f"{k}.wav") for k in ("voice", "bgm", "sfx")]
        missing = [x for x in paths if not Path(x).is_file()]
        if missing:
            raise SystemExit(f"thiếu stem: {', '.join(missing)} (chạy `stems` trước)")
    res = check(Path(a.mix), rules, *(Path(x) if x else None for x in paths))
    for r in res:
        label = "CHƯA KIỂM" if r["status"] == "SKIP" else r["status"]
        print(f"[{label:<4}] {r['id']:<16} {r['value']}  (luật: {r['rule']})")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if any(r["status"] == "FAIL" for r in res):
        return 1
    return 2 if not a.allow_skip and any(r["status"] == "SKIP" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
