# SPDX-License-Identifier: Apache-2.0
"""셀프-컨테인드 HTML 리포트 생성.

분석기는 외부 CDN을 끌어오지 않는다 — 단일 .html 파일이 오프라인에서
공유/아카이브 가능하도록 모든 CSS와 JS를 인라인한다. 차트는 의존성을
피하려고 CSS bar chart로만 구성한다.

설계 결정:
- 통계는 **전체 record**에 대해 계산하지만, 리포트 안의 record 표는
  성능을 위해 ``max_table_rows``개로 제한한다. 더 큰 분석은 CLI의
  ``filter``/``convert`` 서브커맨드로 처리한다.
- record 테이블은 페이로드 hex 미리보기(앞 16바이트)만 보여준다.
- 페이지는 클라이언트 사이드 필터링/페이지네이션을 vanilla JS로 처리.
"""

from __future__ import annotations

import datetime as dt
import html
import json
from dataclasses import dataclass
from pathlib import Path

from hmb_trace import __version__
from hmb_trace.format import HMB_REC_FLAG_TRUNCATED, HMB_REC_FLAG_WRAP_MARKER
from hmb_trace.stats import DT_BUCKETS_NS, TraceStats, format_bytes
from hmb_trace.stream import Record, iter_records

# 리포트가 한 페이지에 박는 record 행 상한.
DEFAULT_MAX_TABLE_ROWS = 5_000


@dataclass(slots=True)
class ReportInputs:
    """리포트 빌더가 받는 입력 묶음."""

    source_path: str
    source_size_bytes: int
    stats: TraceStats
    records: list[Record]
    opcode_catalog: dict[int, str]
    table_truncated: bool
    """records 리스트가 max_table_rows로 잘렸으면 True."""


def build_report(
    source: Path | str,
    *,
    max_table_rows: int = DEFAULT_MAX_TABLE_ROWS,
    opcode_catalog: dict[int, str] | None = None,
) -> ReportInputs:
    """dump를 두 번 훑어 통계 + 테이블용 record를 수집한다.

    파일이 매우 클 경우 record 전체를 메모리에 들고 있지 않도록,
    테이블에 들어갈 후보(최근 N개)만 ring buffer 식으로 유지한다.
    """
    src_path = Path(source)
    size = src_path.stat().st_size if src_path.exists() else 0

    # 1차: 전체 통계
    stats = TraceStats.compute(iter_records(src_path))

    # 2차: 마지막 N개 record를 테이블용으로 모은다.
    tail: list[Record] = []
    total = 0
    for rec in iter_records(src_path):
        total += 1
        tail.append(rec)
        if len(tail) > max_table_rows:
            tail.pop(0)

    return ReportInputs(
        source_path=str(src_path),
        source_size_bytes=size,
        stats=stats,
        records=tail,
        opcode_catalog=opcode_catalog or {},
        table_truncated=total > max_table_rows,
    )


def _flag_names(flags: int) -> list[str]:
    names: list[str] = []
    if flags & HMB_REC_FLAG_WRAP_MARKER:
        names.append("WRAP")
    if flags & HMB_REC_FLAG_TRUNCATED:
        names.append("TRUNCATED")
    # 미지의 비트
    known = HMB_REC_FLAG_WRAP_MARKER | HMB_REC_FLAG_TRUNCATED
    unknown = flags & ~known & 0xFF
    if unknown:
        names.append(f"0x{unknown:02x}")
    return names


def _hex_preview(payload: bytes, n: int = 16) -> str:
    head = payload[:n]
    spaced = " ".join(f"{b:02x}" for b in head)
    if len(payload) > n:
        spaced += " …"
    return spaced


