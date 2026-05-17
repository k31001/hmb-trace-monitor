# SPDX-License-Identifier: Apache-2.0
"""Dump file을 record 단위로 순회.

``hmb-trace-daemon``이 생성한 dump 파일은 32B 헤더 + payload + 8B 정렬
패딩으로 구성된 record들의 연속이다. 이 모듈은 그 스트림을 lazy하게
순회하는 이터레이터를 제공한다.

설계 메모:
- 큰 파일을 메모리에 올리지 않도록 io.BufferedReader를 사용한다.
- 잘못된 magic을 만나면 즉시 멈추고 명확한 ValueError를 던진다.
- wrap marker는 기본적으로 건너뛰지만, 통계에 잡힐 수 있도록
  ``include_wrap_markers=True`` 옵션으로 받을 수도 있다.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from hmb_trace.format import (
    HMB_REC_FLAG_WRAP_MARKER,
    HMB_RECORD_HDR_SIZE,
    RecordHeader,
)


@dataclass(frozen=True, slots=True)
class Record:
    """디코드된 헤더와 raw 페이로드를 가진 단일 트레이스 record."""

    offset: int
    """dump 파일 안에서의 바이트 오프셋 (record 시작점)"""

    header: RecordHeader
    """32바이트 record 헤더"""

    payload: bytes
    """payload_len 바이트의 raw 페이로드 (정렬 패딩은 제외)"""

    @property
    def total_size(self) -> int:
        """이 record가 파일에서 차지하는 바이트 수 (헤더 + 패딩 포함)."""
        return self.header.total_size

    @property
    def is_wrap_marker(self) -> bool:
        return bool(self.header.flags & HMB_REC_FLAG_WRAP_MARKER)


@contextmanager
def _open_source(source: Path | str | BinaryIO) -> Iterator[BinaryIO]:
    """파일 경로면 열고, 이미 열린 스트림이면 그대로 사용.

    contextmanager가 with 문 안에서 try/finally를 보장하므로 SIM115
    경고는 적용되지 않는다.
    """
    if isinstance(source, (str, Path)):
        fh = open(source, "rb")  # noqa: SIM115
        try:
            yield fh
        finally:
            fh.close()
    else:
        yield source


def iter_records(
    source: Path | str | BinaryIO,
    *,
    include_wrap_markers: bool = False,
) -> Iterator[Record]:
    """dump 파일에서 record를 한 개씩 yield한다.

    Args:
        source: 파일 경로 또는 이미 열린 바이너리 스트림.
        include_wrap_markers: True면 wrap marker도 yield. 기본은 건너뜀.

    Raises:
        ValueError: record 헤더가 truncated이거나 magic이 일치하지 않을 때.
    """
    with _open_source(source) as fh:
        offset = 0
        while True:
            hdr_bytes = fh.read(HMB_RECORD_HDR_SIZE)
            if not hdr_bytes:
                return
            if len(hdr_bytes) < HMB_RECORD_HDR_SIZE:
                raise ValueError(
                    f"truncated record header at offset {offset}: "
                    f"got {len(hdr_bytes)} bytes, expected {HMB_RECORD_HDR_SIZE}"
                )
            header = RecordHeader.unpack(hdr_bytes)
            header.validate()

            padded = header.padded_payload_len
            payload_bytes = fh.read(padded)
            if len(payload_bytes) < padded:
                raise ValueError(
                    f"truncated payload at offset {offset + HMB_RECORD_HDR_SIZE}: "
                    f"got {len(payload_bytes)} bytes, expected {padded}"
                )

            actual_payload = bytes(payload_bytes[: header.payload_len])
            record = Record(offset=offset, header=header, payload=actual_payload)

            if record.is_wrap_marker and not include_wrap_markers:
                offset += record.total_size
                continue

            yield record
            offset += record.total_size


def count_records(source: Path | str | BinaryIO) -> int:
    """파일을 1회 스캔해 record 개수를 센다(wrap marker 제외)."""
    return sum(1 for _ in iter_records(source))


def read_bytes_from_buffer(buf: bytes) -> Iterator[Record]:
    """메모리 상의 바이트 버퍼에서 record를 yield(주로 테스트용)."""
    return iter_records(io.BytesIO(buf))
