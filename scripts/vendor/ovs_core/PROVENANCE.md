# PROVENANCE — vendored ovs_core (pro-filmcraft-director v7.9.0, rules.json patched in v7.9.1)

Gate dependencies copied verbatim so PFD has no runtime dependency on the opa-video-studio folder.

- Source: opa-video-studio skill (snapshot) — `rules.json` `version` 3.6.6, `updated` 2026-11-16 (the copy that passed the gates); no local path is needed or recorded.
- Copy date: 2026-11-25
- Override at runtime: env `PFD_OVS_DIR` (must contain `scripts/` and `rules.json`); there is no silent fallback to `~/.gemini` or `~/.claude`.
- Layout mirrors the source tree (`scripts/`, `scripts/apps/craft-handoff/tools/`, `rules.json`) so the relative imports inside the vendored modules keep working.
- Local change (v7.5.0): `scripts/audio_levels.py` only. Optional WARN-only checks (`bgm_no_voice_lu`, `lra_warn_lu`, `short_term_max_lufs`) that exist only when the rules file defines those keys; `LRA` added to `measure()`. Without those keys the verdict list is the original one. The sha256 below is the modified file.
- Local change (v7.6): `scripts/spec_lint.py` (`words_list`: accepts the probe doc `{words | words_tl}` as well as a bare list) and `scripts/edit_rules.py` (same words loader; optional `--profile dviet` / `--lane-b-plates` downgrade C1 + Font 4-6 to WARN with a note, 0 countable fonts is WARN not LỖI). Default behaviour is otherwise unchanged. The sha256 below are the modified files.
- Local change (v7.7.0): `scripts/audit_sfx.py` (`fcproj_sfx_manifest` adds `gain_db` per event), `scripts/apps/talking-head-premiere/scripts/audit_sfx.py` (clipping = peak * 10**(gain_db/20) >= 1.0, adds `peak_linear`, `gain_db`, `peak_dbfs_after_gain`), `scripts/apps/craft-handoff/tools/fc_export.py` (`wait:False` + `jobs.list` polling by job id, `timeout`, job error -> CraftError) and `scripts/apps/craft-handoff/tools/craftctl.py` (`display_alive` probe instead of trusting `/tmp/.X11-unix/Xn`). The sha256 below are the modified files.
- Local change (patched in v7.9.1): `rules.json` only, rule texts (`text`) and `check` fields of A2, A3, B7, B9, B12, B16, C3, D1-D4, D7-D12, D14, D16, E1, F3, F6, G1, G3, G5, H5, P7, P12, X13. They cited upstream scripts that are not vendored (open_in_app, fc_fast_patch, fc_matte_band, retime_voice, motion_fx, matte, cut_plan, broll_fix, render_muse_broll, media_reuse, chroma_studio, studio_plate, frame_person, scene_check, plan_doc, analyze_and_scaffold, voice_level, limit_master, clean_and_master_voice, qa_frames, qa_audio, draw_path, fx_gfx, brooks_text) and were echoed by the gates; each hint now points at this skill's tool (`scripts/tools/filmcraft_cli.py`, `broll_from_video.py`, `probe_and_align.py`, `compile_and_verify.py`, `typography_composer.py`, `web_plate_builder.py`, `presets/broll_lint_contract.json`, vendored `audio_levels.py`) or says "thủ công (manual)". `params`, ids, `source` and `origin` (provenance of each rule) are unchanged. Checked by tests/test_portability_v791.py. The sha256 below is the patched file.
- Not vendored on purpose: `fx_gfx.py` / `motion_fx.py` (lazy imports in `th_transitions.py`, only used when rendering transitions, never by the gates).

| file (relative to scripts/vendor/ovs_core) | sha256 | source (relative to source dir) |
|---|---|---|
| `references/minimal-edu-style.json` | 8b2b849d12ed9ad6efa1c30f78e7e585947ff0dc4957f559b71b0dce32cee6bf | `references/minimal-edu-style.json` |
| `rules.json` | 9fae50adbd61d5c6172e43ff8bc32c45cf467933f7c42b9a2e66fecd81461d00 | `rules.json` (patched in v7.9.1) |
| `scripts/apps/craft-handoff/tools/craftctl.py` | 71c592d5ad7ac2f69be08ad773be003fbc5fd0460bf6599f331435de9de3c256 | `scripts/apps/craft-handoff/tools/craftctl.py` |
| `scripts/apps/craft-handoff/tools/fc_build_fast.py` | a518702e75ae223a707641272f422643536db9c502c7aa293ec3b73de5e0bc23 | `scripts/apps/craft-handoff/tools/fc_build_fast.py` |
| `scripts/apps/craft-handoff/tools/fc_build.py` | bdc77490e3113ba82170fbf7c0595bc62e4824584a36b11d6ce0c1189a76d566 | `scripts/apps/craft-handoff/tools/fc_build.py` |
| `scripts/apps/craft-handoff/tools/fc_export.py` | 029afae19ff331d116adb34d7f93b70807eaf363723ebc681300069f4e571f65 | `scripts/apps/craft-handoff/tools/fc_export.py` |
| `scripts/apps/talking-head-premiere/scripts/audit_sfx.py` | 7157a4884ba6c746374494426045bc8532c9f7199627c4170de1be4d6abdadc5 | `scripts/apps/talking-head-premiere/scripts/audit_sfx.py` |
| `scripts/audio_levels.py` | 0a3918ad855259c164628b65a1aaf8275908301340eb9c769f7d99c19d71c19a | `scripts/audio_levels.py` |
| `scripts/audit_sfx.py` | fec0ea20160266c5d350ddf8a22f5f4b797a1451529d756227fcf3006ec5c944 | `scripts/audit_sfx.py` |
| `scripts/edit_rules.py` | ebd56304e228304d7eab9493233a9f71cb80dae50ba43967bb3d08fdfc6f2bc1 | `scripts/edit_rules.py` |
| `scripts/fc_fast_qa.py` | 16f0b29c29ea0333a2a549c64cd15966e609c3d8328d120c72d352e4edadf7cb | `scripts/fc_fast_qa.py` |
| `scripts/spec_lint.py` | 729da8227078099f719c90e8ddbbd2484162959496bb31e0079ece12b6343c6b | `scripts/spec_lint.py` |
| `scripts/style_profile.py` | 6e2bc24a702f317e19354a0ccd269b146bd28f41d215bd2968790d1e04dee26b | `scripts/style_profile.py` |
| `scripts/text_motion.py` | d8b9d804ecc65c84edd94b0ed2abc0f0551ec8e04ae4cf3f07059c779d1001cd | `scripts/text_motion.py` |
| `scripts/th_transitions.py` | c62c6e8693d5d1e5f5e1cf0188cadc03f6fd812ea38c105524b2fe1a37ffa83b | `scripts/th_transitions.py` |
