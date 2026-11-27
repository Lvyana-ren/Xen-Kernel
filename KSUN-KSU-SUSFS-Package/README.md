# Xen-Kernel KSUN + SuSFS integration source package

This directory is a curated source bundle assembled from the Xen-Kernel `KSUN` branch and the pinned KernelSU-Next revision.

## Source pins

- Xen-Kernel: `Lvyana-ren/Xen-Kernel`, branch `KSUN`, base commit `4bcc6c855e3f4d5301aa7ff41449877ea5e583b4`
- KernelSU-Next: `Lvyana-ren/KernelSU-Next`, commit `7d8c81cc67552ab179702b66b20e811a0d4ef435`
- SUSFS source version: Xen-Kernel branch source; verify `SUSFS_VERSION` in `Xen-Kernel/include/linux/susfs.h` before building.

## Layout

- `Xen-Kernel/`: SUSFS kernel implementation, headers, the original kernel files used by the manual-hook overlay, the vayu defconfig, and the two integration scripts.
- `KernelSU-Next/`: the exact KSUN source files touched by `apply-ksun-susfs-compat.py`. These are compatibility-overlay files, not a complete KernelSU-Next checkout.

## Intended use

1. Start from a clean Xen-Kernel checkout at the recorded Xen-Kernel base commit.
2. Use the exact KernelSU-Next revision recorded above. The eight files in `KernelSU-Next/` are the files the compatibility script expects to patch.
3. Copy the three SUSFS source files to their matching paths in the kernel tree.
4. Apply `Xen-Kernel/scripts/apply-ksun-susfs-compat.py` to the pinned KernelSU-Next checkout.
5. Apply `Xen-Kernel/scripts/apply-ksun-manual-hooks.py` to the Xen-Kernel checkout if those manual KSU call-site hooks are not already present.
6. Review the resulting diff, Kconfig dependencies, Makefile object registration, defconfig symbols, and compile logs before flashing.

## Important scope and safety notes

- This is a source bundle for audit/porting, not a ready-to-flash kernel and not a prebuilt binary.
- The `KernelSU-Next/` folder intentionally contains only the eight exact files referenced by the SUSFS compatibility bridge. It does not replace the rest of the KernelSU-Next repository.
- The original Xen-Kernel files included beside the scripts are patch inputs/reference copies. Do not blindly overwrite a newer kernel tree with them; compare the base commit first.
- The SUSFS import workflow in Xen-Kernel explicitly stages only `fs/susfs.c`, `include/linux/susfs.h`, and `include/linux/susfs_def.h`; it records that Kconfig/Makefile, defconfig, manual hooks and build workflow were not changed by that staging workflow.
- The manual-hook script changes `fs/exec.c`, `fs/open.c`, `fs/read_write.c`, `fs/stat.c`, and `kernel/reboot.c`. It expects each anchor to match exactly once and aborts if the source does not match.
- The compatibility script refuses to run unless the KernelSU-Next HEAD equals the pinned commit. It modifies eight KSUN files and deliberately preserves the manual-hook/KPROBES mode.
- Do not assume the bundle builds just because files are present. Confirm the SUSFS object is registered in the kernel build system and resolve any patch conflicts against the exact target tree.

## Provenance

Every source file in this bundle is copied byte-for-byte from the pinned repository revision shown above. No kernel implementation source was reconstructed or fabricated for this package.
