#!/usr/bin/env bash
set -euo pipefail
KOWSU_REPO="https://github.com/KOWX712/KernelSU"
KOWSU_REF="d4873310a2738c4c5726a804ed58f1b473799a92"
rm -rf KernelSU
git clone --filter=blob:none --no-checkout "$KOWSU_REPO" KernelSU
git -C KernelSU fetch --depth=1 origin "$KOWSU_REF"
git -C KernelSU checkout --detach FETCH_HEAD
echo "KowSU commit: $(git -C KernelSU rev-parse HEAD)"

# Linux 4.14 mount UAPI compatibility: use exported linux/mount.h instead of absent uapi header.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/infra/su_mount_ns.c")
s = p.read_text()
old = "#include <uapi/linux/mount.h>"
new = "#include <linux/mount.h>"
if old not in s:
    raise SystemExit("KowSU mount header include anchor not found")
p.write_text(s.replace(old, new, 1))
PY

# Linux 4.14 seccomp compatibility: native syscall count macro is named NR_syscalls.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/infra/seccomp_cache.c")
s = p.read_text()
if "SECCOMP_ARCH_NATIVE_NR" not in s:
    raise SystemExit("KowSU seccomp_cache.c unexpectedly lacks SECCOMP_ARCH_NATIVE_NR")
if "#ifndef SECCOMP_ARCH_NATIVE_NR" not in s:
    marker = '#include <linux/seccomp.h>\n'
    if marker not in s:
        raise SystemExit("KowSU seccomp_cache.c include anchor not found")
    compat = marker + '''#include <asm/unistd.h>
#ifndef SECCOMP_ARCH_NATIVE_NR
#define SECCOMP_ARCH_NATIVE_NR NR_syscalls
#endif
'''
    s = s.replace(marker, compat, 1)
p.write_text(s)
PY


# Linux 4.14 task_work/fsnotify compatibility for KowSU package observer.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/manager/pkg_observer.c")
s = p.read_text()

# Linux 4.14 task_work_add() takes a boolean notify_resume argument.
s = s.replace("#include <linux/version.h>", """#include <linux/version.h>
#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 3, 0)
#ifndef TWA_RESUME
#define TWA_RESUME true
#endif
#endif""", 1)

# Linux 4.14 fsnotify_ops uses handle_event(group, inode, marks, mask,
# data, data_type, filename, cookie, iter_info), not handle_inode_event().
old_sig = """static int ksu_handle_inode_event(struct fsnotify_mark *mark, u32 mask, struct inode *inode, struct inode *dir,
                                  const struct qstr *file_name, u32 cookie)
{"""
new_sig = """#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 1, 0)
static int ksu_handle_inode_event(struct fsnotify_group *group, struct inode *inode,
                                  struct fsnotify_mark *inode_mark,
                                  struct fsnotify_mark *vfsmount_mark, u32 mask,
                                  const void *data, int data_type,
                                  const unsigned char *file_name, u32 cookie,
                                  struct fsnotify_iter_info *iter_info)
#else
static int ksu_handle_inode_event(struct fsnotify_mark *mark, u32 mask, struct inode *inode, struct inode *dir,
                                  const struct qstr *file_name, u32 cookie)
#endif
{"""
if old_sig not in s:
    raise SystemExit("KowSU observer callback signature anchor not found")
s = s.replace(old_sig, new_sig, 1)

# Old fsnotify passes a filename byte string; newer API passes qstr.
s = s.replace("""    if (!file_name)
        return 0;
    if (mask & FS_ISDIR)
        return 0;
    if (file_name->len == 13 && !memcmp(file_name->name, "packages.list", 13)) {""", """#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 1, 0)
    if (!file_name)
        return 0;
    if (mask & FS_ISDIR)
        return 0;
    if (strlen(file_name) == 13 && !memcmp(file_name, "packages.list", 13)) {
#else
    if (!file_name)
        return 0;
    if (mask & FS_ISDIR)
        return 0;
    if (file_name->len == 13 && !memcmp(file_name->name, "packages.list", 13)) {
#endif""", 1)

s = s.replace("""static const struct fsnotify_ops ksu_ops = {
    .handle_inode_event = ksu_handle_inode_event,
};""", """static const struct fsnotify_ops ksu_ops = {
#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 1, 0)
    .handle_event = ksu_handle_inode_event,
#else
    .handle_inode_event = ksu_handle_inode_event,
#endif
};""", 1)
p.write_text(s)
PY

# Linux 4.14 file_operations compatibility: guard members absent from old kernels.
python3 - <<'PY'
from pathlib import Path
import re

p = Path("KernelSU/kernel/infra/file_wrapper.c")
s = p.read_text()

# iopoll exists only in newer kernels; wrap its declaration variants and assignment.
pattern = r'(#if LINUX_VERSION_CODE >= KERNEL_VERSION\(6, 1, 0\)\nstatic int ksu_wrapper_iopoll.*?#endif\n)'
m = re.search(pattern, s, re.S)
if not m:
    raise SystemExit("KowSU patch: iopoll declaration block not found (source mismatch)")
s = s[:m.start()] + "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 19, 0)\n" + m.group(1) + "#endif\n" + s[m.end():]

pattern = r'(    p->ops\.iopoll = fp->f_op->iopoll \? ksu_wrapper_iopoll : NULL;)'
s, n = re.subn(pattern, "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 19, 0)\n\\1\n#endif", s, count=1)
if n != 1:
    raise SystemExit("KowSU patch: iopoll assignment not found")

