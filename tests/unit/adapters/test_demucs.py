from __future__ import annotations

from pathlib import Path

import pytest

from aidub.adapters.separation_demucs import (
    DemucsSeparationAdapter,
    DemucsSeparationOptions,
)


def test_demucs_options_validation() -> None:
    options = DemucsSeparationOptions(
        model_name="htdemucs",
        device="cpu",
        shifts=2,
    )
    assert options.device == "cpu"
    assert options.shifts == 2

    with pytest.raises(ValueError, match="unsupported device"):
        DemucsSeparationOptions(device="npu")


def test_demucs_adapter_rejects_missing_source(tmp_path: Path) -> None:
    adapter = DemucsSeparationAdapter(DemucsSeparationOptions(device="cpu"))
    out_dir = tmp_path / "stems"

    with pytest.raises(FileNotFoundError, match="source audio does not exist"):
        adapter.separate("dummy_input.wav", str(out_dir))
