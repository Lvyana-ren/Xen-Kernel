#!/usr/bin/env bash
set -euo pipefail
KOWSU_REPO="https://github.com/KOWX712/KernelSU"
KOWSU_REF="d4873310a2738c4c5726a804ed58f1b473799a92"
rm -rf KernelSU
git clone --filter=blob:none --no-checkout "$KOWSU_REPO" KernelSU
git -C KernelSU fetch --depth=1 origin "$KOWSU_REF"
git -C KernelSU checkout --detach FETCH_HEAD
echo "KowSU commit: $(git -C KernelSU rev-parse HEAD)"

# Linux 4.14 file_operations compatibility: omit API members absent from old kernels.
python3 - <<'PY'
from pathlib import Path
p = Path("KernelSU/kernel/infra/file_wrapper.c")
s = p.read_text()

# iopoll is not part of Linux 4.14 file_operations.
start = s.index("#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 1, 0)\\nstatic int ksu_wrapper_iopoll")
end = s.index("#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)\\nstatic int ksu_wrapper_iterate", start)
s = s[:start] + "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 19, 0)\\n" + s[start:end] + "#endif\\n\\n" + s[end:]

# Newer file_operations members: remap_file_range, fadvise and mmap_supported_flags.
start = s.index("// no REMAP_FILE_DEDUP")
end = s.index("static void ksu_release_file_wrapper", start)
s = s[:start] + "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\\n" + s[start:end] + "#endif\\n\\n" + s[end:]

s = s.replace("    p->ops.iopoll = fp->f_op->iopoll ? ksu_wrapper_iopoll : NULL;", "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 19, 0)\\n    p->ops.iopoll = fp->f_op->iopoll ? ksu_wrapper_iopoll : NULL;\\n#endif")
s = s.replace("#else\\n    p->ops.mmap_supported_flags = fp->f_op->mmap_supported_flags;\\n#endif", "#elif LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\\n    p->ops.mmap_supported_flags = fp->f_op->mmap_supported_flags;\\n#endif")
s = s.replace("    p->ops.remap_file_range = fp->f_op->remap_file_range ? ksu_wrapper_remap_file_range : NULL;\\n    p->ops.fadvise = fp->f_op->fadvise ? ksu_wrapper_fadvise : NULL;", "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)\\n    p->ops.remap_file_range = fp->f_op->remap_file_range ? ksu_wrapper_remap_file_range : NULL;\\n    p->ops.fadvise = fp->f_op->fadvise ? ksu_wrapper_fadvise : NULL;\\n#endif")
p.write_text(s)
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
