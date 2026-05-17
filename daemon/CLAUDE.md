# daemon/ — 유저스페이스 HMB 트레이스 consumer

라이선스: GPL-2.0-only. `nvme-hmb-trace.ko`가 노출한 HMB ring을 mmap해
raw record를 파일로 스트리밍하는 **단일 바이너리 C11 데몬**.

## 구성

```
include/hmb_ring.h   kernel/module/hmb_ring.h 의 byte-for-byte 미러
src/main.c           CLI 진입점, 시그널 처리, 데몬화
src/ring.c           SPSC consumer 루프, 랩어라운드, 길이 검증
src/dumper.c         출력 파일 열기/회전/fsync 정책
Makefile             pkg-config 없는 빌드
```

## 빌드

```sh
make           # ./hmb-trace-daemon 생성
make debug     # -O0 -g -fsanitize=address,undefined
make lint      # -Werror 컴파일 검사
make clean
```

크로스 컴파일:

```sh
make CC=aarch64-linux-gnu-gcc
```

## 스타일

- **C11**, 가능한 한 freestanding-friendly 헤더만 사용.
- 컴파일 플래그: `-std=c11 -Wall -Wextra -Werror -Wshadow -Wconversion
  -Wpointer-arith -Wcast-align -Wstrict-prototypes -pedantic`.
- consume hot path에서 `malloc` 금지 — 버퍼는 `main()`에서 미리
  할당한다.
- 모든 syscall은 반환 검사. `EINTR`은 재시도, 그 외 errno는
  `strerror(errno)`와 함께 로깅하고 상위로 전파.
- 출력은 `write(2)` 루프 (`writev`로 헤더+payload iovec 쌍) 사용.
  data path에서 `stdio` 금지.
- 전역 mutable 상태는 `volatile sig_atomic_t` 한 개의 stop 플래그뿐.
- clang-format 스타일: LLVM base, 4-space 들여쓰기, 100-col 한계.
  `make fmt`로 실행.

## 런타임 계약

- 데몬은 payload를 **디코드하지 않는다**. magic, version, payload_len
  만 검증하고 불일치 시 비제로 종료 코드로 abort.
- `HMB_RING_FLAG_OVERFLOWED`가 set되면 경고 로깅 후 계속 진행 —
  overflow 가시성은 펌웨어의 책임이다.
- 출력 파일은 `O_CLOEXEC | O_CREAT | O_APPEND`로 연다. 회전은 호출자의
  몫(logrotate 등). 데몬은 SIGHUP을 "출력 파일 재오픈" 신호로 해석.

## 테스트

- `ring.c`의 단위 테스트는 합성 in-memory ring을 사용(커널 없음).
- end-to-end는 `mock/`을 통해 수행. **호스트의 `/dev/nvme*`에는 절대
  테스트하지 않는다.**

## ABI 규칙

`include/hmb_ring.h`를 **직접 편집하지 않는다**. `kernel/module/hmb_ring.h`
에서 미러링하고, `docs/trace-format.md`도 같은 커밋에서 갱신한다.
pre-commit 훅(예정)이 두 파일이 SPDX 헤더 주석을 제외하면 바이트
단위로 동일한지 확인한다.
