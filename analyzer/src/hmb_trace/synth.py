# SPDX-License-Identifier: Apache-2.0
"""합성 트레이스 dump 생성기.

실제 펌웨어/QEMU mock producer가 준비되기 전에도 분석기/리포트 기능을
연습해 볼 수 있도록 그럴듯한 dump 파일을 만들어 준다. 사용자 친화 옵션
몇 가지(시퀀스 드롭 강제, 트렁케이션, wrap marker 삽입)도 지원한다.

CLI 진입점: ``hmb-trace-synth`` (pyproject.toml에 등록).
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from hmb_trace.format import (
    HMB_REC_FLAG_TRUNCATED,
    HMB_REC_FLAG_WRAP_MARKER,
    HMB_RECORD_ALIGN,
    HMB_RECORD_MAGIC,
    RecordHeader,
)

# 데모용 가짜 opcode 카탈로그.
DEMO_OPCODES: dict[int, str] = {
    0x0001: "NAND_READ",
    0x0002: "NAND_PROGRAM",
    0x0003: "NAND_ERASE",
    0x0010: "FTL_GC_START",
    0x0011: "FTL_GC_END",
    0x0020: "L2P_LOOKUP",
    0x0030: "DMA_SUBMIT",
    0x0031: "DMA_COMPLETE",
    0x00F0: "ERROR",
}


@dataclass(slots=True)
class SynthOptions:
    """합성 dump의 생성 파라미터."""

    count: int = 10_000
    cpus: int = 4
    seed: int = 0
    base_ts_ns: int = 0
    avg_payload: int = 48
    max_payload: int = 256
    drop_every: int = 0
    """0이 아니면 매 N번째 record를 드롭(시퀀스 갭 생성)."""
    truncate_every: int = 0
    """0이 아니면 매 N번째 record에 HMB_REC_FLAG_TRUNCATED 표시."""
    wrap_every: int = 0
    """0이 아니면 매 N번째에 wrap marker 삽입."""


def _pack_record(hdr: RecordHeader, payload: bytes) -> bytes:
    """record 한 개를 8B 정렬로 직렬화한다."""
    hdr_bytes = hdr._STRUCT.pack(
        hdr.magic,
        hdr.seq,
        hdr.ts_ns,
        hdr.opcode,
        hdr.cpu,
        hdr.flags,
        hdr.payload_len,
        hdr.reserved0,
        hdr.reserved1,
    )
    pad = (HMB_RECORD_ALIGN - len(payload) % HMB_RECORD_ALIGN) % HMB_RECORD_ALIGN
    return hdr_bytes + payload + b"\x00" * pad


def _opcode_choices(rng: random.Random) -> list[int]:
    """현실에 가까운 분포 — 자주 쓰는 opcode가 더 자주 등장."""
    weights = {
        0x0001: 40,
        0x0002: 25,
        0x0003: 3,
        0x0010: 4,
        0x0011: 4,
        0x0020: 15,
        0x0030: 4,
        0x0031: 4,
        0x00F0: 1,
    }
    bag: list[int] = []
    for op, w in weights.items():
        bag.extend([op] * w)
    rng.shuffle(bag)
    return bag


def generate(opts: SynthOptions) -> Iterator[bytes]:
    """합성된 record 바이트들을 lazy하게 yield한다."""
    rng = random.Random(opts.seed)
    bag = _opcode_choices(rng)
    seq = 0
    ts = opts.base_ts_ns or rng.randint(10_000_000_000, 100_000_000_000)

    for i in range(opts.count):
        # 드롭: 시퀀스 번호만 건너뛰고 record 자체는 만들지 않는다.
        if opts.drop_every and i > 0 and i % opts.drop_every == 0:
            seq = (seq + rng.randint(1, 3)) & 0xFFFF_FFFF
            continue

        # wrap marker 삽입
        if opts.wrap_every and i > 0 and i % opts.wrap_every == 0:
            wmh = RecordHeader(
                magic=HMB_RECORD_MAGIC,
                seq=seq,
                ts_ns=ts,
                opcode=0,
                cpu=0,
                flags=HMB_REC_FLAG_WRAP_MARKER,
                payload_len=0,
                reserved0=0,
                reserved1=0,
            )
            yield _pack_record(wmh, b"")
            seq = (seq + 1) & 0xFFFF_FFFF
            ts += rng.randint(50, 5_000)

        opcode = rng.choice(bag)
        cpu = rng.randint(0, max(0, opts.cpus - 1))
        # 평균 근처에서 흔들리는 payload 크기, 가끔 큰 게 끼어 들도록.
        if rng.random() < 0.02:
            payload_len = rng.randint(opts.max_payload // 2, opts.max_payload)
        else:
            payload_len = max(0, int(rng.gauss(opts.avg_payload, opts.avg_payload / 2)))
            payload_len = min(payload_len, opts.max_payload)

        flags = 0
        if opts.truncate_every and i > 0 and i % opts.truncate_every == 0:
            flags |= HMB_REC_FLAG_TRUNCATED

        hdr = RecordHeader(
            magic=HMB_RECORD_MAGIC,
            seq=seq,
            ts_ns=ts,
            opcode=opcode,
            cpu=cpu,
            flags=flags,
            payload_len=payload_len,
            reserved0=0,
            reserved1=0,
        )
        payload = bytes(rng.randrange(256) for _ in range(payload_len))
        yield _pack_record(hdr, payload)

        seq = (seq + 1) & 0xFFFF_FFFF
        # opcode별로 약간 다른 평균 dt — 실제 펌웨어 burst를 흉내.
        if opcode in (0x0001, 0x0020):
            ts += rng.randint(500, 5_000)
        elif opcode in (0x0010, 0x0011):
            ts += rng.randint(100_000, 5_000_000)
        else:
            ts += rng.randint(1_000, 50_000)


def write(path: Path | str, opts: SynthOptions) -> int:
    """합성 dump를 파일에 쓰고 총 바이트 수를 반환한다."""
    total = 0
    with open(path, "wb") as fh:
        for chunk in generate(opts):
            fh.write(chunk)
            total += len(chunk)
    return total


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hmb-trace-synth",
        description="HMB 트레이스 dump 합성기 — 분석기/리포트 데모 및 테스트용",
    )
    p.add_argument("output", type=Path, help="출력 파일 경로")
    p.add_argument("-n", "--count", type=int, default=10_000, help="생성할 record 수")
    p.add_argument("--cpus", type=int, default=4, help="가상 CPU 개수")
    p.add_argument("--seed", type=int, default=0, help="난수 시드 (재현 가능)")
    p.add_argument("--avg-payload", type=int, default=48, help="payload 평균 길이(B)")
    p.add_argument("--max-payload", type=int, default=256, help="payload 최대 길이(B)")
    p.add_argument("--drop-every", type=int, default=0, help="매 N개마다 시퀀스 드롭 강제 (0=off)")
    p.add_argument("--truncate-every", type=int, default=0, help="매 N개마다 TRUNCATED 플래그 (0=off)")
    p.add_argument("--wrap-every", type=int, default=0, help="매 N개마다 wrap marker 삽입 (0=off)")
    args = p.parse_args(argv)

    opts = SynthOptions(
        count=args.count,
        cpus=args.cpus,
        seed=args.seed,
        avg_payload=args.avg_payload,
        max_payload=args.max_payload,
        drop_every=args.drop_every,
        truncate_every=args.truncate_every,
        wrap_every=args.wrap_every,
    )
    total = write(args.output, opts)
    print(f"wrote {total} bytes to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
