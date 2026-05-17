---
title: ABI
layout: default
nav_order: 6
---

# 커널 ↔ 유저스페이스 ABI
{: .no_toc }

**상태:** v1 초안. [트레이스 포맷](trace-format.html)이 바이트 레이아웃을 담당한다면, 이 문서는 시스템 콜 표면을 정의합니다.
{: .fs-5 .fw-300 }

<details open markdown="block">
  <summary>목차</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## 캐릭터 디바이스

모듈은 컨트롤러 하나당 `/dev/nvme-hmb-trace0`, `/dev/nvme-hmb-trace1`, ... 를 생성합니다.

| File op       | 동작                                                                  |
|---------------|-----------------------------------------------------------------------|
| `open`        | 트레이스 ring에 대한 **배타적 잠금**을 획득(단일 컨슈머).             |
| `close`       | 잠금 해제. close 시 ring을 drain하지 **않음**.                        |
| `mmap`        | HMB 영역 전체를 read-only로 매핑. 길이는 `GET_INFO`가 보고한 `total_mmap_size`와 동일해야 함. `PROT_WRITE`는 `EACCES`로 거부. |
| `poll`        | `head != tail`이면 `POLLIN` 반환(컨슈머에게 할 일이 있음을 알림).      |
| `ioctl`       | 아래 표 참고.                                                         |

ring 헤더의 `tail` 필드는 컨슈머 커서입니다. 컨슈머가 `tail`을 직접 갱신하는 방법은 별도 메커니즘으로 구현됩니다 — 작은 writable shadow page를 만들거나 전용 ioctl을 두는 안이 검토 중입니다. **v1에서는 미확정**. 그동안 mmap은 read-only로 유지되며, 컨슈머가 (자리표시) `NVME_HMB_TRACE_ADVANCE_TAIL` ioctl을 호출하면 커널이 `tail`을 갱신합니다.

## ioctl 번호

`magic = 'H' = 0x48`. 번호는 추가만 가능 — 절대 재사용 금지.

| 번호   | 이름                            | 방향      | 페이로드                       |
|-------:|---------------------------------|-----------|--------------------------------|
| `0x01` | `NVME_HMB_TRACE_GET_INFO`       | `_IOR`    | `struct nvme_hmb_trace_info`   |

### `struct nvme_hmb_trace_info`

| 오프셋 | 크기 | 필드              | 설명                                          |
|-------:|-----:|-------------------|-----------------------------------------------|
|  0x00  |   4  | `abi_version`     | 모듈이 빌드된 시점의 `HMB_TRACE_ABI_VERSION`  |
|  0x04  |   4  | `ring_size`       | record area 크기                              |
|  0x08  |   4  | `record_area_off` | base → record area 오프셋(v1에서 `0x40`)      |
|  0x0C  |   4  | `total_mmap_size` | 호출자가 `mmap`에 전달해야 하는 바이트 수     |

## sysfs

예정(v1 스텁에는 없음):

- `/sys/class/nvme-hmb-trace/trace0/abi_version`
- `/sys/class/nvme-hmb-trace/trace0/ring_size`
- `/sys/class/nvme-hmb-trace/trace0/overflow_count`

새 sysfs 엔트리를 추가할 때는 반드시 이 문서를 같은 커밋에서 갱신합니다.

## 버전 이력

| 버전 | 날짜       | 비고                                |
|-----:|------------|-------------------------------------|
| 1    | 2026-05-17 | 초기 초안. `GET_INFO` 정의.         |
