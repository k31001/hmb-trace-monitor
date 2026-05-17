# SPDX-License-Identifier: Apache-2.0
# Top-level dispatcher. Component-specific build rules live in each subdir.

SUBDIRS_USERSPACE := daemon analyzer
SUBDIRS_ALL       := kernel daemon analyzer mock

.PHONY: all help kernel daemon analyzer mock-run lint clean docs-example $(SUBDIRS_ALL)

all: daemon analyzer
	@echo "[hmb-trace-monitor] user-space build done."
	@echo "  - run 'make kernel'   to build the module (host-safe; not loaded)"
	@echo "  - run 'make mock-run' to boot QEMU and exercise the full stack"

help:
	@echo "Targets:"
	@echo "  make            - build daemon + analyzer (host-safe)"
	@echo "  make kernel     - build out-of-tree module against host headers"
	@echo "  make daemon     - build user-space daemon"
	@echo "  make analyzer   - sync analyzer Python env"
	@echo "  make mock-run   - boot QEMU guest and run the full stack"
	@echo "  make lint       - checkpatch + -Werror + ruff + mypy"
	@echo "  make docs-example - regenerate docs/examples/sample-report.html locally"
	@echo "  make clean      - clean all components"

kernel:
	$(MAKE) -C kernel modules

daemon:
	$(MAKE) -C daemon

analyzer:
	cd analyzer && uv sync

mock-run:
	$(MAKE) -C mock qemu-run

# 분석기로 합성 트레이스를 만들고 docs/examples/ 아래에 HTML 리포트를
# 떨어뜨린다. CI 워크플로우도 동일한 산출물을 만들며 GitHub Pages에 배포한다.
docs-example:
	@mkdir -p docs/examples
	cd analyzer && uv sync && uv run hmb-trace-synth \
	    /tmp/firmware-trace-sample.bin \
	    -n 150000 --seed 42 \
	    --drop-every 2500 --truncate-every 1200 --wrap-every 8000
	cd analyzer && uv run hmb-trace-analyze report \
	    /tmp/firmware-trace-sample.bin \
	    -o ../docs/examples/sample-report.html
	@echo "→ docs/examples/sample-report.html"

lint:
	$(MAKE) -C kernel   checkpatch
	$(MAKE) -C daemon   lint
	$(MAKE) -C analyzer lint

clean:
	-for d in $(SUBDIRS_ALL); do $(MAKE) -C $$d clean || true; done
