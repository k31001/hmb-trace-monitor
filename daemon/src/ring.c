// SPDX-License-Identifier: GPL-2.0
/*
 * SPSC consumer loop for the HMB trace ring.
 *
 * Reads load `head` with acquire semantics, walks records from `tail`
 * to `head` (handling wrap-around), validates each record header, and
 * hands raw bytes to the dumper. Stores back `tail` with release.
 *
 * Scaffolding only.
 */
#include "hmb_ring.h"

/* TODO: ring init / consume loop. */
