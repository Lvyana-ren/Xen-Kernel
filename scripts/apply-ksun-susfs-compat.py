#!/usr/bin/env python3
"""Apply the Xen-SuSFS v2.3.0 compatibility bridge to the pinned KSUN source.

This is a narrow overlay for the current KSUN pin. It does not replace KSUN,
change hook mode, or enable KPROBES. Run it after checkout of the pinned SHA.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXPECTED_KSUN_SHA = "465490a26667ba4cf00b3be975a7e28e53978829"

KCONFIG_BLOCK = r'''
# XEN-SUSFS-KSUN-COMPAT-BEGIN
menu "KernelSU - SUSFS"

config KSU_SUSFS
    bool "KernelSU addon - SUSFS"
    depends on KSU
    depends on THREAD_INFO_IN_TASK
    default y
    help
        Enable the SUSFS v2.3.0 interface in KernelSU-Next.

config KSU_SUSFS_SUS_PATH
    bool "Enable SUS_PATH"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SUS_MOUNT
    bool "Enable SUS_MOUNT"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SUS_KSTAT
    bool "Enable SUS_KSTAT"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_TRY_UMOUNT
    bool "Enable SUSFS try_umount"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SPOOF_UNAME
    bool "Enable uname spoofing"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_ENABLE_LOG
    bool "Enable SUSFS kernel logging"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS
    bool "Hide KernelSU/SUSFS symbols from kallsyms"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
    bool "Enable cmdline/bootconfig spoofing"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_OPEN_REDIRECT
    bool "Enable open redirect"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SUS_MAP
    bool "Enable SUS_MAP"
    depends on KSU_SUSFS
    default y

config KSU_SUSFS_SUS_MEMFD
    bool "Enable SUS_MEMFD (experimental)"
    depends on KSU_SUSFS
    default n

endmenu
# XEN-SUSFS-KSUN-COMPAT-END
'''

DOMAIN_BRIDGE = r'''/* XEN-SUSFS-KSUN-COMPAT: adapt the SUSFS domain helper to current KSUN */
bool susfs_is_current_ksu_domain(void)
{
	return is_ksu_domain();
}
'''

SETUID_HELPERS = r'''#ifdef CONFIG_KSU_SUSFS
static inline bool is_zygote_isolated_service_uid(uid_t uid)
{
	uid %= 100000;
	return uid >= 99000 && uid < 100000;
}

static inline bool is_zygote_normal_app_uid(uid_t uid)
{
	uid %= 100000;
	return uid >= 10000 && uid < 20000;
}

extern struct work_struct susfs_extra_works;
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
extern void susfs_try_umount(uid_t uid);
#endif

struct susfs_handle_setuid_tw {
	struct callback_head cb;
};

static void susfs_handle_setuid_tw_func(struct callback_head *cb)
{
	struct susfs_handle_setuid_tw *tw =
		container_of(cb, struct susfs_handle_setuid_tw, cb);

	if (ksu_cred) {
		const struct cred *saved = override_creds(ksu_cred);
		revert_creds(saved);
	}
	kfree(tw);
}

static void ksu_handle_extra_susfs_work(void)
{
	struct susfs_handle_setuid_tw *tw;

	if (!ksu_cred)
		return;

	tw = kzalloc(sizeof(*tw), GFP_ATOMIC);
	if (!tw) {
		pr_err("susfs: not enough memory for deferred work\n");
		return;
	}

	if (!schedule_work(&susfs_extra_works)) {
		kfree(tw);
		return;
	}

	tw->cb.func = susfs_handle_setuid_tw_func;
	if (task_work_add(current, &tw->cb, TWA_RESUME)) {
		kfree(tw);
		pr_err("susfs: failed to add deferred setuid task_work\n");
	}
}
#endif /* CONFIG_KSU_SUSFS */'''.replace(r"\t", "\t")

SETUID_FUNCTION = r'''int ksu_handle_setresuid(uid_t old_uid, uid_t new_uid)
{
    // We only process zygote-originated UID transitions for SUSFS.
#ifdef CONFIG_KSU_SUSFS
    if (!is_zygote(current_cred()))
        return 0;
#endif

    pr_info("handle_setresuid from %d to %d\n", old_uid, new_uid);

    if (unlikely(is_uid_manager(new_uid))) {
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
        if (current->seccomp.mode == SECCOMP_MODE_FILTER && current->seccomp.filter) {
            ksu_seccomp_allow_cache(current->seccomp.filter, __NR_reboot);
        }
#else
        disable_seccomp();
#endif

#ifdef KSU_KPROBES_HOOK
        ksu_set_task_tracepoint_flag(current);
#endif
        pr_info("install fd for manager: %d\n", new_uid);
        ksu_install_fd();
        return 0;
    }

#ifdef CONFIG_KSU_SUSFS
    /*
     * Match the legacy SUSFS flow: isolated service UIDs need isolation too,
     * while normal app UIDs are processed when the global KSU policy requests
     * mount isolation. Run these before ordinary allowlist handling.
     */
    if (is_zygote_isolated_service_uid(new_uid) ||
        (is_zygote_normal_app_uid(new_uid) && ksu_uid_should_umount(new_uid)))
        goto do_susfs_umount;
#endif

    if (ksu_is_allow_uid_for_current(new_uid)) {
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
        if (current->seccomp.mode == SECCOMP_MODE_FILTER && current->seccomp.filter) {
            ksu_seccomp_allow_cache(current->seccomp.filter, __NR_reboot);
        }
#else
        disable_seccomp();
#endif

#ifdef KSU_KPROBES_HOOK
        ksu_set_task_tracepoint_flag(current);
#endif
    } else {
#ifdef KSU_KPROBES_HOOK
        ksu_clear_task_tracepoint_flag_if_needed(current);
#endif
    }

#ifndef CONFIG_KSU_SUSFS
    ksu_handle_umount(old_uid, new_uid);
#endif
    return 0;

#ifdef CONFIG_KSU_SUSFS
do_susfs_umount:
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
    susfs_try_umount(new_uid);
#else
    ksu_handle_umount(old_uid, new_uid);
#endif
    ksu_handle_extra_susfs_work();
    susfs_set_current_proc_umounted();
    return 0;
#endif
}'''.replace(r"\t", "\t")

REBOOT_BRIDGE = r'''#ifdef CONFIG_KSU_SUSFS
	/*
	 * XEN-SUSFS-KSUN-COMPAT: syscall bridge
	 * Keep the SUSFS_MAGIC ABI used by ksu_susfs userspace while using
	 * this KSUN revision's existing manual-hook entry point.
	 */
	if (magic2 == SUSFS_MAGIC && current_uid().val == 0) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
		if (cmd == CMD_SUSFS_ADD_SUS_PATH) {
			susfs_add_sus_path(arg);
			return 0;
		}
		if (cmd == CMD_SUSFS_ADD_SUS_PATH_LOOP) {
			susfs_add_sus_path_loop(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
		if (cmd == CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS) {
			susfs_set_hide_sus_mnts_for_non_su_procs(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
		if (cmd == CMD_SUSFS_ADD_SUS_KSTAT ||
		    cmd == CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY) {
			susfs_add_sus_kstat(arg);
			return 0;
		}
		if (cmd == CMD_SUSFS_UPDATE_SUS_KSTAT) {
			susfs_update_sus_kstat(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
		if (cmd == CMD_SUSFS_ADD_TRY_UMOUNT) {
			susfs_add_try_umount(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
		if (cmd == CMD_SUSFS_SET_UNAME) {
			susfs_set_uname(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
		if (cmd == CMD_SUSFS_ENABLE_LOG) {
			susfs_enable_log(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
		if (cmd == CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG) {
			susfs_set_cmdline_or_bootconfig(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
		if (cmd == CMD_SUSFS_ADD_OPEN_REDIRECT) {
			susfs_add_open_redirect(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
		if (cmd == CMD_SUSFS_ADD_SUS_MAP) {
			susfs_add_sus_map(arg);
			return 0;
		}
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MEMFD
		if (cmd == CMD_SUSFS_ADD_SUS_MEMFD)
			return susfs_add_sus_memfd(arg);
#endif
		if (cmd == CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING) {
			susfs_set_avc_log_spoofing(arg);
			return 0;
		}
		if (cmd == CMD_SUSFS_SHOW_ENABLED_FEATURES) {
			susfs_get_enabled_features(arg);
			return 0;
		}
		if (cmd == CMD_SUSFS_SHOW_VARIANT) {
			susfs_show_variant(arg);
			return 0;
		}
		if (cmd == CMD_SUSFS_SHOW_VERSION) {
			susfs_show_version(arg);
			return 0;
		}
		return 0;
	}
#endif /* CONFIG_KSU_SUSFS */
'''

DISPATCH_BOOT_BRIDGE = r'''#ifdef CONFIG_KSU_SUSFS
				susfs_start_sdcard_monitor_fn(); /* XEN-SUSFS-KSUN-COMPAT: boot monitor */
#endif
'''

KBUILD_BLOCK = r'''
# XEN-SUSFS-KSUN-COMPAT-BEGIN
ifeq ($(CONFIG_KSU_SUSFS),y)
ifeq ($(shell test -f $(srctree)/fs/susfs.c -a -f $(srctree)/include/linux/susfs.h && echo yes),)
$(error CONFIG_KSU_SUSFS=y but SUSFS kernel sources are missing)
endif
SUSFS_VERSION := $(shell sed -n 's/^#define SUSFS_VERSION "\([^"]*\)".*/\1/p' $(srctree)/include/linux/susfs.h)
$(info -- XEN-SUSFS compatibility bridge enabled; SUSFS_VERSION=$(SUSFS_VERSION))
endif
# XEN-SUSFS-KSUN-COMPAT-END
'''


def read_text(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Required KSUN source file is missing: {path}")
    return path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /path/to/KernelSU-Next", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()
    if not (root / ".git").exists():
        raise RuntimeError(f"Not a Git checkout: {root}")

    actual_sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != EXPECTED_KSUN_SHA:
        raise RuntimeError(
            "Refusing to patch an unexpected KSUN revision.\n"
            f"Expected: {EXPECTED_KSUN_SHA}\n"
            f"Actual:   {actual_sha}\n"
            "Update the pin and audit compatibility deliberately before retrying."
        )

    kconfig_path = root / "kernel/Kconfig"
    supercall_path = root / "kernel/supercall/supercall.c"
    dispatch_path = root / "kernel/supercall/dispatch.c"
    kbuild_path = root / "kernel/Kbuild"
    selinux_path = root / "kernel/selinux/selinux.c"
    umount_path = root / "kernel/feature/kernel_umount.c"
    init_path = root / "kernel/core/init.c"
    setuid_path = root / "kernel/hook/setuid_hook.c"

    kconfig = read_text(kconfig_path)
    supercall = read_text(supercall_path)
    dispatch = read_text(dispatch_path)
    kbuild = read_text(kbuild_path)
    selinux = read_text(selinux_path)
    umount = read_text(umount_path)
    init = read_text(init_path)
    setuid = read_text(setuid_path)

    markers = [
        "XEN-SUSFS-KSUN-COMPAT-BEGIN" in kconfig,
        "XEN-SUSFS-KSUN-COMPAT: syscall bridge" in supercall,
        "XEN-SUSFS-KSUN-COMPAT: boot monitor" in dispatch,
        "XEN-SUSFS-KSUN-COMPAT-BEGIN" in kbuild,
        "XEN-SUSFS-KSUN-COMPAT: adapt the SUSFS domain helper" in selinux,
        "XEN-SUSFS-KSUN-COMPAT: expose try_umount" in umount,
        "XEN-SUSFS-KSUN-COMPAT: init" in init,
        "XEN-SUSFS-KSUN-COMPAT: setuid runtime" in setuid,
    ]
    if all(markers):
        print("XEN-SUSFS KSUN compatibility bridge is already applied.")
        return 0
    if any(markers):
        raise RuntimeError(
            "Partial XEN-SUSFS bridge detected; inspect the working tree before retrying."
        )

    if "CONFIG_KSU_SUSFS" in kconfig or "SUSFS_MAGIC" in supercall:
        raise RuntimeError(
            "Unexpected existing SUSFS integration found; refusing duplicate insertion."
        )

    # Add the SUSFS Kconfig menu before the single top-level endmenu.
    if kconfig.count("\nendmenu") != 1:
        raise RuntimeError("kernel/Kconfig: expected exactly one top-level endmenu")
    kconfig = replace_once(
        kconfig, "\nendmenu", "\n" + KCONFIG_BLOCK + "\nendmenu",
        "kernel/Kconfig SUSFS menu"
    )

    # Export the existing kernel-side SUSFS ABI through KSUN's current reboot hook.
    include_anchor = '#include <linux/utsname.h> // utsname() and uts_sem\n'
    susfs_include = (
        include_anchor
        + "\n#ifdef CONFIG_KSU_SUSFS\n"
        + '#include <linux/susfs.h> /* XEN-SUSFS-KSUN-COMPAT: include */\n'
        + "#endif\n"
    )
    supercall = replace_once(
        supercall, include_anchor, susfs_include, "supercall SUSFS include"
    )
    reboot_anchor = "\t// Check if this is a request to install KSU fd\n"
    supercall = replace_once(
        supercall, reboot_anchor, REBOOT_BRIDGE + "\n" + reboot_anchor,
        "supercall SUSFS syscall bridge"
    )

    # Start the SUSFS sdcard monitor on the normal boot-completed event.
    dispatch_anchor = '#include "uapi/supercall.h"\n'
    dispatch_include = (
        "#ifdef CONFIG_KSU_SUSFS\n"
        '#include <linux/susfs.h> /* XEN-SUSFS-KSUN-COMPAT: include */\n'
        "#endif\n"
        + dispatch_anchor
    )
    dispatch = replace_once(
        dispatch, dispatch_anchor, dispatch_include, "dispatch SUSFS include"
    )
    boot_anchor = r'''				pr_info("boot_complete triggered\n");
				on_boot_completed();
'''
    dispatch = replace_once(
        dispatch, boot_anchor, boot_anchor + DISPATCH_BOOT_BRIDGE,
        "dispatch boot-completed monitor"
    )

    # The SUSFS v2.3 source expects this helper from the previous KSUN layout.
    selinux_anchor = r'''bool is_ksu_domain(void)
{
    return is_task_ksu_domain(current_cred());
}
'''
    selinux = replace_once(
        selinux, selinux_anchor, selinux_anchor + "\n" + DOMAIN_BRIDGE,
        "SELinux current-domain compatibility bridge"
    )

    # The SUSFS source calls try_umount() when TRY_UMOUNT is enabled.
    # Keep the helper private for builds without that feature.
    umount_anchor = "static void try_umount(const char *mnt, int flags)\n{"
    umount_replacement = (
        "#if !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)\n"
        "static void try_umount(const char *mnt, int flags)\n"
        "#else /* XEN-SUSFS-KSUN-COMPAT: expose try_umount for SUSFS */\n"
        "void try_umount(const char *mnt, int flags)\n"
        "#endif\n{"
    )
    umount = replace_once(
        umount, umount_anchor, umount_replacement,
        "kernel umount exported helper"
    )

    # Initialize SUSFS once after KSUN's normal startup path. The source init
    # sets up the work item used by the setresuid transition below.
    init_include_anchor = '#include "feature/adb_root.h"\n'
    init = replace_once(
        init, init_include_anchor,
        init_include_anchor + "\n#ifdef CONFIG_KSU_SUSFS\n"
        + "#include <linux/susfs.h> /* XEN-SUSFS-KSUN-COMPAT: init include */\n"
        + "#endif\n",
        "kernel core init SUSFS include"
    )
    init_call_anchor = "\t\tksu_throne_tracker_init();\n\n\t\tksu_ksud_init();"
    init_call_replacement = (
        "\t\tksu_throne_tracker_init();\n\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\t\tsusfs_init(); /* XEN-SUSFS-KSUN-COMPAT: init */\n"
        "#endif\n\n"
        "\t\tksu_ksud_init();"
    )
    init = replace_once(
        init, init_call_anchor, init_call_replacement,
        "kernel core init SUSFS initialization"
    )

    # Port the runtime link that the old SUSFS-aware KSUN branch had in its
    # setresuid handler, but preserve this pin's two-argument ABI and manual hooks.
    setuid_include_anchor = '#include "compat/kernel_compat.h"\n'
    setuid = replace_once(
        setuid, setuid_include_anchor,
        setuid_include_anchor
        + "\n#ifdef CONFIG_KSU_SUSFS\n"
        + "#include <linux/cred.h>\n"
        + "#include <linux/susfs.h>\n"
        + "#include <linux/susfs_def.h>\n"
        + "#include <linux/workqueue.h>\n"
        + '#include "ksu.h"\n'
        + '#include "selinux/selinux.h"\n'
        + "#endif\n",
        "setuid SUSFS includes"
    )
    setuid_function_start = "int ksu_handle_setresuid(uid_t old_uid, uid_t new_uid)\n{"
    setuid_function_end = "\nvoid __init ksu_setuid_hook_init(void)"
    if setuid.count(setuid_function_start) != 1:
        raise RuntimeError("setuid hook: expected exactly one current two-argument function")
    start = setuid.index(setuid_function_start)
    end = setuid.find(setuid_function_end, start)
    if end < 0:
        raise RuntimeError("setuid hook: function end marker not found")
    setuid = (
        setuid[:start]
        + SETUID_HELPERS
        + "\n\n"
        + SETUID_FUNCTION
        + setuid[end:]
    )
    setuid = setuid.replace(
        "int ksu_handle_setresuid(uid_t old_uid, uid_t new_uid)\n{",
        "/* XEN-SUSFS-KSUN-COMPAT: setuid runtime */\n"
        "int ksu_handle_setresuid(uid_t old_uid, uid_t new_uid)\n{",
        1
    )

    # Make the module build fail early when SUSFS is enabled without kernel-side sources.
    if "XEN-SUSFS-KSUN-COMPAT-BEGIN" in kbuild:
        raise RuntimeError("kernel/Kbuild already contains the XEN-SUSFS bridge")
    kbuild = kbuild.rstrip() + "\n\n" + KBUILD_BLOCK.strip() + "\n"

    # All anchors are validated before any file is written.
    kconfig_path.write_text(kconfig, encoding="utf-8")
    supercall_path.write_text(supercall, encoding="utf-8")
    dispatch_path.write_text(dispatch, encoding="utf-8")
    kbuild_path.write_text(kbuild, encoding="utf-8")
    selinux_path.write_text(selinux, encoding="utf-8")
    umount_path.write_text(umount, encoding="utf-8")
    init_path.write_text(init, encoding="utf-8")
    setuid_path.write_text(setuid, encoding="utf-8")

    print("Applied XEN-SUSFS v2.3.0 compatibility bridge.")
    print(f"KSUN revision retained: {actual_sha}")
    print("KSU_MANUAL_HOOK and KPROBES settings were not changed.")
    print("Next: verify .config, apply the kernel call-site candidate, then compile.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
