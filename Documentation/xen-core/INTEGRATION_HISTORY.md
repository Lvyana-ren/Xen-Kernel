# Xen Core integration history

Repository: `Lvyana-ren/Xen-Kernel`  
Target branch: `KSUN-Core`  
Target device: POCO X3 Pro (`vayu`)  
Base kernel: Linux 4.14.357

## Changes made

1. Added `fs/proc/xen_core.c`, a built-in, read-only procfs manifest using `seq_file`.
2. Registered `xen_core.o` in `fs/proc/Makefile`.
3. Exposed manifest format version 1 with these fields:
   - `FORMAT=1`
   - `FAMILY=Xen-Kernel`
   - `VERSION=KSUN+4`
   - `DEVICE=vayu`
   - `CORE_KEY=X3691QTZ`
   - `FEATURE_LEVEL=L1`
4. Added `.github/workflows/xen-core-build.yml` to run a vayu ARM64 build check when the relevant files change on `KSUN-Core`.
5. Added `Documentation/xen-core/README.md` with app-side integration instructions, validation flow, build instructions, security caveats, and rollback instructions.

## Commit trail

- `b08e0c3` — Add Xen Core read-only procfs manifest.
- `72b8087` — Document Xen Core kernel interface and app integration.
- `b62c3fd` — Add Xen Core vayu build workflow.
- `2da38f1` — Register Xen Core procfs object in the procfs build.
- `ac543e9` — Include errno definitions for procfs initialization.

## How Xen Core app should use it

1. Read `/proc/xen_core`.
2. Parse the key-value pairs without depending on line order.
3. Validate format, family, device and universal key.
4. If the manifest is absent/invalid, lock Xen-exclusive features and show the relevant unsupported message.
5. Check each feature's actual interface before showing/enabling it.
6. Keep root-only tuning on a separate, explicitly authorized KernelSU Next bridge; the manifest itself is read-only identity data.

## Verification status

The GitHub Actions build workflow was added and automatically triggered by pushes to `KSUN-Core`. Check the Actions page for the latest run before claiming a successful full build. Even a successful compile does not replace a boot test on the target phone and app-side integration testing.

## Known limitations

The universal key is deliberately simple and may be copied or spoofed by a modified kernel. It is a compatibility marker, not cryptographic attestation. The constants currently represent the initial integration and should be coordinated with the Xen Core app before release.
