"""Three-axis state classifier tests (Pitfall 4 / RESEARCH §Pattern 4)."""

from __future__ import annotations

from ga_crawler.parsers.goldapple_microdata import (
    GATE_SHELL_MAX_BYTES,
    GATE_TITLE_MARKER,
    detect_state,
    has_microdata_price,
)


def test_detect_state_gate_shell(gate_shell_html: str) -> None:
    """GroupIB challenge: title=checking device + size <30KB."""
    assert len(gate_shell_html) < 30_000
    state = detect_state(gate_shell_html, title="Gold Apple — checking device")
    assert state == "gate-shell"


def test_detect_state_real_pdp(goldapple_pdp_html: str) -> None:
    """Real Givenchy PDP fixture is >=100KB."""
    assert len(goldapple_pdp_html) >= 30_000
    state = detect_state(goldapple_pdp_html, title="Givenchy — купить ...")
    assert state == "real-pdp"


def test_detect_state_stale_sku(stale_sku_html: str) -> None:
    """Synthesized stale-SKU: ~9.5KB, title='Loading <url>', no microdata."""
    assert len(stale_sku_html) < 30_000
    state = detect_state(stale_sku_html, title="Loading https://goldapple.kz/7681000002-foo")
    assert state == "stale-sku"


def test_detect_state_case_insensitive_title() -> None:
    assert detect_state("<html></html>", title="Checking Device") == "gate-shell"
    assert detect_state("<html></html>", title="CHECKING") == "gate-shell"


def test_detect_state_empty_html_is_stale_sku() -> None:
    """Edge case: empty HTML + empty title -> stale-sku (size <30KB, no challenge marker)."""
    assert detect_state("", title="") == "stale-sku"


def test_detect_state_boundary_at_30000() -> None:
    """Strict less-than: size == 30000 is real-pdp (boundary RESEARCH lines 536-540)."""
    html_30k = "x" * GATE_SHELL_MAX_BYTES
    assert detect_state(html_30k, title="checking device") == "real-pdp"


def test_detect_state_boundary_below_30000() -> None:
    """size 29_999 + checking title -> still gate-shell (strict <)."""
    html_just_under = "x" * (GATE_SHELL_MAX_BYTES - 1)
    assert detect_state(html_just_under, title="checking device") == "gate-shell"


def test_has_microdata_price_real_pdp(goldapple_pdp_html: str) -> None:
    """Spike L94-110 contract: real PDP returns (True, True)."""
    has_offer, has_value = has_microdata_price(goldapple_pdp_html)
    assert has_offer is True
    assert has_value is True


def test_has_microdata_price_gate_shell(gate_shell_html: str) -> None:
    """Gate shell has no microdata."""
    assert has_microdata_price(gate_shell_html) == (False, False)


def test_has_microdata_price_stale_sku(stale_sku_html: str) -> None:
    """Stale-SKU shell has no microdata (Pitfall 4 - distinct from gate-shell by title only)."""
    assert has_microdata_price(stale_sku_html) == (False, False)


def test_constants_match_spike() -> None:
    """Hard-pin: spike notebook.py L48-49 values; if these drift, sanity-gate logic also must."""
    assert GATE_SHELL_MAX_BYTES == 30_000
    assert GATE_TITLE_MARKER == "checking"
