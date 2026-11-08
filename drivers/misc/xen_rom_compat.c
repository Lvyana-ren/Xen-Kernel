// SPDX-License-Identifier: GPL-2.0
/*
 * Xen ROM compatibility selector.
 *
 * This is deliberately a policy/identification layer only: it does not
 * disable vendor drivers or alter device-tree data by itself. ROM-specific
 * consumers must opt in after their dependencies have been audited.
 */
#include <linux/init.h>
#include <linux/module.h>
#include <linux/errno.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/string.h>
#include <linux/sysfs.h>
#include <linux/xen_rom_compat.h>

static int xen_rom_type __read_mostly = XEN_ROM_AUTO;

int xen_rom_get_type(void)
{
	return READ_ONCE(xen_rom_type);
}
EXPORT_SYMBOL_GPL(xen_rom_get_type);

bool xen_rom_is_oos(void)
{
	return xen_rom_get_type() == XEN_ROM_OOS;
}
EXPORT_SYMBOL_GPL(xen_rom_is_oos);

static int __init xen_parse_rom_args(char *args)
{
	char *token;

	if (!args)
		return 0;

	while ((token = strsep(&args, ", ")) != NULL) {
		if (!*token)
			continue;

		if (!strcmp(token, "rom_aosp"))
			xen_rom_type = XEN_ROM_AOSP;
		else if (!strcmp(token, "rom_oem"))
			xen_rom_type = XEN_ROM_OEM;
		else if (!strcmp(token, "rom_oos") ||
			 !strcmp(token, "rom_oxygen"))
			xen_rom_type = XEN_ROM_OOS;
		else if (!strcmp(token, "rom_auto"))
			xen_rom_type = XEN_ROM_AUTO;
		else
			pr_warn("Xen-ROM: unknown xen_args token '%s'\n",
				token);
	}

	pr_info("Xen-ROM: selected mode %d\n", xen_rom_type);
	return 0;
}
early_param("xen_args", xen_parse_rom_args);

static struct kobject *xen_rom_kobj;

static const char *xen_rom_name(int type)
{
	switch (type) {
	case XEN_ROM_AOSP:
		return "aosp";
	case XEN_ROM_OEM:
		return "oem";
	case XEN_ROM_OOS:
		return "oxygenos";
	default:
		return "auto";
	}
}

static ssize_t mode_show(struct kobject *kobj,
			 struct kobj_attribute *attr, char *buf)
{
	int type = xen_rom_get_type();

	return scnprintf(buf, PAGE_SIZE, "%s (%d)\n", xen_rom_name(type), type);
}
static struct kobj_attribute mode_attr = __ATTR_RO(mode);

static struct attribute *xen_rom_attrs[] = {
	&mode_attr.attr,
	NULL,
};
ATTRIBUTE_GROUPS(xen_rom);

static int __init xen_rom_compat_init(void)
{
	xen_rom_kobj = kobject_create_and_add("xen_rom", kernel_kobj);
	if (!xen_rom_kobj)
		return -ENOMEM;

	if (sysfs_create_groups(xen_rom_kobj, xen_rom_groups)) {
		kobject_put(xen_rom_kobj);
		xen_rom_kobj = NULL;
		return -ENOMEM;
	}

	pr_info("Xen-ROM: compatibility selector initialized (%s)\n",
		xen_rom_name(xen_rom_get_type()));
	return 0;
}
late_initcall(xen_rom_compat_init);
