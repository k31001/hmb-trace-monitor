# SPDX-License-Identifier: Apache-2.0
"""struct 직렬화/역직렬화 라운드트립."""

from __future__ import annotations

import pytest

from hmb_trace.format import (
    HMB_RECORD_HDR_SIZE,
    HMB_RECORD_MAGIC,
    HMB_RING_HDR_SIZE,
    HMB_TRACE_ABI_VERSION,
    HMB_TRACE_MAGIC,
    RecordHeader,
    RingHeader,
)


def test_struct_sizes_are_64_and_32() -> None:
    assert RingHeader._STRUCT.size == HMB_RING_HDR_SIZE == 64
    assert RecordHeader._STRUCT.size == HMB_RECORD_HDR_SIZE == 32


def test_record_header_roundtrip() -> None:
    h = RecordHeader(
        magic=HMB_RECORD_MAGIC,
        seq=42,
        ts_ns=1_234_567_890,
        opcode=0x0020,
        cpu=3,
        flags=0x02,
        payload_len=17,
        reserved0=0,
        reserved1=0,
    )
    buf = RecordHeader._STRUCT.pack(
        h.magic,
        h.seq,
        h.ts_ns,
        h.opcode,
        h.cpu,
        h.flags,
        h.payload_len,
        h.reserved0,
        h.reserved1,
    )
    assert len(buf) == HMB_RECORD_HDR_SIZE
    decoded = RecordHeader.unpack(buf)
    assert decoded == h
    decoded.validate()


def test_record_header_padded_payload_len() -> None:
    h = RecordHeader(
        magic=HMB_RECORD_MAGIC,
        seq=0,
        ts_ns=0,
        opcode=0,
        cpu=0,
        flags=0,
        payload_len=17,
        reserved0=0,
        reserved1=0,
    )
    # 17 → 24 (next 8-byte boundary)
    assert h.padded_payload_len == 24
    assert h.total_size == 32 + 24


def test_record_header_rejects_bad_magic() -> None:
    h = RecordHeader(
        magic=0xDEADBEEF,
        seq=0,
        ts_ns=0,
        opcode=0,
        cpu=0,
        flags=0,
        payload_len=0,
        reserved0=0,
        reserved1=0,
    )
    with pytest.raises(ValueError, match="bad record magic"):
        h.validate()


def test_ring_header_rejects_future_version() -> None:
    h = RingHeader(
        magic=HMB_TRACE_MAGIC,
        version=HMB_TRACE_ABI_VERSION + 1,
        ring_size=4096,
        record_area_off=0x40,
        head=0,
        tail=0,
        flags=0,
        reserved0=0,
        reserved1=0,
        reserved2=0,
        reserved3=0,
    )
    with pytest.raises(ValueError, match="newer than supported"):
        h.validate()


def test_ring_header_rejects_non_power_of_two_size() -> None:
    h = RingHeader(
        magic=HMB_TRACE_MAGIC,
        version=HMB_TRACE_ABI_VERSION,
        ring_size=4000,
        record_area_off=0x40,
        head=0,
        tail=0,
        flags=0,
        reserved0=0,
        reserved1=0,
        reserved2=0,
        reserved3=0,
    )
    with pytest.raises(ValueError, match="power of 2"):
        h.validate()
