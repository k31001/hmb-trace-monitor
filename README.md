# hmb-trace-monitor

NVMe SSD의 HMB(Host Memory Buffer)를 활용한 **고속 펌웨어 트레이스
파이프라인**입니다.

SSD 펌웨어가 호스트 RAM에 carve-out된 ring 버퍼(HMB)에 트레이스
레코드를 직접 기록(DMA)하면, 작은 Linux 커널 모듈이 그 ring을 캐릭터
디바이스로 노출하고, 유저스페이스 데몬이 mmap으로 비워 파일에
떨어뜨립니다. Python 도구가 그 파일을 오프라인 디코드합니다.

```
  +-----------+   HMB ring   +-----------+   mmap   +--------+   파일   +----------+
  |  SSD FW   | -----------> |  Kernel   | -------> | Daemon | -------> | Analyzer |
  | (producer)|              |  module   |          |  (C)   |          | (Python) |
  +-----------+              +-----------+          +--------+          +----------+
```

## 문서 사이트

상세 문서는 GitHub Pages로 서비스됩니다.

**▶ <https://k31001.github.io/hmb-trace-monitor/>** (배포 후 활성화)

오프라인에서 보고 싶다면 [docs/](docs/) 디렉토리의 Markdown을 직접 읽으셔도 됩니다.

- [개요](docs/index.md)
- [아키텍처](docs/architecture.md)
- [동작 과정](docs/operation.md)
- [개발 튜토리얼](docs/tutorial.md)
- [트레이스 포맷](docs/trace-format.md)
- [ABI](docs/abi.md)

## 디렉토리 구조

```
kernel/     NVMe 드라이버 패치 + nvme-hmb-trace.ko (GPL-2.0)
daemon/     유저스페이스 consumer (C11, GPL-2.0)
analyzer/   오프라인 디코더 & CLI (Python 3.11+, Apache-2.0)
docs/       바이너리 포맷·ABI 명세 + GitHub Pages 사이트
mock/       QEMU + virtio-nvme 기반 end-to-end 테스트 하네스
```

컴포넌트 인터페이스와 위험 명령 정책은 [CLAUDE.md](CLAUDE.md)에 있습니다.

## 빠른 시작 (호스트에서 안전)

```sh
# 유저스페이스 컴포넌트만 빌드
make

# 커널 모듈 빌드 (호스트 안전, 적재하지 않음)
make kernel

# 전체 린트
make lint
```

## 빠른 시작 (mock 환경)

QEMU 하네스는 모듈을 실제로 적재하고 end-to-end를 돌릴 수 있는
**유일한 장소**입니다.

```sh
make -C mock build-guest-kernel
make -C mock qemu-run
# 게스트 안에서:
#   insmod nvme-hmb-trace.ko
#   hmb-trace-daemon -o /tmp/trace.bin &
#   ./produce-mock-trace
# 호스트로 돌아와서:
uv run --project analyzer hmb-trace-analyze decode /tmp/trace.bin
```

전체 단계는 [docs/tutorial.md](docs/tutorial.md) 참고.

## GitHub Pages 배포 방법

저장소를 GitHub에 푸시한 뒤:

1. **Repository → Settings → Pages → Build and deployment**
2. **Source**를 `GitHub Actions`로 변경.
3. 메인 브랜치에 푸시가 일어나면 `.github/workflows/pages.yml`이
   자동으로 사이트를 빌드/배포합니다.

URL이 `https://<owner>.github.io/hmb-trace-monitor/` 형식이 아닌
다른 도메인이면 `docs/_config.yml`의 `url`/`baseurl`을 조정하세요.

## 상태

스캐폴딩 단계입니다. 실 구현(드라이버 패치, 데몬 consumer 루프,
QEMU mock producer)은 후속 작업입니다.

## 라이선스

- `kernel/`, `daemon/` → GPL-2.0-only
- `analyzer/`, `docs/`, `mock/` → Apache-2.0

전문은 [LICENSES/](LICENSES/)에 있으며, 모든 소스 파일은 SPDX 헤더를
포함합니다.
