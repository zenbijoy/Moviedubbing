"""
Unit tests for Real C2PA Content Credentials Signing and DCT Audio Watermarking.
"""

from __future__ import annotations

import numpy as np

from aidub.security.c2pa_manifest import C2PAManifest, C2PAManifestBuilder
from aidub.security.provenance_watermark import AIProvenanceWatermarker


def test_c2pa_manifest_signing_and_verification() -> None:
    secret_key = "studio_super_secret_signing_key_2026"
    builder = C2PAManifestBuilder(signing_key=secret_key)

    manifest = builder.build_c2pa_manifest(
        project_id="hollywood_blockbuster_dub_01",
        actions=["c2pa.dubbed", "c2pa.translated", "c2pa.voice_cloned"],
    )

    assert isinstance(manifest, C2PAManifest)
    assert len(manifest.digital_signature_sha256) == 64
    assert manifest.claim_generator == "AIDub Studio Enterprise v2.1"
    assert "c2pa.voice_cloned" in manifest.ai_actions_performed

    # Verify signature passes with correct key
    is_valid = C2PAManifestBuilder.verify_manifest(
        manifest, project_id="hollywood_blockbuster_dub_01", signing_key=secret_key
    )
    assert is_valid is True

    # Verify signature fails with wrong key or tampered project_id
    is_tampered = C2PAManifestBuilder.verify_manifest(
        manifest, project_id="tampered_project_id", signing_key=secret_key
    )
    assert is_tampered is False


def test_signal_domain_audio_watermarking_and_extraction() -> None:
    watermarker = AIProvenanceWatermarker(configured=True, secret_key="watermark_master_seed")  # noqa: S106

    # Generate 5 seconds of 48kHz audio (240,000 samples)
    fs = 48000
    duration_s = 5.0
    t = np.linspace(0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)
    # Speech-like audio signal with harmonics
    clean_audio = (
        0.4 * np.sin(2.0 * np.pi * 220.0 * t)
        + 0.2 * np.sin(2.0 * np.pi * 440.0 * t)
        + 0.1 * np.sin(2.0 * np.pi * 880.0 * t)
    )

    provenance_id = "provenance_asset_987654321"

    # Embed watermark signal
    watermarked_audio = watermarker.embed_watermark_signal(
        clean_audio, provenance_id, fs=fs, alpha=0.008
    )

    # Audio should remain virtually indistinguishable (high SNR)
    noise_diff = watermarked_audio - clean_audio
    snr = 10.0 * np.log10(np.sum(clean_audio**2) / np.sum(noise_diff**2))
    assert snr > 35.0  # SNR > 35 dB (completely imperceptible to human ear)

    # Extract and verify watermark
    verified = watermarker.verify_watermark_signal(watermarked_audio, provenance_id)
    assert verified is True

    # Verification should fail for wrong provenance id
    fake_verified = watermarker.verify_watermark_signal(watermarked_audio, "fake_asset_000000000")
    assert fake_verified is False
