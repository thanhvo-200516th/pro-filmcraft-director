#!/usr/bin/env python3
"""flow_3d_assets.py — Lập kế hoạch, kiểm định, tách nền RGBA & ghép bảng kiểm QA cho asset 3D minh hoạ câu thoại qua Google Flow.

Standalone harvested tool for `pro-filmcraft-director/scripts/tools/`.

Chạy:
    PY=~/.venvs/video-skills/bin/python3
    $PY scripts/tools/flow_3d_assets.py plan --manifest 00_storyboard_manifest.json --out-dir work/3d_assets
    $PY scripts/tools/flow_3d_assets.py lint-plan work/3d_assets/3d_assets_plan.json
    $PY scripts/tools/flow_3d_assets.py extract-alpha raw.png out_alpha.png --bg auto --pad 16 --max-size 720
    $PY scripts/tools/flow_3d_assets.py sheet work/3d_assets/3d_assets_plan.json --out work/3d_assets/3d_assets_sheet.jpg
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- Standalone helpers (harvested)
PAIN_LEXICON: list[str] = [
    "mất khách", "mất tiền", "mất thời gian", "tốn thời gian", "tốn tiền", "tốn công", "tốn kém", "đốt tiền",
    "không có khách", "không ra đơn", "không biết bắt đầu", "không biết làm", "không biết", "không có thời gian",
    "không hiệu quả", "không ai xem", "không ai mua", "bế tắc", "kiệt sức", "quá tải", "áp lực", "căng thẳng",
    "thất bại", "sai lầm", "lãng phí", "phá sản", "thua lỗ", "thua", "lỗ", "nợ", "chán nản", "bỏ cuộc",
    "mệt mỏi", "khó khăn", "chậm", "trễ", "rủi ro", "bị lừa", "mất", "tốn", "burnout", "stress", "deadline",
    "bỏ tiền túi", "vứt xó", "xa rời thực tế", "tự bơi", "bị ngợp", "chỉ đạo trên mây",
    "đốt ba mươi triệu", "đốt 30 triệu", "mất một nửa đơn hàng", "chậm quá năm phút", "chậm quá 5 phút",
    "ngại lên hình", "ngâm tin nhắn", "khách rời đi", "ăn mòn lợi nhuận", "sưu tầm công cụ", "loạn não",
    "rò rỉ từng ngày", "phần mềm rời rạc", "doanh nghiệp thất bại", "quy trình rác", "đống rác nhanh hơn",
    "nói lan man", "thông điệp rối rắm", "tiền lương vô ích", "nghiện cảm giác", "toát mồ hôi", "việc vẫn tắc",
    "3 giây đã lướt qua", "ba giây đã lướt qua", "văn mẫu công nghiệp", "đơ cứng", "thiếu sức sống",
    "viết ngô nghê", "sáo rỗng", "không biết một chữ", "tốn cả trăm triệu", "mất cả tháng trời", "không có lửa",
    "tốn gần 200 triệu", "tốn gần hai trăm triệu", "bạn ấy xin nghỉ", "dạy lại từ con số 0",
    "dạy lại từ con số không", "mất trắng quy trình", "quay cuồng", "phình quỹ lương", "tuyển thêm người",
    "dựng thủ công", "cồng kềnh", "chờ suốt hai ngày", "chờ suốt 2 ngày", "sai chính tả", "lệch tông màu",
    "khá thô", "thiếu tự nhiên", "câu lệnh chung chung", "hỗn độn", "mày mò lại từ đầu",
    "ngồi nói chay", "lướt qua ngay", "công cốc", "vẽ thủ công", "hết cả ngày",
    "điên đầu nhất", "chờ nó chạy lại", "chat đi chat lại", "đốt sạch hạn mức",
    "hàng trăm lần thử sai", "đè lên mặt", "lặp lại lỗi cũ", "vài tuần loay hoay",
]

ANTI_SLOP_WORDS = (
    "stunning", "breathtaking", "hyper-detailed", "hyperdetailed",
    "8k masterpiece", "4k masterpiece", "photorealistic masterpiece",
    "8k", "4k", "masterpiece", "magical", "very realistic",
    "ultra-realistic", "ultra realistic", "photorealistic",
    "award-winning", "best quality",
)
ANTI_SLOP_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(w) for w in sorted(ANTI_SLOP_WORDS, key=len, reverse=True)) + r")(?!\w)",
    re.I,
)
PLASTIC_AI_WORDS = (
    "3d render", "cgi", "unreal engine", "octanerender", "octane", "blender render",
    "glowing prism", "amber prism", "frosted-glass gears", "hologram", "holographic",
    "cyberpunk", "neon cyber", "futuristic glowing", "glowing nodes", "floating icons",
    "pipeline rail", "parallel steel tracks", "sci-fi", "plastic sheen", "porcelain skin",
    "rubbery", "energy core",
)
PLASTIC_AI_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(w) for w in sorted(PLASTIC_AI_WORDS, key=len, reverse=True)) + r")(?!\w)",
    re.I,
)
WEIGHT_SYNTAX_RE = re.compile(r"\([^()]+:\s*\d+(?:\.\d+)?\)|(?<!\w)\w+::\s*-?\d+(?:\.\d+)?")
NEGATIVE_TAIL_RE = re.compile(r"\b(?:no texts?|no subtitles?|no watermarks?|no logos?)\b", re.I)
CAMERA_MOTION_RE = re.compile(
    r"\b(?:dolly|push[- ]in|pull[- ]back|tracking|orbit|pan|whip[- ]pan|whip[- ]tilt|"
    r"tilt|handheld|static|tripod|drift|arc|crane|zoom|gimbal|steadicam)\b",
    re.I,
)
REALISM_CUE_RE = re.compile(
    r"(?<!\w)(?:35mm|50mm|24mm|85mm|documentary|handheld|film grain|grain|"
    r"shallow depth of field|shallow focus|window light|daylight|overcast|"
    r"tungsten|warm lamp|natural light|skin texture|micro-pores|pores|"
    r"flyaway|matte|cotton|linen|wooden|ceramic|desaturated|candid|"
    r"f/(?:\d+(?:\.\d+)?)?)(?!\w)",
    re.I,
)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").lower().replace("_", " ")
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def has_diacritics(text: str) -> bool:
    nfd = unicodedata.normalize("NFD", text or "")
    return "đ" in (text or "").lower() or any(unicodedata.combining(c) for c in nfd)


def find_pain_in_text(text: str, extra: list[str] | None = None) -> list[str]:
    """Các cụm nỗi đau trong `text`, theo thứ tự xuất hiện; cụm nằm trong cụm dài hơn thì bỏ."""
    t = unicodedata.normalize("NFC", text or "").lower()
    hits: list[tuple[int, int, str]] = []
    for p in sorted(set(PAIN_LEXICON) | set(extra or []), key=len, reverse=True):
        pn = unicodedata.normalize("NFC", p).lower()
        if not pn:
            continue
        start = 0
        while (i := t.find(pn, start)) != -1:
            j = i + len(pn)
            whole = (i == 0 or not t[i - 1].isalnum()) and (j == len(t) or not t[j].isalnum())
            if whole and not any(a <= i and j <= b for a, b, _ in hits):
                hits.append((i, j, p))
            start = j
    return [p for _, _, p in sorted(hits)]


def at_speed(items: list, f: float, fps: int = 30) -> list:
    """Chia mốc cho tốc độ f. Cặp (a, b) → bám khung `fps` MỘT lần (a/f, b/f)."""
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append({**it, "start": round(it["start"] / f, 3), "end": round(it["end"] / f, 3)})
        else:
            out.append(tuple(round(x / f * fps) / fps for x in it))
    return out


def audit_prompt_architecture(prompt: str, mode: str = "t2v") -> dict[str, Any]:
    """Kiểm nhẹ kiến trúc prompt (Anti-Slop, Anti-Plastic-CGI, cấm syntax trọng số CLIP, Realism Cue & Camera Move)."""
    text = (prompt or "").strip()
    words = text.split()
    primacy_preview = " ".join(words[:35])
    anti_slop_hits = sorted({m.group(0).lower() for m in ANTI_SLOP_RE.finditer(text)})
    plastic_ai_hits = sorted({m.group(0).lower() for m in PLASTIC_AI_RE.finditer(text)})
    weight_syntax_hits = [m.group(0) for m in WEIGHT_SYNTAX_RE.finditer(text)]
    has_realism_cue = bool(text and REALISM_CUE_RE.search(text))
    warnings: list[str] = []

    if anti_slop_hits:
        warnings.append(
            "Anti-Slop: tránh từ sáo rỗng ("
            + ", ".join(anti_slop_hits)
            + "); thay bằng thông số vật lý/quang học/sinh học đo lường được"
        )
    if plastic_ai_hits:
        warnings.append(
            "Plastic/CGI AI-Tell: tránh từ khoá CGI/nhựa lộ AI ("
            + ", ".join(plastic_ai_hits)
            + "); thay bằng vật liệu và ánh sáng đời thực"
        )
    if weight_syntax_hits:
        warnings.append(
            "T5-XXL/Gemma: cấm cú pháp trọng số CLIP ("
            + ", ".join(weight_syntax_hits[:3])
            + "); dùng khuếch đại ngữ nghĩa hoặc khối tiêu đề in hoa"
        )
    if mode in ("t2v", "i2v", "flow") and text and not CAMERA_MOTION_RE.search(text):
        warnings.append(
            "4-Axis Motion: nên nêu rõ 1 chuyển động camera duy nhất (vd: slow push-in, lateral tracking, orbit, static tripod)"
        )
    if mode in ("t2v", "i2v", "t2i", "flow") and text and not has_realism_cue:
        warnings.append(
            "Realism Cue: thiếu chỉ dấu quang học / chất liệu đời thực chống nhựa (vd: 35mm, 50mm, window light, daylight, shallow depth of field, film grain, skin texture, wooden, matte)"
        )
    if mode in ("t2v", "flow") and NEGATIVE_TAIL_RE.search(text):
        warnings.append(
            "Flow T2V: tránh cụm phủ định 'no text/logos/subtitles'; dùng ràng buộc khẳng định (blank, unbranded, out of focus)"
        )

    return {
        "ok": len(warnings) == 0,
        "mode": mode,
        "word_count": len(words),
        "primacy_preview": primacy_preview,
        "anti_slop_hits": anti_slop_hits,
        "plastic_ai_hits": plastic_ai_hits,
        "has_realism_cue": has_realism_cue,
        "weight_syntax_hits": weight_syntax_hits,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- Core 3D Assets Planner
VALID_MODES = ("image_alpha", "video_3d", "mixed")
VALID_ASSET_MODES = ("image_alpha", "video_3d")
VALID_PLACEMENTS = ("upper_right", "upper_left", "center_card", "full_cutaway")

PLACEMENT_LAYOUT: dict[str, dict[str, Any]] = {
    "upper_right": {"pos": [760, 560], "scale": 38.0, "anim": "float"},
    "upper_left": {"pos": [320, 560], "scale": 38.0, "anim": "float"},
    "center_card": {"pos": [540, 820], "scale": 46.0, "anim": "spin3d"},
    "full_cutaway": {"pos": [540, 880], "scale": 68.0, "anim": "slide"},
}

BACKDROP_SPECS: dict[str, tuple[str, str]] = {
    "green": ("#00FF00", "uniform solid flat chroma green #00FF00 seamless cyclorama backdrop"),
    "white": ("#FFFFFF", "uniform solid pure white #FFFFFF seamless cyclorama backdrop"),
    "charcoal": ("#0A0E17", "uniform solid deep charcoal #0A0E17 seamless cyclorama backdrop"),
}

NUMBER_RE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?%?\b|\b(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|nghìn|triệu|tỷ|"
    r"phần trăm|phút|giờ|ngày|tháng|năm|hạng\s*[sabc]|tier)\b)",
    re.I,
)
TOOL_AI_CUES = (
    "ai", "agent", "tự động", "automation", "phần mềm", "hệ thống", "quy trình",
    "dữ liệu", "công cụ", "lập trình", "pipeline", "nội dung", "video",
    "doanh thu", "lợi nhuận", "chi phí", "khách hàng", "đơn hàng", "bán hàng",
)
METAPHOR_CUES = (
    "bảng xếp hạng", "bộ não", "nút thắt", "bước ngoặt", "mũi nhọn",
    "đẻ ra tiền", "làm màu", "văn mẫu", "bỏ tiền túi", "thuê ngoài",
    "tự bơi", "đốt tiền", "rò rỉ", "đòn bẩy", "cỗ máy", "hào nhoáng",
)

# Bảng ánh xạ từ khoá kịch bản -> vật thể 3D vật lý sạch (không chữ/số/UI/logo, không Anti-Slop)
CONCEPT_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("bảng xếp hạng", "tier", "hạng s", "hạng a", "hạng b", "hạng c", "xếp hạng"),
        "a stepped three-tier matte clay and brushed anodized aluminum podium with a frosted-glass crystal prism on the top step",
        "the frosted-glass crystal prism levitates gently above the top step while the podium tiers align smoothly",
    ),
    (
        ("bộ não", "second brain", "dữ liệu", "thông tin", "kiến thức"),
        "a translucent frosted-glass geometric brain sculpture cradling interlocking brushed anodized aluminum spherical nodes",
        "soft warm light pulses travel smoothly along the frosted-glass sculpture",
    ),
    (
        ("bỏ tiền túi", "đốt tiền", "chi phí", "thuê ngoài", "lãng phí", "rò rỉ", "mất tiền"),
        "a matte-terracotta ceramic coin jar with brushed-brass metallic discs spilling gently beside a frosted-glass balance beam",
        "the frosted-glass balance beam tilts gently as two brushed-brass discs settle softly",
    ),
    (
        ("doanh thu", "lợi nhuận", "đẻ ra tiền", "triệu", "tỷ", "tiền", "chốt đơn", "bán hàng"),
        "an ascending row of frosted-glass and brushed-brass prism bars beside stacked unbranded metallic tokens",
        "the frosted-glass prism bars glide smoothly upward in sequence",
    ),
    (
        ("video", "dựng", "edit", "nội dung", "viết bài", "văn mẫu"),
        "a tactile matte-clay cinema clapperboard paired with floating translucent frosted-glass layer blocks",
        "the translucent frosted-glass blocks glide into crisp layered alignment",
    ),
    (
        ("ai", "agent", "tự động", "phần mềm", "hệ thống", "quy trình", "lập trình", "công cụ"),
        "a modular matte-clay and brushed-aluminum cube assembly with interlocking precision ceramic cogwheels",
        "the interlocking ceramic cogwheels rotate steadily in unison",
    ),
    (
        ("phút", "giờ", "ngày", "tháng", "năm", "thời gian", "chậm", "quá tải"),
        "a minimalist brushed-aluminum hourglass with golden sand grains suspended inside clear blown glass",
        "golden sand grains drift slowly through the glass hourglass neck",
    ),
    (
        ("nút thắt", "bước ngoặt", "mũi nhọn", "gỡ"),
        "a smooth matte-charcoal sphere gliding cleanly through a flared brushed-brass funnel ring",
        "the matte-charcoal sphere passes smoothly through the center of the brass ring",
    ),
    (
        ("khách hàng", "đơn hàng", "doanh nghiệp", "công ty", "cửa hàng"),
        "a stylized isometric matte-clay architectural storefront cube with floating frosted-glass parcel blocks",
        "the floating frosted-glass parcel blocks orbit gently around the architectural cube",
    ),
]
FALLBACK_CONCEPT = (
    "a minimalist tactile 3D isometric geometric totem combining matte ceramic spheres, brushed anodized aluminum rings, and a soft frosted-glass core",
    "the frosted-glass core levitates gently inside the brushed-aluminum rings",
)


def _norm_lower(text: str) -> str:
    return _norm(text)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _extract_clauses(text: str) -> list[str]:
    """Tách đoạn lời thành các câu / mệnh đề gọn để chọn anchor_quote sát nhất."""
    raw = re.split(r"[.?!…;]+", text or "")
    clauses: list[str] = []
    for part in raw:
        part = " ".join(part.split()).strip(" ,:-")
        if not part:
            continue
        if len(part.split()) > 16 and "," in part:
            subparts = [s.strip(" ,:-") for s in part.split(",") if s.strip(" ,:-")]
            clauses.extend(subparts)
        else:
            clauses.append(part)
    return clauses or ([" ".join((text or "").split())] if (text or "").strip() else [])


def _score_phrase(text: str, extra_pain: list[str] | None = None) -> tuple[float, list[str]]:
    """Chấm điểm mức độ đắt giá thị giác của một câu / mệnh đề."""
    norm = _norm_lower(text)
    if not norm:
        return 0.0, []
    score = 0.0
    reasons: list[str] = []

    pains = find_pain_in_text(text, extra=extra_pain or None)
    if pains:
        score += 32.0 + 10.0 * (len(pains) - 1)
        reasons.append(f"nỗi đau ({', '.join(pains[:2])})")

    nums = NUMBER_RE.findall(text)
    if nums:
        score += 22.0 + 4.0 * min(len(nums) - 1, 2)
        reasons.append(f"số liệu/mốc ({', '.join(dict.fromkeys(nums[:2]))})")

    ai_hits = [c for c in TOOL_AI_CUES if re.search(rf"(?<!\w){re.escape(c)}(?!\w)", norm)]
    if ai_hits:
        score += 18.0 + 3.0 * min(len(ai_hits) - 1, 2)
        reasons.append(f"khái niệm AI/hệ thống ({', '.join(ai_hits[:2])})")

    meta_hits = [c for c in METAPHOR_CUES if c in norm]
    if meta_hits:
        score += 18.0 + 4.0 * min(len(meta_hits) - 1, 2)
        reasons.append(f"ẩn dụ lõi ({', '.join(meta_hits[:2])})")

    if len(text.split()) >= 5:
        score += 4.0
    return round(score, 2), reasons


def _pick_anchor_quote(seg_text: str, extra_pain: list[str] | None = None) -> tuple[str, float, list[str]]:
    """Chọn cụm nguyên văn đắt giá nhất nằm trong seg_text."""
    clauses = _extract_clauses(seg_text)
    if not clauses:
        return "", 0.0, []
    best_clause = clauses[0]
    best_score, best_reasons = _score_phrase(best_clause, extra_pain)
    for cl in clauses[1:]:
        sc, rs = _score_phrase(cl, extra_pain)
        if sc > best_score:
            best_clause, best_score, best_reasons = cl, sc, rs
    if _norm_lower(best_clause) not in _norm_lower(seg_text):
        best_clause = " ".join(seg_text.split())
    return best_clause, best_score, best_reasons


def _concept_for_text(phrase: str, full_seg_text: str, used: set[str] | None = None) -> tuple[str, str]:
    """Ánh xạ ý câu thoại sang vật thể 3D vật lý + chuyển động gợi ý (ưu tiên đa dạng vật thể trong 1 video)."""
    hay = _norm_lower(f"{phrase} {full_seg_text}")
    matches = [(obj_desc, motion_desc) for keys, obj_desc, motion_desc in CONCEPT_RULES if any(k in hay for k in keys)]
    if matches:
        if used:
            for obj_desc, motion_desc in matches:
                if obj_desc not in used:
                    return obj_desc, motion_desc
        return matches[0]
    return FALLBACK_CONCEPT


def build_3d_prompt(
    concept_object: str,
    mode: str = "image_alpha",
    backdrop: str = "green",
    motion_hint: str | None = None,
) -> str:
    """Sinh prompt asset 3D theo SPEC-MASTER-VIDEO-PROMPT-ARCH-V1 (0 Anti-Slop, 0 CLIP weights, affirmative clean-frame)."""
    obj_clean = re.sub(r"^(?:a|an)\s+", "", concept_object.strip(), flags=re.I)
    if mode == "image_alpha":
        _, backdrop_desc = BACKDROP_SPECS.get(backdrop, BACKDROP_SPECS["green"])
        return (
            f"Studio macro product photograph of a stylized tactile 3D isometric {obj_clean}. "
            f"LIGHTING & OPTICS: studio three-point rim light, soft diffused top key light, 50mm macro f/4, crisp edge separation. "
            f"BACKDROP: centered with generous margin on a {backdrop_desc}. "
            f"Clean isolated object, unbranded, blank surfaces, centered with full margin."
        )
    if mode == "video_3d":
        action = motion_hint or FALLBACK_CONCEPT[1]
        return (
            f"Slow 3D turntable orbit around a tactile 3D macro diorama of {concept_object}. "
            f"SUBJECT ACTION: {action}. "
            f"LIGHTING & OPTICS: studio three-point rim light, 50mm macro f/4, deep charcoal #0A0E17 seamless studio cyclorama. "
            f"Smooth 24fps motion, consistent geometry, clean isolated frame, unbranded, blank surfaces."
        )
    raise ValueError(f"Mode không hợp lệ: {mode}")


def _timeline_map_from_speed_plan(speed_plan: dict[str, Any]) -> tuple[float, dict[str, tuple[float, float]]]:
    """Tính mốc (at, dur) chính xác trên timeline từ speed_plan.json."""
    speed = float(speed_plan.get("speed") or 1.0)
    fps = 30
    t_acc = 0.0
    mapping: dict[str, tuple[float, float]] = {}
    for sc in speed_plan.get("scenes", []):
        segs = at_speed(sc.get("segs") or [], speed, fps)
        sc_start = t_acc
        sc_dur = 0.0
        for a, b in segs:
            d = round(round((b - a) * fps) / fps, 3)
            sc_dur = round(sc_dur + d, 3)
            t_acc = round(t_acc + d, 3)
        if sc_dur <= 0 and sc.get("src_dur"):
            sc_dur = round(float(sc["src_dur"]) / speed, 3)
            t_acc = round(t_acc + sc_dur, 3)
        mapping[str(sc.get("seq_prefix", ""))] = (round(sc_start, 3), round(max(0.4, sc_dur), 3))
    return speed, mapping


def _load_source_entries(
    manifest_path: Path | None,
    plan_path: Path | None,
    speed: float,
    speed_plan: dict[str, Any] | None,
) -> tuple[str, str, str, float, list[dict[str, Any]]]:
    """Chuẩn hoá segment từ manifest hoặc broll_plan thành danh sách đồng nhất."""
    tl_map: dict[str, tuple[float, float]] = {}
    if speed_plan:
        speed, tl_map = _timeline_map_from_speed_plan(speed_plan)

    entries: list[dict[str, Any]] = []
    if manifest_path:
        data = _load_json(manifest_path)
        script_id = str(data.get("script_id") or manifest_path.parent.name)
        t_acc = 0.0
        segs = sorted(data.get("segments", []), key=lambda s: int(s.get("seq_index", 0)))
        for seg in segs:
            seq = int(seg.get("seq_index") or len(entries) + 1)
            prefix = str(seg.get("seq_prefix") or f"{seq:02d}")
            raw_dur = float(seg.get("duration_sec") or 3.0)
            if prefix in tl_map:
                seg_at, seg_dur = tl_map[prefix]
            else:
                seg_at = round(t_acc, 3)
                seg_dur = round(max(0.5, raw_dur / speed), 3)
                t_acc = round(t_acc + seg_dur, 3)
            tts = str(seg.get("tts_text") or seg.get("display_text") or "").strip()
            extra_pain = [*(seg.get("pain_keywords") or []), *(seg.get("keywords") or [])]
            entries.append({
                "seq": seq,
                "seq_prefix": prefix,
                "role": str(seg.get("role_id") or seg.get("type") or "segment"),
                "is_broll": str(seg.get("type") or "").lower() == "b-roll",
                "at": seg_at,
                "dur": seg_dur,
                "text": tts,
                "display_text": str(seg.get("display_text") or tts).strip(),
                "extra_pain": extra_pain,
            })
        return "manifest", str(manifest_path.resolve()), script_id, speed, entries
    assert plan_path is not None
    data = _load_json(plan_path)
    script_id = plan_path.parent.name
    for slot in data.get("slots", []):
        seq = int(slot.get("slot_id") or len(entries) + 1)
        prefix = str(slot.get("seq_prefix") or f"{seq:02d}")
        if prefix in tl_map:
            seg_at, seg_dur = tl_map[prefix]
        else:
            s0 = float(slot.get("start") or 0.0)
            s1 = float(slot.get("end") or (s0 + float(slot.get("voice_len") or 3.0)))
            seg_at = round(s0 / speed, 3)
            seg_dur = round(max(0.5, (s1 - s0) / speed), 3)
        text = str(slot.get("anchor_quote") or "").strip()
        entries.append({
            "seq": seq,
            "seq_prefix": prefix,
            "role": str(slot.get("role_id") or slot.get("role") or "slot"),
            "is_broll": str(slot.get("role") or "").upper() == "B-ROLL",
            "at": seg_at,
            "dur": seg_dur,
            "text": text,
            "display_text": text,
            "extra_pain": list(slot.get("pain_keywords") or []),
        })
    return "broll_plan", str(plan_path.resolve()), script_id, speed, entries


def _choose_placement(is_broll: bool, asset_mode: str, aroll_idx: int, broll_idx: int) -> str:
    if asset_mode == "video_3d":
        return "full_cutaway" if is_broll else "center_card"
    if is_broll:
        return ("center_card", "upper_right", "upper_left")[broll_idx % 3]
    return "upper_right" if aroll_idx % 2 == 0 else "upper_left"


def build_assets_plan(
    manifest_path: Path | None = None,
    plan_path: Path | None = None,
    speed_plan_path: Path | None = None,
    speed: float = 1.10,
    max_assets: int = 6,
    mode: str = "image_alpha",
    backdrop: str = "green",
) -> dict[str, Any]:
    """Chọn các câu đắt giá nhất trong kịch bản / broll_plan và sinh kế hoạch 3D asset chuẩn Flow."""
    if mode not in VALID_MODES:
        raise ValueError(f"mode không hợp lệ: {mode}")
    if backdrop not in BACKDROP_SPECS:
        raise ValueError(f"backdrop không hợp lệ: {backdrop}")
    if max_assets < 1:
        raise ValueError("max_assets phải >= 1")

    sp = _load_json(speed_plan_path) if speed_plan_path else None
    src_type, src_path, script_id, eff_speed, entries = _load_source_entries(manifest_path, plan_path, speed, sp)
    if not entries:
        raise ValueError("Nguồn đầu vào không có segment/slot nào.")

    scored: list[dict[str, Any]] = []
    for idx, e in enumerate(entries):
        if not e["text"]:
            continue
        anchor, sc, reasons = _pick_anchor_quote(e["text"], e["extra_pain"])
        full_sc, full_rs = _score_phrase(e["text"], e["extra_pain"])
        total_sc = round(max(sc, full_sc * 0.9) + (3.0 if e["is_broll"] else 0.0) + (2.0 if e["dur"] >= 2.5 else 0.0), 2)
        if idx == 0 and total_sc < 30.0:
            total_sc -= 5.0
        combined_reasons = reasons or full_rs or ["minh hoạ ý chính đoạn thoại"]
        scored.append({**e, "idx": idx, "anchor_quote": anchor, "score": total_sc, "reasons": combined_reasons})

    ranked = sorted(scored, key=lambda x: (-x["score"], x["at"]))[:max_assets]
    selected = sorted(ranked, key=lambda x: x["at"])

    backdrop_hex, _ = BACKDROP_SPECS[backdrop]
    aroll_n = broll_n = 0
    used_concepts: set[str] = set()
    assets: list[dict[str, Any]] = []
    for i, item in enumerate(selected, start=1):
        if mode == "mixed":
            asset_mode = "video_3d" if (item["is_broll"] and (i == 1 or i % 3 == 0)) else "image_alpha"
        else:
            asset_mode = mode

        placement = _choose_placement(item["is_broll"], asset_mode, aroll_n, broll_n)
        if item["is_broll"]:
            broll_n += 1
        else:
            aroll_n += 1
        layout = PLACEMENT_LAYOUT[placement]

        seg_at, seg_dur = item["at"], item["dur"]
        offset = round(min(0.15, seg_dur * 0.08), 3)
        at = round(seg_at + offset, 3)
        avail = max(0.4, seg_dur - offset - 0.04)
        dur = round(min(max(1.2, avail * 0.9) if avail >= 1.2 else avail, 3.2), 3)

        concept_obj, motion_hint = _concept_for_text(item["anchor_quote"], item["text"], used=used_concepts)
        used_concepts.add(concept_obj)
        prompt = build_3d_prompt(concept_obj, mode=asset_mode, backdrop=backdrop, motion_hint=motion_hint)
        aid = f"3d_{i:02d}"
        entry: dict[str, Any] = {
            "asset_id": aid,
            "seq": item["seq"],
            "seq_prefix": item["seq_prefix"],
            "role": item["role"],
            "mode": asset_mode,
            "model": "nano-banana-pro" if asset_mode == "image_alpha" else "omni-flash",
            "aspect_ratio": "1:1" if asset_mode == "image_alpha" else "9:16",
            "at": at,
            "dur": dur,
            "anchor_quote": item["anchor_quote"],
            "segment_text": item["text"],
            "concept_object": concept_obj,
            "placement": placement,
            "pos": list(layout["pos"]),
            "scale": layout["scale"],
            "anim": layout["anim"],
            "cue": "pop",
            "backdrop": backdrop_hex if asset_mode == "image_alpha" else "#0A0E17",
            "prompt": prompt,
            "raw_file": f"{aid}_raw.png" if asset_mode == "image_alpha" else f"{aid}_raw.mp4",
            "alpha_file": f"{aid}_alpha.png" if asset_mode == "image_alpha" else f"{aid}_3d.mp4",
            "score": item["score"],
            "reasons": item["reasons"],
        }
        assets.append(entry)

    full_script = " ".join(e["text"] for e in entries if e["text"])
    return {
        "version": "1.0",
        "source_type": src_type,
        "source_path": src_path,
        "script_id": script_id,
        "speed": eff_speed,
        "mode": mode,
        "backdrop": backdrop_hex,
        "full_script_text": full_script,
        "assets": assets,
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# Kế hoạch 3D Assets Google Flow — {plan.get('script_id', '')}",
        "",
        f"- **Nguồn:** `{plan.get('source_type')}` (`{plan.get('source_path')}`)",
        f"- **Tốc độ timeline:** `{plan.get('speed')}x` · **Chế độ:** `{plan.get('mode')}` · **Nền tách alpha:** `{plan.get('backdrop')}`",
        f"- **Số asset đề xuất:** **{len(plan.get('assets', []))}**",
        "",
        "| ID | Seq | Timeline (`at` + `dur`) | Mode | Model | Placement | anchor_quote | Lý do |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for a in plan.get("assets", []):
        q = str(a["anchor_quote"]).replace("|", "\\|")
        rs = ", ".join(a.get("reasons") or []).replace("|", "\\|")
        lines.append(
            f"| `{a['asset_id']}` | `{a['seq_prefix']}` | `{a['at']:.2f}s` (`{a['dur']:.2f}s`) | "
            f"`{a['mode']}` | `{a['model']}` | `{a['placement']}` | {q} | {rs} |"
        )
    lines.extend(["", "## Prompt chuẩn kiến trúc 8 tầng (Google Flow MCP)", ""])
    for a in plan.get("assets", []):
        lines.extend([
            f"### {a['asset_id']} (`seq {a['seq_prefix']}` · `{a['at']:.2f}s` · `{a['placement']}`)",
            f"- **anchor_quote:** \"{a['anchor_quote']}\"",
            f"- **concept_object:** {a['concept_object']}",
            f"- **model:** `{a['model']}` · **aspectRatio:** `{a['aspect_ratio']}`",
            f"- **prompt:** `{a['prompt']}`",
            "",
        ])
    return "\n".join(lines) + "\n"


def lint_plan(plan: dict[str, Any], script_override: str | None = None) -> list[str]:
    """Kiểm định 3d_assets_plan.json: kiến trúc prompt (0 Anti-Slop, 0 CLIP), anchor_quote trong kịch bản, mode & placement."""
    errors: list[str] = []
    assets = plan.get("assets")
    if not isinstance(assets, list) or not assets:
        return ["Plan thiếu danh sách assets hợp lệ."]

    script_parts = [str(plan.get("full_script_text") or "")]
    if script_override:
        script_parts.append(script_override)
    src_path = plan.get("source_path")
    if src_path and Path(src_path).is_file():
        try:
            src_data = _load_json(Path(src_path))
            for s in src_data.get("segments", []):
                script_parts.append(str(s.get("tts_text") or ""))
                script_parts.append(str(s.get("display_text") or ""))
            for s in src_data.get("slots", []):
                script_parts.append(str(s.get("anchor_quote") or ""))
        except (OSError, ValueError, KeyError):
            pass
    norm_script = _norm_lower(" ".join(script_parts))

    for idx, a in enumerate(assets):
        aid = str(a.get("asset_id") or f"#{idx + 1}")
        mode = a.get("mode")
        if mode not in VALID_ASSET_MODES:
            errors.append(f"{aid}: mode '{mode}' không hợp lệ (cần image_alpha | video_3d)")
            continue
        placement = a.get("placement")
        if placement not in VALID_PLACEMENTS:
            errors.append(f"{aid}: placement '{placement}' không hợp lệ (cần {VALID_PLACEMENTS})")

        at = a.get("at")
        dur = a.get("dur")
        if not isinstance(at, (int, float)) or at < 0:
            errors.append(f"{aid}: at không hợp lệ ({at})")
        if not isinstance(dur, (int, float)) or dur <= 0:
            errors.append(f"{aid}: dur phải > 0 ({dur})")

        anchor = str(a.get("anchor_quote") or "").strip()
        if not anchor:
            errors.append(f"{aid}: thiếu anchor_quote")
        elif _norm_lower(anchor) not in norm_script:
            errors.append(f"{aid}: anchor_quote không nằm trong kịch bản ({anchor!r})")

        prompt = str(a.get("prompt") or "").strip()
        if not prompt:
            errors.append(f"{aid}: prompt rỗng")
            continue
        if has_diacritics(prompt):
            errors.append(f"{aid}: prompt chứa dấu tiếng Việt")

        arch_mode = "t2i" if mode == "image_alpha" else "t2v"
        arch = audit_prompt_architecture(prompt, mode=arch_mode)
        for w in arch["warnings"]:
            errors.append(f"{aid}: {w}")
        if mode == "image_alpha" and NEGATIVE_TAIL_RE.search(prompt):
            errors.append(f"{aid}: tránh cụm phủ định 'no text/logos/subtitles'; dùng ràng buộc khẳng định")

    return errors


def _detect_bg_mode(rgb: Any) -> str:
    import numpy as np

    h, w = rgb.shape[:2]
    b = max(1, min(4, h // 10, w // 10))
    border = np.concatenate([
        rgb[:b, :, :].reshape(-1, 3),
        rgb[-b:, :, :].reshape(-1, 3),
        rgb[:, :b, :].reshape(-1, 3),
        rgb[:, -b:, :].reshape(-1, 3),
    ], axis=0)
    med = np.median(border, axis=0)
    r, g, bl = float(med[0]), float(med[1]), float(med[2])
    if g > r + 35 and g > bl + 35 and g >= 85:
        return "green"
    if min(r, g, bl) >= 205:
        return "white"
    if max(r, g, bl) <= 50:
        return "black"
    return "chroma"


def extract_alpha(
    input_path: Path,
    output_path: Path,
    bg: str = "auto",
    pad: int = 16,
    max_size: int = 720,
    feather: float = 1.2,
    crop: bool = True,
) -> dict[str, Any]:
    """Tách nền ảnh 3D thành RGBA PNG sạch metadata (edge flood-fill + green despill + anti-aliased edge)."""
    import cv2
    import numpy as np
    from PIL import Image

    with Image.open(input_path) as im:
        rgba = np.array(im.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[..., :3]
    h, w = rgb.shape[:2]

    mode = _detect_bg_mode(rgb) if bg == "auto" else bg
    if mode not in ("green", "white", "black", "chroma"):
        raise ValueError(f"bg không hợp lệ: {bg}")

    rgb_f = rgb.astype(np.float32)
    b = max(1, min(4, h // 10, w // 10))
    border = np.concatenate([
        rgb_f[:b, :, :].reshape(-1, 3),
        rgb_f[-b:, :, :].reshape(-1, 3),
        rgb_f[:, :b, :].reshape(-1, 3),
        rgb_f[:, -b:, :].reshape(-1, 3),
    ], axis=0)
    bg_color = np.median(border, axis=0)
    dist = np.linalg.norm(rgb_f - bg_color, axis=-1)

    r_ch, g_ch, b_ch = rgb_f[..., 0], rgb_f[..., 1], rgb_f[..., 2]
    max_c = np.maximum(np.maximum(r_ch, g_ch), b_ch)
    min_c = np.minimum(np.minimum(r_ch, g_ch), b_ch)
    sat = max_c - min_c

    if mode == "green":
        g_excess = g_ch - np.maximum(r_ch, b_ch)
        bg_cand = (g_excess > 24.0) & (g_ch > 65.0)
        bg_cand = bg_cand | ((dist < 52.0) & (g_ch >= np.maximum(r_ch, b_ch)))
    elif mode == "white":
        bg_cand = (dist < 44.0) & (sat < 36.0) & (min_c > 190.0)
    elif mode == "black":
        bg_cand = (dist < 44.0) & (max_c < 60.0)
    else:
        bg_cand = dist < 42.0

    num_labels, labels = cv2.connectedComponents(bg_cand.astype(np.uint8), connectivity=4)
    border_labels = np.unique(np.concatenate([
        labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1],
    ]))
    border_labels = border_labels[border_labels > 0]
    bg_connected = np.isin(labels, border_labels)

    fg_hard = ~bg_connected
    k3 = np.ones((3, 3), np.uint8)
    fg_eroded = cv2.erode(fg_hard.astype(np.uint8), k3, iterations=1) > 0
    bg_eroded = cv2.erode(bg_connected.astype(np.uint8), k3, iterations=1) > 0

    alpha_f = fg_hard.astype(np.float32)
    edge_band = (~fg_eroded) & (~bg_eroded)
    if mode == "green":
        soft_fg = np.clip(1.0 - (g_ch - np.maximum(r_ch, b_ch)) / 140.0, 0.0, 1.0)
        alpha_f[edge_band] = np.minimum(alpha_f[edge_band], soft_fg[edge_band])
    else:
        soft_fg = np.clip((dist - 14.0) / 40.0, 0.0, 1.0)
        alpha_f[edge_band] = np.where(fg_hard[edge_band], np.maximum(soft_fg[edge_band], 0.5), soft_fg[edge_band])

    if feather > 0:
        alpha_blur = cv2.GaussianBlur(alpha_f, (0, 0), sigmaX=feather, sigmaY=feather)
        alpha_f = np.where(fg_eroded, 1.0, np.where(bg_eroded, 0.0, alpha_blur))

    alpha = np.clip(np.round(alpha_f * 255.0), 0, 255).astype(np.uint8)

    out_rgb = rgb.copy()
    if mode == "green":
        edge_halo = (cv2.dilate(bg_connected.astype(np.uint8), k3, iterations=3) > 0) | (alpha < 252)
        rb_max = np.maximum(out_rgb[..., 0], out_rgb[..., 2])
        spill_mask = edge_halo & (out_rgb[..., 1] > rb_max)
        out_rgb[..., 1] = np.where(spill_mask, rb_max, out_rgb[..., 1])
        out_rgb[alpha == 0] = 0

    out_rgba = np.dstack([out_rgb, alpha])

    if crop:
        ys, xs = np.where(alpha > 8)
        if len(ys) > 0 and len(xs) > 0:
            p = max(0, int(pad))
            y0 = max(0, int(ys.min()) - p)
            y1 = min(h, int(ys.max()) + 1 + p)
            x0 = max(0, int(xs.min()) - p)
            x1 = min(w, int(xs.max()) + 1 + p)
            out_rgba = out_rgba[y0:y1, x0:x1]

    out_im = Image.fromarray(out_rgba, mode="RGBA")
    if max_size > 0 and max(out_im.size) > max_size:
        scale_ratio = max_size / max(out_im.size)
        new_size = (max(1, round(out_im.width * scale_ratio)), max(1, round(out_im.height * scale_ratio)))
        out_im = out_im.resize(new_size, Image.Resampling.LANCZOS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_im = Image.new("RGBA", out_im.size)
    clean_im.paste(out_im)
    clean_im.save(output_path, format="PNG", pnginfo=None, optimize=True)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "bg_detected": mode,
        "size": list(clean_im.size),
    }


def _make_checkerboard(w: int, h: int, cell: int = 16) -> Any:
    from PIL import Image, ImageDraw

    bg = Image.new("RGBA", (w, h), (188, 192, 200, 255))
    d = ImageDraw.Draw(bg)
    dark = (148, 152, 162, 255)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2 == 1:
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=dark)
    return bg


def render_sheet(
    out_path: Path,
    plan: dict[str, Any] | None = None,
    images: list[Path] | None = None,
    assets_dir: Path | None = None,
    cols: int = 3,
) -> Path:
    """Vẽ ảnh kiểm tra QA nền caro (checkerboard) cho toàn bộ 3D RGBA assets."""
    from PIL import Image, ImageDraw, ImageFont

    items: list[dict[str, str]] = []
    if plan is not None:
        base_dir = assets_dir or Path(".")
        for a in plan.get("assets", []):
            cand_alpha = base_dir / str(a.get("alpha_file") or "")
            cand_raw = base_dir / str(a.get("raw_file") or "")
            img_p = cand_alpha if cand_alpha.is_file() else (cand_raw if cand_raw.is_file() else None)
            items.append({
                "path": str(img_p) if img_p else "",
                "title": f"{a['asset_id']} · seq {a['seq_prefix']} @ {a['at']:.2f}s ({a['placement']})",
                "quote": str(a.get("anchor_quote") or ""),
            })
    elif images:
        for idx, p in enumerate(images, start=1):
            items.append({
                "path": str(p),
                "title": f"#{idx:02d} · {p.name}",
                "quote": "",
            })
    else:
        raise ValueError("Cần truyền plan hoặc danh sách --images")

    if not items:
        raise ValueError("Không có asset nào để vẽ contact sheet.")

    cols = max(1, min(cols, len(items)))
    rows = (len(items) + cols - 1) // cols
    cell_w, cell_h, label_h, head_h, pad = 340, 340, 68, 52, 16
    total_w = cols * cell_w + (cols + 1) * pad
    total_h = head_h + rows * (cell_h + label_h) + (rows + 1) * pad

    canvas = Image.new("RGB", (total_w, total_h), (20, 22, 28))
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if Path(font_path).is_file():
        font_big = ImageFont.truetype(font_path, 22)
        font_sm = ImageFont.truetype(font_path, 14)
    else:
        font_big = ImageFont.load_default()
        font_sm = ImageFont.load_default()

    header = f"3D Assets QA Sheet ({len(items)} items)"
    if plan and plan.get("script_id"):
        header = f"3D Assets QA · {plan['script_id']} ({len(items)} items)"
    draw.text((pad, 14), header, font=font_big, fill=(255, 255, 255))

    for idx, it in enumerate(items):
        r, c = divmod(idx, cols)
        x0 = pad + c * (cell_w + pad)
        y0 = head_h + pad + r * (cell_h + label_h + pad)
        checker = _make_checkerboard(cell_w, cell_h, cell=18)
        p = Path(it["path"]) if it["path"] else None
        if p and p.is_file():
            try:
                with Image.open(p) as im:
                    fg = im.convert("RGBA")
                fg.thumbnail((cell_w - 24, cell_h - 24), Image.Resampling.LANCZOS)
                ox = (cell_w - fg.width) // 2
                oy = (cell_h - fg.height) // 2
                layer = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
                layer.paste(fg, (ox, oy))
                checker = Image.alpha_composite(checker, layer)
            except OSError:
                pass
        canvas.paste(checker.convert("RGB"), (x0, y0))
        if not p or not p.is_file():
            draw.text((x0 + 20, y0 + cell_h // 2 - 10), "Chưa có file ảnh", font=font_sm, fill=(220, 40, 40))

        draw.text((x0 + 4, y0 + cell_h + 8), it["title"][:44], font=font_sm, fill=(255, 210, 65))
        if it["quote"]:
            q = it["quote"]
            draw.text((x0 + 4, y0 + cell_h + 30), (q[:42] + "…") if len(q) > 42 else q, font=font_sm, fill=(220, 225, 235))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="JPEG", quality=90)
    return out_path


# ---------------------------------------------------------------- CLI
def cmd_plan(args: argparse.Namespace) -> int:
    manifest_p = Path(args.manifest) if args.manifest else None
    plan_p = Path(args.plan) if args.plan else None
    speed_plan_p = Path(args.speed_plan) if args.speed_plan else None
    src_ref = manifest_p or plan_p
    assert src_ref is not None
    if not src_ref.is_file():
        print(f"[3D PLAN FAIL] Không thấy file: {src_ref}", file=sys.stderr)
        return 2
    if speed_plan_p and not speed_plan_p.is_file():
        print(f"[3D PLAN FAIL] Không thấy speed_plan: {speed_plan_p}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else (src_ref.parent / "3d_assets")
    plan = build_assets_plan(
        manifest_path=manifest_p,
        plan_path=plan_p,
        speed_plan_path=speed_plan_p,
        speed=args.speed,
        max_assets=args.max_assets,
        mode=args.mode,
        backdrop=args.backdrop,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "3d_assets_plan.json"
    md_out = out_dir / "3d_assets_plan.md"
    _save_json(json_out, plan)
    md_out.write_text(render_plan_markdown(plan), encoding="utf-8")
    print(f"[3D PLAN OK] {len(plan['assets'])} assets ({plan['mode']}, {plan['speed']}x) -> {json_out}")
    return 0


def cmd_lint_plan(args: argparse.Namespace) -> int:
    target = args.plan_opt or args.plan_pos
    if not target:
        print("[3D LINT FAIL] Cần truyền đường dẫn 3d_assets_plan.json", file=sys.stderr)
        return 2
    p = Path(target)
    if not p.is_file():
        print(f"[3D LINT FAIL] Không thấy file: {p}", file=sys.stderr)
        return 2
    try:
        plan = _load_json(p)
    except (OSError, ValueError) as exc:
        print(f"[3D LINT FAIL] Lỗi đọc JSON: {exc}", file=sys.stderr)
        return 2

    errs = lint_plan(plan)
    if errs:
        for e in errs:
            print(f"[3D LINT FAIL] {e}")
        return 1
    print(f"[3D LINT OK] {len(plan.get('assets', []))} assets đạt chuẩn prompt & anchor_quote.")
    return 0


def cmd_extract_alpha(args: argparse.Namespace) -> int:
    inp = Path(args.input)
    out = Path(args.out_opt or args.output)
    if not inp.is_file():
        print(f"[ALPHA FAIL] Không thấy file đầu vào: {inp}", file=sys.stderr)
        return 2
    info = extract_alpha(
        inp,
        out,
        bg=args.bg,
        pad=args.pad,
        max_size=args.max_size,
        feather=args.feather,
        crop=not args.no_crop,
    )
    print(f"[ALPHA OK] {info['output']} (bg={info['bg_detected']}, size={info['size'][0]}x{info['size'][1]})")
    return 0


def cmd_sheet(args: argparse.Namespace) -> int:
    plan_target = args.plan_opt or args.plan_pos
    plan_data = None
    assets_dir = Path(args.assets_dir) if args.assets_dir else None
    if plan_target:
        p = Path(plan_target)
        if not p.is_file():
            print(f"[SHEET FAIL] Không thấy file plan: {p}", file=sys.stderr)
            return 2
        plan_data = _load_json(p)
        if assets_dir is None:
            assets_dir = p.parent
        out_path = Path(args.out) if args.out else (p.parent / "3d_assets_sheet.jpg")
    else:
        out_path = Path(args.out or "3d_assets_sheet.jpg")

    imgs = [Path(x) for x in (args.images or [])]
    if not plan_data and not imgs:
        print("[SHEET FAIL] Cần truyền 3d_assets_plan.json hoặc --images ...", file=sys.stderr)
        return 2
    written = render_sheet(out_path, plan=plan_data, images=imgs or None, assets_dir=assets_dir, cols=args.cols)
    print(f"[SHEET OK] {written}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Lập kế hoạch, kiểm định, tách nền RGBA & ghép sheet QA cho 3D assets qua Google Flow.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Phân tích manifest/broll_plan -> 3d_assets_plan.json & 3d_assets_plan.md")
    src = p_plan.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", help="Đường dẫn 00_storyboard_manifest.json")
    src.add_argument("--plan", help="Đường dẫn broll_plan.json")
    p_plan.add_argument("--speed-plan", help="Đường dẫn speed_plan.json (tuỳ chọn, cho mốc at/dur chính xác)")
    p_plan.add_argument("--speed", type=float, default=1.10, help="Tốc độ tăng tốc mặc định nếu không có --speed-plan (mặc định 1.10)")
    p_plan.add_argument("--max-assets", type=int, default=6, help="Số lượng asset 3D tối đa (mặc định 6)")
    p_plan.add_argument("--mode", choices=VALID_MODES, default="image_alpha", help="image_alpha | video_3d | mixed")
    p_plan.add_argument("--backdrop", choices=tuple(BACKDROP_SPECS), default="green", help="Màu nền tạo ảnh tách alpha (mặc định green #00FF00)")
    p_plan.add_argument("--out-dir", help="Thư mục lưu 3d_assets_plan.json và 3d_assets_plan.md")
    p_plan.set_defaults(fn=cmd_plan)

    p_lint = sub.add_parser("lint-plan", help="Kiểm tra prompt kiến trúc V1 & anchor_quote của 3d_assets_plan.json")
    p_lint.add_argument("plan_pos", nargs="?", help="Đường dẫn 3d_assets_plan.json")
    p_lint.add_argument("--plan", dest="plan_opt", help="Đường dẫn 3d_assets_plan.json")
    p_lint.set_defaults(fn=cmd_lint_plan)

    p_ext = sub.add_parser("extract-alpha", help="Tách nền ảnh Flow PNG -> RGBA PNG trong suốt, sạch metadata")
    p_ext.add_argument("input", help="Đường dẫn ảnh raw PNG")
    p_ext.add_argument("output", nargs="?", help="Đường dẫn ảnh RGBA PNG đầu ra")
    p_ext.add_argument("--out", "-o", dest="out_opt", help="Đường dẫn ảnh RGBA PNG đầu ra")
    p_ext.add_argument("--bg", choices=("auto", "green", "white", "black"), default="auto", help="Loại nền cần tách")
    p_ext.add_argument("--pad", type=int, default=16, help="Khoảng đệm viền khi crop gọn (px, mặc định 16)")
    p_ext.add_argument("--max-size", type=int, default=720, help="Kích thước cạnh dài tối đa (px, 0 để giữ nguyên)")
    p_ext.add_argument("--feather", type=float, default=1.2, help="Độ làm mịn viền alpha (mặc định 1.2)")
    p_ext.add_argument("--no-crop", action="store_true", help="Không cắt gọn bounding box")
    p_ext.set_defaults(fn=cmd_extract_alpha)

    p_sh = sub.add_parser("sheet", help="Tạo bảng kiểm QA nền caro (3d_assets_sheet.jpg)")
    p_sh.add_argument("plan_pos", nargs="?", help="Đường dẫn 3d_assets_plan.json")
    p_sh.add_argument("--plan", dest="plan_opt", help="Đường dẫn 3d_assets_plan.json")
    p_sh.add_argument("--images", nargs="+", help="Danh sách ảnh RGBA PNG nếu không truyền plan")
    p_sh.add_argument("--assets-dir", help="Thư mục chứa ảnh alpha/raw (mặc định cùng thư mục plan)")
    p_sh.add_argument("--out", "-o", help="Đường dẫn ảnh JPEG đầu ra")
    p_sh.add_argument("--cols", type=int, default=3, help="Số cột trên bảng kiểm (mặc định 3)")
    p_sh.set_defaults(fn=cmd_sheet)

    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    if args.cmd == "extract-alpha" and not (args.out_opt or args.output):
        ap.error("extract-alpha cần truyền đường dẫn output")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
