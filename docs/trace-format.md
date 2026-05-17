---
title: 트레이스 포맷
layout: default
nav_order: 6
---

# 트레이스 바이너리 포맷
{: .no_toc }

**상태:** v1 초안. SSD 펌웨어(producer), `nvme-hmb-trace.ko` 커널 모듈, `hmb-trace-daemon` 컨슈머, `hmb_trace` Python 디코더가 공유하는 on-wire/in-memory 레이아웃의 권위 있는 명세입니다.
{: .fs-5 .fw-300 }

이 문서와 헤더 파일이 일치하지 않으면, 일치시키는 작업이 끝날 때까지는 **이 문서가 우선**합니다.

<details open markdown="block">
  <summary>목차</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## 1. 범위

Host Memory Buffer(HMB)는 호스트가 NVMe 컨트롤러에 광고하는 호스트 RAM 영역입니다(`Set Features 0Dh`). 본 명세는 HMB의 연속된 한 슬라이스를 SSD → 호스트 방향의 펌웨어 트레이스 레코드 전달용 **single-producer / single-consumer (SPSC) 링 버퍼**로 사용하는 방법을 정의합니다.

펌웨어가 **producer**, 호스트 유저스페이스 데몬이 **consumer**입니다. 커널 모듈은 mmap을 통해 영역을 노출하는 수동적인 통로일 뿐 바이트를 옮기지 않습니다.

모든 다바이트 정수는 **little-endian**입니다. 모든 구조체는 **packed**(암묵적 패딩 없음)이며, 명시된 위치에 한해 명시적으로 패딩됩니다.

## 2. 영역 레이아웃

```
offset  size   내용
------  -----  -------------------------------------------------------
0x000     64   struct hmb_ring_hdr   (3장)
0x040    var   record area, ring_size 바이트, 8바이트 정렬, 랩어라운드
```

`ring_size`는 반드시 2의 제곱이고 8의 배수여야 합니다. 호스트가 mmap하는 전체 영역 크기는 `record_area_off + ring_size`이며, 커널 모듈은 이 값을 `NVME_HMB_TRACE_GET_INFO`로 알려줍니다.

## 3. `struct hmb_ring_hdr` (64 바이트)

| 오프셋 | 크기 | 필드              | 타입     | 설명                                              |
|-------:|-----:|-------------------|----------|---------------------------------------------------|
|  0x00  |   4  | `magic`           | u32 LE   | `0x54424D48` (`'HMBT'`)                           |
|  0x04  |   4  | `version`         | u32 LE   | `HMB_TRACE_ABI_VERSION`, 현재 `1`                 |
|  0x08  |   4  | `ring_size`       | u32 LE   | record area 크기(바이트), 2의 제곱                |
|  0x0C  |   4  | `record_area_off` | u32 LE   | base → record area 오프셋, v1에서 반드시 `0x40`   |
|  0x10  |   8  | `head`            | u64 LE   | producer 커서(펌웨어가 기록)                      |
|  0x18  |   8  | `tail`            | u64 LE   | consumer 커서(호스트가 기록)                      |
|  0x20  |   4  | `flags`           | u32 LE   | `HMB_RING_FLAG_*`                                 |
|  0x24  |   4  | `reserved0`       | u32 LE   | MBZ                                               |
|  0x28  |   8  | `reserved1`       | u64 LE   | MBZ                                               |
|  0x30  |   8  | `reserved2`       | u64 LE   | MBZ                                               |
|  0x38  |   8  | `reserved3`       | u64 LE   | MBZ                                               |

### Ring 플래그

| 비트 | 이름                       | 의미                                                       |
|-----:|----------------------------|------------------------------------------------------------|
|  0   | `HMB_RING_FLAG_OVERFLOWED` | Producer가 consumer를 추월하여 일부 record가 드롭됨.       |
|  1   | `HMB_RING_FLAG_FROZEN`     | 펌웨어가 기록을 중단함(컨트롤러 리셋, 셧다운).             |

### 커서 의미

- `head`와 `tail`은 **단조 증가하는** 바이트 카운터이며, modulo 오프셋이 아닙니다. record area 안의 바이트 오프셋은 `cursor & (ring_size - 1)`로 계산합니다.
- `head - tail`은 미독 바이트 수입니다(항상 `ring_size` 이하).
- Producer 순서: payload 바이트 기록 → 메모리 배리어 → `head` publish.
  Consumer 순서: acquire 의미로 `head` 로드 → 바이트 복사 → release 의미로 `tail` publish.
- Producer는 `head - tail + new_record_size > ring_size`가 되면 overflow를 감지합니다. overflow 시 펌웨어는 새 record를 드롭하고 `HMB_RING_FLAG_OVERFLOWED`를 set 할 수 있습니다. 절대 조용히 덮어쓰지 않습니다.

## 4. `struct hmb_record_hdr` (32 바이트)

모든 record는 record area 안의 8바이트 정렬 오프셋에서 시작하며, 다음 고정 헤더로 시작합니다.

