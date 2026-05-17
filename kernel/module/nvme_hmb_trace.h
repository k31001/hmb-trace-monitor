/* SPDX-License-Identifier: GPL-2.0 */
/*
 * nvme-hmb-trace: user-space ABI for the trace char device.
 *
 * Numbers in this file are part of the user-visible ABI; renumbering
 * breaks user-space. Append new ioctls only; never re-use a number.
 */
#ifndef _NVME_HMB_TRACE_UAPI_H
#define _NVME_HMB_TRACE_UAPI_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define NVME_HMB_TRACE_DEV_NAME  "nvme-hmb-trace"
#define NVME_HMB_TRACE_IOC_MAGIC 'H'

/**
 * struct nvme_hmb_trace_info - geometry returned by GET_INFO ioctl.
 * @abi_version:     value of HMB_TRACE_ABI_VERSION the module was built with
 * @ring_size:       size of the record area in bytes (power of 2)
 * @record_area_off: byte offset from the start of the mmap to the record area
 * @total_mmap_size: bytes the caller must request via mmap()
 */
struct nvme_hmb_trace_info {
	__u32 abi_version;
	__u32 ring_size;
	__u32 record_area_off;
	__u32 total_mmap_size;
};

#define NVME_HMB_TRACE_GET_INFO \
	_IOR(NVME_HMB_TRACE_IOC_MAGIC, 0x01, struct nvme_hmb_trace_info)

#endif /* _NVME_HMB_TRACE_UAPI_H */
