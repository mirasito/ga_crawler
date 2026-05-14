"""TH-02c sidecar JSON round-trip (FixtureMetadata)."""
from __future__ import annotations

from pathlib import Path

from tests._fixture_metadata import FixtureMetadata, read_sidecar, write_sidecar


def test_sidecar_round_trip(tmp_path: Path) -> None:
    fixture_path = tmp_path / "_live-test.html"
    fixture_path.write_text("<html/>", encoding="utf-8")
    meta = FixtureMetadata(
        date="2026-05-14T12:00:00+00:00",
        url="https://goldapple.kz/test",
        status=200,
        html_size=8,
        title="Test",
        camoufox_version="0.4.11",
    )
    sidecar_path = write_sidecar(fixture_path, meta)
    assert sidecar_path.exists()
    assert sidecar_path == fixture_path.with_suffix(".json")
    loaded = read_sidecar(fixture_path)
    assert loaded == meta


def test_read_sidecar_missing_returns_none(tmp_path: Path) -> None:
    fixture_path = tmp_path / "_live-missing.html"
    fixture_path.write_text("<html/>", encoding="utf-8")
    assert read_sidecar(fixture_path) is None
