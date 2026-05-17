# SPDX-License-Identifier: Apache-2.0
"""트레이스 통계 계산.

단일 패스로 record를 훑으면서 아래를 집계한다:
- 총 record 수, opcode/CPU별 분포
- 시간 범위와 records-per-second
- payload 길이 분포
- 인접 record 사이 간격(dt) 통계
- 시퀀스 갭(드롭 추정)
- HMB_REC_FLAG_TRUNCATED / wrap marker 카운트
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self

from hmb_trace.format import HMB_REC_FLAG_TRUNCATED, HMB_REC_FLAG_WRAP_MARKER
from hmb_trace.stream import Record

# 인접 record 간격(ns)을 분류할 버킷 경계 — log scale 비슷하게.
DT_BUCKETS_NS: tuple[int, ...] = (
    100,
    1_000,
    10_000,
    100_000,
    1_000_000,
    10_000_000,
    100_000_000,
    1_000_000_000,
)


@dataclass(slots=True)
class SeqGap:
    """시퀀스 번호 점프 — 보통 펌웨어가 드롭한 record를 의미."""

    prev_seq: int
    next_seq: int
    prev_ts_ns: int
    next_ts_ns: int

    @property
    def dropped_count(self) -> int:
        """건너뛴 시퀀스 번호 개수. seq가 32비트라 wrap 가능성도 고려."""
        diff = (self.next_seq - self.prev_seq - 1) & 0xFFFF_FFFF
        return diff


@dataclass(slots=True)
class TraceStats:
    """단일 dump 파일에 대한 집계 통계."""

    total_records: int = 0
    wrap_markers: int = 0
    truncated_records: int = 0

    by_opcode: Counter[int] = field(default_factory=Counter)
    by_cpu: Counter[int] = field(default_factory=Counter)
    by_flag_bit: Counter[int] = field(default_factory=Counter)

    first_ts_ns: int | None = None
    last_ts_ns: int | None = None

    payload_size_total: int = 0
    payload_size_min: int | None = None
    payload_size_max: int | None = None

    dt_histogram_ns: dict[int, int] = field(default_factory=dict)
    """버킷 상한(ns) → 개수. 모든 DT_BUCKETS_NS 키 + 'overflow'(=0)."""

    dt_min_ns: int | None = None
    dt_max_ns: int | None = None
    dt_total_ns: int = 0
    dt_samples: int = 0

    seq_gaps: list[SeqGap] = field(default_factory=list)

    @property
    def duration_ns(self) -> int:
        if self.first_ts_ns is None or self.last_ts_ns is None:
            return 0
        return self.last_ts_ns - self.first_ts_ns

    @property
    def duration_s(self) -> float:
        return self.duration_ns / 1e9

    @property
    def records_per_sec(self) -> float:
        if self.duration_ns <= 0:
            return 0.0
        return self.total_records / self.duration_s

    @property
    def payload_size_mean(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.payload_size_total / self.total_records

    @property
    def dt_mean_ns(self) -> float:
        if self.dt_samples == 0:
            return 0.0
        return self.dt_total_ns / self.dt_samples

    @property
    def total_dropped(self) -> int:
        return sum(g.dropped_count for g in self.seq_gaps)

    @classmethod
    def compute(cls, records: Iterable[Record]) -> Self:
        stats = cls()
        for bucket in DT_BUCKETS_NS:
            stats.dt_histogram_ns[bucket] = 0
        stats.dt_histogram_ns[0] = 0  # overflow 버킷(상한 초과)

        prev_seq: int | None = None
        prev_ts: int | None = None

        for rec in records:
            hdr = rec.header

            if hdr.flags & HMB_REC_FLAG_WRAP_MARKER:
                stats.wrap_markers += 1
                continue

            stats.total_records += 1
            if hdr.flags & HMB_REC_FLAG_TRUNCATED:
                stats.truncated_records += 1

            stats.by_opcode[hdr.opcode] += 1
            stats.by_cpu[hdr.cpu] += 1
            for bit in range(8):
                if hdr.flags & (1 << bit):
                    stats.by_flag_bit[bit] += 1

            if stats.first_ts_ns is None:
                stats.first_ts_ns = hdr.ts_ns
            stats.last_ts_ns = hdr.ts_ns

            plen = hdr.payload_len
            stats.payload_size_total += plen
            pmin = stats.payload_size_min
            pmax = stats.payload_size_max
            stats.payload_size_min = plen if pmin is None else min(pmin, plen)
            stats.payload_size_max = plen if pmax is None else max(pmax, plen)

            if prev_seq is not None and prev_ts is not None:
                expected = (prev_seq + 1) & 0xFFFF_FFFF
                if hdr.seq != expected:
                    stats.seq_gaps.append(
                        SeqGap(
                            prev_seq=prev_seq,
                            next_seq=hdr.seq,
                            prev_ts_ns=prev_ts,
                            next_ts_ns=hdr.ts_ns,
                        )
                    )

                dt = hdr.ts_ns - prev_ts
                if dt >= 0:
                    stats.dt_samples += 1
                    stats.dt_total_ns += dt
                    stats.dt_min_ns = dt if stats.dt_min_ns is None else min(stats.dt_min_ns, dt)
                    stats.dt_max_ns = dt if stats.dt_max_ns is None else max(stats.dt_max_ns, dt)
                    placed = False
                    for bucket in DT_BUCKETS_NS:
                        if dt <= bucket:
                            stats.dt_histogram_ns[bucket] += 1
                            placed = True
                            break
                    if not placed:
                        stats.dt_histogram_ns[0] += 1

            prev_seq = hdr.seq
            prev_ts = hdr.ts_ns

        return stats


def opcode_label(opcode: int, catalog: dict[int, str] | None = None) -> str:
    """opcode → 사람이 읽을 수 있는 라벨. 모르면 헥스 표기."""
    if catalog and opcode in catalog:
        return f"0x{opcode:04x} ({catalog[opcode]})"
    return f"0x{opcode:04x}"


def format_duration_ns(ns: int) -> str:
    """나노초를 가장 적절한 단위로 포매팅."""
    if ns < 1_000:
        return f"{ns} ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.2f} µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    return f"{ns / 1_000_000_000:.3f} s"


def format_bytes(n: int) -> str:
    """바이트를 KB/MB/GB로 포매팅."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# 알려지지 않은 opcode 카탈로그 — 후속 작업에서 채움.
# 사용자는 자기 펌웨어 opcode 맵을 yaml/json으로 넘길 수 있게 할 예정.
DEFAULT_OPCODE_CATALOG: dict[int, str] = {}
