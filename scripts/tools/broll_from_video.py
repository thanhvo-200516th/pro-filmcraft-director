#!/usr/bin/env python3
"""
broll_from_video.py — stateless B-roll slot planner + ONE prompt lint for AI B-roll (Google Flow). No generation code.

  broll_from_video.py analyze --transcript words_tl.json --out broll_plan.json
  broll_from_video.py analyze --video A_ROLL.mp4          --out broll_plan.json     (transcribes through probe_and_align.py)
        Splits the speech into 3-10 s blocks and marks B-roll slots:
          D1  inserts cover >= 25 percent of the video and talk-only runs stay <= 8 s (the opening hook block stays A-roll);
          E2  blocks containing a pain keyword are preferred (list: presets/pain_keywords.json, JSON array the brain can edit;
              --pain-keywords PATH swaps it).
        Writes broll_plan.json, broll_plan.md and prompts_template.json (one record per B-roll slot, bound to its
        anchor_quote, `prompt` empty: the brain writes the English prompt). Slot ids are 1-based block numbers.
  broll_from_video.py check-prompts --plan broll_plan.json --prompts prompts.json [--out flow_ready.json] [--outputs 2]
        Lints every prompt against presets/broll_lint_contract.json (the single contract): English, 8-60 words, anchor_quote
        present and inside the slot text, no text-in-image / brand / face, and PFD R200 (AI B-roll is never proof: a clip that would
        act as claim evidence is flagged). Exit 1 on any failure, otherwise writes the Flow-ready job list.

transcript = words_tl.json ({"words": [[word, start, end], ...]}), a bare [[word, start, end], ...] list, a list of
{word|text, start|s, end|e} objects, Scribe JSON or Whisper segments.
The Google Flow workflow itself (flow_* tools, polling, upscale, download, Muse fallback) is brain-side: references/22_flow_broll.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]
PRESETS = SKILL_ROOT / "presets"
CONTRACT_PATH = PRESETS / "broll_lint_contract.json"
PAIN_PATH = PRESETS / "pain_keywords.json"
PROBE_AND_ALIGN = Path(__file__).resolve().parent / "probe_and_align.py"
PROBE_TIMEOUT_S = float(os.environ.get("PFD_PROBE_TIMEOUT_S") or 3600)  # ASR of a long raw video; never hangs forever

PAUSE_SPLIT_SEC = 0.45
ACTION_CUES = (
    "ví dụ", "thực tế", "kết quả", "văn phòng", "bàn làm việc", "nhân viên", "đội ngũ", "khách hàng", "quy trình", "sản phẩm",
    "hệ thống", "công việc", "buổi sáng", "ban đêm", "ngồi", "làm việc", "gõ", "kiểm tra", "chạy", "tìm", "viết", "xây", "tạo",
    "tăng", "giảm", "tiết kiệm", "hiệu quả", "cửa hàng", "quán", "kho", "xưởng", "màn hình", "báo cáo", "doanh thu", "đơn hàng",
    "tin nhắn", "thời gian", "chi phí", "tự động", "thủ công",
)
CTA_CUES = ("follow", "theo dõi", "bình luận", "comment", "nhắn tin", "inbox", "đăng ký", "lưu lại", "chia sẻ", "link", "liên hệ",
            "bấm vào", "hãy thử", "đừng quên", "kết nối")
SENTENCE_END_RE = re.compile(r"[.?!…]+[\"'”’)\]]*$")
CLAUSE_END_RE = re.compile(r"[,;:]+[\"'”’)\]]*$")
VI_DIACRITICS_RE = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def nfc_lower(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower()


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    return load_json(path)


def load_pain(path: Path = PAIN_PATH) -> list[str]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"{path}: pain keywords must be a JSON array of strings")
    return [unicodedata.normalize("NFC", str(p)).strip() for p in data if str(p).strip()]


# ----------------------------------------------------------------------------- pain keywords (E2)
def find_pain_in_text(text: str, lexicon: list[str]) -> list[str]:
    """Pain phrases in `text` in order of appearance; a phrase inside a longer matched phrase is dropped."""
    t = nfc_lower(text)
    hits: list[tuple[int, int, str]] = []
    for p in sorted(set(lexicon), key=len, reverse=True):
        needle = nfc_lower(p)
        start = 0
        while (i := t.find(needle, start)) != -1:
            j = i + len(needle)
            whole = (i == 0 or not t[i - 1].isalnum()) and (j == len(t) or not t[j].isalnum())
            if whole and not any(a <= i and j <= b for a, b, _ in hits):
                hits.append((i, j, p))
            start = j
    return [p for _, _, p in sorted(hits)]


# ----------------------------------------------------------------------------- transcript
def extract_words(doc: Any) -> list[dict[str, Any]]:
    """Normalise a transcript into [{text, start, end}] sorted by time."""
    seq: Any = doc
    if isinstance(doc, dict):
        seq = doc.get("words") or doc.get("words_tl")
        if seq is None and isinstance(doc.get("segments"), list):
            return _words_from_segments(doc["segments"])
    words: list[dict[str, Any]] = []
    for w in seq or []:
        if isinstance(w, (list, tuple)) and len(w) >= 3:
            text, start, end = str(w[0]), float(w[1]), float(w[2])
        elif isinstance(w, dict):
            if w.get("type", "word") != "word":
                continue
            text = str(w.get("text") or w.get("word") or "")
            start = float(w.get("start", w.get("s", 0.0)) or 0.0)
            end = float(w.get("end", w.get("e", start)) or start)
        else:
            continue
        text = unicodedata.normalize("NFC", text).strip()
        if text:
            words.append({"text": text, "start": round(start, 3), "end": round(max(end, start + 0.05), 3)})
    if not words:
        raise ValueError("the transcript has no words with timestamps")
    words.sort(key=lambda x: (x["start"], x["end"]))
    return words


def _words_from_segments(segments: list) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        sw = seg.get("words")
        if isinstance(sw, list) and sw:
            words += extract_words(sw)
            continue
        toks = str(seg.get("text") or "").split()
        if toks:
            s0 = float(seg.get("start") or 0.0)
            s1 = max(float(seg.get("end") or s0), s0 + 0.1 * len(toks))
            step = (s1 - s0) / len(toks)
            words += [{"text": t, "start": round(s0 + i * step, 3), "end": round(s0 + (i + 1) * step, 3)} for i, t in enumerate(toks)]
    if not words:
        raise ValueError("the transcript has no words with timestamps")
    return sorted(words, key=lambda x: (x["start"], x["end"]))


# ----------------------------------------------------------------------------- blocks
def _make_span(ws: list[dict[str, Any]]) -> dict[str, Any]:
    start, end = round(float(ws[0]["start"]), 3), round(float(ws[-1]["end"]), 3)
    return {"words": ws, "text": " ".join(w["text"] for w in ws).strip(), "start": start, "end": end,
            "dur": round(max(0.05, end - start), 3), "ends_sentence": bool(SENTENCE_END_RE.search(ws[-1]["text"]))}


def _split_oversized(ws: list[dict[str, Any]], max_dur: float) -> list[dict[str, Any]]:
    """Split a too-long word run at a comma or the widest gap into pieces <= max_dur."""
    if not ws:
        return []
    span = _make_span(ws)
    if span["dur"] <= max_dur or len(ws) == 1:
        return [span]
    t0, t1 = ws[0]["start"], ws[-1]["end"]
    mid = (t0 + t1) / 2.0
    best_idx, best = None, -1.0
    for i in range(1, len(ws)):
        left, right = ws[i - 1]["end"] - t0, t1 - ws[i]["start"]
        if left < 1.2 or right < 1.2:
            continue
        gap = max(0.0, ws[i]["start"] - ws[i - 1]["end"])
        comma = 1.0 if CLAUSE_END_RE.search(ws[i - 1]["text"]) else 0.0
        balance = 1.0 - abs(((t0 + left) - mid) / max(0.1, (t1 - t0) / 2.0))
        score = gap * 4.0 + comma * 2.5 + balance
        if left <= max_dur and score > best:
            best, best_idx = score, i
    if best_idx is None:
        for i in range(1, len(ws)):
            if ws[i - 1]["end"] - t0 <= max_dur:
                best_idx = i
        if best_idx is None:
            best_idx = max(1, len(ws) // 2)
    return _split_oversized(ws[:best_idx], max_dur) + _split_oversized(ws[best_idx:], max_dur)


def build_blocks(words: list[dict[str, Any]], min_seg: float = 3.0, max_seg: float = 10.0,
                 pause_split: float = PAUSE_SPLIT_SEC) -> list[dict[str, Any]]:
    """Group words into meaning blocks of [min_seg, max_seg] seconds, split at sentence ends and pauses."""
    if min_seg <= 0 or max_seg < min_seg:
        raise ValueError("need 0 < min_seg <= max_seg")
    clauses: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    for i, w in enumerate(words):
        cur.append(w)
        last = i == len(words) - 1
        gap = 0.0 if last else max(0.0, words[i + 1]["start"] - w["end"])
        if last or SENTENCE_END_RE.search(w["text"]) or gap > pause_split:
            clauses.extend(_split_oversized(cur, max_seg))
            cur = []
    if not clauses:
        return []
    blocks: list[dict[str, Any]] = []
    acc = clauses[0]
    for nxt in clauses[1:]:
        eff_max = min(max_seg, 7.5) if not blocks else max_seg          # block 0 is the hook: <= 7.5 s
        merged = nxt["end"] - acc["start"]
        gap = max(0.0, nxt["start"] - acc["end"])
        if acc["dur"] < min_seg and merged <= eff_max:
            acc = _make_span(acc["words"] + nxt["words"])
        elif acc["dur"] >= min_seg:
            if acc["ends_sentence"] or gap > pause_split or acc["dur"] >= 5.0 or merged > eff_max:
                blocks.append(acc)
                acc = nxt
            else:
                acc = _make_span(acc["words"] + nxt["words"])
        else:
            blocks.append(acc)
            acc = nxt
    blocks.append(acc)
    if len(blocks) >= 2 and blocks[-1]["dur"] < min(min_seg, 2.0):       # tiny tail joins the previous block when it fits
        limit = min(max_seg, 7.5) if len(blocks) == 2 else max_seg
        if blocks[-1]["end"] - blocks[-2]["start"] <= limit:
            blocks[-2] = _make_span(blocks[-2]["words"] + blocks[-1]["words"])
            blocks.pop()
    return blocks


def _cues_in(text: str, cues: tuple[str, ...]) -> list[str]:
    norm = nfc_lower(text)
    return [c for c in cues if re.search(rf"(?<!\w){re.escape(c)}(?!\w)", norm)]


def _score_block(block: dict[str, Any], idx: int, total: int, pain: list[str], long_talk: float) -> dict[str, Any]:
    dur = block["dur"]
    pain_hits = find_pain_in_text(block["text"], pain)
    action_hits = _cues_in(block["text"], ACTION_CUES)
    cta_hits = _cues_in(block["text"], CTA_CUES)
    score = dur * 2.0 + (15.0 if dur >= long_talk else 0.0) + 35.0 * len(pain_hits) + 10.0 * min(len(action_hits), 3)
    if idx == 0:
        score -= 1000.0                                   # the hook keeps the speaker's face
    if total >= 3 and idx == total - 1 and (cta_hits or dur <= 4.5):
        score -= 50.0
    return {"pain_hits": pain_hits, "action_hits": action_hits, "cta_hits": cta_hits, "score": round(score, 2)}


def _max_aroll_run(blocks: list[dict[str, Any]], roles: list[str]) -> tuple[float, list[int]]:
    worst, worst_run, cur = 0.0, [], []
    for i, role in enumerate(roles + ["B-ROLL"]):
        if role == "A-ROLL":
            cur.append(i)
            continue
        if cur:
            span = blocks[cur[-1]]["end"] - blocks[cur[0]]["start"]
            if span > worst:
                worst, worst_run = span, list(cur)
            cur = []
    return round(worst, 3), worst_run


def flow_seconds(voice_len: float, flow: dict) -> int:
    return max(flow["min_sec"], min(flow["max_sec"], int(-(-(voice_len + flow["voice_pad_sec"]) // 1))))


def flow_credits(secs: int, outputs: int, flow: dict) -> int:
    extra = max(0, secs - flow["base_sec"])
    gen = min(secs, flow["base_sec"]) * flow["rate_per_sec"] + extra * flow["rate_per_sec_long"]
    return outputs * gen + extra


def _hint(meta: dict[str, Any]) -> str:
    if meta["pain_hits"]:
        focus = f"an action that illustrates the pain '{meta['pain_hits'][0]}' without text, numbers, charts, logos or UI"
    elif meta["action_hits"]:
        focus = f"a real scene illustrating '{', '.join(meta['action_hits'][:2])}', staying close to the anchor_quote"
    else:
        focus = "a concrete action or setting that illustrates the anchor_quote"
    return ("English, 8-60 words: [Vietnamese subject seen from behind / over the shoulder / hands only] + [" + focus +
            "] + [real setting; any screen or paper out of focus or blank] + [natural warm light] + [one smooth camera move]. "
            "Never present it as proof (R200).")


def plan_broll(blocks: list[dict[str, Any]], pain: list[str], contract: dict, min_coverage: float | None = None,
               outputs: int | None = None) -> dict[str, Any]:
    """Choose B-roll slots: D1 (no A-roll run > max_aroll_run_sec, B-roll >= min_coverage) with E2 (pain blocks first)."""
    cfg, flow = contract["plan"], contract["flow"]
    min_cov = cfg["min_broll_share"] if min_coverage is None else min_coverage
    outs = flow["outputs_default"] if outputs is None else outputs
    max_run, long_talk = float(cfg["max_aroll_run_sec"]), float(cfg["long_talk_sec"])
    n = len(blocks)
    if n == 0:
        raise ValueError("no blocks to plan")
    metas = [_score_block(b, i, n, pain, long_talk) for i, b in enumerate(blocks)]
    roles = ["A-ROLL"] * n
    broke_long = [False] * n
    for_cov = [False] * n

    while True:                                          # pass 1: no talk-only run longer than max_run
        span, run = _max_aroll_run(blocks, roles)
        if span <= max_run or not run:
            break
        pick = max([i for i in run if i != 0] or run, key=lambda i: metas[i]["score"])
        roles[pick], broke_long[pick] = "B-ROLL", True

    total = round(max(blocks[-1]["end"], sum(b["dur"] for b in blocks)), 3)
    spoken = round(sum(b["dur"] for b in blocks), 3)

    def broll_dur() -> float:
        return sum(blocks[i]["dur"] for i, r in enumerate(roles) if r == "B-ROLL")

    def next_to_broll(i: int) -> bool:
        return (i > 0 and roles[i - 1] == "B-ROLL") or (i + 1 < n and roles[i + 1] == "B-ROLL")

    for i in sorted((i for i in range(1, n) if roles[i] == "A-ROLL" and metas[i]["pain_hits"]),   # pass 2: E2 pain blocks
                    key=lambda i: metas[i]["score"], reverse=True):
        if i == n - 1 and metas[i]["cta_hits"]:
            continue
        if not next_to_broll(i) and (broll_dur() + blocks[i]["dur"]) / max(0.1, total) <= 0.60:
            roles[i] = "B-ROLL"

    while broll_dur() / max(0.1, total) < min_cov:        # pass 3: reach the coverage floor
        avail = [i for i in range(n) if roles[i] == "A-ROLL"]
        if not avail:
            break
        pool = [i for i in avail if i != 0 and not next_to_broll(i)] or [i for i in avail if i != 0] or avail
        pick = max(pool, key=lambda i: metas[i]["score"])
        roles[pick], for_cov[pick] = "B-ROLL", True

    slots: list[dict[str, Any]] = []
    a_idx = b_idx = credits = 0
    a_dur = b_dur = 0.0
    for i, (b, role, meta) in enumerate(zip(blocks, roles, metas)):
        vlen = round(b["dur"], 3)
        if role == "B-ROLL":
            b_idx += 1
            fsec = flow_seconds(vlen, flow)
            fcred = flow_credits(fsec, outs, flow)
            credits += fcred
            b_dur += vlen
            reasons = []
            if meta["pain_hits"]:
                reasons.append(f"E2: pain keyword ({', '.join(meta['pain_hits'][:2])})")
            if broke_long[i]:
                reasons.append(f"D1: breaks a talk-only run over {max_run:g} s")
            if for_cov[i]:
                reasons.append(f"D1: lifts B-roll coverage to >= {min_cov:.0%}")
            if vlen + flow["voice_pad_sec"] > flow["max_sec"]:
                reasons.append(f"longer than the Flow maximum ({flow['max_sec']} s): split into two inserts")
            slot = {"role": "B-ROLL", "role_id": f"b-roll-{b_idx}", "flow_seconds": fsec, "flow_credits": fcred,
                    "reason": "; ".join(reasons) or "keeps the visual rhythm", "prompt_hint": _hint(meta)}
        else:
            a_idx += 1
            a_dur += vlen
            why = "hook: keep the speaker's face for the first seconds" if i == 0 else \
                  "closing call to action on the speaker" if i == n - 1 and meta["cta_hits"] else \
                  f"talk-only run stays <= {max_run:g} s"
            slot = {"role": "A-ROLL", "role_id": f"a-roll-{a_idx}", "flow_seconds": 0, "flow_credits": 0, "reason": why, "prompt_hint": ""}
        slots.append({"slot_id": i + 1, "seq_prefix": f"{i + 1:02d}", **slot, "start": b["start"], "end": b["end"], "voice_len": vlen,
                      "anchor_quote": b["text"], "pain_keywords": meta["pain_hits"], "score": meta["score"]})

    run_after, _ = _max_aroll_run(blocks, roles)
    return {"video_duration": total, "spoken_duration": spoken, "aroll_duration": round(a_dur, 3), "broll_duration": round(b_dur, 3),
            "aroll_pct": round(a_dur / total * 100.0, 2) if total else 0.0, "broll_pct": round(b_dur / total * 100.0, 2) if total else 0.0,
            "target_broll_pct": round(min_cov * 100.0, 1), "max_aroll_run_sec": run_after, "outputs": outs,
            "total_credits": credits, "broll_slots_count": b_idx, "slots": slots}


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# B-roll plan (D1 / E2)", "",
        f"- Duration: `{plan['video_duration']:.2f} s` (speech `{plan['spoken_duration']:.2f} s`)",
        f"- B-roll coverage: `{plan['broll_duration']:.2f} s` (**{plan['broll_pct']:.1f}%**, target >= {plan['target_broll_pct']:.1f}%) in "
        f"**{plan['broll_slots_count']}** inserts",
        f"- Longest talk-only run: `{plan['max_aroll_run_sec']:.2f} s`",
        f"- Flow budget (x{plan['outputs']} generations + 1080p upscale of the pick): **{plan['total_credits']} credits**", "",
        "| Slot | Role | Time (s) | Voice (s) | Flow (s) | Credits | anchor_quote | Reason |", "|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for s in plan["slots"]:
        q, r = s["anchor_quote"].replace("|", "\\|"), s["reason"].replace("|", "\\|")
        flow_col = f"{s['flow_seconds']}s" if s["role"] == "B-ROLL" else "—"
        lines.append(f"| `{s['seq_prefix']}` | **{s['role']}** (`{s['role_id']}`) | {s['start']:.2f}–{s['end']:.2f} | {s['voice_len']:.2f} | "
                     f"{flow_col} | {s['flow_credits']} | {q} | {r} |")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- lint (the single contract)
def _phrase_re(tok: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in re.split(r"[-\s]+", tok.strip().lower()) if p]
    return re.compile(r"(?<![\w])" + r"[-\s]+".join(parts) + r"(?![\w])", re.I)


def _hits(text: str, tokens: list[str]) -> list[str]:
    return [t for t in tokens if _phrase_re(t).search(text)]


def claim_triggers(text: str, contract: dict) -> list[str]:
    """Narration phrases that assert a verifiable claim (drive claim_gate)."""
    t = nfc_lower(text)
    cfg = contract["claim_triggers"]
    found = [p for p in cfg["phrases"] if re.search(rf"(?<!\w){re.escape(nfc_lower(p))}(?!\w)", t)]
    found += [m.group(0) for rx in cfg["regex"] for m in re.finditer(rx, t)]
    return found


def prompt_rule_hits(prompt: str, contract: dict) -> dict[str, list[str]]:
    """v7.9.1: the shared token matcher of the ONE B-roll lint (also used by visual_blocks.lint_broll_prompt).
    {rule code: matched tokens} for TEXT_IN_IMAGE, BRAND, FACE (allowed_phrases removed first) and R200; empty lists dropped."""
    low = unicodedata.normalize("NFC", str(prompt or "")).strip().lower()
    rules = contract["rules"]
    hits = {code: _hits(low, rules[code]["tokens"]) for code in ("TEXT_IN_IMAGE", "BRAND")}
    face_low = low
    for ok in rules["FACE"].get("allowed_phrases", []):
        face_low = _phrase_re(ok).sub(" ", face_low)
    hits["FACE"] = _hits(face_low, rules["FACE"]["tokens"])
    hits["R200"] = _hits(low, rules["R200"]["evidence_terms"])
    return {k: v for k, v in hits.items() if v}


def lint_prompt(prompt: str, anchor_quote: str | None, slot_text: str | None, contract: dict) -> list[dict[str, str]]:
    """The ONE ingest-level B-roll lint. Returns [{code, message, hint}]; empty list = pass."""
    errs: list[dict[str, str]] = []
    text = unicodedata.normalize("NFC", str(prompt or "")).strip()
    rules = contract["rules"]

    def add(code: str, msg: str, hint: str = "") -> None:
        errs.append({"code": code, "message": msg, "hint": hint})

    if not text:
        add("EMPTY", "prompt is empty", "write an English scene description bound to the anchor_quote")
        text_ok = False
    else:
        text_ok = True
    if text_ok:
        n = len(text.split())
        if not contract["min_words"] <= n <= contract["max_words"]:
            add("WORDS", f"{n} words, need {contract['min_words']}-{contract['max_words']}")
        if VI_DIACRITICS_RE.search(text):
            add("NOT_ENGLISH", "contains Vietnamese letters; the prompt must be 100 percent English", "translate the scene, keep it concrete")
        hits = prompt_rule_hits(text, contract)
        for code in ("TEXT_IN_IMAGE", "BRAND"):
            if hits.get(code):
                add(code, f"banned words: {', '.join(hits[code])}", rules[code]["hint"])
        if hits.get("FACE"):
            add("FACE", f"shows a face: {', '.join(hits['FACE'])}", rules["FACE"]["hint"])
        if hits.get("R200"):
            add("R200", f"would pass as claim evidence: {', '.join(hits['R200'])}", rules["R200"]["hint"])
    if contract.get("require_anchor_quote", True):
        anchor = nfc_lower(anchor_quote or "").strip()
        if not anchor:
            add("ANCHOR_MISSING", "anchor_quote is missing", "copy the exact words from the slot's anchor_quote that the clip illustrates")
        elif slot_text is not None and " ".join(anchor.split()) not in " ".join(nfc_lower(slot_text).split()):
            add("ANCHOR_NOT_IN_TEXT", "anchor_quote is not inside the slot text", "quote the spoken words verbatim")
    return errs


def check_prompts_against_plan(plan: dict[str, Any], prompts: list[Any], contract: dict, outputs: int | None = None
                               ) -> tuple[list[str], dict[str, Any]]:
    slots = plan.get("slots")
    if not isinstance(slots, list):
        raise ValueError("the plan has no slots")
    if not isinstance(prompts, list):
        raise ValueError("prompts must be a JSON array [{slot_id, prompt, anchor_quote}, ...]")
    flow = contract["flow"]
    outs = outputs if outputs is not None else int(plan.get("outputs") or flow["outputs_default"])
    all_by_id = {int(s["slot_id"]): s for s in slots}
    broll = {sid: s for sid, s in all_by_id.items() if s.get("role") == "B-ROLL"}
    problems: list[str] = []
    seen: set[int] = set()
    jobs: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    total_secs = total_credits = 0
    for idx, entry in enumerate(prompts):
        if not isinstance(entry, dict):
            problems.append(f"entry {idx}: not a JSON object")
            continue
        try:
            sid = int(entry.get("slot_id", entry.get("seq")))
        except (TypeError, ValueError):
            problems.append(f"entry {idx}: missing or invalid slot_id")
            continue
        if sid not in all_by_id:
            problems.append(f"slot {sid}: not in the plan")
            continue
        if sid not in broll:
            problems.append(f"slot {sid}: is A-ROLL, not B-ROLL")
            continue
        if sid in seen:
            problems.append(f"slot {sid}: duplicate prompt")
            continue
        seen.add(sid)
        slot = broll[sid]
        errs = lint_prompt(entry.get("prompt", ""), entry.get("anchor_quote"), slot.get("anchor_quote", ""), contract)
        if errs:
            problems += [f"slot {sid}: {e['code']} {e['message']}" + (f" -> {e['hint']}" if e["hint"] else "") for e in errs]
            continue
        fsec = flow_seconds(float(slot.get("voice_len") or 4.0), flow)
        fcred = flow_credits(fsec, outs, flow)
        total_secs += fsec
        total_credits += fcred
        trig = claim_triggers(slot.get("anchor_quote", ""), contract)
        if trig:
            claims.append({"slot_id": sid, "anchor_quote": slot["anchor_quote"], "triggers": trig})
        jobs.append({"slot_id": sid, "seq_prefix": slot["seq_prefix"], "role_id": slot["role_id"],
                     "file_stem": f"{slot['seq_prefix']}_{slot['role_id']}", "start": slot["start"], "end": slot["end"],
                     "voice_len": slot["voice_len"], "duration_seconds": fsec, "outputs": outs, "credits": fcred,
                     "model": flow["model"], "aspect_ratio": flow["aspect_ratio"], "upscale": flow["upscale"],
                     "anchor_quote": entry.get("anchor_quote"), "prompt": str(entry["prompt"]).strip()})
    for sid in sorted(broll):
        if sid not in seen:
            problems.append(f"slot {sid}: missing prompt for B-ROLL ({broll[sid]['role_id']})")
    jobs.sort(key=lambda j: j["slot_id"])
    ready = {"outputs": outs, "total_jobs": len(jobs), "total_flow_seconds": total_secs, "total_credits": total_credits,
             "claim_gate": bool(claims), "claim_reasons": [c["anchor_quote"] for c in claims], "claims": claims, "jobs": jobs}
    return problems, ready


# ----------------------------------------------------------------------------- CLI
def _transcribe_with_probe(video: Path, work: Path) -> Path:
    """words_tl.json for a raw video via probe_and_align.py (faster-whisper inside); the brain reuses it afterwards."""
    probe_dir = work / "probe"
    try:
        r = subprocess.run([sys.executable, str(PROBE_AND_ALIGN), "--input", str(video), "--work", str(probe_dir), "--tier", "fast"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"probe_and_align.py did not finish within {PROBE_TIMEOUT_S:.0f} s (env PFD_PROBE_TIMEOUT_S)") from exc
    found = sorted(probe_dir.rglob("words_tl.json"))
    if r.returncode != 0 or not found:
        raise RuntimeError(f"probe_and_align.py gave no words_tl.json (rc={r.returncode}): {(r.stderr or r.stdout)[-300:]}")
    return found[0]


def cmd_analyze(a: argparse.Namespace) -> int:
    out_arg = Path(a.out)
    if out_arg.suffix.lower() == ".json":
        work, json_path = out_arg.parent, out_arg
    else:
        work, json_path = out_arg, out_arg / "broll_plan.json"
    md_path, tpl_path = json_path.with_suffix(".md"), json_path.with_name("prompts_template.json")
    try:
        contract = load_contract()
        pain = load_pain(Path(a.pain_keywords) if a.pain_keywords else PAIN_PATH)
        if a.video:
            if not Path(a.video).is_file():
                print(f"video not found: {a.video}", file=sys.stderr)
                return 2
            work.mkdir(parents=True, exist_ok=True)
            tr_path = _transcribe_with_probe(Path(a.video), work)
        else:
            tr_path = Path(a.transcript)
            if not tr_path.is_file():
                print(f"transcript not found: {tr_path}", file=sys.stderr)
                return 2
        cfg = contract["plan"]
        words = extract_words(load_json(tr_path))
        blocks = build_blocks(words, a.min_seg or cfg["min_block_sec"], a.max_seg or cfg["max_block_sec"])
        plan = plan_broll(blocks, pain, contract, a.min_coverage, a.outputs)
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as e:
        print(f"analyze failed: {e}", file=sys.stderr)
        return 2
    plan["source_transcript"] = tr_path.name
    save_json(json_path, plan)
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    save_json(tpl_path, [{"slot_id": s["slot_id"], "anchor_quote": s["anchor_quote"], "prompt": "", "hint": s["prompt_hint"]}
                         for s in plan["slots"] if s["role"] == "B-ROLL"])
    print(f"[PLAN OK] {len(plan['slots'])} slots ({plan['broll_slots_count']} B-ROLL, {plan['broll_pct']:.1f}% >= {plan['target_broll_pct']:.1f}%), "
          f"longest talk-only run {plan['max_aroll_run_sec']:.2f} s, Flow x{plan['outputs']}: {plan['total_credits']} credits")
    print(f"  plan: {json_path}\n  md: {md_path}\n  prompts template: {tpl_path}")
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    try:
        contract = load_contract()
        problems, ready = check_prompts_against_plan(load_json(Path(a.plan)), load_json(Path(a.prompts)), contract, a.outputs)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"[CHECK ERROR] {e}", file=sys.stderr)
        return 2
    if problems:
        for p in problems:
            print(f"[LINT FAIL] {p}")
        print(f"{len(problems)} problem(s): fix the prompts and run check-prompts again.")
        return 1
    out = Path(a.out) if a.out else Path(a.prompts).with_name(f"{Path(a.prompts).stem}.flow_ready.json")
    save_json(out, ready)
    print(f"[LINT OK] {ready['total_jobs']} prompts · Flow {ready['total_flow_seconds']} s · {ready['total_credits']} credits (x{ready['outputs']})"
          + (" · claim_gate: TRUE (verify before publishing)" if ready["claim_gate"] else ""))
    print(f"  flow-ready: {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="transcript or video -> broll_plan.json / .md / prompts_template.json")
    src = an.add_mutually_exclusive_group(required=True)
    src.add_argument("--transcript", help="words_tl.json (or any word-timestamp JSON)")
    src.add_argument("--video", help="raw A-roll video (transcribed through probe_and_align.py)")
    an.add_argument("--out", required=True, help="broll_plan.json path, or a folder")
    an.add_argument("--pain-keywords", default=None, help="JSON array of pain phrases (default presets/pain_keywords.json)")
    an.add_argument("--min-seg", type=float, default=None, help="shortest block, seconds (contract default 3)")
    an.add_argument("--max-seg", type=float, default=None, help="longest block, seconds (contract default 10)")
    an.add_argument("--min-coverage", type=float, default=None, help="B-roll share of the video (contract default 0.25)")
    an.add_argument("--outputs", type=int, default=None, help="Flow generations per insert for the budget (default 2)")
    an.set_defaults(fn=cmd_analyze)
    ck = sub.add_parser("check-prompts", help="lint prompts against presets/broll_lint_contract.json")
    ck.add_argument("--plan", required=True)
    ck.add_argument("--prompts", required=True)
    ck.add_argument("--out", default=None, help="flow-ready JSON (default <prompts>.flow_ready.json)")
    ck.add_argument("--outputs", type=int, default=None)
    ck.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