def _records_to_json(records: list[Record], catalog: dict[int, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for r in records:
        h = r.header
        rows.append(
            {
                "offset": r.offset,
                "seq": h.seq,
                "ts_ns": h.ts_ns,
                "opcode": h.opcode,
                "opcode_label": catalog.get(h.opcode, ""),
                "cpu": h.cpu,
                "flags": h.flags,
                "flag_names": _flag_names(h.flags),
                "payload_len": h.payload_len,
                "payload_hex": _hex_preview(r.payload),
            }
        )
    return rows


def _stats_to_json(stats: TraceStats, catalog: dict[int, str]) -> dict[str, object]:
    return {
        "total_records": stats.total_records,
        "wrap_markers": stats.wrap_markers,
        "truncated_records": stats.truncated_records,
        "first_ts_ns": stats.first_ts_ns,
        "last_ts_ns": stats.last_ts_ns,
        "duration_ns": stats.duration_ns,
        "records_per_sec": stats.records_per_sec,
        "payload_size_min": stats.payload_size_min,
        "payload_size_max": stats.payload_size_max,
        "payload_size_mean": stats.payload_size_mean,
        "payload_size_total": stats.payload_size_total,
        "dt_min_ns": stats.dt_min_ns,
        "dt_max_ns": stats.dt_max_ns,
        "dt_mean_ns": stats.dt_mean_ns,
        "dt_samples": stats.dt_samples,
        "dt_histogram_ns": stats.dt_histogram_ns,
        "by_opcode": [
            {"opcode": op, "label": catalog.get(op, ""), "count": cnt}
            for op, cnt in stats.by_opcode.most_common()
        ],
        "by_cpu": [{"cpu": cpu, "count": cnt} for cpu, cnt in sorted(stats.by_cpu.items())],
        "seq_gaps": [
            {
                "prev_seq": g.prev_seq,
                "next_seq": g.next_seq,
                "prev_ts_ns": g.prev_ts_ns,
                "next_ts_ns": g.next_ts_ns,
                "dropped_count": g.dropped_count,
            }
            for g in stats.seq_gaps[:200]
        ],
        "seq_gap_total_count": len(stats.seq_gaps),
        "total_dropped_estimate": stats.total_dropped,
        "dt_buckets_ns": list(DT_BUCKETS_NS),
    }


# fmt: off
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>HMB Trace Report — __TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
  --bg: #0d1117;
  --bg-panel: #161b22;
  --bg-row: #1c2029;
  --bg-row-alt: #181d25;
  --fg: #e6edf3;
  --fg-dim: #8b949e;
  --accent: #58a6ff;
  --good: #3fb950;
  --warn: #d29922;
  --bad: #f85149;
  --border: #30363d;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans CJK KR", "Apple SD Gothic Neo", sans-serif;
}
header {
  padding: 24px 28px 16px;
  border-bottom: 1px solid var(--border);
}
header h1 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
}
header .meta {
  color: var(--fg-dim);
  font-size: 13px;
  word-break: break-all;
}
main { padding: 24px 28px 64px; max-width: 1200px; }
section { margin-bottom: 32px; }
section h2 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--fg-dim);
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  margin: 0 0 16px;
  font-weight: 600;
}
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px 16px;
}
.card .label { color: var(--fg-dim); font-size: 12px; }
.card .value { font-size: 22px; font-weight: 600; margin-top: 4px; font-variant-numeric: tabular-nums; }
.card .sub { color: var(--fg-dim); font-size: 12px; margin-top: 2px; }
.bars { display: grid; gap: 6px; }
.bar-row { display: grid; grid-template-columns: 220px 1fr auto; align-items: center; gap: 12px; }
.bar-label { color: var(--fg-dim); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { background: var(--bg-panel); border: 1px solid var(--border); height: 18px; border-radius: 3px; overflow: hidden; }
.bar-fill { background: linear-gradient(90deg, #2f81f7, #58a6ff); height: 100%; }
.bar-count { font-variant-numeric: tabular-nums; font-size: 12px; color: var(--fg); min-width: 80px; text-align: right; }
.flags { display: flex; gap: 8px; flex-wrap: wrap; }
.pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid var(--border); background: var(--bg-panel); color: var(--fg-dim); }
.pill.good { color: var(--good); border-color: rgba(63,185,80,.4); }
.pill.warn { color: var(--warn); border-color: rgba(210,153,34,.4); }
.pill.bad  { color: var(--bad); border-color: rgba(248,81,73,.4); }
.controls { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
.controls input, .controls select {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  color: var(--fg);
  padding: 6px 10px;
  font-size: 13px;
  border-radius: 4px;
}
.controls .count { color: var(--fg-dim); font-size: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; font-variant-numeric: tabular-nums; }
th, td {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
th { color: var(--fg-dim); font-weight: 500; text-transform: uppercase; letter-spacing: .05em; font-size: 11px; }
tbody tr:nth-child(odd)  { background: var(--bg-row); }
tbody tr:nth-child(even) { background: var(--bg-row-alt); }
td.mono, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.paginator { display: flex; gap: 6px; align-items: center; margin-top: 10px; font-size: 12px; color: var(--fg-dim); }
.paginator button {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  color: var(--fg);
  padding: 4px 10px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}
.paginator button:disabled { opacity: .4; cursor: default; }
footer { color: var(--fg-dim); font-size: 12px; padding: 16px 28px 32px; border-top: 1px solid var(--border); }
.gap-row { color: var(--warn); }
.gap-row strong { color: var(--bad); }
.dim { color: var(--fg-dim); }
.notice {
  background: rgba(210,153,34,.08);
  border: 1px solid rgba(210,153,34,.3);
  padding: 10px 14px;
  border-radius: 4px;
  color: var(--warn);
  margin-bottom: 16px;
  font-size: 13px;
}
</style>
</head>
<body>
<header>
  <h1>HMB Trace Report</h1>
  <div class="meta">
    소스: <span class="mono">__SOURCE_PATH__</span><br>
    크기: __SOURCE_SIZE__ · 생성: __GENERATED_AT__ · 분석기 v__VERSION__
  </div>
</header>
<main>

<section>
  <h2>요약</h2>
  <div id="summary-cards" class="cards"></div>
  <div id="flag-pills" class="flags" style="margin-top:14px"></div>
  <div id="table-truncated-notice"></div>
</section>

<section>
  <h2>Opcode 분포</h2>
  <div id="opcode-bars" class="bars"></div>
</section>

<section>
  <h2>CPU 분포</h2>
  <div id="cpu-bars" class="bars"></div>
</section>

<section>
  <h2>인접 record 간격 (dt) 히스토그램</h2>
  <div id="dt-bars" class="bars"></div>
</section>

<section>
  <h2>시퀀스 갭 <span class="dim" id="gap-summary"></span></h2>
  <table id="gap-table">
    <thead><tr><th>이전 seq</th><th>다음 seq</th><th>드롭</th><th>이전 ts</th><th>다음 ts</th></tr></thead>
    <tbody></tbody>
  </table>
</section>

<section>
  <h2>레코드 <span class="dim" id="table-total"></span></h2>
  <div class="controls">
    <input id="filter-opcode" placeholder="opcode (10진/0x16진)" size="14">
    <input id="filter-cpu" placeholder="cpu" size="6">
    <input id="filter-flags" placeholder="플래그 이름" size="14">
    <input id="filter-search" placeholder="payload hex 검색" size="20">
    <span class="count" id="filter-count"></span>
  </div>
  <table id="record-table">
    <thead>
      <tr>
        <th>#</th><th>seq</th><th>ts (ms)</th><th>opcode</th><th>cpu</th>
        <th>flags</th><th>payload</th><th>preview</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
  <div class="paginator">
    <button id="prev-page">◀ 이전</button>
    <span id="page-info"></span>
    <button id="next-page">다음 ▶</button>
  </div>
</section>

</main>
<footer>
  hmb-trace-monitor analyzer · 셀프-컨테인드 HTML · 오프라인에서도 동작
</footer>

<script id="report-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  const DATA = JSON.parse(document.getElementById("report-data").textContent);
  const stats = DATA.stats;
  const records = DATA.records;
  const tableTruncated = DATA.table_truncated;

  function fmtInt(n) {
    if (n == null) return "—";
    return n.toLocaleString("ko-KR");
  }
  function fmtNs(ns) {
    if (ns == null || isNaN(ns)) return "—";
    if (ns < 1000) return ns + " ns";
    if (ns < 1e6) return (ns / 1e3).toFixed(2) + " µs";
    if (ns < 1e9) return (ns / 1e6).toFixed(2) + " ms";
    return (ns / 1e9).toFixed(3) + " s";
  }
  function fmtBytes(n) {
    if (n == null) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + " " + units[i];
  }
  function hex16(n) { return "0x" + n.toString(16).padStart(4, "0"); }

  // --- 요약 카드 ---
  const cards = [
    { label: "총 record", value: fmtInt(stats.total_records), sub: stats.wrap_markers + " wrap markers" },
    { label: "기간", value: fmtNs(stats.duration_ns), sub: stats.records_per_sec.toFixed(0) + " rec/s" },
    { label: "payload 평균", value: stats.payload_size_mean.toFixed(1) + " B",
      sub: "min " + (stats.payload_size_min ?? "—") + " · max " + (stats.payload_size_max ?? "—") },
    { label: "dt 평균", value: fmtNs(stats.dt_mean_ns),
      sub: "min " + fmtNs(stats.dt_min_ns) + " · max " + fmtNs(stats.dt_max_ns) },
    { label: "Opcodes", value: fmtInt(stats.by_opcode.length), sub: "고유 opcode 수" },
    { label: "CPUs", value: fmtInt(stats.by_cpu.length), sub: "활성 코어" },
    { label: "Truncated", value: fmtInt(stats.truncated_records), sub: "HMB_REC_FLAG_TRUNCATED" },
    { label: "Seq gaps", value: fmtInt(stats.seq_gap_total_count),
      sub: "드롭 추정 " + fmtInt(stats.total_dropped_estimate) },
  ];
  const cardsEl = document.getElementById("summary-cards");
  cards.forEach(c => {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = "<div class='label'>" + c.label + "</div>" +
                    "<div class='value'>" + c.value + "</div>" +
                    "<div class='sub'>" + c.sub + "</div>";
    cardsEl.appendChild(div);
  });

  // --- 상태 pill ---
  const pillsEl = document.getElementById("flag-pills");
  function pill(label, kind) {
    const s = document.createElement("span");
    s.className = "pill " + (kind || "");
    s.textContent = label;
    return s;
  }
  pillsEl.appendChild(pill(
    stats.truncated_records > 0 ? "TRUNCATED " + stats.truncated_records : "TRUNCATED 0",
    stats.truncated_records > 0 ? "warn" : "good"
  ));
  pillsEl.appendChild(pill(
    stats.seq_gap_total_count > 0 ? "GAPS " + stats.seq_gap_total_count : "GAPS 0",
    stats.seq_gap_total_count > 0 ? "bad" : "good"
  ));
  pillsEl.appendChild(pill(
    stats.wrap_markers > 0 ? "WRAP " + stats.wrap_markers : "WRAP 0",
    "warn"
  ));

  // --- 테이블 truncation 안내 ---
  if (tableTruncated) {
    const notice = document.getElementById("table-truncated-notice");
    notice.className = "notice";
    notice.textContent = "주의: 통계는 전체 record에 대해 계산했지만, 아래 record 테이블은 마지막 " +
      fmtInt(records.length) + "개로 잘렸습니다. 전체를 다루려면 CLI(filter/convert)를 사용하세요.";
  }

  // --- bar 차트 헬퍼 ---
  function renderBars(rootId, items, maxValue) {
    const root = document.getElementById(rootId);
    const max = maxValue || Math.max(...items.map(i => i.count), 1);
    items.forEach(it => {
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = "<div class='bar-label'>" + it.label + "</div>" +
                      "<div class='bar-track'><div class='bar-fill' style='width:" +
                      (it.count * 100 / max).toFixed(2) + "%'></div></div>" +
                      "<div class='bar-count'>" + fmtInt(it.count) +
                      " <span class='dim'>(" + (it.count * 100 / (it.total || 1)).toFixed(1) + "%)</span></div>";
      root.appendChild(row);
    });
  }

  // --- Opcode 분포 ---
  const opTotal = stats.by_opcode.reduce((a, x) => a + x.count, 0);
  renderBars("opcode-bars", stats.by_opcode.map(o => ({
    label: hex16(o.opcode) + (o.label ? "  " + o.label : ""),
    count: o.count, total: opTotal,
  })));

  // --- CPU 분포 ---
  const cpuTotal = stats.by_cpu.reduce((a, x) => a + x.count, 0);
  renderBars("cpu-bars", stats.by_cpu.map(c => ({
    label: "cpu " + c.cpu, count: c.count, total: cpuTotal,
  })));

  // --- dt 히스토그램 ---
  const buckets = stats.dt_buckets_ns;
  const histTotal = Object.values(stats.dt_histogram_ns).reduce((a, b) => a + b, 0);
  const dtItems = buckets.map((b, i) => {
    const prev = i === 0 ? 0 : buckets[i - 1];
    return {
      label: "≤ " + fmtNs(b) + "  (>" + fmtNs(prev) + ")",
      count: stats.dt_histogram_ns[b] || 0,
      total: histTotal,
    };
  });
  dtItems.push({ label: "> " + fmtNs(buckets[buckets.length - 1]),
                 count: stats.dt_histogram_ns[0] || 0, total: histTotal });
  renderBars("dt-bars", dtItems);

  // --- 시퀀스 갭 표 ---
  const gapBody = document.querySelector("#gap-table tbody");
  const gapSummary = document.getElementById("gap-summary");
  if (stats.seq_gaps.length === 0) {
    gapSummary.textContent = "(없음)";
    gapBody.innerHTML = "<tr><td colspan='5' class='dim'>시퀀스 갭이 없습니다.</td></tr>";
  } else {
    gapSummary.textContent = "(상위 " + stats.seq_gaps.length + " / 전체 " +
      stats.seq_gap_total_count + ", 추정 드롭 " + stats.total_dropped_estimate + "건)";
    stats.seq_gaps.forEach(g => {
      const tr = document.createElement("tr");
      tr.className = "gap-row";
      tr.innerHTML = "<td class='mono'>" + fmtInt(g.prev_seq) + "</td>" +
                     "<td class='mono'>" + fmtInt(g.next_seq) + "</td>" +
                     "<td><strong>" + fmtInt(g.dropped_count) + "</strong></td>" +
                     "<td class='mono'>" + fmtNs(g.prev_ts_ns) + "</td>" +
                     "<td class='mono'>" + fmtNs(g.next_ts_ns) + "</td>";
      gapBody.appendChild(tr);
    });
  }

  // --- record 테이블 (필터 + 페이지네이션) ---
  const PAGE_SIZE = 100;
  let page = 0;
  let filtered = records.slice();

  const tbody = document.querySelector("#record-table tbody");
  const pageInfo = document.getElementById("page-info");
  const filterCount = document.getElementById("filter-count");
  const tableTotal = document.getElementById("table-total");
  tableTotal.textContent = "(테이블 " + fmtInt(records.length) + "행)";

  function parseInt0xOrDec(s) {
    if (!s) return null;
    s = s.trim();
    if (!s) return null;
    if (/^0x[0-9a-f]+$/i.test(s)) return parseInt(s, 16);
    if (/^[0-9]+$/.test(s)) return parseInt(s, 10);
    return NaN;
  }

  function applyFilter() {
    const op = parseInt0xOrDec(document.getElementById("filter-opcode").value);
    const cpu = parseInt0xOrDec(document.getElementById("filter-cpu").value);
    const fl = document.getElementById("filter-flags").value.trim().toUpperCase();
    const q = document.getElementById("filter-search").value.trim().toLowerCase();
    filtered = records.filter(r => {
      if (op != null && !isNaN(op) && r.opcode !== op) return false;
      if (cpu != null && !isNaN(cpu) && r.cpu !== cpu) return false;
      if (fl) {
        if (!r.flag_names.some(n => n.includes(fl))) return false;
      }
      if (q && r.payload_hex.toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    page = 0;
    render();
  }

  function render() {
    const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    page = Math.min(page, pages - 1);
    const start = page * PAGE_SIZE;
    const slice = filtered.slice(start, start + PAGE_SIZE);
    tbody.innerHTML = "";
    slice.forEach((r, i) => {
      const tr = document.createElement("tr");
      const flagPills = r.flag_names.length === 0 ? "" :
        r.flag_names.map(n => "<span class='pill'>" + n + "</span>").join(" ");
      tr.innerHTML =
        "<td class='dim mono'>" + (start + i + 1) + "</td>" +
        "<td class='mono'>" + r.seq + "</td>" +
        "<td class='mono'>" + (r.ts_ns / 1e6).toFixed(3) + "</td>" +
        "<td class='mono'>" + hex16(r.opcode) +
          (r.opcode_label ? " <span class='dim'>" + r.opcode_label + "</span>" : "") + "</td>" +
        "<td class='mono'>" + r.cpu + "</td>" +
        "<td>" + flagPills + "</td>" +
        "<td class='mono'>" + r.payload_len + " B</td>" +
        "<td class='mono dim'>" + r.payload_hex + "</td>";
      tbody.appendChild(tr);
    });
    pageInfo.textContent = (page + 1) + " / " + pages + " (" + fmtInt(filtered.length) + "행)";
    filterCount.textContent = "필터: " + fmtInt(filtered.length) + " / " + fmtInt(records.length);
    document.getElementById("prev-page").disabled = page === 0;
    document.getElementById("next-page").disabled = page >= pages - 1;
  }

  document.getElementById("prev-page").onclick = () => { page--; render(); };
  document.getElementById("next-page").onclick = () => { page++; render(); };
  ["filter-opcode", "filter-cpu", "filter-flags", "filter-search"]
    .forEach(id => document.getElementById(id).addEventListener("input", applyFilter));

  render();
})();
</script>
</body>
</html>
"""
# fmt: on


def render(inputs: ReportInputs) -> str:
    """ReportInputs를 단일 HTML 문자열로 렌더링."""
    payload = {
        "stats": _stats_to_json(inputs.stats, inputs.opcode_catalog),
        "records": _records_to_json(inputs.records, inputs.opcode_catalog),
        "table_truncated": inputs.table_truncated,
    }
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # <script> 종료 태그가 데이터 안에 나타나면 XSS 위험. JSON 안에서는 <로 이스케이프.
    data_json = data_json.replace("</", "<\\/")

    return (
        _HTML_TEMPLATE.replace("__TITLE__", html.escape(Path(inputs.source_path).name))
        .replace("__SOURCE_PATH__", html.escape(inputs.source_path))
        .replace("__SOURCE_SIZE__", format_bytes(inputs.source_size_bytes))
        .replace("__GENERATED_AT__", dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
        .replace("__VERSION__", __version__)
        .replace("__DATA_JSON__", data_json)
    )


def write_report(
    source: Path | str,
    out: Path | str,
    *,
    max_table_rows: int = DEFAULT_MAX_TABLE_ROWS,
    opcode_catalog: dict[int, str] | None = None,
) -> Path:
    """리포트를 빌드해 HTML 파일로 저장하고 출력 경로를 반환."""
    inputs = build_report(source, max_table_rows=max_table_rows, opcode_catalog=opcode_catalog)
    html_str = render(inputs)
    out_path = Path(out)
    out_path.write_text(html_str, encoding="utf-8")
    return out_path
