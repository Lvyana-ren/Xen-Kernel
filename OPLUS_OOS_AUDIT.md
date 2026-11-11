# Xen OPLUS Compatibility Audit

## Source of truth

- Repository: https://github.com/Lvyana-ren/kernel_vayu_sm8150-OOS
- Branch: `oos-miniBpf515`
- Source commit: `68ada51611a7291cead104846ceb595a9937928a`
- Upstream subsystem entry: `drivers/oplus/Kconfig` and `drivers/oplus/Makefile`

## OPLUS components present in the OOS source

`binder_strategy`, `bootprof`, `devinfo`, `dump_reason`, `force_shutdown`,
`frame_boost`, `hans`, `midas`, `process_reclaim`, `project`,
`sched_info`, `shutdown_detect`, `storage`, `vnet`.

Source directory:
https://github.com/Lvyana-ren/kernel_vayu_sm8150-OOS/tree/oos-miniBpf515/drivers/oplus

## Porting rule

The OOS reference is a newer kernel tree (5.15-family); Xen is Linux 4.14.357.
Do **not** blindly wire these sources into Xen's build. Each subsystem must be
ported/adapted against Xen 4.14 APIs and reviewed for scheduler, Binder, MM,
network, tracepoint, and device-interface dependencies. Until adapted, these
sources are references, not compiled Xen drivers.

## Kernel uname spoof (ported)

In `kernel/sys.c`, `newuname()` returns release `5.10.239` only to UID 0
processes whose `comm` is `bpfloader`, `netbpfload`, or `netd`.
All other processes retain Xen's real release. This affects the userspace
`uname()` result only; it does not change `UTS_RELEASE`, `LINUX_VERSION_CODE`,
or add 5.10 BPF APIs.

## Current status

- [x] OOS source repository/branch pinned for audit.
- [x] Scoped uname spoof added to Xen `kernel/sys.c`.
- [ ] OPLUS subsystem source/API porting and build integration.
- [ ] Build validation.
- [ ] OOS boot/runtime validation.
