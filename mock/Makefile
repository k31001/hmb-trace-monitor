# SPDX-License-Identifier: Apache-2.0
# QEMU-based mock harness. The ONLY place that loads the module or
# touches qemu/insmod/disk-image commands.

SHELL := /bin/bash

LINUX_VER  ?= 6.6.30
LINUX_DIR  := linux
BUILD_DIR  := build
WORK_DIR   := work
IMAGE      := $(BUILD_DIR)/rootfs.qcow2
KERNEL_BIN := $(LINUX_DIR)/arch/x86/boot/bzImage

export MOCK_GUARD := 1

.PHONY: help build-guest-kernel image qemu-run qemu-stop clean distclean

help:
	@echo "Targets:"
	@echo "  build-guest-kernel - fetch + build Linux $(LINUX_VER) into $(LINUX_DIR)"
	@echo "  image              - build a disposable rootfs.qcow2 under $(BUILD_DIR)"
	@echo "  qemu-run           - boot the guest with the trace module side-loaded"
	@echo "  qemu-stop          - kill any qemu started here"
	@echo "  clean              - remove build/work artifacts (keep guest kernel)"
	@echo "  distclean          - clean + remove the guest kernel tree"

build-guest-kernel:
	@echo "TODO: fetch linux-$(LINUX_VER), apply ../kernel/patches/*, build bzImage"
	@mkdir -p $(LINUX_DIR)

image:
	@mkdir -p $(BUILD_DIR)
	@echo "TODO: build minimal rootfs into $(IMAGE)"

qemu-run:
	@mkdir -p $(WORK_DIR)
	./qemu/run.sh "$(KERNEL_BIN)" "$(IMAGE)" "$(WORK_DIR)"

qemu-stop:
	-pkill -f "qemu-system.*nvme-hmb-trace" || true

clean:
	rm -rf $(BUILD_DIR) $(WORK_DIR)

distclean: clean
	rm -rf $(LINUX_DIR)
