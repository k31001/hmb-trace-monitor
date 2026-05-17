#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Fetch Linux 6.6 LTS, apply kernel/patches/*.patch, configure, and
# build a bzImage suitable for the QEMU guest. Scaffolding only.

set -euo pipefail

LINUX_VER=${LINUX_VER:-6.6.30}
TARBALL_URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${LINUX_VER}.tar.xz"
DEST=${1:-linux}

if [[ -d "${DEST}" && -f "${DEST}/Makefile" ]]; then
    echo "kernel tree already present at ${DEST}; skipping fetch."
else
    echo "TODO: fetch ${TARBALL_URL} into ${DEST}"
fi

echo "TODO: apply ../../kernel/patches/*.patch"
echo "TODO: copy a minimal x86_64 config and run 'make olddefconfig'"
echo "TODO: make -j\$(nproc) bzImage"
