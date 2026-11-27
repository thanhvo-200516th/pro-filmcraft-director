#!/usr/bin/env python3
"""
Tests for the stateless ported tools (P2): silence_cut, speed_media, sfx_auto, qa_sync + sfx_shift,
broll_from_video (+ presets/broll_lint_contract.json, presets/pain_keywords.json, presets/sfx_catalog.json).

All media and generated JSON are synthesized with ffmpeg / numpy at run time into a temporary directory (removed at exit);
only the two hand-written inputs events_sample.json / words_tl_sample.json are read from tests/fixtures_ports/.
No whisper, no network, no FilmCraft.
"""
from __future__ import annotations

import json
import math
import atexit
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import wave
import zlib
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS = SKILL_ROOT / "scripts" / "tools"
PRESETS = SKILL_ROOT / "presets"
_FIX_TMP = tempfile.TemporaryDirectory(prefix="fixtures_ports_")
atexit.register(_FIX_TMP.cleanup)
FIX = Path(_FIX_TMP.name)
FIX_STATIC = Path(__file__).resolve().parent / "fixtures_ports"  # tracked, hand-written, read-only inputs

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
SR = 48000


# ----------------------------------------------------------------------------- helpers
def run_tool(name: str, *args: str, expect: int | None = 0) -> subprocess.CompletedProcess:
    p = subprocess.run([sys.executable, str(TOOLS / f"{name}.py"), *map(str, args)], capture_output=True, text=True)
    if expect is not None:
        assert p.returncode == expect, f"{name} {args} -> rc={p.returncode} (want {expect})\nSTDOUT:{p.stdout[-1500:]}\nSTDERR:{p.stderr[-1500:]}"
    return p


def ff(*args: str) -> None:
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def tone(dur: float, freq: float = 440.0, amp: float = 0.4) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    return amp * np.sin(2 * np.pi * freq * t)


def silence(dur: float) -> np.ndarray:
    return np.zeros(int(dur * SR))


