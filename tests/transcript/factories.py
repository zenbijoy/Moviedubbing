from aidub.domain import (
    AudioSamplePosition,
    AudioSampleRange,
    RationalRate,
    RationalTime,
    TimeRange,
    Utterance,
    UtteranceStatus,
    WordTiming,
)
from aidub.transcript import Transcript

RATE = RationalRate(numerator=1_000)
PROJECT_ID = "prj_movie_001"
MEDIA_ID = "med_source_001"


def time_range(start: int, end: int) -> TimeRange:
    return TimeRange.from_start_end(
        RationalTime(ticks=start, rate=RATE),
        RationalTime(ticks=end, rate=RATE),
    )


def word(text: str, start: int, end: int) -> WordTiming:
    return WordTiming(text=text, source_range=time_range(start, end), confidence=0.97)


def audio_range(start: int, count: int) -> AudioSampleRange:
    return AudioSampleRange(
        start=AudioSamplePosition(sample_index=start, sample_rate=48_000),
        sample_count=count,
    )


def utterance(
    utterance_id: str = "utt_line_001",
    *,
    project_id: str = PROJECT_ID,
    language: str = "bn-BD",
    source_start: int = 1_000,
    source_end: int = 3_000,
    edit_start: int = 5_000,
    edit_end: int = 7_000,
    source_text: str = "আমি এখানে আছি",
    words: tuple[WordTiming, ...] = (),
    samples: AudioSampleRange | None = None,
    revision: int = 0,
    status: UtteranceStatus = UtteranceStatus.DRAFT,
) -> Utterance:
    return Utterance(
        utterance_id=utterance_id,
        project_id=project_id,
        source_range=time_range(source_start, source_end),
        edit_range=time_range(edit_start, edit_end),
        source_audio_range=samples,
        source_text=source_text,
        source_language=language,
        confidence=0.95,
        words=words,
        status=status,
        revision=revision,
    )


def transcript(
    *lines: Utterance,
    revision: int = 0,
    language: str = "bn-BD",
) -> Transcript:
    return Transcript(
        project_id=PROJECT_ID,
        media_asset_id=MEDIA_ID,
        language=language,
        revision=revision,
        utterances=lines,
    )
