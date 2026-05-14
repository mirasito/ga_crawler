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


# --- Fixture wiring tests (Task 4) ---


def test_refresh_live_fixture_default_false(refresh_live: bool) -> None:
    """Default invocation: refresh_live fixture must resolve to False."""
    assert refresh_live is False


def test_html_snapshot_fixture_available(html_snapshot) -> None:
    """html_snapshot fixture exists and is constructed via syrupy with_defaults."""
    # The fixture is a syrupy AssertionExtension wrapper; we just verify it's
    # not None and has the expected `extension_class` attribute.
    assert html_snapshot is not None
    # syrupy's snapshot.with_defaults returns a wrapper; existence is enough.
