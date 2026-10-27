# Cross-Team Handoff Requests (Round 1)

This file records requests from the **ENGINE** agent for the **UI** and **QA** agents to complete Round 1 objectives.

---

## 1. Requests for UI Agent (`src/aidub/ui/`)

### Request UI-1: Fast Profile Parameter Binding in `DubbingEngineWorker`
* **File:** `src/aidub/ui/workers.py` (lines 156–166)
* **Context:** When the operator initiates dubbing using the "fast" quality profile:
  ```python
  cfg = PipelineConfig(
      input=self.input_path,
      output=out_path,
      tgt_lang=self.target_lang,
      keep_music=self.quality_profile != "fast",  # False for fast profile
      diarize=self.quality_profile != "fast",  # False for fast profile
      lipsync=self.lipsync,
      lipsync_tier=self.lipsync_tier,
      voice_name=self.voice_name,
      character_voices=self.character_voices,
  )
  ```
* **Requirement:** Ensure that when "Fast" profile is selected in the UI, `self.quality_profile` is `"fast"` so that heavy Demucs stem separation and PyAnnote diarization are bypassed for CPU-friendly execution.

### Request UI-2: Progress Stage Display in Timeline Overlay
* **File:** `src/aidub/ui/screens/timeline_editor.py` (`_on_dubbing_progress`)
* **Requirement:** `DubbingEngine` emits progress with frozen stage names:
  `ingest`, `extract_audio`, `separate_stems` (or `separate_stems_skipped`), `diarize` (or `diarize_skipped`), `asr`, `translate`, `tts`, `assemble`, `mix`, `mux`, `complete`.
  Verify that the timeline AI overlay displays these stage names and percentage bars smoothly without getting stuck.

### Request UI-3: Auto-Load Dubbed MP4 into Player Upon Completion
* **File:** `src/aidub/ui/screens/timeline_editor.py` (`_on_dubbing_completed`)
* **Requirement:** In `_on_dubbing_completed(self, result: dict[str, Any])`, after setting `generated_paths`, automatically call:
  ```python
  output_video = str(result.get("output_file", ""))
  if output_video and Path(output_video).is_file():
      self.monitor_panel.load_media(output_video)
  ```
  This satisfies the Round 1 goal: "from the desktop app, import a 2-minute clip, press Dub, see progress, and play the dubbed MP4".

---

## 2. Requests for QA Agent (`tests/`)

### Request QA-1: E2E Fast Profile Acceptance Verification
* **Test Case:** End-to-end execution of `DubbingEngine` on a 2-minute (120s) clip with `keep_music=False` and `diarize=False`.
* **Acceptance Criteria:**
  1. Output MP4 exists, is playable, and has valid H.264 video + AAC stereo audio.
  2. Duration of output matches source within $\pm 0.5$ seconds (120.0s $\pm 0.5$s).
  3. Audio is audible and clear: mean volume $\ge -22$ dBFS, peak $\ge -1.0$ dBFS (never silent or inaudible).
  4. Bilingual subtitle file (`bilingual.srt`) is generated and has aligned Bengali translations.
  5. All unit and integration tests pass cleanly with `QT_QPA_PLATFORM=offscreen pytest -q`.
