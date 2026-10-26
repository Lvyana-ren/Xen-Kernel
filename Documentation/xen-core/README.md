# Xen Core kernel interface — implementation and application

## Goal

This change adds a small read-only kernel identity interface for Xen Core / Xen Control on POCO X3 Pro (codename `vayu`). It has no network dependency and exposes a fixed key and feature level for the app's local checks.

## Interface

Path: `/proc/xen_core`

Expected output for this initial integration:

```ini
FORMAT=1
FAMILY=Xen-Kernel
VERSION=KSUN+4
DEVICE=vayu
CORE_KEY=X3691QTZ
FEATURE_LEVEL=L1
```

The initial universal key `X3691QTZ` and level `L1` are provisional project constants. Change them in `fs/proc/xen_core.c` before a public release if the project chooses different values.

## Kernel implementation

1. `fs/proc/xen_core.c` formats the manifest using the kernel's seq_file helpers.
2. `fs/proc/Makefile` includes `xen_core.o` in the built-in procfs objects.
3. The entry is created read-only with mode `0444`; userspace cannot change the manifest through this file.
4. The implementation is built into the kernel and does not require a module, network service, or root access just to read the manifest.

## Xen Core app integration

On app startup:

1. Check device compatibility (expected device is `vayu`) and the running kernel release / family information.
2. Read `/proc/xen_core`. Treat a missing file or malformed manifest as unsupported.
3. Parse key-value lines; do not depend on line order.
4. Require `FORMAT=1`, `FAMILY=Xen-Kernel`, expected device, and an exact `CORE_KEY` match.
5. If identity check fails, lock Xen-exclusive features and show **Kernel not supported**.
6. If the kernel identity check passes but the key is missing or mismatched, lock Xen-exclusive features and show **Xen Kernel not support feature**.
7. Even with a matching key, gate each individual control on its actual kernel interface / capability. `FEATURE_LEVEL=L1` is not proof that every tuning interface exists.
8. Keep generic read-only device information available when compatible, even if Xen-exclusive features are locked.

Reading `/proc/xen_core` is not privileged. Writing CPU/GPU/sysfs controls is a separate operation and may require an explicit KernelSU Next root grant or a dedicated privileged bridge.

## Important security limitation

The family, version, device, and universal key are compiled into the kernel, but they are still readable and can be copied or spoofed by a modified kernel. This scheme is intentionally a simple compatibility gate, not cryptographic verification or anti-tamper protection. Do not use the manifest alone to authorize dangerous operations; validate capability and bounds for every control.

## Build and verification

From the repository root, using the project's established ARM64 Clang toolchain:

```sh
make ARCH=arm64 O=out vayu_defconfig
make ARCH=arm64 O=out CC=clang LD=ld.lld AR=llvm-ar \
  NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump \
  CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- \
  LLVM=1 LLVM_IAS=1 -j"$(nproc)"
```

After flashing and booting a build containing this change:

```sh
cat /proc/xen_core
test "$(grep -c '^CORE_KEY=' /proc/xen_core)" -eq 1
```

A source-level CI check can verify that the interface is wired into procfs, but only a successful full kernel build and device boot can verify the runtime interface end-to-end.

## Implementation history

- Designed a local, offline Xen Core activation gate: kernel/device identification followed by a universal key check.
- Selected `/proc/xen_core` as the read-only kernel-to-app manifest path.
- Added a built-in procfs implementation and Makefile registration.
- Defined manifest format version 1 and fields `FAMILY`, `VERSION`, `DEVICE`, `CORE_KEY`, and `FEATURE_LEVEL`.
- Documented app-side parsing, lock states, capability checks, and the separate root/privileged tuning path.
- Pending verification: full CI build, flashing/boot test on vayu, and app-side integration in the Xen Core repository.

## Rollback

Remove `proc-y += xen_core.o` from `fs/proc/Makefile` and remove `fs/proc/xen_core.c`; no existing procfs interface is replaced.
