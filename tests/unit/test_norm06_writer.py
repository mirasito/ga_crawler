"""NORM-06 + D-208 markdown schema verification."""
from ga_crawler.storage.norm06_writer import Norm06Writer


def test_writes_markdown_table(tmp_path):
    w = Norm06Writer(repo_root=tmp_path)
    out = w.persist(
        run_id=44,
        viled_unmatched=["jo_malone_london"],
        goldapple_new_slugs=["tom-ford-private-blend"],
    )
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# NORM-06 Review Queue — Run 44" in content
    assert "| brand_or_slug | source | run_id | status |" in content
    assert "| jo_malone_london | viled-unmatched | 44 | pending |" in content
    assert "| tom-ford-private-blend | goldapple-new-slug | 44 | pending |" in content


def test_status_pending_default(tmp_path):
    w = Norm06Writer(repo_root=tmp_path)
    out = w.persist(run_id=10, viled_unmatched=["b1", "b2"], goldapple_new_slugs=["s1"])
    content = out.read_text(encoding="utf-8")
    # 3 data rows; each ends with " pending |"
    pending_count = content.count("| pending |")
    assert pending_count == 3


def test_empty_inputs_writes_header_only(tmp_path):
    w = Norm06Writer(repo_root=tmp_path)
    out = w.persist(run_id=99, viled_unmatched=[], goldapple_new_slugs=[])
    content = out.read_text(encoding="utf-8")
    assert "# NORM-06 Review Queue — Run 99" in content
    assert "| brand_or_slug | source | run_id | status |" in content
    # No "viled-unmatched" or "goldapple-new-slug" data rows
    assert "viled-unmatched" not in content
    assert "goldapple-new-slug" not in content


def test_writes_to_planning_runs_subdir(tmp_path):
    """D-208: file lives at .planning/runs/{run_id}/norm06-review.md."""
    w = Norm06Writer(repo_root=tmp_path)
    out = w.persist(run_id=77, viled_unmatched=[], goldapple_new_slugs=[])
    expected = tmp_path / ".planning" / "runs" / "77" / "norm06-review.md"
    assert out == expected
    assert out.exists()
