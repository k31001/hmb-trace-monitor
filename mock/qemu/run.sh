#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Launch a QEMU guest configured with a virtio-nvme device that exposes
# a mock HMB region, with the repository mounted via virtiofs at /repo.
#
# Scaffolding only — flags below describe the intended invocation but
# are gated on TODOs (kernel + rootfs missing).

set -euo pipefail

KERNEL=${1:?"usage: $0 <kernel> <image> <workdir>"}
IMAGE=${2:?}
WORKDIR=${3:?}
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "${KERNEL}" ]]; then
    echo "guest kernel not built yet: ${KERNEL}" >&2
    echo "run 'make build-guest-kernel' first." >&2
    exit 1
fi

if [[ ! -f "${IMAGE}" ]]; then
    echo "rootfs not built yet: ${IMAGE}" >&2
    echo "run 'make image' first." >&2
    exit 1
fi

mkdir -p "${WORKDIR}"

# TODO: wire up the QEMU-side mock HMB producer (see nvme-hmb-overlay.patch).
exec qemu-system-x86_64 \
    -enable-kvm -cpu host -smp 4 -m 2G \
    -kernel "${KERNEL}" \
    -append "root=/dev/vda console=ttyS0 nokaslr" \
    -drive file="${IMAGE}",if=virtio,format=qcow2,snapshot=on \
    -device nvme,drive=nvme0,serial=hmbtrace0,hmb-size=64M \
    -drive file="${WORKDIR}/nvme0.img",if=none,id=nvme0,format=raw \
    -virtfs local,path="${REPO_ROOT}",mount_tag=repo,security_model=mapped-xattr,id=repo \
    -nographic -no-reboot
