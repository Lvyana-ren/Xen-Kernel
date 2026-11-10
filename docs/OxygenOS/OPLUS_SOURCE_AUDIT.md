# Xen OxygenOS OPLUS implementation audit

Status: source reconnaissance only; no OPLUS code has been transplanted or claimed boot-tested.

## Xen baseline
- Target branch: `OxygenOS-Beta-Integration`
- Kernel line: Linux 4.14.x (Xen vayu)
- Audit branch: `OxygenOS-OPLUS-Audit`

## Public donor trees
- OPPO SM8250 ColorOS source (S 12.1): https://github.com/oppo-source/android_kernel_oppo_sm8250/tree/oppo/sm8250_s_12.1
- OnePlus SM8250 source: https://github.com/oplus-kona/android_kernel_oneplus_sm8250
- OnePlus community OOS tree: https://github.com/LineageOS/android_kernel_oneplus_sm8250
- OPLUS build-feature makefile: https://github.com/oppo-source/android_kernel_oppo_sm8250/blob/oppo/sm8250_s_12.1/OplusKernelEnvConfig.mk
- OPLUS SOC Kconfig: https://github.com/oppo-source/android_kernel_oppo_sm8250/blob/oppo/sm8250_s_12.1/drivers/soc/oplus/Kconfig
- OPLUS SOC Makefile: https://github.com/oppo-source/android_kernel_oppo_sm8250/blob/oppo/sm8250_s_12.1/drivers/soc/oplus/Makefile
- HANS Kconfig/Makefile: https://github.com/oppo-source/android_kernel_oppo_sm8250/tree/oppo/sm8250_s_12.1/drivers/staging/android
- HANS header: https://github.com/oppo-source/android_kernel_oppo_sm8250/blob/oppo/sm8250_s_12.1/include/linux/hans.h

## Important compatibility finding
The OPPO donor is Linux **4.19.157**, whereas Xen is Linux **4.14.x**. It is not a drop-in source transplant: APIs, scheduler hooks, binder internals, and build/Kconfig integration may differ. Any port must be a deliberate 4.19 -> 4.14 backport and compile-tested.

## Recovered Optimus symbols: preliminary status
The recovered Optimus config contains (among others):
- `CONFIG_OPLUS_FEATURE_HANS`
- `CONFIG_OPLUS_FEATURE_FRAME_BOOST`
- `CONFIG_OPLUS_FEATURE_MULTI_FBG`
- `CONFIG_OPLUS_FEATURE_MIDAS_V2`
- `CONFIG_OPLUS_FEATURE_BINDER_STATS_ENABLE`
- `CONFIG_OPLUS_FEATURE_VIRTUAL_NET`
- `CONFIG_OPLUS_DEVICE_IFNO`
- `CONFIG_OPLUS_POGOPIN_FUNCTION`
- `CONFIG_OPLUS_FEATURE_OPROJECT`
- `CONFIG_OPLUS_FEATURE_FORCE_SHUTDOWN`
- `CONFIG_OPLUS_FEATURE_STORAGE_IO_METRICS`
- `CONFIG_OPLUS_FEATURE_FILE_MONITOR`
- `CONFIG_OPLUS_FEATURE_STORAGE_LOG`
- `CONFIG_OPLUS_BOOTPROF`
- `CONFIG_OPLUS_FEATURE_DUMP_REASON`
- `CONFIG_OPLUS_FEATURE_CPU_JANKINFO`
- `CONFIG_OPLUS_BINDER_STRATEGY`
- `CONFIG_OPLUS_FEATURE_SHUTDOWN_DETECT`

A config name is not proof of implementation. Initial donor code search found HANS code and binder stats references, but several recovered names do not appear as exact symbols in this OPPO SM8250 S12.1 tree. Some OPLUS features are injected as preprocessor macros by `OplusKernelEnvConfig.mk` / `oplus_native_features.mk`, not represented as ordinary Kconfig options. Optimus' config therefore cannot be blindly copied and expected to enable the right code.

## Donor structure observed
- `drivers/soc/oplus/` includes `device_info`, `healthinfo`, `iomonitor`, `midas`, `system`, `lowmem_dbg`, etc.
- `drivers/staging/android/hans.c` and `hans_netfilter.c` are built under the HANS feature gate.
- `drivers/soc/oplus/Kconfig` conditionally sources sub-Kconfigs based on OPLUS feature macros.
- `OplusKernelEnvConfig.mk` injects OPLUS compile macros and accepts a defined list of native features.
- This source is OPLUS/ColorOS-specific and must be matched against the actual OxygenOS userspace/vendor expectations, not enabled wholesale.

## Safe next port order
1. Obtain exact OxygenOS kernel source/commit (or matching OPLUS SM8250 source release) used by the ROM; identify vendor feature gates and ABI.
2. Compare the exact Optimus image's build fingerprint/config with donor source branch and locate implementation of each config symbol (including renamed symbols).
3. Port only boot-critical integration first: OPLUS environment macros, system/device info, bootprof/dump-reason/shutdown interfaces as proven required by OOS init/vendor.
4. Keep scheduler/performance features (HANS, frame boost, FBG, MIDAS) separate; they touch scheduler and task lifecycle, highest regression risk on 4.14.
5. Add Kconfig/Makefile wiring and compile-time guards; verify symbols survive `olddefconfig` and appear in final `.config`.
6. Build, inspect link/map/strings, then test boot with ramoops/pstore and OOS init/vendor logs.

## Conclusion
This branch documents the evidence and donor paths. It intentionally does **not** add unsupported OPLUS flags to Xen's defconfig or pretend to integrate binary-only features. A real code port requires matching source implementations and compatibility patches; the Optimus flashable ZIP and recovered `.config` alone are insufficient to reconstruct proprietary/modified source.
