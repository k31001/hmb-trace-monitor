# SPDX-License-Identifier: Apache-2.0
"""synth → stream → stats 라운드트립."""

from __future__ import annotations

from pathlib import Path

import pytest

from hmb_trace.stats import TraceStats
from hmb_trace.stream import count_records, iter_records
from hmb_trace.synth import SynthOptions, write


def test_synth_then_iterate_recovers_count(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=500, seed=1))
    assert count_records(out) == 500


def test_synth_then_compute_stats(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=1_000, seed=42, cpus=4))
    stats = TraceStats.compute(iter_records(out))
    assert stats.total_records == 1_000
    assert len(stats.by_cpu) <= 4
    assert stats.duration_ns > 0
    assert stats.records_per_sec > 0
    assert stats.payload_size_mean >= 0
    assert all(g.dropped_count >= 1 for g in stats.seq_gaps)


def test_drop_every_introduces_gaps(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=1_000, seed=7, drop_every=50))
    stats = TraceStats.compute(iter_records(out))
    # 50개마다 드롭이 강제됐으므로 최소 일부 갭은 잡혀야 함.
    assert len(stats.seq_gaps) > 0
    assert stats.total_dropped > 0


def test_truncate_flag_is_counted(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=200, seed=3, truncate_every=10))
    stats = TraceStats.compute(iter_records(out))
    assert stats.truncated_records > 0
    assert stats.by_flag_bit.get(1, 0) == stats.truncated_records  # HMB_REC_FLAG_TRUNCATED bit


def test_wrap_markers_are_skipped_by_default(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=300, seed=11, wrap_every=20))
    default_count = count_records(out)
    full_count = sum(1 for _ in iter_records(out, include_wrap_markers=True))
    # wrap marker는 기본 이터레이션에서 빠지지만 include 옵션 켜면 보임.
    assert full_count > default_count
    stats = TraceStats.compute(iter_records(out, include_wrap_markers=True))
    assert stats.wrap_markers > 0
    # wrap marker는 by_opcode에 잡히지 않아야 함 (compute_stats가 continue함)
    assert stats.total_records == default_count


def test_truncated_file_raises(tmp_path: Path) -> None:
    out = tmp_path / "t.bin"
    write(out, SynthOptions(count=10, seed=0))
    raw = out.read_bytes()
    # 헤더 중간에서 자르기
    truncated = raw[: len(raw) - 5]
    bad = tmp_path / "bad.bin"
    bad.write_bytes(truncated)
    with pytest.raises(ValueError, match="truncated"):
        list(iter_records(bad))


def test_empty_file_yields_zero(tmp_path: Path) -> None:
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    assert count_records(empty) == 0
    stats = TraceStats.compute(iter_records(empty))
    assert stats.total_records == 0
    assert stats.duration_ns == 0
    assert stats.records_per_sec == 0.0
