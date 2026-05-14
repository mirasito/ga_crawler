"""TH-01 sanity: HTMLSnapshotExtension exists + correct class config."""
from __future__ import annotations

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from tests._snapshot_extension import HTMLSnapshotExtension


def test_extension_subclasses_single_file() -> None:
    assert issubclass(HTMLSnapshotExtension, SingleFileSnapshotExtension)


def test_extension_file_extension_is_html() -> None:
    assert HTMLSnapshotExtension._file_extension == "html"


def test_extension_write_mode_is_text() -> None:
    assert HTMLSnapshotExtension._write_mode is WriteMode.TEXT
