# Recommended End-to-End Bengali Movie Dubbing Architecture

Synthesized blueprint incorporating the strongest architectural patterns discovered across the 41 audited repositories.

```mermaid
graph TD
    subgraph INGEST ["1. Media Ingestion & Preflight"]
        RawVideo[Source Video MKV / MP4] --> Probe[FFprobe Container & Sample Rate Check]
        Probe --> BSRoformer[Mel-Band Roformer Separation]
        BSRoformer --> StemsVocals[Isolated Vocals Stem]
        BSRoformer --> StemsME[Preserved Music & Effects Stem]
    end

    subgraph PERCEPTION ["2. Speech & Character Perception"]
        StemsVocals --> WhisperX[Faster-Whisper Large-v3 + Word Alignment]
        StemsVocals --> Pyannote[Pyannote 3.1 Diarization]
        RawVideo --> FaceDetect[Face Recognition & Visual Co-occurrence]
        Pyannote --> SpeakerCluster[Speaker Timelines]
        FaceDetect --> CharBinder[Character Binding: Face + Voice Profile]
        SpeakerCluster --> CharBinder
    end

    subgraph LINGUISTICS ["3. Script Stabilization & Translation"]
        WhisperX --> SubClean[8-Stage Subtitle Stabilization - ZastTranslate]
        SubClean --> DurationBudget[Syllable & Character Budget Calculator - Voxa]
        DurationBudget --> LLMTrans[5-Pass Contextual Bengali Translation - DeepSeek / Qwen]
    end

    subgraph SYNTHESIS ["4. Performance & Voice Synthesis"]
        LLMTrans --> TimingCheck{Duration Match?}
        TimingCheck -- Overrun > 8% --> LLMTrans
        TimingCheck -- Fits Slot --> TTSSelect[TTS Engine]
        TTSSelect --> EdgeRVC[Edge-TTS Bengali + Character RVC v2 Conversion]
        TTSSelect --> ChatterboxBN[Chatterbox Bengali Zero-Shot Engine]
        EdgeRVC --> DubbedAudio[Dubbed Dialogue Takes]
        ChatterboxBN --> DubbedAudio
    end

    subgraph ALIGNMENT ["5. Spatial Placement & Visual Dubbing"]
        DubbedAudio --> AnchoredSync[Anchored Timeline Placement - Voxa]
        AnchoredSync --> ShotClassifier{Close-Up Speaking Face?}
        ShotClassifier -- Yes --> LatentSync[LatentSync / Wav2Lip + GFPGAN]
        ShotClassifier -- No / Wide --> Passthrough[Passthrough Original Video Frame]
        LatentSync --> SyncedVideo[Visually Dubbed Video Stream]
        Passthrough --> SyncedVideo
    end

    subgraph MASTERING ["6. Audio Mastering & Deliverables"]
        StemsME --> Mixer[FFmpeg Sidechain Audio Mixer]
        DubbedAudio --> Mixer
        Mixer --> Loudnorm[Two-Pass EBU R128 Loudness Normalization -14 LUFS]
        Loudnorm --> FinalMux[Final Muxer: SyncedVideo + Mastered Audio + Bengali SRT]
        FinalMux --> Deliverable[Release-Ready Bengali Dubbed Movie Master]
    end
```

---

## MVP vs. Full Build Roadmap

### Phase 1: MVP Pipeline (2 Weeks)
* Mel-Band Roformer separation
* Faster-Whisper ASR + WhisperX alignment
* Voxa-style anchored placement
* Gemini/Qwen length-budgeted Bengali translation
* Edge-TTS Bengali (`bn-BD-NabanitaNeural` / `bn-BD-PradeepNeural`)
* FFmpeg M&E stem mix with loudness normalization

### Phase 2: Character Identity & Zero-Shot Cloning (3 Weeks)
* Face + Voice co-occurrence character binding (Dub Studio pattern)
* RVC v2 voice conversion model per character
* 8-stage subtitle stabilization (ZastTranslate pattern)
* Automated back-transcription quality control gate

### Phase 3: Visual Lip-Sync & Desktop Workstation (4 Weeks)
* Selective shot-based LatentSync visual dubbing
* PySide6 / Qt6 editorial timeline with draggable utterance waveforms
* Embedded MCP server for autonomous AI assistant control
