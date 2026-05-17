# SPDX-License-Identifier: Apache-2.0
# Top-level dispatcher. Component-specific build rules live in each subdir.

SUBDIRS_USERSPACE := daemon analyzer
SUBDIRS_ALL       := kernel daemon analyzer mock

.PHONY: all help kernel daemon analyzer mock-run lint clean $(SUBDIRS_ALL)

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
	@echo "  make clean      - clean all components"

kernel:
	$(MAKE) -C kernel modules

daemon:
	$(MAKE) -C daemon

analyzer:
	cd analyzer && uv sync

mock-run:
	$(MAKE) -C mock qemu-run

lint:
	$(MAKE) -C kernel   checkpatch
	$(MAKE) -C daemon   lint
	$(MAKE) -C analyzer lint

clean:
	-for d in $(SUBDIRS_ALL); do $(MAKE) -C $$d clean || true; done
