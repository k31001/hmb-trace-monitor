# SPDX-License-Identifier: Apache-2.0
"""Binary layout for HMB trace ring and records.

Mirror of ``kernel/module/hmb_ring.h`` / ``daemon/include/hmb_ring.h``.
Authoritative spec: ``docs/trace-format.md``. Any change to constants
or struct layout here MUST be made in lockstep with the C headers and
the spec, and MUST bump ``HMB_TRACE_ABI_VERSION``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import ClassVar, Self

HMB_TRACE_MAGIC: int = 0x54424D48  # b"HMBT" little-endian
HMB_RECORD_MAGIC: int = 0x54434552  # b"RECT" little-endian
HMB_TRACE_ABI_VERSION: int = 1
HMB_RING_HDR_SIZE: int = 64
HMB_RECORD_HDR_SIZE: int = 32
HMB_RECORD_ALIGN: int = 8

# Ring-level flags.
HMB_RING_FLAG_OVERFLOWED: int = 1 << 0
HMB_RING_FLAG_FROZEN: int = 1 << 1

# Record-level flags.
HMB_REC_FLAG_WRAP_MARKER: int = 1 << 0
HMB_REC_FLAG_TRUNCATED: int = 1 << 1


@dataclass(frozen=True, slots=True)
class RingHeader:
    """First 64 bytes of the HMB region."""

    _STRUCT: ClassVar[struct.Struct] = struct.Struct("<IIIIQQII QQQ")

    magic: int
    version: int
    ring_size: int
    record_area_off: int
    head: int
    tail: int
    flags: int
    reserved0: int
    reserved1: int
    reserved2: int
    reserved3: int

    @classmethod
    def unpack(cls, buf: bytes | memoryview) -> Self:
        if len(buf) < HMB_RING_HDR_SIZE:
            raise ValueError(f"need {HMB_RING_HDR_SIZE} bytes, got {len(buf)}")
        fields = cls._STRUCT.unpack_from(buf, 0)
        return cls(*fields)

    def validate(self) -> None:
        if self.magic != HMB_TRACE_MAGIC:
            raise ValueError(f"bad ring magic: {self.magic:#x}")
        if self.version > HMB_TRACE_ABI_VERSION:
            raise ValueError(
                f"ring ABI v{self.version} newer than supported v{HMB_TRACE_ABI_VERSION}"
            )
        if self.ring_size == 0 or (self.ring_size & (self.ring_size - 1)):
            raise ValueError(f"ring_size must be power of 2, got {self.ring_size}")


@dataclass(frozen=True, slots=True)
class RecordHeader:
    """32-byte fixed header preceding every record's payload."""

    _STRUCT: ClassVar[struct.Struct] = struct.Struct("<IIQ HBB HH Q")

    magic: int
    seq: int
    ts_ns: int
    opcode: int
    cpu: int
    flags: int
    payload_len: int
    reserved0: int
    reserved1: int

    @classmethod
    def unpack(cls, buf: bytes | memoryview) -> Self:
        if len(buf) < HMB_RECORD_HDR_SIZE:
            raise ValueError(f"need {HMB_RECORD_HDR_SIZE} bytes, got {len(buf)}")
        fields = cls._STRUCT.unpack_from(buf, 0)
        return cls(*fields)

    def validate(self) -> None:
        if self.magic != HMB_RECORD_MAGIC:
            raise ValueError(f"bad record magic: {self.magic:#x}")

    @property
    def padded_payload_len(self) -> int:
        """payload_len rounded up to HMB_RECORD_ALIGN."""
        return (self.payload_len + HMB_RECORD_ALIGN - 1) & ~(HMB_RECORD_ALIGN - 1)

    @property
    def total_size(self) -> int:
        """Bytes consumed by this record, header + padded payload."""
        return HMB_RECORD_HDR_SIZE + self.padded_payload_len


# Sanity: the struct strings agree with the documented sizes.
assert RingHeader._STRUCT.size == HMB_RING_HDR_SIZE, RingHeader._STRUCT.size
assert RecordHeader._STRUCT.size == HMB_RECORD_HDR_SIZE, RecordHeader._STRUCT.size
