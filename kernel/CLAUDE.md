# kernel/ — NVMe 드라이버 패치 + nvme-hmb-trace.ko

라이선스: GPL-2.0-only. 타깃: **Linux 6.6 LTS** (`drivers/nvme/host/`).

## 구성

```
module/      out-of-tree LKM 소스 (nvme_hmb_trace.{c,h}, hmb_ring.h)
patches/     drivers/nvme/host 대상 git format-patch 시리즈
Makefile     KDIR 기반 out-of-tree 빌드 래퍼
Kbuild       모듈용 in-kernel 빌드 디스크립터
```

`module/hmb_ring.h`는 HMB ring/record 레이아웃의 **단일 진실
공급원**입니다. `daemon/include/hmb_ring.h`는 그것의 byte-for-byte
미러입니다.

## 빌드 (호스트, 안전)

```sh
# 기본은 실행 중인 호스트의 헤더 사용. cross 빌드 시 KDIR override.
make modules                # = make -C $(KDIR) M=$(PWD)/module modules
make modules KDIR=/path/to/linux-6.6
make clean
```

`.ko` 빌드는 호스트 안전 작업입니다. **모듈 적재(`insmod`/`modprobe`)는
반드시 `mock/` 안에서만** 수행합니다 — 실행 중인 호스트 커널에 절대
적재하지 않습니다.

## 스타일 & 품질 게이트

- Linux 커널 코딩 스타일(탭 1 = 8칸, K&R 중괄호, 트레일링 스페이스 금지).
- `scripts/checkpatch.pl --strict --no-tree -f <file>` **반드시** 통과.
  - `make checkpatch`로 `module/` + `patches/` 전체에 일괄 실행.
- `sparse`와 `make C=2` 권장. 새로 등장하는 경고는 받아주지 않습니다.
- 외부로 노출되는 모든 심볼은 `EXPORT_SYMBOL_GPL` 사용.
- hot path에서 `printk` 금지 — 필요하면 `trace_printk`나 tracepoint.
- **커널 소스 안의 주석은 영어를 권장**합니다(주류 커널 컨벤션).
  CLAUDE.md 같은 산문 문서만 한국어로 작성.

## 패치 시리즈 워크플로우

NVMe 코어 변경(HMB 분할, 트레이스 consumer를 기존 `nvme_set_host_mem`
경로에 접목)은 `module/`이 아니라 `patches/` 아래의 패치 시리즈로
관리합니다. 재생성:

```sh
git format-patch -v1 -o patches/ --subject-prefix="PATCH nvme" \
    --base=v6.6 origin/nvme-hmb-trace
```

각 패치는 `Signed-off-by:`를 포함하고 `checkpatch.pl --strict`를
통과해야 합니다.

## ABI 규칙

- `struct hmb_ring_hdr` 또는 `struct hmb_record_hdr`의 모든 변경:
  - `module/hmb_ring.h`의 `HMB_TRACE_ABI_VERSION` bump
  - `daemon/include/hmb_ring.h`에 동일 변경 미러
  - `docs/trace-format.md`, `docs/abi.md` 갱신
  - 위 작업을 **모두 같은 커밋**에 담는다
- 새 `ioctl` 번호는 `module/nvme_hmb_trace.h`에 추가. 추후 uapi 헤더
  (`include/uapi/linux/nvme_hmb_trace.h`)를 vendor 하기 시작하면 그쪽에서
  재노출.

## 금지 사항

- 여기서 `insmod` 하지 않는다. 모듈 적재는 `mock/`의 일이다.
- 어떤 테스트 타깃에서도 실 `/dev/nvme*`를 만지지 않는다.
- 새 sysfs 노브를 `docs/abi.md` 갱신 없이 추가하지 않는다.
