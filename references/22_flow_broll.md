# 22 — Flow B-roll (brain-side workflow) and the ported ingest tools

> Scope: how the **brain** (Claude) plans, prompts, generates and receives AI B-roll through the `google-flow` MCP, and where the stateless tools
> `silence_cut`, `speed_media`, `broll_from_video`, `sfx_auto`, `qa_sync`, `sfx_shift` sit in the pipeline.
> The tools measure and lint. **They contain no generation code**; every generation step below is an MCP call made by the brain.

## 1. Where the tools sit (order matters)

| Step | Tool | Rule |
|---|---|---|
| 1 | `silence_cut.py plan` then `apply` | Runs on the **raw A-roll, before `probe_and_align`**, so `words_tl.json` is built on the cut media. |
| 2 | `speed_media.py plan` then `apply` + `check` | Advisory. Only on the **pre-ingest media**, never after a spec exists. Policy 1.10 -> 1.05 -> 1.0; under 45 s stays 1.0; 1.15 / 1.25 banned. |
| 3 | `probe_and_align.py` | Builds `words_tl.json` on the cut (and optionally sped-up) media. |
| 4 | `broll_from_video.py analyze` | `words_tl.json` -> `broll_plan.json` + `prompts_template.json`. |
| 5 | brain writes prompts, `check-prompts` | One contract: `presets/broll_lint_contract.json`. |
| 6 | Flow generation (section 2) | MCP only. |
| 7 | `sfx_auto.py plan` | events -> `cues.json` (hero +100..300 ms, opening frame 0-1, heavy whoosh cap 5/min, 7 Organic Foley fallback). |
| 8 | `compile_and_verify.py` | Compiles the spec to `.fcproj`. No `.mp4` unless the user asks. |
| 9 | `qa_sync.py` (only on an already exported mp4) then at most one `sfx_shift.py` | Brain-triggered Gate 7b, never an automatic loop. A `.fcproj` is exported through `fc_export.py` only when the user asked for the mp4. |

## 2. Google Flow workflow (MCP `google-flow`, tools `flow_*`)

Use the `flow_*` tools exclusively, in this order, whatever language the user writes in:

1. `flow_list_accounts`. If `readyForGeneration` is true, use `defaultAccountId` and do not call any connection or login-diagnostic tool.
   If no account is connected: `flow_begin_account_connection`, stop, tell the user to click Connect in the Flow Login Bridge, then
   `flow_complete_account_connection` with the exact `connectionId` once the user confirms.
2. `flow_inspect_account`. Use only the models, aspect ratios, durations and upscales it reports as available.
3. `flow_generate_video` per B-roll slot from `flow_ready.json` (`jobs[]`):
   - `model: "omni-flash"`, `aspectRatio: "9:16"`, `outputs: 2` (two takes to choose from), `durationSeconds` = the job's `duration_seconds`
     (voice length + 0.3 s, clamped 3-15 s) only when `visibleDurations` reports that value, `upscale: "none"` at this stage;
   - `prompt` = the lint-passed English prompt (the job's `prompt`), `fileName` = the job's `file_stem` (for example `02_b-roll-1`);
   - `outputDirectory` = an absolute folder inside the project work dir; `confirmCreditSpend: true` (a direct user request to produce B-roll is
     the authorization for the credits in `flow_ready.json`; if the budget was never shown to the user, show it first).
4. If the call returns `status: processing`, the job is already submitted. Poll `flow_job_status` with the **same** `jobId` until it is
   completed or failed. Never call a generation tool again for the same request.
5. Pick the best take (check the first and last frames and motion), then `flow_upscale_video` with that `jobId` and `factor: "1080p"`
   (or the 1080p ID `flow_inspect_account` reports).
6. `flow_download_job` with the exact `jobId`. Never guess from gallery order and never substitute another job. On
   `job_asset_identity_missing` or `generated_asset_not_found`, report it and stop for that slot.
7. **Strip metadata after download** (EXIF / XMP / C2PA / prompt text) before the clip enters the project: use the `strip-media-metadata` skill.
   Then the usual B-roll hygiene: remove letterbox bars, drop the audio stream (B-roll is silent, the A-roll voice carries the video), conform to 30 fps.

### Hard rules

- **Never automate `labs.google/fx`** (or any Flow web page) with browser, computer-use, keyboard, mouse, Playwright or web tools. The MCP owns all Flow
  browser interaction. If a tool reports `login_required` or `flow_access_unavailable`, stop and report that exact error or restart the connection
  steps. Never compensate with browser automation.
- Never claim a generation started unless `flow_generate_video` returned a job ID.
- **Muse fallback**: when Flow is unavailable (login lost, quota, repeated failure) the brain may use the Muse generator for the same slot with the
  same lint-passed prompt (maximum 10 s per clip, so ask for `ceil(voice_len + 0.3)` clamped 2-10 s). Record in the report which slots used the fallback.
  Never fall back to a browser-driven Flow session.
- **B-roll is never faked proof (PFD R200).** AI B-roll illustrates; it never acts as evidence. No before/after photos, results, screenshots,
  certificates, test reports, revenue or analytics visuals, "real customer" footage. When the narration asserts a verifiable claim
  (`claim_gate: true` in `flow_ready.json`, with `claim_reasons`), use real footage supplied by the user or a typographic block
  (`metric_kpi_hero`, `versus_split_card`) and set `claim_gate` and `claim_reasons` in the spec so `EDITOR-REPORT.md` asks for human verification.

## 3. Writing a prompt that passes (`check-prompts`)

- English only, 8-60 words, one continuous scene, no brand names, no readable text, no faces (over the shoulder, from behind, hands only,
  silhouette), no evidence-like content (R200).
- Bind it to the slot: put the exact words of the slot's `anchor_quote` in the record's `anchor_quote`; it must appear verbatim in the slot text.
- Structure: [Vietnamese subject, faceless framing] + [action that illustrates the anchor] + [real setting, screens/paper out of focus or blank] +
  [natural light] + [one smooth camera move].
- Example: `A Vietnamese shop owner seen from behind rearranges neatly folded clothes on a wooden shelf, soft morning window light, slow push-in, shallow depth of field`.

`check-prompts` supersedes `visual_blocks.lint_broll_prompt`'s 45-token rule as the ingest-level lint (that function is unchanged and still lints plate-level prompts).
The pain-keyword list that steers slot choice (rule E2) is `presets/pain_keywords.json`: a plain JSON array of NFC strings that the brain may edit per industry
(or replace with `--pain-keywords`).

## 4. Rules the planner enforces (D1 / E2)

- D1: inserts cover at least 25 percent of the video; talk-only runs stay at most 8 s; the opening hook block stays on the speaker.
- E2: blocks containing a pain keyword are chosen first, a pain block is not made an insert when it sits next to an existing insert, and the closing call to action stays on the speaker.
- Blocks are 3-10 s, split at sentence ends and pauses over 0.45 s.
