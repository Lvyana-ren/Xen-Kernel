// SPDX-License-Identifier: GPL-2.0
/*
 * Xen Core identity interface.
 *
 * This interface is an identification/capability hint for Xen Control.
 * It is not a cryptographic attestation of the running kernel.
 */

#include <linux/fs.h>
#include <linux/init.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>

#define XEN_CORE_FAMILY       "Xen-Kernel"
#define XEN_CORE_VERSION      "KSUN+4"
#define XEN_CORE_DEVICE       "vayu"
#define XEN_CORE_KEY          "X3691QTZ"
#define XEN_CORE_FEATURE_LEVEL "L1"

static int xen_core_proc_show(struct seq_file *m, void *v)
{
	seq_puts(m, "FORMAT=1\n");
	seq_printf(m, "FAMILY=%s\n", XEN_CORE_FAMILY);
	seq_printf(m, "VERSION=%s\n", XEN_CORE_VERSION);
	seq_printf(m, "DEVICE=%s\n", XEN_CORE_DEVICE);
	seq_printf(m, "CORE_KEY=%s\n", XEN_CORE_KEY);
	seq_printf(m, "FEATURE_LEVEL=%s\n", XEN_CORE_FEATURE_LEVEL);
	return 0;
}

static int xen_core_proc_open(struct inode *inode, struct file *file)
{
	return single_open(file, xen_core_proc_show, NULL);
}

static const struct file_operations xen_core_proc_fops = {
	.open = xen_core_proc_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

static int __init xen_core_proc_init(void)
{
	if (!proc_create("xen_core", 0444, NULL, &xen_core_proc_fops))
		return -ENOMEM;

	return 0;
}
fs_initcall(xen_core_proc_init);
