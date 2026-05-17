# SPDX-License-Identifier: Apache-2.0
# Thin wrapper so the top-level `make` can recurse into analyzer/.

UV ?= uv

.PHONY: all sync lint fmt test clean

all: sync

sync:
	$(UV) sync

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test:
	$(UV) run pytest

clean:
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache dist build *.egg-info
