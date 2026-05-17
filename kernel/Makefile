# SPDX-License-Identifier: GPL-2.0
# Out-of-tree build for nvme-hmb-trace.ko.
# Loading the resulting module on the host is FORBIDDEN — use mock/.

KDIR ?= /lib/modules/$(shell uname -r)/build
PWD  := $(CURDIR)

MODULE_DIR := $(PWD)/module
CHECKPATCH := $(KDIR)/scripts/checkpatch.pl

.PHONY: modules clean checkpatch help

modules:
	$(MAKE) -C $(KDIR) M=$(MODULE_DIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(MODULE_DIR) clean || true
	rm -f $(MODULE_DIR)/*.o $(MODULE_DIR)/*.ko $(MODULE_DIR)/*.mod*

checkpatch:
	@if [ ! -x "$(CHECKPATCH)" ]; then \
	    echo "checkpatch.pl not found at $(CHECKPATCH); set KDIR=" >&2; \
	    exit 1; \
	fi
	@set -e; for f in $(MODULE_DIR)/*.c $(MODULE_DIR)/*.h; do \
	    [ -e "$$f" ] || continue; \
	    echo "==> checkpatch $$f"; \
	    $(CHECKPATCH) --strict --no-tree -f "$$f"; \
	done
	@set -e; for p in $(PWD)/patches/*.patch; do \
	    [ -e "$$p" ] || continue; \
	    echo "==> checkpatch $$p"; \
	    $(CHECKPATCH) --strict $$p; \
	done

help:
	@echo "modules     - build nvme-hmb-trace.ko (KDIR=$(KDIR))"
	@echo "checkpatch  - run scripts/checkpatch.pl --strict over module/ and patches/"
	@echo "clean       - remove build artifacts"
