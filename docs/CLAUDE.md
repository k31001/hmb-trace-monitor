# docs/ — 명세 & 설계 노트 / GitHub Pages 사이트

라이선스: Apache-2.0. 형식: 일반 Markdown(Jekyll 호환).
이 디렉토리는 모든 컴포넌트 간 계약(ABI, 바이너리 포맷, 데이터 흐름)에
대해 **권위 있는 단일 출처**입니다. 코드와 이 문서가 어긋나면 둘을
맞출 때까지는 이 문서가 우선합니다.

또한 이 디렉토리는 **GitHub Pages**의 소스이기도 합니다.
배포는 `.github/workflows/pages.yml`이 담당합니다.

## 파일 구성

| 파일                | 역할                                                       |
|---------------------|------------------------------------------------------------|
| `_config.yml`       | Jekyll 설정(테마: `just-the-docs`, 한국어, 제외 목록)      |
| `Gemfile`           | 로컬 미리보기용 의존성                                     |
| `index.md`          | 사이트 랜딩(개요)                                          |
| `architecture.md`   | 아키텍처 / 데이터 흐름 / 실패 모드                         |
| `operation.md`      | producer/consumer 동작 과정(단계별)                        |
| `tutorial.md`       | 개발 셋업부터 mock 환경 end-to-end까지                     |
| `trace-format.md`   | HMB ring + record 바이너리 ABI                             |
| `abi.md`            | 캐릭터 디바이스/ioctl/mmap/poll/sysfs 표면                 |
| `test-vectors/`     | 헥스 dump fixture + 골든 디코드(예정)                      |
| `CLAUDE.md`         | (이 파일) — 사이트 빌드에서는 제외됨                       |

## 작성 규칙

- 모든 산문은 **한국어**로 작성합니다. 코드 식별자, struct 필드 이름,
  SPDX, 라이선스 본문은 영어 유지.
- 소스 Markdown은 diff 친화적으로 **한 문장당 한 줄**을 권장.
- 모든 struct 필드 표는 **오프셋 / 크기 / 이름 / 타입 / endian / 설명**
  순서를 지킵니다.
- 정수 상수는 10진수와 16진수를 함께 표기.
- 명세 문서를 손대면 맨 아래 "버전 이력" 표에 한 줄을 **append**합니다.

## Jekyll 페이지 프론트 매터

GitHub Pages로 렌더링되는 파일은 다음을 갖춥니다.

```yaml
---
title: 페이지 제목(한국어)
layout: default
nav_order: N           # 사이드바 순서
permalink: /slug/      # 짧은 URL
---
```

`CLAUDE.md`, `Gemfile`, `_config.yml`은 프론트 매터 없이 사이트에서 제외됩니다.

## ABI 변경 절차

on-wire 바이트나 syscall 번호에 영향이 있는 모든 변경은:

1. `kernel/module/hmb_ring.h`,
   `daemon/include/hmb_ring.h`,
   `analyzer/src/hmb_trace/format.py` 의
   `HMB_TRACE_ABI_VERSION` 을 bump 한다;
2. `docs/trace-format.md` 의 struct 표 + 버전 이력을 갱신한다;
3. syscall 표면이 바뀌면 `docs/abi.md` 도 함께 갱신한다;
4. 위 모든 변경은 **같은 커밋**으로 들어간다.

**후방 호환성:** 마이너 bump는 옵션 플래그 비트 추가나 reserved 필드
의미 부여 등에만 허용됩니다. 오프셋·크기·기존 필드 의미를 바꾸는
변경은 메이저 bump가 필요합니다.

## 버전 표기

```
MAJOR.MINOR   (HMB_TRACE_ABI_VERSION은 상위 16비트에 MAJOR를 packing)
```

(현재는 평탄한 `uint32_t == 1`. major/minor 분할은 문서화만 되어 있고
v2가 등장할 때부터 실제 사용됩니다.)

## 로컬 미리보기 (선택)

```sh
cd docs
bundle install
bundle exec jekyll serve
# http://127.0.0.1:4000/ 에서 확인
```

CI 빌드는 `.github/workflows/pages.yml` 이 ubuntu-latest에서 수행하므로
로컬 미리보기는 어디까지나 작성자 편의용입니다.
