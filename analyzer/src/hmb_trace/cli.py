# SPDX-License-Identifier: Apache-2.0
"""``hmb-trace-analyze`` CLI 진입점.

서브커맨드:
- ``info``     dump의 빠른 요약 (디폴트)
- ``stats``    상세 통계 (rich 테이블/패널)
- ``decode``   레코드를 사람이 읽을 수 있게 dump
- ``filter``   opcode/cpu/시간 범위로 필터링해 텍스트로 출력
- ``convert``  CSV / JSON Lines로 export (확장자로 결정)
- ``gaps``     시퀀스 갭(드롭) 목록
- ``report``   셀프-컨테인드 HTML 리포트 생성 (웹 뷰어)

종속성으로 ``rich`` 만 추가. 시스템에 컬러가 없거나 파이프되면 자동으로
plain 모드로 떨어진다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import webbrowser
from collections.abc import Iterator, Sequence
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from hmb_trace import (
    HMB_RECORD_HDR_SIZE,
    HMB_RING_HDR_SIZE,
    HMB_TRACE_ABI_VERSION,
    __version__,
)
from hmb_trace.report import DEFAULT_MAX_TABLE_ROWS, write_report
from hmb_trace.stats import (
    DT_BUCKETS_NS,
    TraceStats,
    format_bytes,
    format_duration_ns,
    opcode_label,
)
from hmb_trace.stream import Record, iter_records

# 데모용 기본 opcode 카탈로그 — synth가 생성하는 값과 맞춤.
DEFAULT_CATALOG: dict[int, str] = {
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


def _load_catalog(path: Path | None) -> dict[int, str]:
    """opcode → 이름 카탈로그를 JSON 파일에서 로드. 없으면 기본 사용."""
    if path is None:
        return dict(DEFAULT_CATALOG)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(k, 0): str(v) for k, v in raw.items()}


def _parse_int(s: str) -> int:
    return int(s, 0)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hmb-trace-analyze",
        description="NVMe HMB 트레이스 dump를 디코드/분석/시각화한다.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="opcode→이름 JSON 카탈로그 파일 (없으면 빌트인 데모 카탈로그)",
    )
    p.add_argument("--no-color", action="store_true", help="컬러 출력 비활성화")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("info", help="빠른 요약 (총 record, 시간 범위, 경고)")
    pi.add_argument("dump", type=Path)

    ps = sub.add_parser("stats", help="상세 통계: opcode/cpu/dt 분포, 갭")
    ps.add_argument("dump", type=Path)
    ps.add_argument("--top", type=int, default=10, help="상위 N개만 표시")

    pd = sub.add_parser("decode", help="record를 텍스트 한 줄씩 dump")
    pd.add_argument("dump", type=Path)
    pd.add_argument("-n", "--limit", type=int, default=20, help="앞에서 N개만 (0=전부)")
    pd.add_argument("--show-payload", action="store_true", help="payload hex 미리보기 표시")

    pf = sub.add_parser("filter", help="opcode/cpu/ts 범위로 필터링")
    pf.add_argument("dump", type=Path)
    pf.add_argument(
        "--opcode", type=_parse_int, action="append", default=[], help="이 opcode만 (반복 가능, 0x16진/10진)"
    )
    pf.add_argument("--cpu", type=_parse_int, action="append", default=[], help="이 cpu만 (반복 가능)")
    pf.add_argument("--from-ts", type=int, default=None, help="이 ts_ns 이상 (ns)")
    pf.add_argument("--to-ts", type=int, default=None, help="이 ts_ns 미만 (ns)")
    pf.add_argument("-n", "--limit", type=int, default=100, help="최대 출력 행 (0=전부)")

    pc = sub.add_parser("convert", help="CSV/JSONL로 export")
    pc.add_argument("dump", type=Path)
    pc.add_argument("out", type=Path, help="확장자로 포맷 결정 (.csv, .jsonl)")
    pc.add_argument("--include-payload", action="store_true", help="payload를 hex 문자열로 함께 export")

    pg = sub.add_parser("gaps", help="시퀀스 갭(드롭 추정) 목록")
    pg.add_argument("dump", type=Path)
    pg.add_argument("-n", "--limit", type=int, default=50)

    pr = sub.add_parser("report", help="셀프-컨테인드 HTML 리포트 생성 (웹 뷰어)")
    pr.add_argument("dump", type=Path)
    pr.add_argument("-o", "--output", type=Path, default=None, help="기본: <dump>.report.html")
    pr.add_argument(
        "--max-table-rows",
        type=int,
        default=DEFAULT_MAX_TABLE_ROWS,
        help="HTML 테이블에 박을 record 최대 행 수",
    )
    pr.add_argument("--open", action="store_true", help="생성 후 기본 브라우저로 열기")

    return p


# ---------- helpers ----------


def _console(no_color: bool) -> Console:
    return Console(
        no_color=no_color,
        force_terminal=False if no_color else None,
        highlight=False,
        soft_wrap=True,
    )


def _filtered(
    dump: Path,
    *,
    opcodes: Sequence[int] = (),
    cpus: Sequence[int] = (),
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> Iterator[Record]:
    op_set = set(opcodes) if opcodes else None
    cpu_set = set(cpus) if cpus else None
    for r in iter_records(dump):
        h = r.header
        if op_set is not None and h.opcode not in op_set:
            continue
        if cpu_set is not None and h.cpu not in cpu_set:
            continue
        if from_ts is not None and h.ts_ns < from_ts:
            continue
        if to_ts is not None and h.ts_ns >= to_ts:
            continue
        yield r


def _format_record_line(r: Record, catalog: dict[int, str], *, show_payload: bool) -> str:
    h = r.header
    flag_str = ""
    if h.flags:
        names = []
        if h.flags & 0x01:
            names.append("WRAP")
        if h.flags & 0x02:
            names.append("TRUNCATED")
        flag_str = " [" + ",".join(names) + "]"
    line = (
        f"#{h.seq:10d}  ts={h.ts_ns / 1e6:>12.3f}ms  "
        f"op={opcode_label(h.opcode, catalog):<22s}  "
        f"cpu={h.cpu:>2d}  len={h.payload_len:>4d}{flag_str}"
    )
    if show_payload and r.payload:
        head = " ".join(f"{b:02x}" for b in r.payload[:16])
        if len(r.payload) > 16:
            head += " …"
        line += f"\n    payload: {head}"
    return line


# ---------- commands ----------


def _cmd_info(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    dump: Path = args.dump
    size = dump.stat().st_size
    stats = TraceStats.compute(iter_records(dump))

    panel = Table.grid(padding=(0, 2))
    panel.add_column(style="dim")
    panel.add_column()
    panel.add_row("소스", str(dump))
    panel.add_row("크기", format_bytes(size))
    panel.add_row(
        "ABI",
        f"v{HMB_TRACE_ABI_VERSION} · ring_hdr={HMB_RING_HDR_SIZE}B · rec_hdr={HMB_RECORD_HDR_SIZE}B",
    )
    panel.add_row("총 record", f"{stats.total_records:,}")
    panel.add_row("기간", format_duration_ns(stats.duration_ns))
    panel.add_row("Records/sec", f"{stats.records_per_sec:,.0f}")
    panel.add_row("payload 평균", f"{stats.payload_size_mean:.1f} B")
    panel.add_row("Opcodes", f"{len(stats.by_opcode)} 개")
    panel.add_row("CPUs", f"{len(stats.by_cpu)} 개")

    warn_lines = []
    if stats.truncated_records:
        warn_lines.append(f"[yellow]TRUNCATED: {stats.truncated_records:,}건[/yellow]")
    if stats.wrap_markers:
        warn_lines.append(f"[yellow]WRAP marker: {stats.wrap_markers:,}건[/yellow]")
    if stats.seq_gaps:
        warn_lines.append(
            f"[red]시퀀스 갭: {len(stats.seq_gaps):,}건 · 추정 드롭 {stats.total_dropped:,}건[/red]"
        )

    console.print(Panel(panel, title="hmb-trace info", border_style="cyan"))
    if warn_lines:
        console.print(Panel("\n".join(warn_lines), title="경고", border_style="yellow"))
    else:
        console.print("[green]경고 없음.[/green]")
    return 0


def _cmd_stats(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    dump: Path = args.dump
    stats = TraceStats.compute(iter_records(dump))

    # opcode 분포
    op_table = Table(title="Opcode 분포", box=box.SIMPLE_HEAD, expand=False)
    op_table.add_column("opcode", style="cyan")
    op_table.add_column("이름", style="dim")
    op_table.add_column("count", justify="right")
    op_table.add_column("비율", justify="right")
    op_total = sum(stats.by_opcode.values()) or 1
    for op, cnt in stats.by_opcode.most_common(args.top):
        op_table.add_row(f"0x{op:04x}", catalog.get(op, ""), f"{cnt:,}", f"{cnt * 100 / op_total:.1f}%")
    console.print(op_table)

    # CPU 분포
    cpu_table = Table(title="CPU 분포", box=box.SIMPLE_HEAD)
    cpu_table.add_column("cpu", justify="right", style="cyan")
    cpu_table.add_column("count", justify="right")
    cpu_table.add_column("비율", justify="right")
    cpu_total = sum(stats.by_cpu.values()) or 1
    for cpu, cnt in sorted(stats.by_cpu.items()):
        cpu_table.add_row(str(cpu), f"{cnt:,}", f"{cnt * 100 / cpu_total:.1f}%")
    console.print(cpu_table)

    # dt 히스토그램
    dt_table = Table(title="인접 record dt 히스토그램", box=box.SIMPLE_HEAD)
    dt_table.add_column("≤", justify="right", style="cyan")
    dt_table.add_column("count", justify="right")
    dt_table.add_column("비율", justify="right")
    dt_total = sum(stats.dt_histogram_ns.values()) or 1
    for bucket in DT_BUCKETS_NS:
        cnt = stats.dt_histogram_ns.get(bucket, 0)
        dt_table.add_row(format_duration_ns(bucket), f"{cnt:,}", f"{cnt * 100 / dt_total:.1f}%")
    over = stats.dt_histogram_ns.get(0, 0)
    dt_table.add_row(
        f"> {format_duration_ns(DT_BUCKETS_NS[-1])}", f"{over:,}", f"{over * 100 / dt_total:.1f}%"
    )
    console.print(dt_table)

    # 요약 한 줄
    console.print(
        Text.from_markup(
            f"dt min/avg/max: "
            f"[cyan]{format_duration_ns(stats.dt_min_ns or 0)}[/cyan] / "
            f"[cyan]{format_duration_ns(int(stats.dt_mean_ns))}[/cyan] / "
            f"[cyan]{format_duration_ns(stats.dt_max_ns or 0)}[/cyan]  ·  "
            f"payload min/avg/max: "
            f"[cyan]{stats.payload_size_min or 0}[/cyan] / "
            f"[cyan]{stats.payload_size_mean:.1f}[/cyan] / "
            f"[cyan]{stats.payload_size_max or 0}[/cyan] B"
        )
    )

    if stats.seq_gaps:
        console.print(
            f"[red]시퀀스 갭 {len(stats.seq_gaps):,}건 · 추정 드롭 {stats.total_dropped:,}건[/red] "
            f"(자세히는 `gaps` 서브커맨드)"
        )
    return 0


def _cmd_decode(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    n = 0
    for i, r in enumerate(iter_records(args.dump), start=1):
        console.print(_format_record_line(r, catalog, show_payload=args.show_payload))
        n = i
        if args.limit and n >= args.limit:
            break
    return 0


def _cmd_filter(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    n = 0
    matched = 0
    for r in _filtered(
        args.dump,
        opcodes=args.opcode,
        cpus=args.cpu,
        from_ts=args.from_ts,
        to_ts=args.to_ts,
    ):
        matched += 1
        if args.limit and n >= args.limit:
            continue
        console.print(_format_record_line(r, catalog, show_payload=False))
        n += 1
    console.print(f"[dim]matched {matched:,}건 (출력 {n:,})[/dim]")
    return 0


def _cmd_convert(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    out: Path = args.out
    suffix = out.suffix.lower()
    if suffix not in (".csv", ".jsonl", ".json"):
        console.print(f"[red]지원하지 않는 확장자: {suffix}. .csv 또는 .jsonl 을 사용하세요.[/red]")
        return 2

    cols = ["offset", "seq", "ts_ns", "opcode", "opcode_label", "cpu", "flags", "payload_len"]
    if args.include_payload:
        cols.append("payload_hex")

    written = 0
    if suffix == ".csv":
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in iter_records(args.dump):
                row = [
                    r.offset,
                    r.header.seq,
                    r.header.ts_ns,
                    f"0x{r.header.opcode:04x}",
                    catalog.get(r.header.opcode, ""),
                    r.header.cpu,
                    f"0x{r.header.flags:02x}",
                    r.header.payload_len,
                ]
                if args.include_payload:
                    row.append(r.payload.hex())
                w.writerow(row)
                written += 1
    else:  # jsonl / json (jsonl로 처리)
        with out.open("w", encoding="utf-8") as fh:
            for r in iter_records(args.dump):
                obj: dict[str, object] = {
                    "offset": r.offset,
                    "seq": r.header.seq,
                    "ts_ns": r.header.ts_ns,
                    "opcode": r.header.opcode,
                    "opcode_label": catalog.get(r.header.opcode, ""),
                    "cpu": r.header.cpu,
                    "flags": r.header.flags,
                    "payload_len": r.header.payload_len,
                }
                if args.include_payload:
                    obj["payload_hex"] = r.payload.hex()
                fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
                written += 1
    console.print(f"[green]wrote {written:,} rows → {out}[/green]")
    return 0


def _cmd_gaps(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    stats = TraceStats.compute(iter_records(args.dump))
    if not stats.seq_gaps:
        console.print("[green]시퀀스 갭이 없습니다.[/green]")
        return 0
    table = Table(
        title=f"시퀀스 갭 (총 {len(stats.seq_gaps):,}건 · 드롭 추정 {stats.total_dropped:,}건)",
        box=box.SIMPLE_HEAD,
    )
    table.add_column("이전 seq", justify="right", style="cyan")
    table.add_column("다음 seq", justify="right", style="cyan")
    table.add_column("드롭", justify="right", style="red")
    table.add_column("이전 ts", justify="right")
    table.add_column("다음 ts", justify="right")
    for g in stats.seq_gaps[: args.limit]:
        table.add_row(
            f"{g.prev_seq:,}",
            f"{g.next_seq:,}",
            f"{g.dropped_count:,}",
            format_duration_ns(g.prev_ts_ns),
            format_duration_ns(g.next_ts_ns),
        )
    console.print(table)
    return 0


def _cmd_report(args: argparse.Namespace, console: Console, catalog: dict[int, str]) -> int:
    out: Path = args.output or args.dump.with_suffix(args.dump.suffix + ".report.html")
    console.print(f"[dim]리포트 빌드 중 ({args.dump})...[/dim]")
    written = write_report(
        args.dump,
        out,
        max_table_rows=args.max_table_rows,
        opcode_catalog=catalog,
    )
    console.print(f"[green]wrote report → {written}[/green]")
    if args.open:
        webbrowser.open(written.resolve().as_uri())
    else:
        console.print(f"  브라우저에서 열기: file://{written.resolve()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    console = _console(args.no_color)

    try:
        catalog = _load_catalog(args.catalog)
    except (OSError, ValueError) as e:
        console.print(f"[red]카탈로그 로드 실패: {e}[/red]")
        return 2

    handlers = {
        "info": _cmd_info,
        "stats": _cmd_stats,
        "decode": _cmd_decode,
        "filter": _cmd_filter,
        "convert": _cmd_convert,
        "gaps": _cmd_gaps,
        "report": _cmd_report,
    }
    fn = handlers[args.cmd]

    try:
        return fn(args, console, catalog)
    except FileNotFoundError as e:
        console.print(f"[red]파일을 찾을 수 없습니다: {e.filename}[/red]")
        return 1
    except ValueError as e:
        console.print(f"[red]dump가 손상되었거나 ABI가 일치하지 않습니다: {e}[/red]")
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
