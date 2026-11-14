#!/usr/bin/env bash
set -euo pipefail
KOWSU_REPO="https://github.com/KOWX712/KernelSU"
KOWSU_REF="d4873310a2738c4c5726a804ed58f1b473799a92"
rm -rf KernelSU
git clone --filter=blob:none --no-checkout "$KOWSU_REPO" KernelSU
git -C KernelSU fetch --depth=1 origin "$KOWSU_REF"
git -C KernelSU checkout --detach FETCH_HEAD
echo "KowSU commit: $(git -C KernelSU rev-parse HEAD)"

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
