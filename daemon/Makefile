# SPDX-License-Identifier: GPL-2.0
CC      ?= cc
CSTD    := -std=c11
WARN    := -Wall -Wextra -Werror -Wshadow -Wconversion -Wpointer-arith \
           -Wcast-align -Wstrict-prototypes -Wmissing-prototypes \
           -Wold-style-definition -pedantic
OPT     ?= -O2
CFLAGS  ?= $(CSTD) $(WARN) $(OPT) -D_GNU_SOURCE -Iinclude
LDFLAGS ?=
LDLIBS  ?=

BIN     := hmb-trace-daemon
BUILD   := build
SRC     := $(wildcard src/*.c)
OBJ     := $(patsubst src/%.c,$(BUILD)/%.o,$(SRC))

.PHONY: all debug lint fmt clean

all: $(BIN)

$(BIN): $(OBJ)
	$(CC) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BUILD):
	mkdir -p $@

debug:
	$(MAKE) OPT="-O0 -g -fsanitize=address,undefined" \
	        LDFLAGS="-fsanitize=address,undefined" all

# 'lint' is a compile-only -Werror run; semantic checks happen via clang-tidy
# in CI (TBD).
lint: clean
	$(MAKE) all

fmt:
	clang-format -i src/*.c include/*.h

clean:
	rm -rf $(BUILD) $(BIN)

-include $(OBJ:.o=.d)
