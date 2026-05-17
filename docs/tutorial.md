---
title: 개발 튜토리얼
layout: default
nav_order: 4
---

# 개발 튜토리얼
{: .no_toc }

저장소를 클론한 직후부터 mock 환경에서 트레이스 한 줄을 디코드해 보기까지의 과정을 단계별로 안내합니다.
{: .fs-5 .fw-300 }

<details open markdown="block">
  <summary>목차</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## 0. 사전 준비

| 도구           | 버전          | 용도                                       |
|----------------|---------------|--------------------------------------------|
| Linux          | 6.6 LTS 헤더  | 커널 모듈 빌드(호스트 안전)                |
| gcc / clang    | C11 지원      | `daemon/` 빌드                             |
| Python         | 3.11 이상     | `analyzer/`                                |
| [uv](https://docs.astral.sh/uv/) | 최신          | Python 환경/패키지 관리                    |
| QEMU           | 8.x 이상      | mock 환경(`mock/`)                         |
| `git`          | 임의          | 패치 시리즈 관리                           |

호스트 OS는 어느 배포판이든 무방하지만, **모듈을 실제로 적재(`insmod`)하는 동작은 반드시 `mock/`의 QEMU 게스트에서만** 합니다 ([위험 명령 정책](../CLAUDE.html) 참조).

## 1. 저장소 받기

```sh
git clone https://github.com/<your-org>/hmb-trace-monitor.git
cd hmb-trace-monitor
```

레포 구조는 [개요](./) 페이지에 정리되어 있습니다. 컴포넌트별 빌드/스타일 규칙은 각 디렉토리의 `CLAUDE.md`를 따릅니다.

## 2. 호스트에서 안전한 빌드

전체 유저스페이스를 한 번에 빌드하려면:

```sh
make            # daemon + analyzer
```

개별 컴포넌트:

```sh
make -C daemon              # ./daemon/hmb-trace-daemon 생성
make -C daemon debug        # ASan + UBSan + -O0 -g
make -C analyzer sync       # uv가 .venv 생성, dev 의존성 설치
make -C analyzer lint       # ruff + mypy
make -C analyzer test       # pytest
```

커널 모듈도 호스트 헤더로 빌드만 해 볼 수 있습니다(적재는 금지).

```sh
make -C kernel modules      # nvme_hmb_trace.ko 생성
make -C kernel checkpatch   # Linux 코딩 스타일 검사 (--strict)
```

다른 커널 트리에 대해 빌드하려면:

```sh
make -C kernel modules KDIR=/path/to/linux-6.6
```

## 3. ABI 변경 절차

`struct hmb_ring_hdr` 또는 `struct hmb_record_hdr`의 어떤 필드라도 손대면 다음 파일을 **같은 커밋 안에서 모두** 갱신해야 합니다.

1. `kernel/module/hmb_ring.h` — 단일 진실 공급원
2. `daemon/include/hmb_ring.h` — 바이트 단위 미러
3. `analyzer/src/hmb_trace/format.py` — `struct.Struct` 포맷 문자열과 dataclass 필드
4. `docs/trace-format.md` — 오프셋·타입 표
5. `HMB_TRACE_ABI_VERSION` 상수 bump (위 1·2·3)

마이너 bump는 새 플래그 비트 추가 등 후방 호환 변경에만, 메이저 bump는 오프셋/크기/의미 변경에 사용합니다.

> CI에 등록 예정: 4개 파일의 `HMB_TRACE_ABI_VERSION`이 모두 같은지, 그리고 C 헤더 두 개의 struct 정의가 byte-for-byte 동일한지 검사.

## 4. mock 환경에서 end-to-end 돌려 보기

`mock/`은 QEMU 게스트 안에서 모든 위험 명령(`insmod`, qemu, 디스크 이미지 조작)을 격리합니다.

### 4.1. 게스트 커널 빌드

```sh
make -C mock build-guest-kernel     # linux-6.6.x 를 받아 빌드
```

이 단계는 `kernel/patches/*.patch`를 게스트 트리에 적용한 후 `bzImage`를 생성합니다.

### 4.2. 디스크 이미지 준비

```sh
make -C mock image                  # mock/build/rootfs.qcow2 생성
```

작고 일회용인 루트파일시스템을 만듭니다. 호스트의 어떤 블록 디바이스도 건드리지 않습니다.

### 4.3. 게스트 부팅

```sh
make -C mock qemu-run
```

QEMU가 부팅하며, 호스트의 저장소가 게스트 안 `/repo`로 9p/virtiofs 마운트됩니다. 게스트 안에서 곧바로 모듈을 빌드해 적재할 수 있습니다.

### 4.4. 게스트 안에서 트레이스 흘려 보기

```sh
# (게스트 셸)
cd /repo
make -C kernel modules KDIR=/usr/src/linux
sudo ./mock/scripts/load-module.sh /repo/kernel/module/nvme_hmb_trace.ko load

make -C daemon
sudo ./daemon/hmb-trace-daemon -o /tmp/trace.bin &

# mock 환경의 QEMU-side producer가 합성된 record들을 흘려보냄
./mock/scripts/produce-mock-trace      # (스캐폴딩, 추후 구현)

sudo kill %1
sync
```

`/tmp/trace.bin`은 9p 마운트를 통해 호스트의 `mock/work/trace.bin`으로 그대로 보입니다.

### 4.5. 호스트에서 분석

```sh
# (호스트 셸)
uv run --project analyzer hmb-trace-analyze decode mock/work/trace.bin
uv run --project analyzer hmb-trace-analyze stats  mock/work/trace.bin
```

## 5. 새 트레이스 이벤트 추가하기

새 opcode를 도입하는 일은 보통 ABI 변경이 아닙니다 — `opcode`는 펌웨어 정의 식별자이기 때문입니다. 다음만 갱신하세요.

1. 펌웨어 측에서 새 opcode 번호와 payload 구조를 정의.
2. `analyzer/src/hmb_trace/`에 해당 opcode 디코더(클래스/함수) 추가, 단위 테스트도 함께.
3. `docs/trace-format.md`의 "opcode 카탈로그" 섹션(향후 추가 예정)에 한 줄 등록.

## 6. 자주 마주치는 문제

| 증상                                        | 원인                              | 해결                                            |
|---------------------------------------------|-----------------------------------|-------------------------------------------------|
| `daemon`이 즉시 `ENODEV`로 종료              | 모듈이 적재되지 않음              | 게스트에서 `lsmod | grep nvme_hmb_trace` 확인   |
| `magic mismatch` abort                      | ring 손상 또는 ABI 버전 불일치    | `version` 비교, dump 보존 후 재현 시나리오 작성 |
| `version newer than supported`              | 분석기가 구버전                   | 분석기/헤더 ABI 버전을 일치시킨 후 다시 빌드    |
| `make -C kernel checkpatch`가 SCRIPT 미발견 | `KDIR` 미설정                     | `make -C kernel checkpatch KDIR=/path/to/linux` |

## 7. 다음 단계

- 컨슈머 루프(`daemon/src/ring.c`) 실제 구현
- QEMU-side mock HMB producer 패치(`mock/qemu/nvme-hmb-overlay.patch`) 작성
- `docs/test-vectors/v1/` 골든 파일 추가 및 `tests/test_format.py` 라운드트립 테스트
- `kernel/patches/0001-*` 실제 NVMe core 변경으로 교체

여기까지 따라오셨다면 [동작 과정](operation.html) 문서로 돌아가 producer/consumer 규약을 다시 한 번 점검하는 것을 권합니다.
