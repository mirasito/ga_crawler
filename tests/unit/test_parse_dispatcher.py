"""PARSE-02 — `ParseDispatcher` retailer-keyed parser dispatch.

Wave 3 / Plan 02-04 implements the concrete `ParseDispatcher` (interfaces.py
defines only the Protocol). Registers goldapple-microdata + viled-nextdata
parsers; `dispatch(retailer, html_or_data)` routes by retailer-id.

Asserts:
  - `dispatch("viled", html)` invokes viled_nextdata parser
  - `dispatch("goldapple", html)` invokes goldapple_microdata parser
  - `dispatch("unknown", html)` returns None (or raises per Protocol contract)

Source: 02-RESEARCH.md §Validation Architecture row 18; 02-CONTEXT.md D-213.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
