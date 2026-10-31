# AI Movie Dubbing Studio (DubForge) — Manual Dubbing Feature Specification & Roadmap

> **Target:** AI Movie Dubbing Studio (DubForge) — PySide6 desktop, local-first, modular workers, non-destructive artifacts.  
> **Status:** Production Verified — Phases M0 through M7 Fully Implemented & Passing (30/30 Unit Tests)  
> **Updated:** 2026-10-27  

---

## 0. Market Feature Cloning Matrix

| Market Tool | Feature Cloned | DubForge Equivalent | Implementation Module | Status |
|---|---|---|---|---|
| **Premiere Pro / DaVinci Resolve** | Blade, ripple delete, trim, slip/slide, speed ramp | Timeline Core & Cutting Engine | `aidub.application.timeline.cut_engine` | **Verified** ✅ |
| **Descript** | Text-based editing, overdub punch-in, ADR comping | Transcript Editor + ADR Comping | `aidub.application.audio.adr_recorder` | **Verified** ✅ |
| **Adobe Audition / iZotope RX** | Parametric EQ, de-ess, leveler/compressor, limiter | Voice DSP Chain Suite | `aidub.application.audio.dsp_chain` | **Verified** ✅ |
| **Melodyne / Revoice Pro** | Pitch/time/formant manipulation, WSOLA stretch | Prosody & Performance Editor | `aidub.media.pro_audio_editor` | **Verified** ✅ |
| **ElevenLabs Studio** | Voice changer, 3D PAD emotion, intensity sliders | Pro Emotion Director Studio | `aidub.application.emotion.emotion_editor` | **Verified** ✅ |
| **Nuendo / Fairlight** | ADR recording, retake lanes, comping, stems | ADR Studio + Delivery Exporter | `aidub.application.export.delivery` | **Verified** ✅ |
| **Synchro Arts Revoice** | Lead/lag offset calibration, ITU-R BT.1359 | Frame-Accurate Lip-Sync Studio | `aidub.application.lipsync.manual_lipsync` | **Verified** ✅ |
| **CapCut** | Subtitle interchange, timeline toolbars | Multitrack NLE Toolbar | `aidub.ui.timeline.edit_tools` | **Verified** ✅ |
| **HeyGen / Rask / Perso** | Viseme mapping, mocap blendshapes, tier picker | Viseme Timeline & Mocap Rig | `aidub.domain.viseme` | **Verified** ✅ |
| **Deepdub / Papercup** | Diarization cluster merge, emotion transfer, QC | Character Classification + QC Gate | `aidub.application.qc.qc_dashboard` | **Verified** ✅ |

---

## 1. Architecture & Data Model

### Domain Contracts (`src/aidub/domain/`)
- `edit_ops.py` — `EditCommand`, `CommandGraph`, `UndoStack`, `SnapshotCheckpoint`, `EditCommandType`.
- `invalidation.py` — `InvalidationGraph`, `ArtifactDependency`, `PipelineStage`, `CueArtifactRecord`.
- `audio_edit.py` — `AudioSelection`, `EffectRack`, `DspEffectNode`, `Take`, `CompingRegion`, `FadeSpec`.
- `emotion.py` — `EmotionSpec`, `EmotionCurve`, `EmotionKeyframe`, `VocalizationMarker`, `EmotionObservation`.
- `voice_classification.py` — `ClassificationResult`, `DiarizationCluster`, `SpeakerMergeOperation`, `CharacterVoiceProfile`.
- `viseme.py` — `VisemeTimeline`, `VisemeKeyframe`, `VisemeGroup`, `VisemeGeometry`, `LipSyncOffset`.

---

## 2. Implementation Phases & Completion Status

### [x] Phase M0 — Foundations & CommandGraph (COMPLETED)
- [x] Implemented `src/aidub/domain/edit_ops.py` (atomic commands, command graph, undo stack).
- [x] Implemented `src/aidub/domain/invalidation.py` & `src/aidub/application/timeline/invalidation_graph.py` (fine-grained downstream invalidation).
- [x] Implemented `src/aidub/application/timeline/edit_engine.py` (`EditEngine.apply()`, undo, redo, dirty checkpointing).
- [x] Implemented `src/aidub/domain/viseme.py` (viseme keyframes, timeline, Disney/MPEG-4 blendshape geometries).
- [x] Tests passing in `tests/unit/domain/test_edit_ops.py`, `tests/unit/domain/test_viseme_contracts.py`, and `tests/unit/application/test_edit_engine.py`.

