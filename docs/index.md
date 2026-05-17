---
title: 개요
layout: default
nav_order: 1
description: "NVMe SSD HMB(Host Memory Buffer)를 활용한 고속 펌웨어 트레이스 파이프라인"
permalink: /
---

# hmb-trace-monitor
{: .fs-9 }

NVMe SSD 펌웨어가 HMB(Host Memory Buffer) 영역의 링 버퍼에 트레이스 레코드를 적재(producer)하고, 호스트 유저스페이스 데몬이 이를 mmap으로 빨아내 파일로 덤프(consumer)하는 시스템입니다. 펌웨어 디버깅/성능 분석에 필요한 대량의 이벤트를 SSD → 호스트로 고속 전달하는 것이 목적입니다.
{: .fs-5 .fw-300 }

[아키텍처 보기](architecture.html){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[동작 과정](operation.html){: .btn .fs-5 .mb-4 .mb-md-0 .mr-2 }
[튜토리얼 시작](tutorial.html){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## 한눈에 보기

```
   SSD 펌웨어 (producer)
       │  HMB ring buffer (host RAM)에 DMA로 기록
       ▼
   ┌──────────────────────┐
   │  nvme-hmb-trace.ko   │  ─── /dev/nvme-hmb-traceN
   └──────────────────────┘                │ mmap, poll
                                           ▼
                                   hmb-trace-daemon (C11)
                                           │ writev(raw bytes)
                                           ▼
                                       trace.bin
                                           │ 오프라인
                                           ▼
                                  hmb-trace-analyze (Python)
```

## 구성 요소

| 디렉토리      | 언어    | 라이선스    | 역할                                                            |
|---------------|---------|-------------|-----------------------------------------------------------------|
| `kernel/`     | C       | GPL-2.0     | NVMe 드라이버 패치 + `nvme-hmb-trace.ko` (HMB 분할, 캐릭터 디바이스, mmap) |
| `daemon/`     | C (C11) | GPL-2.0     | 유저스페이스 컨슈머. ring을 mmap해 raw 바이트로 덤프            |
| `analyzer/`   | Python  | Apache-2.0  | 오프라인 디코더 / CLI (`hmb-trace-analyze`)                     |
| `docs/`       | 문서    | Apache-2.0  | 바이너리 포맷·ABI 명세(이 사이트)                               |
| `mock/`       | shell   | Apache-2.0  | QEMU + virtio-nvme 기반 테스트 하네스 (위험 명령은 여기서만)    |

## 빠른 시작

```sh
# 호스트에서 안전한 빌드만
make                # daemon + analyzer
make kernel         # 모듈 빌드 (insmod는 하지 않음)
make lint           # checkpatch + -Werror + ruff + mypy

# 분석기를 합성 데이터로 즉시 체험 (펌웨어/모듈 없이도 가능)
uv run --project analyzer hmb-trace-synth /tmp/demo.bin -n 50000 --drop-every 1000
uv run --project analyzer hmb-trace-analyze info /tmp/demo.bin
uv run --project analyzer hmb-trace-analyze report /tmp/demo.bin --open

# 전체 스택을 끝에서 끝까지 돌려 보려면 mock/ 환경에서
make -C mock build-guest-kernel
make -C mock qemu-run
```

자세한 단계는 [개발 튜토리얼](tutorial.html)을 참고하세요. 분석기 단독 사용은
[분석기 & 웹 뷰어](analyzer.html) 페이지에 정리되어 있습니다.

## 문서 구성

- **[아키텍처](architecture.html)** — 컴포넌트 분리, 데이터 흐름, 실패 모드
- **[동작 과정](operation.html)** — HMB 링의 producer/consumer 규약, wrap-around, 동기화
- **[튜토리얼](tutorial.html)** — 개발 환경 셋업부터 trace 한 줄 디코드까지
- **[분석기 & 웹 뷰어](analyzer.html)** — `hmb-trace-analyze` CLI와 HTML 리포트
- **[트레이스 포맷](trace-format.html)** — 바이너리 ABI 명세
- **[ABI](abi.html)** — 캐릭터 디바이스 / ioctl / mmap 인터페이스

## 라이선스

- `kernel/`, `daemon/` → GPL-2.0-only
- `analyzer/`, `docs/`, `mock/` → Apache-2.0

모든 소스 파일은 `SPDX-License-Identifier` 헤더를 포함합니다.
