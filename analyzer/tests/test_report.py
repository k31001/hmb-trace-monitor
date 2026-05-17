# SPDX-License-Identifier: Apache-2.0
"""HTML 리포트 빌드 검증."""

from __future__ import annotations

from pathlib import Path

from hmb_trace.report import write_report
from hmb_trace.synth import SynthOptions, write


def test_report_writes_self_contained_html(tmp_path: Path) -> None:
    src = tmp_path / "t.bin"
    write(src, SynthOptions(count=200, seed=5, drop_every=30, truncate_every=20))

    out = tmp_path / "report.html"
    written = write_report(src, out, max_table_rows=100)
    assert written == out
    text = out.read_text(encoding="utf-8")

    # 기본 sanity
    assert text.startswith("<!DOCTYPE html>")
    assert "HMB Trace Report" in text
    assert "report-data" in text

    # 외부 의존성이 없어야 한다 (CDN 링크 금지)
    assert "https://cdn." not in text
    assert "https://unpkg.com" not in text
    assert '<link rel="stylesheet"' not in text  # 인라인 CSS만

    # 데이터가 임베드됐는지
    assert "by_opcode" in text
    assert "seq_gaps" in text


def test_report_marks_truncated_when_records_exceed_limit(tmp_path: Path) -> None:
    src = tmp_path / "t.bin"
    write(src, SynthOptions(count=500, seed=0))

    out = tmp_path / "r.html"
    write_report(src, out, max_table_rows=100)
    text = out.read_text(encoding="utf-8")
    assert '"table_truncated":true' in text


def test_report_no_truncation_when_records_fit(tmp_path: Path) -> None:
    src = tmp_path / "t.bin"
    write(src, SynthOptions(count=50, seed=0))

    out = tmp_path / "r.html"
    write_report(src, out, max_table_rows=100)
    text = out.read_text(encoding="utf-8")
    assert '"table_truncated":false' in text