### [x] Phase M1 — Voice Editing DSP & ADR Comping (COMPLETED)
- [x] Implemented `src/aidub/domain/audio_edit.py` (selection, effect rack, takes, comping regions).
- [x] Implemented `src/aidub/application/audio/dsp_chain.py` (4-band parametric EQ, de-esser, leveler/limiter, reverb matcher, peak normalizer).
- [x] Implemented `src/aidub/application/audio/adr_recorder.py` (multi-take recording lanes, active take switching, S-curve crossfaded comping assembly).
- [x] Implemented `src/aidub/ui/screens/voice_editor.py` (waveform display + effects rack UI, headless safe).
- [x] Tests passing in `tests/unit/application/test_dsp_chain.py` and `tests/unit/application/test_adr_recorder.py`.

### [x] Phase M2 — Pro Emotion Director Studio (COMPLETED)
- [x] Extended `src/aidub/domain/emotion.py` (`EmotionSpec`, `EmotionCurve`, `VocalizationMarker`).
- [x] Implemented `src/aidub/application/emotion/emotion_editor.py` (12 Hollywood cinematic presets, 0-200% intensity, 3D PAD coordinates, native W3C SSML generation).
- [x] Implemented `src/aidub/application/emotion/emotion_transfer.py` (acoustic feature extraction, emotion transfer intent, compliance match score).
- [x] Implemented `src/aidub/ui/screens/emotion_editor.py` (interactive 3D PAD director screen, headless safe).
- [x] Tests passing in `tests/unit/application/test_emotion_editor.py`.

### [x] Phase M3 — Voice Exchanger & Timbre Morphing (COMPLETED)
- [x] Implemented `src/aidub/application/voice/voice_exchanger.py` (batch re-casting, dual-voice linear timbre morphing, pitch/formant shifting).
- [x] Enforced cryptographic consent verification via `VoiceRightsService`.
- [x] Implemented `src/aidub/ui/screens/voice_exchanger.py` (curated voice browser + morph sliders, headless safe).
- [x] Tests passing in `tests/unit/application/test_voice_exchanger.py`.

### [x] Phase M4 — Voice & Character Classification (COMPLETED)
- [x] Implemented `src/aidub/application/voice/character_registry.py` (production cast roster, voice assignment, consent audit log).
- [x] Implemented `src/aidub/application/voice/voice_classifier.py` (confidence attribution, <75% review flagging, 1-click diarization cluster merge).
- [x] Implemented `src/aidub/ui/screens/voice_classification.py` (character matrix + 1-click merge toolbar, headless safe).
- [x] Tests passing in `tests/unit/application/test_voice_classifier.py`.

### [x] Phase M5 — Frame-Accurate Manual Lip-Sync Studio (COMPLETED)
- [x] Implemented `src/aidub/application/lipsync/manual_lipsync.py` (ITU-R BT.1359 broadcast check, lead/lag frame nudge, viseme override, tier selection).
- [x] Implemented `src/aidub/ui/timeline/viseme_lane.py` (colored viseme track lane widget, headless safe).
- [x] Implemented `src/aidub/ui/screens/manual_lipsync.py` (interactive slip-and-slide studio, mocap JSON exporter).
- [x] Tests passing in `tests/unit/application/test_manual_lipsync.py`.

### [x] Phase M6 — NLE Video & Audio Cutting Engine (COMPLETED)
- [x] Implemented `src/aidub/application/timeline/cut_engine.py` (blade split at playhead, trim head/tail, ripple delete gap closure, speed ramp, slip nudge).
- [x] Implemented `src/aidub/ui/timeline/edit_tools.py` (NLE toolbar: Selection, Blade, Trim, Ripple, Slip, Speed, Marker).
- [x] Tests passing in `tests/unit/application/test_cut_engine.py`.

### [x] Phase M7 — QC Dashboard & Delivery Exporter (COMPLETED)
- [x] Implemented `src/aidub/application/qc/qc_dashboard.py` (automated detection of clipping, timing overrun, lip-sync misalignment; blocker gating).
- [x] Implemented `src/aidub/application/export/delivery.py` (isolated dialogue stem -14 LUFS, M&E stem, master mix EBU R128 -23 LUFS, cue sheet CSV, SRT subtitles).
- [x] Implemented `src/aidub/ui/screens/qc_dashboard.py` (health score banner, defect table with 1-click auto-fix, deliverable export gate).
- [x] Tests passing in `tests/unit/application/test_qc_dashboard.py`.

### [ ] Phase M8 — Production Hardening & Benchmarking (Target: Active)
- [ ] VRAM memory paging confirmation ($\le 12.0$ GB).
- [ ] Full regression suite run across the entire workspace.