def probe(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,r_frame_rate,avg_frame_rate,duration:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    d = json.loads(out)
    info = {"duration": float(d["format"]["duration"])}
    for s in d.get("streams", []):
        info.setdefault(s["codec_type"], s)
    return info


def make_av(path: Path, audio: np.ndarray, fps: int = 30, size: str = "160x90") -> Path:
    wav = path.with_suffix(".src.wav")
    write_wav(wav, audio)
    dur = len(audio) / SR
    ff("-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}:duration={dur:.3f}", "-i", wav,
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", path)
    return path


def is_snapped(x: float, fps: int) -> bool:
    return abs(x * fps - round(x * fps)) < 1e-3


# ----------------------------------------------------------------------------- 1. silence_cut
def test_01_silence_cut() -> None:
    src = make_av(FIX / "sc_basic.mp4", np.concatenate([tone(1.0), silence(1.0), tone(1.0), silence(0.8), tone(0.6)]))
    p = run_tool("silence_cut", "plan", "--input", src, "--out", FIX / "sc_basic.plan.json")
    plan = json.loads(p.stdout)
    segs = plan["segments"]
    assert len(segs) == 3, segs
    for a, b in segs:
        assert is_snapped(a, 30) and is_snapped(b, 30), f"not frame-snapped: {a},{b}"
    # keep = complement of silence (+0.07 before / +0.09 after): tones at 0-1, 2-3, 3.8-4.4
    expect = [(0.0, 1.09), (1.93, 3.09), (3.73, 4.4)]
    for (a, b), (ea, eb) in zip(segs, expect):
        assert abs(a - ea) <= 0.06 and abs(b - eb) <= 0.06, ((a, b), (ea, eb))
    assert plan["kept_seconds"] < plan["duration"] - 1.0
    assert json.loads((FIX / "sc_basic.plan.json").read_text())["segments"] == segs

    # merge gap: a 0.2 s hole is silence for --min-silence 0.1, but pads (0.07+0.09) leave < 0.12... -> merged
    gap = make_av(FIX / "sc_gap.mp4", np.concatenate([tone(1.0), silence(0.2), tone(1.0), silence(1.0), tone(0.5)]))
    merged = json.loads(run_tool("silence_cut", "plan", "--input", gap, "--min-silence", "0.1", "--merge-gap", "0.3").stdout)["segments"]
    split = json.loads(run_tool("silence_cut", "plan", "--input", gap, "--min-silence", "0.1", "--merge-gap", "0.0").stdout)["segments"]
    assert len(merged) == len(split) - 1, (merged, split)

    # 60 fps snapping
    p60 = json.loads(run_tool("silence_cut", "plan", "--input", src, "--fps", "60").stdout)
    assert p60["fps"] == 60 and all(is_snapped(a, 60) and is_snapped(b, 60) for a, b in p60["segments"])

    # apply: output length == sum of kept segments, CFR 30
    out = FIX / "sc_basic.cut.mp4"
    res = json.loads(run_tool("silence_cut", "apply", "--input", src, "--out", out).stdout)
    want = sum(b - a for a, b in segs)
    got = probe(out)
    assert abs(got["duration"] - want) <= 2 / 30, (got["duration"], want)
    assert got["video"]["r_frame_rate"] == "30/1", got["video"]
    assert res["segments"] == 3
    print("[PASS] silence_cut: keep = complement of silencedetect, frame-snapped, merge-gap, apply CFR")


# ----------------------------------------------------------------------------- 2. speed_media
def test_02_speed_media() -> None:
    sys.path.insert(0, str(TOOLS))
    import speed_media as sm
    assert sm.choose_speed(40.0) == 1.0 and sm.choose_speed(44.99) == 1.0
    assert sm.choose_speed(49.5) == 1.10 and sm.choose_speed(48.0) == 1.05 and sm.choose_speed(47.25) == 1.05
    assert sm.choose_speed(47.0) == 1.0
    for banned in (1.15, 1.25):
        assert banned not in sm.ALLOWED_SPEEDS

    short = FIX / "sp_40s.wav"
    write_wav(short, tone(40.0))
    pl = json.loads(run_tool("speed_media", "plan", "--input", short).stdout)
    assert pl["speed"] == 1.0, pl
    long_ = make_av(FIX / "sp_50s.mp4", tone(50.0, 440.0))
    pl = json.loads(run_tool("speed_media", "plan", "--input", long_).stdout)
    assert pl["speed"] == 1.10 and pl["out_duration"] >= 45.0, pl
    mid = FIX / "sp_48s.wav"
    write_wav(mid, tone(48.0))
    assert json.loads(run_tool("speed_media", "plan", "--input", mid).stdout)["speed"] == 1.05

    # 1.15 / 1.25 are refused (argparse error -> rc 2)
    for banned in ("1.15", "1.25"):
        run_tool("speed_media", "apply", "--input", long_, "--out", FIX / "sp_bad.mp4", "--speed", banned, expect=2)

    # <45 s: apply is a no-op (nothing written)
    noop = FIX / "sp_noop.wav"
    noop.unlink(missing_ok=True)
    r = json.loads(run_tool("speed_media", "apply", "--input", short, "--out", noop).stdout)
    assert r["speed"] == 1.0 and not noop.exists()
    run_tool("speed_media", "check", "--input", short, "--out", noop)   # nothing to check at 1.0 -> ok

    out = FIX / "sp_50s.x110.mp4"
    r = json.loads(run_tool("speed_media", "apply", "--input", long_, "--out", out).stdout)
    assert r["speed"] == 1.10
    info = probe(out)
    assert info["video"]["r_frame_rate"] == "30/1" and info["video"]["avg_frame_rate"] == "30/1", info["video"]
    assert abs(info["duration"] - 50.0 / 1.10) <= 1 / 30 + 0.03, info["duration"]
    run_tool("speed_media", "check", "--input", long_, "--out", out)

    # pitch preserved (atempo): a 440 Hz tone stays 440 Hz
    pcm = subprocess.run([FFMPEG, "-v", "error", "-i", str(out), "-vn", "-t", "5", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float64)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f0 = float(np.argmax(spec)) * 16000 / len(x)
    assert abs(f0 - 440.0) < 6.0, f"pitch moved: {f0} Hz"

    # an output sped up by a banned 1.25 must FAIL check
    bad = FIX / "sp_50s.x125.mp4"
    ff("-i", long_, "-filter_complex", "[0:v]setpts=PTS/1.25,fps=30[v];[0:a]atempo=1.25[a]", "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", bad)
    run_tool("speed_media", "check", "--input", long_, "--out", bad, expect=1)

    hp = run_tool("speed_media", "--help").stdout
    assert "pre-ingest" in hp and "never after a spec exists" in hp
    print("[PASS] speed_media: policy 1.10 -> 1.05 -> 1.0, <45 s stays 1.0, 1.15/1.25 banned, CFR, pitch kept")


# ----------------------------------------------------------------------------- 3. sfx_auto
def _file_peak(rel: str) -> tuple[float, float]:
    """Deterministic synthetic (lead, peak) in seconds for a catalog file."""
    h = zlib.crc32(rel.encode())
    return 0.02 + 0.005 * (h % 4), 0.08 + 0.01 * ((h >> 3) % 6)


def _synth_sfx_library(root: Path, catalog: dict) -> None:
    rng = np.random.default_rng(7)
    rels = {f for k in catalog["kinds"].values() for f in k["files"]} | {f for p in catalog["opening"]["pairs"] for f in p}
    for rel in rels:
        lead, peak = _file_peak(rel)
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        env = np.where(t < lead, 0.0, np.where(t < peak, (t - lead) / (peak - lead), np.exp(-(t - peak) * 22.0)))
        x = env * rng.uniform(-1, 1, n) * 0.8
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_wav(dest, x)   # WAV bytes under any extension: ffmpeg probes content


def _json_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _json_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _json_strings(v)


HEAVY_HINTS = ("whoosh", "swoosh", "swish", "whip", "impact", "boom", "slam", "thud", "braam", "riser_hit", "punch", "sub_drop", "chuyển cảnh")


def test_03_sfx_auto() -> None:
    cat_path = PRESETS / "sfx_catalog.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    rules = json.loads((PRESETS / "sfx_micro_sync_rules.json").read_text(encoding="utf-8"))

    # no absolute paths anywhere in the catalog (json scan)
    for s in _json_strings(catalog):
        assert not s.startswith("/") and "/home/" not in s and not re.match(r"^[A-Za-z]:[\\/]", s) and ".." not in s.split("/"), s
    files = [f for k in catalog["kinds"].values() for f in k["files"]] + [f for p in catalog["opening"]["pairs"] for f in p]
    assert len(files) > 100 and all(not f.startswith("/") for f in files)
    # the 7 Organic Foley groups exist and the rules file keeps its original keys
    assert all(g in catalog["kinds"] for g in rules["organic_foley_7"]["catalog_groups"]) and len(rules["organic_foley_7"]["archetypes"]) == 7
    for key in ("schema_version", "master_targets", "bus_levels_dbfs", "ducking_4_point_envelope", "micro_sync_offsets_30fps"):
        assert key in rules
    assert rules["heavy_whoosh_cap_per_min"] == 5

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "lib with space"
        _synth_sfx_library(root, catalog)
        events = FIX_STATIC / "events_sample.json"
        outs = {}
        for seed in (0, 1):
            out = Path(td) / f"cues{seed}.json"
            run_tool("sfx_auto", "plan", "--events", events, "--catalog", cat_path, "--sfx-root", root,
                     "--opening-seed", str(seed), "--out", out)
            outs[seed] = json.loads(out.read_text(encoding="utf-8"))
        doc = outs[0]
        clips = doc["clips"]
        ev = json.loads(events.read_text(encoding="utf-8"))
        dur = ev["duration"]

        # relative src only, and the file exists under the root
        for c in clips:
            assert not c["src"].startswith("/") and (root / c["src"]).is_file(), c["src"]
            assert 0.0 <= c["at"] and c["at"] + c["dur"] <= dur + 1e-6
        assert not any("/home/" in s for s in _json_strings(doc) if s != str(root) and "sfx_root" not in s)

        # hero word: sound lands +100..+300 ms after the cue, measured on the synthetic file itself
        heroes = [c for c in clips if c["cue"] == "hero_word"]
        assert len(heroes) == 6
        for c in heroes:
            assert 100 <= c["offset_ms"] <= 300, c
            lead, peak = _file_peak(c["src"])
            land = c["at"] + (peak - c["in"]) if c["align"] == "peak" else c["at"] + (lead - c["in"])
            assert abs(land - (c["t_cue"] + c["offset_ms"] / 1000.0)) <= 0.03, (land, c)
            assert c["at"] >= c["t_cue"] - 0.002, f"hero sound starts before the word enters: {c}"

        # opening: frame 0-1, and the pair differs per seed
        op0 = [c for c in outs[0]["clips"] if c["cue"] == "opening"]
        op1 = [c for c in outs[1]["clips"] if c["cue"] == "opening"]
        assert op0 and op1 and all(c["at"] <= 1 / 30 + 1e-6 for c in op0 + op1)
        assert {c["src"] for c in op0} != {c["src"] for c in op1}

        # heavy whoosh cap <= 5/min (same detector as compile_and_verify): 12 transitions in 60 s must be downgraded
        heavy_groups = set(rules["heavy_groups"])

        def is_heavy(c: dict) -> bool:
            stem = Path(c["src"]).stem.lower()
            return c["group"] in heavy_groups or any(h in f"{c['name'].lower()} {stem}" for h in HEAVY_HINTS)

        n_heavy = sum(1 for c in clips if is_heavy(c))
        assert n_heavy / (dur / 60.0) <= 5.0 + 1e-6, f"heavy {n_heavy} in {dur}s"
        assert doc["stats"]["heavy"] <= 5 and doc["downgraded"], doc["stats"]
        assert all(d["to"].startswith("foley_") for d in doc["downgraded"])

        # missing library -> cues skipped, rc 1 (the brain must look)
        empty = Path(td) / "empty"
        empty.mkdir()
        p = run_tool("sfx_auto", "plan", "--events", events, "--catalog", cat_path, "--sfx-root", empty,
                     "--out", Path(td) / "none.json", expect=1)
        assert json.loads((Path(td) / "none.json").read_text(encoding="utf-8"))["skipped"]
    print("[PASS] sfx_auto: hero +100..300 ms, opening frame 0-1 per seed, relative catalog, heavy cap <=5/min + foley fallback")


# ----------------------------------------------------------------------------- 4. qa_sync + sfx_shift
def _qa_fixture(td: Path, click_at: float = 1.11, name: str = "qa") -> tuple[Path, Path]:
    # 3 s dark clip with a 1-frame white flash at t = 1.0 s (frame 30)
    video = FIX / "qa_flash.mp4"
    ff("-f", "lavfi", "-i", "color=c=0x303030:s=90x160:r=30:d=3",
       "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='between(t,1.0,1.03)'",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", video)
    click = FIX / "qa_click.wav"
    x = silence(0.4)
    x[int(0.010 * SR):int(0.030 * SR)] = np.random.default_rng(3).uniform(-0.9, 0.9, int(0.020 * SR)) * np.exp(-np.linspace(0, 6, int(0.020 * SR)))
    write_wav(click, x)
    spec = {"fps": 30, "duration": 3.0, "name": "qa fixture",
            "tracks": [
                {"type": "video", "name": "V1", "clips": [{"at": 0.0, "dur": 1.0, "name": "a"}, {"at": 1.0, "dur": 2.0, "name": "b"}]},
                {"type": "audio", "name": "SFX 1", "clips": [{"at": click_at, "in": 0.0, "dur": 0.4, "src": "qa_click.wav",
                                                              "gain_db": 0, "name": "SFX whoosh · cut"}]}]}
    sp = td / f"{name}.craft.json"
    sp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return video, sp


def test_04_qa_sync_and_sfx_shift() -> None:
    with tempfile.TemporaryDirectory() as td_s:
        td = Path(td_s)
        video, spec = _qa_fixture(td)
        shutil.copy(FIX / "qa_click.wav", td / "qa_click.wav")           # relative src resolves next to the spec
        shifts_path = td / "sfx_shifts.json"
        p = run_tool("qa_sync", "--video", video, "--spec", spec, "--out", shifts_path, expect=None)
        assert p.returncode == 0, p.stdout + p.stderr                      # late sound is a report, not a block
        assert "LỆCH" in p.stdout
        shifts = json.loads(shifts_path.read_text(encoding="utf-8"))
        assert len(shifts) == 1 and shifts[0]["beat"] == "cut"
        assert abs(shifts[0]["shift"] - (-0.12)) <= 0.04, shifts            # click peak 0.12 s after the flash

        # on-time sound -> no shift entries
        _, spec_ok = _qa_fixture(td, click_at=0.99, name="qa_ok")
        run_tool("qa_sync", "--video", video, "--spec", spec_ok, "--out", td / "ok_shifts.json")
        assert json.loads((td / "ok_shifts.json").read_text(encoding="utf-8")) == []
        # sound well before the picture changes -> blocking exit 1
        _, spec_early = _qa_fixture(td, click_at=0.60, name="qa_early")
        run_tool("qa_sync", "--video", video, "--spec", spec_early, "--out", td / "early.json", expect=1)

        # sfx_shift: writes a NEW spec, once only
        new_spec = td / "qa.shifted.craft.json"
        run_tool("sfx_shift", "--spec", spec, "--shifts", shifts_path, "--out", new_spec)
        new = json.loads(new_spec.read_text(encoding="utf-8"))
        clip = next(t for t in new["tracks"] if t["name"] == "SFX 1")["clips"][0]
        assert abs(clip["at"] - 0.99) <= 0.045, clip
        assert new["meta"]["sfx_shifted_once"] is True
        orig = json.loads(spec.read_text(encoding="utf-8"))
        assert next(t for t in orig["tracks"] if t["name"] == "SFX 1")["clips"][0]["at"] == 1.11 and "meta" not in orig
        again = run_tool("sfx_shift", "--spec", new_spec, "--shifts", shifts_path, "--out", td / "third.craft.json", expect=None)
        assert again.returncode != 0 and "sfx_shifted_once" in (again.stdout + again.stderr)
        assert not (td / "third.craft.json").exists()
        run_tool("sfx_shift", "--spec", spec, "--shifts", shifts_path, "--out", spec, expect=2)   # never overwrite the source spec

        # missing .fcproj -> clean error, no traceback
        miss = run_tool("qa_sync", "--video", td / "none.fcproj", "--spec", spec, expect=None)
        assert miss.returncode != 0 and "Traceback" not in miss.stderr
    print("[PASS] qa_sync measures flash vs click (~0.12 s late); sfx_shift writes a new spec and refuses a second shift")


# ----------------------------------------------------------------------------- 5. broll
def test_05_broll_contract_and_lint() -> None:
    sys.path.insert(0, str(TOOLS))
    import broll_from_video as bv

    contract = json.loads((PRESETS / "broll_lint_contract.json").read_text(encoding="utf-8"))
    assert "lint_broll_prompt" in contract["supersedes"] and "45-token" in contract["supersedes"]
    assert contract["min_words"] == 8 and contract["max_words"] == 60 and contract["language"] == "en"

    # the contract covers every token of the rule it supersedes (visual_blocks.BROLL_BANNED_TOKENS)
    import visual_blocks as vb
    covered = {t for r in ("TEXT_IN_IMAGE", "BRAND") for t in contract["rules"][r]["tokens"]}
    assert set(vb.BROLL_BANNED_TOKENS) <= covered, sorted(set(vb.BROLL_BANNED_TOKENS) - covered)

    pain = json.loads((PRESETS / "pain_keywords.json").read_text(encoding="utf-8"))
    assert isinstance(pain, list) and len(pain) >= 100 and len(set(pain)) == len(pain)
    assert all(isinstance(p, str) and p == unicodedata.normalize("NFC", p) and p.strip() == p and p for p in pain)
    assert "mất khách" in pain

    anchor = "nhiều bạn mất khách vì video làm quá chậm"
    good = ("A Vietnamese shop owner seen from behind rearranges neatly folded clothes on a wooden shelf, "
            "soft morning window light, slow push-in, shallow depth of field")
    assert bv.lint_prompt(good, anchor, anchor, contract) == []

    def codes(prompt: str, quote: str = anchor, tts: str = anchor) -> set[str]:
        return {e["code"] for e in bv.lint_prompt(prompt, quote, tts, contract)}

    assert "NOT_ENGLISH" in codes("Một chủ cửa hàng đang sắp xếp quần áo trên kệ gỗ dưới ánh sáng buổi sáng dịu nhẹ")   # Vietnamese rejected
    assert "WORDS" in codes("A shop owner folds clothes")                      # < 8 words
    assert "WORDS" in codes(" ".join(["calm"] * 61))                           # > 60 words
    assert "ANCHOR_MISSING" in codes(good, quote="")
    assert "ANCHOR_NOT_IN_TEXT" in codes(good, quote="câu nói khác hoàn toàn")
    assert "TEXT_IN_IMAGE" in codes(good + ", with a neon sign that says OPEN and a printed price label")
    assert "BRAND" in codes(good + ", holding a Samsung phone next to a TikTok screen")
    assert "FACE" in codes("Extreme close-up of a smiling woman's face looking straight at the camera in bright natural light")
    # faceless framing is fine
    assert not (codes("Over the shoulder view of a Vietnamese woman packing parcels at a wooden table, warm light, slow tracking shot")
                & {"FACE", "BRAND", "TEXT_IN_IMAGE", "R200"})
    # R200: AI B-roll must not act as claim evidence
    r200 = codes("Before and after photos of a client's skin on a clinic table, clinical lighting, slow push-in, shallow depth of field")
    assert "R200" in r200
    r200b = codes("A laptop screenshot of a revenue dashboard showing growth, desk, soft light, slow push-in",
                  "doanh thu tăng gấp ba", "doanh thu tăng gấp ba")
    assert "R200" in r200b
    assert "R200" not in codes(good)

    # plan side: claim narration is surfaced for claim_gate
    assert bv.claim_triggers("doanh thu tăng 300 phần trăm sau một tháng", contract)
    assert not bv.claim_triggers("mình thích uống cà phê buổi sáng", contract)
    print("[PASS] broll lint contract: English 8-60 words, anchor, text/brand/face, Vietnamese rejected, R200 flagged, pain NFC")


def test_06_broll_analyze_and_check() -> None:
    sys.path.insert(0, str(TOOLS))
    import broll_from_video as bv

    tr = FIX_STATIC / "words_tl_sample.json"
    with tempfile.TemporaryDirectory() as td_s:
        td = Path(td_s)
        out = td / "broll_plan.json"
        p = run_tool("broll_from_video", "analyze", "--transcript", tr, "--out", out)
        plan = json.loads(out.read_text(encoding="utf-8"))
        slots = plan["slots"]
        assert all(3.0 - 1e-6 <= s["voice_len"] <= 10.0 + 1e-6 or s["slot_id"] in (1, len(slots)) for s in slots), [s["voice_len"] for s in slots]
        assert plan["broll_pct"] >= 25.0 - 1e-6                                   # D1: >= 25% inserts
        assert plan["max_aroll_run_sec"] <= 8.0 + 1e-6                            # D1: talk-only <= 8 s
        assert slots[0]["role"] == "A-ROLL"                                       # hook stays on the speaker
        broll = [s for s in slots if s["role"] == "B-ROLL"]
        assert broll and all(s["anchor_quote"] for s in broll)
        pains = {k for s in broll for k in s["pain_keywords"]}
        assert pains & {"mất khách", "lãng phí", "tốn thời gian"}, pains         # E2: pain keywords drive slots
        tpl = json.loads((td / "prompts_template.json").read_text(encoding="utf-8"))
        assert {t["slot_id"] for t in tpl} == {s["slot_id"] for s in broll}
        assert all(t["anchor_quote"] and t["prompt"] == "" for t in tpl)

        # the pain list is the brain-editable preset: an extra keyword changes the result
        custom = td / "pain.json"
        custom.write_text(json.dumps(["xin chào"], ensure_ascii=False), encoding="utf-8")
        out2 = td / "plan2.json"
        run_tool("broll_from_video", "analyze", "--transcript", tr, "--out", out2, "--pain-keywords", custom)
        assert not any(s["pain_keywords"] for s in json.loads(out2.read_text(encoding="utf-8"))["slots"][1:])

        # check-prompts: empty template fails, filled template passes, Vietnamese entry fails
        bad = run_tool("broll_from_video", "check-prompts", "--plan", out, "--prompts", td / "prompts_template.json", expect=1)
        assert "NOT_ENGLISH" in bad.stdout or "WORDS" in bad.stdout or "EMPTY" in bad.stdout
        filled = []
        for t in tpl:
            filled.append({**t, "prompt": "A Vietnamese office worker seen from behind types at a tidy wooden desk, warm morning window light, "
                                          "slow push-in, shallow depth of field"})
        okp = td / "prompts_ok.json"
        okp.write_text(json.dumps(filled, ensure_ascii=False), encoding="utf-8")
        ready_path = td / "ready.json"
        run_tool("broll_from_video", "check-prompts", "--plan", out, "--prompts", okp, "--out", ready_path)
        ready = json.loads(ready_path.read_text(encoding="utf-8"))
        assert ready["total_jobs"] == len(broll) and all(j["aspect_ratio"] == "9:16" for j in ready["jobs"])
        filled[0]["prompt"] = "Một nhân viên đang gõ máy tính ở bàn gỗ dưới ánh sáng buổi sáng ấm áp"
        vi = td / "prompts_vi.json"
        vi.write_text(json.dumps(filled, ensure_ascii=False), encoding="utf-8")
        res = run_tool("broll_from_video", "check-prompts", "--plan", out, "--prompts", vi, expect=1)
        assert "NOT_ENGLISH" in res.stdout
    print("[PASS] broll analyze (D1 >=25% inserts, A-roll run <=8 s, E2 pain slots) + check-prompts round trip")


# ----------------------------------------------------------------------------- 7. cross-cutting
def test_07_help_and_portability() -> None:
    names = ["silence_cut", "speed_media", "sfx_auto", "qa_sync", "sfx_shift", "broll_from_video"]
    for n in names:
        p = run_tool(n, "--help")
        assert "usage" in p.stdout.lower()
        src = (TOOLS / f"{n}.py").read_text(encoding="utf-8")
        for bad in ("/home/" + "vmiz", "/home/" + "thanh", "opa-video" + "-studio"):
            assert bad not in src and bad not in p.stdout, f"{bad} in {n}"
        assert unicodedata.normalize("NFC", src) == src
    for f in ("sfx_catalog.json", "pain_keywords.json", "broll_lint_contract.json", "sfx_micro_sync_rules.json"):
        raw = (PRESETS / f).read_text(encoding="utf-8")
        assert unicodedata.normalize("NFC", raw) == raw
        json.loads(raw)
    for f in ("sfx_catalog.json", "pain_keywords.json", "broll_lint_contract.json"):
        raw = (PRESETS / f).read_text(encoding="utf-8")
        assert "/home/" not in raw and "opa-video" + "-studio" not in raw
    print("[PASS] --help for all six tools, no host paths / legacy-skill names, NFC presets")


if __name__ == "__main__":
    test_01_silence_cut()
    test_02_speed_media()
    test_03_sfx_auto()
    test_04_qa_sync_and_sfx_shift()
    test_05_broll_contract_and_lint()
    test_06_broll_analyze_and_check()
    test_07_help_and_portability()
    print("TẤT CẢ ĐẠT (ports P2)")
