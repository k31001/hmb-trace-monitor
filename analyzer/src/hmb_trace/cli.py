# SPDX-License-Identifier: Apache-2.0
"""``hmb-trace-analyze`` CLI entrypoint.

Scaffolding only — subcommands are stubs that print plan-level intent.
See ``analyzer/CLAUDE.md`` for the planned surface.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from hmb_trace import HMB_RECORD_HDR_SIZE, HMB_RING_HDR_SIZE, HMB_TRACE_ABI_VERSION, __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hmb-trace-analyze",
        description="Decode and analyze NVMe HMB firmware trace dumps.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_decode = sub.add_parser("decode", help="Pretty-print all records in a dump")
    p_decode.add_argument("dump", help="Path to raw dump file")

    p_stats = sub.add_parser("stats", help="Summarize records (counts per opcode/cpu)")
    p_stats.add_argument("dump", help="Path to raw dump file")

    p_conv = sub.add_parser("convert", help="Export records as CSV")
    p_conv.add_argument("dump", help="Path to raw dump file")
    p_conv.add_argument("out", help="Output CSV path")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    print(
        f"hmb-trace-analyze: scaffolding only "
        f"(ABI v{HMB_TRACE_ABI_VERSION}, ring_hdr={HMB_RING_HDR_SIZE}B, "
        f"rec_hdr={HMB_RECORD_HDR_SIZE}B)",
        file=sys.stderr,
    )
    print(f"requested: {args.cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
