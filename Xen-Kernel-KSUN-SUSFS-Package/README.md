# Xen-Kernel KSUN + SuSFS source package

This directory is a source-layout package assembled from two pinned sources.

## Source pins
- Xen-Kernel: branch `KSUN` (the package branch is based on this branch).
- KernelSU-Next: `Lvyana-ren/KernelSU-Next`, commit `7d8c81cc67552ab179702b66b20e811a0d4ef435`.
- SuSFS: v2.3.0, as declared by `include/linux/susfs.h`.

## Layout
- `kernel-overlay/`: files copied from Xen-Kernel/KSUN that contain SuSFS integration and the kernel-side manual-hook patch targets.
- `KernelSU-Next/kernel/`: complete KernelSU-Next kernel source subtree at the pinned commit. In the build workflow, this subtree is linked as `drivers/kernelsu`.
- `scripts/`: KSUN/SuSFS compatibility and manual-hook scripts copied from Xen-Kernel/KSUN.

## Important integration notes
1. This is a source package, not a ready-to-flash kernel or a guaranteed drop-in patch for a different kernel revision.
2. Files under `kernel-overlay/` preserve the exact source contents from the Xen-Kernel KSUN branch. For another kernel tree, compare/merge VFS and Kconfig/Makefile files instead of blindly overwriting them.
3. The manual-hook script expects the kernel source root as its current working directory and patches `fs/exec.c`, `fs/open.c`, `fs/read_write.c`, `fs/stat.c`, and `kernel/reboot.c`.
4. The compatibility bridge script expects a Git checkout of KernelSU-Next at the exact pinned commit and patches files inside its `kernel/` subtree.
5. The build workflow links `KernelSU-Next/kernel` to `drivers/kernelsu` and adds `source "drivers/kernelsu/Kconfig"` to `drivers/Kconfig` when absent.
6. Do not enable SuSFS config options unless the corresponding source and hooks are present. Validate the resulting .config and compile before flashing.

## Integrity
A source manifest is provided alongside this README. File SHA-1 values are Git blob object IDs returned by GitHub for the original source files.
