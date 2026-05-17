// SPDX-License-Identifier: GPL-2.0
/*
 * nvme-hmb-trace: expose a slice of HMB as a read-only ring buffer to
 * user space through a char device. SSD firmware is the producer;
 * a user-space daemon is the consumer.
 *
 * SCAFFOLDING ONLY. The actual HMB carve-out hooks live in the NVMe
 * core patches under ../patches/; this module currently just registers
 * a char device and stubs file ops so the layout compiles.
 */
#include <linux/cdev.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/poll.h>
#include <linux/uaccess.h>

#include "hmb_ring.h"
#include "nvme_hmb_trace.h"

#define DRV_NAME "nvme-hmb-trace"

static int hmb_trace_open(struct inode *inode, struct file *filp)
{
	(void)inode;
	(void)filp;
	return -ENODEV; /* wired up by NVMe core patch */
}

static int hmb_trace_release(struct inode *inode, struct file *filp)
{
	(void)inode;
	(void)filp;
	return 0;
}

static long hmb_trace_ioctl(struct file *filp, unsigned int cmd,
			    unsigned long arg)
{
	(void)filp;
	(void)cmd;
	(void)arg;
	return -ENOTTY;
}

static int hmb_trace_mmap(struct file *filp, struct vm_area_struct *vma)
{
	(void)filp;
	(void)vma;
	return -ENODEV;
}

static __poll_t hmb_trace_poll(struct file *filp, poll_table *wait)
{
	(void)filp;
	(void)wait;
	return 0;
}

static const struct file_operations hmb_trace_fops = {
	.owner          = THIS_MODULE,
	.open           = hmb_trace_open,
	.release        = hmb_trace_release,
	.unlocked_ioctl = hmb_trace_ioctl,
	.compat_ioctl   = hmb_trace_ioctl,
	.mmap           = hmb_trace_mmap,
	.poll           = hmb_trace_poll,
	.llseek         = no_llseek,
};

static int __init hmb_trace_init(void)
{
	pr_info(DRV_NAME ": loaded (ABI v%u, scaffolding only)\n",
		HMB_TRACE_ABI_VERSION);
	(void)&hmb_trace_fops;
	return 0;
}

static void __exit hmb_trace_exit(void)
{
	pr_info(DRV_NAME ": unloaded\n");
}

module_init(hmb_trace_init);
module_exit(hmb_trace_exit);

MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("Expose NVMe HMB trace ring buffer to user space");
MODULE_AUTHOR("hmb-trace-monitor authors");
MODULE_VERSION("0.0.1");
