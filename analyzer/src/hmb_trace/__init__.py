# SPDX-License-Identifier: Apache-2.0
"""hmb_trace: NVMe HMB 펌웨어 트레이스 dump의 오프라인 디코더."""

from hmb_trace.format import (
    HMB_RECORD_HDR_SIZE,
    HMB_RECORD_MAGIC,
    HMB_RING_HDR_SIZE,
    HMB_TRACE_ABI_VERSION,
    HMB_TRACE_MAGIC,
    RecordHeader,
    RingHeader,
)
from hmb_trace.stats import (
    DT_BUCKETS_NS,
    SeqGap,
    TraceStats,
    format_bytes,
    format_duration_ns,
    opcode_label,
)
from hmb_trace.stream import Record, count_records, iter_records, read_bytes_from_buffer

__all__ = [
    "DT_BUCKETS_NS",
    "HMB_RECORD_HDR_SIZE",
    "HMB_RECORD_MAGIC",
    "HMB_RING_HDR_SIZE",
    "HMB_TRACE_ABI_VERSION",
    "HMB_TRACE_MAGIC",
    "Record",
    "RecordHeader",
    "RingHeader",
    "SeqGap",
    "TraceStats",
    "count_records",
    "format_bytes",
    "format_duration_ns",
    "iter_records",
    "opcode_label",
    "read_bytes_from_buffer",
]

__version__ = "0.1.0"
