/* SPDX-License-Identifier: GPL-2.0 */
/*
 * HMB trace ring buffer ABI.
 *
 * Single source of truth for the on-wire/in-memory layout shared between
 * SSD firmware (producer), the kernel module, and the user-space daemon
 * (consumer). Mirror this file at daemon/include/hmb_ring.h byte-for-byte;
 * any change must bump HMB_TRACE_ABI_VERSION and update docs/trace-format.md
 * in the same commit.
 *
 * Layout (little-endian, packed, all multi-byte fields LE):
 *
 *   +0x000  struct hmb_ring_hdr      (64 B)
 *   +0x040  record area, power-of-2 size, 8 B aligned, wrap-around
 *
 * Each record begins with struct hmb_record_hdr (32 B) followed by a
 * variable payload of payload_len bytes, padded with zero bytes up to
 * the next 8 B boundary.
 */
#ifndef _NVME_HMB_TRACE_RING_H
#define _NVME_HMB_TRACE_RING_H

#include <linux/types.h>

#define HMB_TRACE_MAGIC          0x54424d48u  /* "HMBT" little-endian */
#define HMB_RECORD_MAGIC         0x54434552u  /* "RECT" little-endian */
#define HMB_TRACE_ABI_VERSION    1u
#define HMB_RECORD_HDR_SIZE      32u
#define HMB_RECORD_ALIGN         8u

/* Header flags. */
#define HMB_RING_FLAG_OVERFLOWED (1u << 0)  /* producer lapped consumer */
#define HMB_RING_FLAG_FROZEN     (1u << 1)  /* firmware stopped tracing */

/* Record flags. */
#define HMB_REC_FLAG_WRAP_MARKER (1u << 0)  /* synthetic record: skip to ring start */
#define HMB_REC_FLAG_TRUNCATED   (1u << 1)  /* payload clipped by firmware */

/*
 * Ring-buffer header. Occupies the first 64 B of the HMB region.
 *
 * head/tail are byte offsets into the record area (0 .. ring_size-1).
 * Producer (firmware) writes head; consumer (host) writes tail. SPSC.
 */
struct hmb_ring_hdr {
	__le32 magic;            /* HMB_TRACE_MAGIC */
	__le32 version;          /* HMB_TRACE_ABI_VERSION */
	__le32 ring_size;        /* size of record area in bytes, power of 2 */
	__le32 record_area_off;  /* offset from base to record area (= 0x40) */
	__le64 head;             /* producer cursor (firmware) */
	__le64 tail;             /* consumer cursor (host) */
	__le32 flags;            /* HMB_RING_FLAG_* */
	__le32 reserved0;
	__le64 reserved1;
	__le64 reserved2;
	__le64 reserved3;
} __packed;

/*
 * Record header. Exactly 32 B. Followed by payload_len payload bytes,
 * then 0-padding to the next 8 B boundary.
 */
struct hmb_record_hdr {
	__le32 magic;        /* HMB_RECORD_MAGIC */
	__le32 seq;          /* monotonic, wraps */
	__le64 ts_ns;        /* firmware monotonic clock, nanoseconds */
	__le16 opcode;       /* trace event id (firmware-defined) */
	__u8   cpu;          /* originating firmware core/CPU id */
	__u8   flags;        /* HMB_REC_FLAG_* */
	__le16 payload_len;  /* actual payload bytes (pre-padding) */
	__le16 reserved0;
	__le64 reserved1;
} __packed;

/* Compile-time guards: the wire format MUST stay byte-exact. */
#define HMB_BUILD_BUG_ON_SIZE(t, n) \
	typedef char __hmb_size_##t[(sizeof(struct t) == (n)) ? 1 : -1]
HMB_BUILD_BUG_ON_SIZE(hmb_ring_hdr, 64);
HMB_BUILD_BUG_ON_SIZE(hmb_record_hdr, 32);
#undef HMB_BUILD_BUG_ON_SIZE

#endif /* _NVME_HMB_TRACE_RING_H */
