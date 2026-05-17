# hmb-trace-monitor — 프로젝트 컨텍스트

> NVMe SSD 펌웨어가 HMB(Host Memory Buffer) ring 버퍼에 트레이스
> 레코드를 producer로 적재하고, 유저스페이스 데몬이 캐릭터 디바이스
> 너머의 mmap을 통해 그 ring을 consumer로 비워 파일에 dump하는
> 시스템. Python 분석기가 그 파일을 오프라인 디코드한다.

## 문서 작성 규칙

**모든 산문 문서(README, CLAUDE.md, docs/, GitHub Pages 페이지)는
한국어로 작성한다.** 코드 식별자(struct/필드 이름, 매크로),
SPDX 헤더, `LICENSES/`의 라이선스 본문, 패치 메타데이터만 영어를
유지한다. 새 문서나 기존 문서 수정 시 부분 영문 잔존을 두지 않는다.

## 구성 요소

| 디렉토리      | 언어    | 라이선스    | 역할                                                              |
|---------------|---------|-------------|-------------------------------------------------------------------|
| `kernel/`     | C       | GPL-2.0     | NVMe 드라이버 패치 + `nvme-hmb-trace.ko` (HMB 분할, char device, mmap) |
| `daemon/`     | C (C11) | GPL-2.0     | 유저스페이스 consumer. mmap한 ring을 raw 바이트로 dump            |
| `analyzer/`   | Python  | Apache-2.0  | 오프라인 디코더/CLI (`hmb-trace-analyze`)                         |
| `docs/`       | Markdown| Apache-2.0  | 바이너리 포맷 + ABI 명세(단일 진실 공급원, GitHub Pages 소스)     |
| `mock/`       | shell   | Apache-2.0  | QEMU + virtio-nvme 기반 테스트 하네스                             |

타깃 커널: **Linux 6.6 LTS**. 타깃 QEMU: 8.x 이상 + virtio-nvme.

## 컴포넌트 인터페이스 (ABI)

펌웨어에 노출되는 HMB 영역의 레이아웃:

```
+0x000  struct hmb_ring_hdr   (64 B, docs/trace-format.md 참조)
+0x040  record area (2의 제곱 크기, 8 B 정렬, 랩어라운드)
```

각 record는 고정 **32 B 헤더** + payload_len 바이트의 가변 payload로
구성되며, 8 B로 패딩됩니다.

커널 → 유저스페이스 표면 (`/dev/nvme-hmb-trace0`):
- `ioctl(NVME_HMB_TRACE_GET_INFO)` — ring 크기, record area 오프셋 반환
- `mmap()` — ring(헤더 + record area)의 read-only 뷰
- `poll()` — 새 record가 도착하면 깨움

데몬은 payload를 **해석하지 않는다**. magic, version, payload_len
검증만 수행하고, `head`/`tail`을 추적하며 raw 바이트를 dump 파일로
스트리밍한다. 디코딩은 analyzer의 책임이다.

**ABI 단일 진실 공급원**: `kernel/module/hmb_ring.h`.
`daemon/include/hmb_ring.h`는 byte-for-byte 미러.
변경 시 두 파일 + `docs/trace-format.md` + `analyzer/src/hmb_trace/format.py`
를 **같은 커밋**으로 갱신한다.

## 빌드 진입점

```sh
make            # daemon + analyzer (호스트에서 안전)
make kernel     # 호스트 헤더로 .ko 빌드 (적재는 하지 않음)
make mock-run   # mock/ 에서 QEMU 게스트 부팅
make lint       # checkpatch + -Werror + ruff + mypy
make clean
```

컴포넌트별 단축:

```sh
make -C kernel     modules
make -C daemon
( cd analyzer && uv run hmb-trace-analyze --help )
make -C mock       qemu-run
```

## 위험 명령 정책 (반드시 읽을 것)

다음 명령은 레포 루트나 `mock/` 외 어떤 디렉토리에서도, **CI에서조차도
실행해서는 안 된다.**

- `insmod`, `modprobe`, `rmmod` (`nvme-hmb-trace.ko` 대상)
- `qemu-system-*`, `kvm`
- `/dev/nvme*`, `/sys/class/nvme/*`, 실제 디스크 디바이스에 쓰기
- 블록 디바이스에 대한 `dd`, `mkfs.*`, `parted`, `wipefs`

위 작업이 필요한 단계는 모두 `mock/`에 속한다. mock 환경은 일회용
디스크 이미지와 게스트 커널을 사용하므로 호스트 상태가 그대로
유지된다. 자세한 규칙은 `mock/CLAUDE.md` 참고.

`kernel/`의 호스트 빌드(`make -C kernel modules`)는 .ko 파일만
생성하므로 허용된다. **그 .ko를 실행 중인 호스트 커널에 적재하는
것은 허용되지 않는다.**

## 컨벤션

- **커밋**: 컴포넌트별 prefix (`kernel:`, `daemon:`, `analyzer:`,
  `docs:`, `mock:`).
- **ABI 변경**: `hmb_ring.h`의 버전과 `trace-format.md`를 같은
  커밋에서 함께 bump. minor = 후방 호환 추가, major = 비호환 변경.
- **SPDX 헤더**: 모든 소스/헤더 파일은 컴포넌트 라이선스에 맞는
  `SPDX-License-Identifier:` 줄로 시작.
- **번들 바이너리 금지**. 테스트 벡터는 `docs/test-vectors/` 아래에
  헥스 dump + README로 둔다.

## GitHub Pages

`docs/`는 곧 GitHub Pages 사이트의 소스이다. 배포는
`.github/workflows/pages.yml`이 자동으로 수행한다. 새 페이지를
추가할 때는 Jekyll front matter(`title`, `nav_order`, `permalink`)를
포함하고, 사이트에서 숨기고 싶은 파일은 `docs/_config.yml`의
`exclude` 목록에 추가한다.

## 컴포넌트별 CLAUDE.md

각 서브디렉토리에는 빌드 명령과 스타일 규칙이 담긴 자체 CLAUDE.md가
있다. 그 디렉토리의 파일을 손대기 전 먼저 그 CLAUDE.md를 읽는다.
