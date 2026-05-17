#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Side-load nvme-hmb-trace.ko inside the guest. MUST run inside the
# QEMU guest, never on the host. The script refuses to run unless
# /run/.in-mock-guest exists (the guest cloud-init drops that file).

set -euo pipefail

if [[ ! -e /run/.in-mock-guest ]]; then
    echo "refusing to run outside the mock QEMU guest." >&2
    echo "if you are inside the guest, 'touch /run/.in-mock-guest' first." >&2
    exit 2
fi

MOD=${1:-/repo/kernel/module/nvme_hmb_trace.ko}

if [[ ! -f "${MOD}" ]]; then
    echo "module not found: ${MOD}" >&2
    exit 1
fi

case "${2:-load}" in
    load)
        sudo insmod "${MOD}"
        ;;
    unload)
        sudo rmmod nvme_hmb_trace
        ;;
    reload)
        sudo rmmod nvme_hmb_trace || true
        sudo insmod "${MOD}"
        ;;
    *)
        echo "usage: $0 <module.ko> {load|unload|reload}" >&2
        exit 2
        ;;
esac
