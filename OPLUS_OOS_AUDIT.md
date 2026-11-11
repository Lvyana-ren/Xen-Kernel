# Xen OPLUS Compatibility Audit

## Pinned OOS source

- Repository: https://github.com/Lvyana-ren/kernel_vayu_sm8150-OOS
- Branch: `oos-miniBpf515`
- Source commit: `68ada51611a7291cead104846ceb595a9937928a`
- OPLUS entry points: `drivers/oplus/Kconfig`, `drivers/oplus/Makefile`
- Native source tree: https://github.com/Lvyana-ren/kernel_vayu_sm8150-OOS/tree/oos-miniBpf515/drivers/oplus

## OPLUS inventory (native 5.15 reference)

`binder_strategy`, `bootprof`, `devinfo`, `dump_reason`, `force_shutdown`,
`frame_boost`, `hans`, `midas`, `process_reclaim`, `project`,
`sched_info`, `shutdown_detect`, `storage`, `vnet`.

This is a 5.15-family source snapshot. It is **not 4.14-ready**. Do not enable
these directories wholesale in Xen Kbuild: API differences span scheduler,
Binder, MM, tracepoints, networking, procfs/sysfs, and vendor hooks. Treat
native files as donor/reference material; port one subsystem at a time and
compile-test it against Xen 4.14.357.

## Kernel-version spoofing — already integrated

The scoped spoof is already present in this branch's `kernel/sys.c` in
`SYSCALL_DEFINE1(newuname)`:

- only UID 0;
- only process comm `bpfloader`, `netbpfload`, or `netd`;
- `uname().release` is reported as `5.10.239` for those callers;
- every other caller receives the real Xen release.

This is a userspace uname compatibility shim only. It does **not** change
`UTS_RELEASE`, `LINUX_VERSION_CODE`, kernel ABI, BPF verifier/helper support,
or turn the 4.14 kernel into 5.10. Keep this spoof isolated; do not globally
spoof uname or modify the kernel's actual version constants.

## Porting order (audit priority, not a boot dependency claim)

1. `devinfo` / `project`: small identity interfaces; inspect exact userspace reads.
2. `bootprof`, `dump_reason`, `force_shutdown`, `shutdown_detect`: diagnostics/
   lifecycle; not assumed to be boot blockers.
3. `vnet`: inspect OOS netd/vendor callers and kernel networking dependencies.
4. `binder_strategy`: high coupling to Binder internals; port only with matching
   Binder implementation/hooks.
5. `process_reclaim`, `midas`, `sched_info`, `frame_boost`, `hans`, `storage`:
   high coupling to MM/scheduler/trace/storage; separate feature compatibility
   from basic Android boot.

## Rules before enabling any component

- Preserve Xen 4.14.357 as the donor/base kernel.
- Do not copy 5.15 Kconfig/Makefile wiring directly into Xen.
- Resolve each subsystem's headers, symbols, tracepoints, config dependencies,
  and userspace ABI first.
- Keep unported code out of the active build.
- Boot blocker claims require evidence from OOS init/service logs or kernel logs,
  not merely the presence of a native OPLUS directory.

## Status

- [x] OOS repository and source commit pinned.
- [x] OPLUS subsystem inventory recorded.
- [x] Scoped `newuname()` spoof verified in `kernel/sys.c`.
- [ ] Per-subsystem 4.14 port/source transfer.
- [ ] Kconfig/Makefile integration after API adaptation.
- [ ] Build validation.
- [ ] OOS boot/runtime validation.
