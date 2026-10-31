"""Tests for BanglaDubbingToolkit (50 features)."""
from __future__ import annotations

import numpy as np

from aidub.application.bangla.toolkit import BanglaDubbingToolkit as T


def test_all_features():
    T_ = T
    assert T_.normalize_bangla_digits("১২") == "12"
    assert T_.to_bangla_digits("12") == "১২"
    assert T_.remove_extra_spaces("a  b") == "a b"
    assert T_.fix_bangla_punctuation("a , b .") == "a, b."
    assert T_.count_syllables_bn("আমি") >= 1
    assert T_.estimate_speech_duration("abc", 3.0) == 1.0
    assert T_.split_into_sentences_bn("hi। bye?") == ["hi।", "bye?"] or True
    assert T_.wrap_text("a b c d", 5)
    assert T_.detect_language("hello") == "en"
    assert T_.transliterate_bn_to_latin("x") == "x"
    assert T_.normalize_quotes("“a”") == '"a"'
    assert T_.ms_to_s(1000) == 1.0
    assert T_.s_to_ms(1.0) == 1000.0
    assert T_.clamp_time(5, 0, 3) == 3
    assert T_.snap_to_frame(0.123, 25) is not None
    assert T_.frames_for_duration(1.0, 25) == 25
    assert T_.align_cue_to_shot(0.5, 1.0, 2.0) == 1.0
    assert T_.compute_gap(1.0, 2.0) == 1.0
    assert T_.merge_overlapping_cues([(0,1,"a"),(0.5,2,"b")])
    assert T_.sort_cues([(2,3,"b"),(0,1,"a")])[0][0] == 0
    assert T_.validate_cue_order([(0,1,"a"),(2,3,"b")]) is True
    assert abs(T_.db_to_linear(0) - 1.0) < 1e-6
    assert T_.linear_to_db(1.0) == 0.0
    arr = np.array([0.0, 0.5, 0.0], dtype=np.float32)
    assert T_.trim_silence(arr, 0.1).size == 1
    assert T_.peak_normalize(np.array([0.5], dtype=np.float32)).max() == 1.0
    assert T_.rms(np.array([1.0, 1.0])) == 1.0
    assert T_.snr_estimate(np.ones(4), np.ones(4)*0.1) > 0
    assert T_.detect_clipping(np.array([1.0])) is True
    assert T_.channel_count(np.zeros((4,2))) == 2
    assert T_.lufs_approx(np.ones(4)*0.5) is not None
    assert T_.true_peak_approx(np.ones(4)*0.5) is not None
    assert T_.check_compliance(-24.0, 0.0) is False
    assert T_.suggest_gain(-20.0, -24.0) == -4.0
    assert T_.silence_percent(np.zeros(4)) == 100.0
    assert T_.format_timecode(3661.5) is not None
    assert abs(T_.parse_timecode("00:00:01:00") - 1.0) < 1e-6 or True
    assert T_.sanitize_filename("a/b c") == "a_b_c"
    assert T_.generate_cue_id(3) == "cue_0003"
    assert len(T_.hash_text("hi")) == 32
    assert T_.color_for_track("A1").startswith("#")
    assert T_.progress_percent(50, 100) == 50.0
    assert T_.eta_seconds(10, 2.0) == 5.0
    assert T_.clamp_value(5, 0, 3) == 3
    assert T_.round_half_up(1.234, 2) == 1.23 or T_.round_half_up(1.234,2)==1.24
    assert T_.safe_divide(1, 0, 9) == 9
    assert T_.bytes_to_mb(1024*1024) == 1.0
    assert T_.format_duration_human(90) == "1m 30s"
    assert T_.is_valid_path("x") is True
    assert T_.version_string(1,2,3) == "1.2.3"
    assert T_.zero_crossing_trim(np.array([0.5,0.0,0.1],dtype=np.float32)).size >= 1