| 오프셋 | 크기 | 필드          | 타입     | 설명                                       |
|-------:|-----:|---------------|----------|--------------------------------------------|
|  0x00  |   4  | `magic`       | u32 LE   | `0x54434552` (`'RECT'`)                    |
|  0x04  |   4  | `seq`         | u32 LE   | 단조 증가 record 시퀀스, wrap 허용         |
|  0x08  |   8  | `ts_ns`       | u64 LE   | 펌웨어 monotonic clock, 나노초             |
|  0x10  |   2  | `opcode`      | u16 LE   | 트레이스 이벤트 ID(펌웨어 정의)            |
|  0x12  |   1  | `cpu`         | u8       | 발생 펌웨어 코어 ID                         |
|  0x13  |   1  | `flags`       | u8       | `HMB_REC_FLAG_*`                           |
|  0x14  |   2  | `payload_len` | u16 LE   | payload 바이트 수(패딩 전)                 |
|  0x16  |   2  | `reserved0`   | u16 LE   | MBZ                                        |
|  0x18  |   8  | `reserved1`   | u64 LE   | MBZ                                        |

### Record 플래그

| 비트 | 이름                       | 의미                                                                                       |
|-----:|----------------------------|--------------------------------------------------------------------------------------------|
|  0   | `HMB_REC_FLAG_WRAP_MARKER` | 합성 record: 현재 lap의 남은 바이트를 건너뛰고 offset 0부터 재개. v1에서 `payload_len`은 항상 0. |
|  1   | `HMB_REC_FLAG_TRUNCATED`   | 펌웨어가 payload를 클리핑함(길이 한도 초과).                                               |

### Payload

- 헤더 바로 뒤에 `payload_len` 바이트의 payload가 따라옵니다.
- 다음 record는 그 다음 8바이트 경계에서 시작합니다. 사이의 빈틈은 producer가 0으로 패딩합니다.
- `payload_len`은 0일 수 있습니다(헤더만 있는 record).
- v1의 최대 `payload_len`: `4096 - 32 = 4064`. 더 큰 이벤트는 펌웨어가 분할해야 합니다.

## 5. 랩어라운드 규칙

Producer가 ring의 어느 지점에 도달했는데 `ring_size`까지 남은 연속 공간이 32바이트(record header 하나) 미만이면, 현재 head 위치에 `HMB_REC_FLAG_WRAP_MARKER` 플래그를 가진 `payload_len = 0` record를 쓰고, record area의 offset 0으로 돌아가 produce를 재개합니다. Consumer는 wrap marker를 no-op으로 처리합니다.

이렇게 하면 record가 ring 경계를 가로질러 잘리는 일을 막을 수 있습니다.

## 6. 후방 호환성 규칙

- 예약 필드와 미사용 플래그 비트는 기록 시 **MBZ**(반드시 0), 읽기 시 **MBR**(다음 메이저 bump 전에는 의미를 부여하지 않음)입니다.
- 모르는 record 플래그를 만난 consumer는 그 record를 무시하되 `payload_len`을 8바이트 정렬하여 반드시 진행해야 합니다.
- 모르는 ring 플래그를 만난 consumer는 로깅만 하고 그 외에는 정상 동작해야 합니다.
- `version > HMB_TRACE_ABI_VERSION`인 ring을 만난 consumer는 해석을 거부하고 명확한 에러를 사용자에게 보여 주어야 합니다.

## 6.5. Dump 파일 포맷

`hmb-trace-daemon`이 디스크에 떨어뜨리는 파일은 HMB 영역의 **전체
스냅샷이 아니라** record들의 연속입니다.

```
dump file = [record_0][record_1]...[record_N-1]
record    = hmb_record_hdr(32B) + payload(payload_len B) + 0-padding(8B 정렬)
```

규칙:

- 각 record는 파일 안에서 8바이트 정렬을 유지한다.
- 데몬은 `HMB_REC_FLAG_WRAP_MARKER` record도 그대로 기록한다(ring 상태 보존).
  분석기는 이를 투명하게 건너뛰되 통계로는 집계한다.
- `hmb_ring_hdr`는 dump 파일에 포함되지 않는다. ring 상태(`head`, `tail`,
  플래그)는 ring 자체에만 존재하며, dump는 비결정적인 ring 메타데이터와
  분리해 record 스트림만을 보관한다.
- 파일 끝에서 record 헤더 읽기가 truncate되면 분석기는 명확한 에러로
  중단한다(완전성 검증).

## 7. 테스트 벡터

(미구현. 예정 위치: `docs/test-vectors/v1/`)

- `empty.bin` — 헤더만, `head == tail == 0`.
- `single.bin` — offset 0에 payload 16바이트짜리 record 한 개.
- `wrap.bin` — wrap marker 한 번을 포함해 record area를 한 바퀴 채움.

Python `hmb_trace` 디코더는 `tests/test_format.py`에서 이 fixture들을 로드해 기대 JSON과 비교합니다.

## 8. 버전 이력

| 버전 | 날짜       | 비고                              |
|-----:|------------|-----------------------------------|
| 1    | 2026-05-17 | 초기 초안. 레이아웃 확정.         |
