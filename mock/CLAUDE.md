# mock/ — QEMU 테스트 하네스

라이선스: Apache-2.0. 호스트에 영향을 주는 명령(`qemu-system-*`,
`insmod`/`modprobe`, 게스트 커널 빌드, 디스크 이미지 생성 등)을
**실행해도 되는 유일한 디렉토리**입니다.

## 원칙

실행 중인 호스트 커널을 바꾸거나, 실제 블록 디바이스를 건드리거나,
커널 네트워크/디바이스 소켓을 여는 명령은 — 전부 `mock/scripts/`에
속하고 `make`를 통해 호출됩니다. `mock/` 바깥에서는 위 명령을 돌리지
않습니다. CI는 `mock/Makefile`에서 `MOCK_GUARD=1`을 export 하고, 다른
컴포넌트 Makefile은 이 변수가 set되어 있으면 실행을 거부하도록 구성
예정입니다.

## 구성

```
qemu/run.sh                  qemu-system-x86_64 + virtio-nvme 런처 (스텁)
qemu/nvme-hmb-overlay.patch  QEMU 측 mock HMB producer (자리표시)
scripts/build-guest-kernel.sh   6.6 LTS 게스트 커널 fetch + 빌드
scripts/load-module.sh          게스트 안에서만 도는 insmod/rmmod 헬퍼
Makefile                     make 기반 진입점
```

## Make 타깃

```sh
make build-guest-kernel    # Linux 6.6을 mock/linux/ 에 fetch + 빌드
make image                 # 최소 rootfs qcow2 생성
make qemu-run              # 게스트 부팅 + 트레이스 모듈 side-load
make qemu-stop             # 우리가 띄운 qemu만 종료
make clean                 # 이미지/빌드 산출물 삭제 (커널 캐시는 유지)
make distclean             # mock/linux/ 까지 삭제
```

런처는 저장소를 게스트 안 `/repo` 로 9p 또는 virtiofs 마운트합니다.
덕분에 게스트 안의 `make`가 게스트 헤더로 `daemon/`과
`kernel/module/`을 재빌드할 수 있습니다.

## 게스트 안 워크플로우 (참고)

```sh
# qemu-run 후 게스트 셸
cd /repo
make -C kernel KDIR=/usr/src/linux modules
sudo insmod kernel/module/nvme_hmb_trace.ko
sudo make -C daemon
sudo ./daemon/hmb-trace-daemon -o /tmp/trace.bin &
./mock/scripts/produce-mock-trace      # 예정: 합성 producer
sudo kill %1
```

`/tmp/trace.bin`은 9p 마운트로 호스트에서도 곧바로 보이며,
호스트 측에서 다음과 같이 디코드합니다.

```sh
uv run --project analyzer hmb-trace-analyze decode mock/work/trace.bin
```

## 금지 사항

- `mock/` 바깥에서 `qemu-system-*` 실행 금지. 런처가 안전한 기본값
  (`-snapshot`, 기본적으로 host bridging 없음, 일회용 디스크 이미지)을
  설정해 둡니다.
- 이 디렉토리 안에서 `mock/` 바깥 경로에 쓰지 않습니다. 단,
  `mock/work/` 아래의 analyzer 캐시는 예외.
- **호스트 커널에 모듈을 적재하지 않습니다. 절대.**
