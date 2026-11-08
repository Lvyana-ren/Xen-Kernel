/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_XEN_ROM_COMPAT_H
#define _LINUX_XEN_ROM_COMPAT_H

#include <linux/types.h>

enum xen_rom_type {
	XEN_ROM_AUTO = 0,
	XEN_ROM_AOSP = 1,
	XEN_ROM_OEM = 2,
	XEN_ROM_OOS = 3,
};

#ifdef CONFIG_XEN_ROM_COMPAT
int xen_rom_get_type(void);
bool xen_rom_is_oos(void);
#else
static inline int xen_rom_get_type(void) { return XEN_ROM_AUTO; }
static inline bool xen_rom_is_oos(void) { return false; }
#endif

#endif /* _LINUX_XEN_ROM_COMPAT_H */
