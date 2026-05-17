// SPDX-License-Identifier: GPL-2.0
/*
 * hmb-trace-daemon: open /dev/nvme-hmb-trace0, mmap the ring, drain
 * records to an output file. Scaffolding only — see CLAUDE.md.
 */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "hmb_ring.h"

static volatile sig_atomic_t g_stop;

static void on_signal(int sig)
{
	(void)sig;
	g_stop = 1;
}

int main(int argc, char **argv)
{
	(void)argc;
	(void)argv;

	struct sigaction sa = { .sa_handler = on_signal };
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);

	fprintf(stderr,
	        "hmb-trace-daemon: scaffolding only (ABI v%u, hdr=%zu B, rec=%zu B)\n",
	        HMB_TRACE_ABI_VERSION,
	        sizeof(struct hmb_ring_hdr),
	        sizeof(struct hmb_record_hdr));
	return EXIT_FAILURE;
}