# remap_file_range and fadvise are absent from Linux 4.14 file_operations.
pattern = r'(// no REMAP_FILE_DEDUP.*?static int ksu_wrapper_fadvise\(.*?\n\})'
m = re.search(pattern, s, re.S)
if not m:
    raise SystemExit("KowSU patch: remap/fadvise block not found (source mismatch)")
s = s[:m.start()] + "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\n" + m.group(1) + "\n#endif\n" + s[m.end():]

pattern = r'(    p->ops\.remap_file_range = .*?\n    p->ops\.fadvise = .*?;)'
s, n = re.subn(pattern, "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\n\\1\n#endif", s, count=1)
if n != 1:
    raise SystemExit("KowSU patch: remap/fadvise assignments not found")

# mmap_supported_flags was added after Linux 4.14; fop_flags is newer still.
s = s.replace("#else\n    p->ops.mmap_supported_flags = fp->f_op->mmap_supported_flags;\n#endif",
              "#elif LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\n    p->ops.mmap_supported_flags = fp->f_op->mmap_supported_flags;\n#endif")
p.write_text(s)
PY

# Linux 4.14 seccomp struct compatibility: filter_count was added in Linux 5.9.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/policy/app_profile.c")
s = p.read_text()
old = "    atomic_set(&current->seccomp.filter_count, 0);"
new = """#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)
    atomic_set(&current->seccomp.filter_count, 0);
#endif"""
if old not in s:
    raise SystemExit("KowSU seccomp filter_count compatibility anchor not found")
p.write_text(s.replace(old, new, 1))
PY
# Linux 4.14 arm64 compatibility: upstream syscall_hook.h omits arm64 typedef.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/hook/syscall_hook.h")
s = p.read_text()
needle = "#elif defined(__riscv)\ntypedef long (*syscall_fn_t)(const struct pt_regs *);"
replacement = "#elif defined(__aarch64__)\ntypedef long (*syscall_fn_t)(const struct pt_regs *);\n#elif defined(__riscv)\ntypedef long (*syscall_fn_t)(const struct pt_regs *);"
if "defined(__aarch64__)" not in s:
    if needle not in s: raise SystemExit("No syscall_fn_t insertion anchor; abort")
    p.write_text(s.replace(needle, replacement, 1))

# Linux 4.14 exports architecture page-table headers as asm/pgtable.h.
p = Path("KernelSU/kernel/feature/sucompat.c")
s = p.read_text()
s = s.replace("#include <linux/pgtable.h>", """#include <linux/version.h>
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)
#include <linux/pgtable.h>
#else
#include <asm/pgtable.h>
#endif""")
p.write_text(s)

# MODULE_IMPORT_NS was introduced after Linux 4.14; avoid unsupported macro.
p = Path("KernelSU/kernel/core/init.c")
s = p.read_text()
s = s.replace('''#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 13, 0)
MODULE_IMPORT_NS("VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver");
#else
MODULE_IMPORT_NS(VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver);
#endif''', '''#ifdef MODULE_IMPORT_NS
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 13, 0)
MODULE_IMPORT_NS("VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver");
#else
MODULE_IMPORT_NS(VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver);
#endif
#endif''')
p.write_text(s)
PY

echo "=== KowSU ARM64/4.14 compatibility patch ==="
grep -n -A5 -B3 'syscall_fn_t' KernelSU/kernel/hook/syscall_hook.h
grep -n -A6 'MODULE_IMPORT_NS' KernelSU/kernel/core/init.c || true
test -s KernelSU/kernel/Kconfig
test -s KernelSU/kernel/Kbuild
test -s KernelSU/kernel/Makefile
ln -sfn ../KernelSU/kernel drivers/kernelsu
grep -qE '^obj-\$\(CONFIG_KSU\)[[:space:]]*\+= kernelsu/' drivers/Makefile || printf '\nobj-$(CONFIG_KSU) += kernelsu/\n' >> drivers/Makefile
grep -qF 'source "drivers/kernelsu/Kconfig"' drivers/Kconfig || sed -i '/^endmenu/i source "drivers/kernelsu/Kconfig"' drivers/Kconfig
git diff --check

# Temporary Linux 4.14 SELinux API compatibility gate.
# Modern KowSU policy replacement depends on selinux_state.policy (>=5.x).
# Keep legacy kernel buildable while a native policydb transaction port is developed.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/selinux/rules.c")
s = p.read_text()
if "XEN_KOWSU_SELINUX_414_GATE" in s:
    raise SystemExit("SELinux 4.14 gate already applied")
fallback = r"""
#else /* XEN_KOWSU_SELINUX_414_GATE */
#include <linux/errno.h>
#include <linux/types.h>
struct selinux_policy;
struct selinux_policy *backup_sepolicy;
void apply_kernelsu_rules(void)
{
    pr_warn("KowSU SELinux rules: Linux 4.14 policydb port pending; built-in rules skipped\\n");
}
int handle_sepolicy(void __user *user_data, u64 data_len)
{
    return -EOPNOTSUPP;
}
#endif /* XEN_KOWSU_SELINUX_414_GATE */
"""
s = "#define XEN_KOWSU_SELINUX_414_GATE\\n" + s
# use the version gate before any modern-only declarations/functions
s = s.replace("#include \\"linux/rcupdate.h\\"",
              "#include <linux/version.h>\\n#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 0, 0)\\n#include \\"linux/rcupdate.h\\", 1)
# The fallback is deliberately compile-only and fails closed for runtime sepolicy batches.
s += fallback
p.write_text(s)
PY
