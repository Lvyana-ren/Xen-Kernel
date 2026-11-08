# Xen-Kernel OxygenOS port compatibility

This branch adds a **ROM-mode selector** to the Vayu kernel. It is a compatibility
metadata/policy hook, not a claim that any OxygenOS port boots without matching
vendor, firmware, DTB/DTBO and ramdisk components.

## Kernel selector

Pass one of these tokens through the kernel command line:

- `xen_args=rom_auto` — default; no ROM-specific behavior is assumed.
- `xen_args=rom_aosp` — AOSP mode.
- `xen_args=rom_oem` — OEM/MIUI-style mode.
- `xen_args=rom_oos` (alias `rom_oxygen`) — OxygenOS mode.

The early parser is implemented in `drivers/misc/xen_rom_compat.c`.
When `CONFIG_XEN_ROM_COMPAT=y`, the selected mode is readable at:

```
/sys/kernel/xen_rom/mode
```

Kernel consumers can include `linux/xen_rom_compat.h` and call
`xen_rom_get_type()` or `xen_rom_is_oos()`. The selector defaults to AUTO,
so existing AOSP/HyperOS boots remain unchanged when no argument is supplied.

## What this branch intentionally does not do

The selector does **not**:
- inject OxygenOS vendor drivers into the Xiaomi Vayu kernel;
- blindly skip OPlus/QCOM initcalls;
- rewrite DTB/DTBO or battery characteristics;
- bypass SELinux, AVB, or vendor ABI requirements.

These are not safe global switches. Any ROM-specific driver gating must be
added only after its init path and dependencies have been audited against the
actual Vayu/OOS port.

## RE404-derived boot/install notes

RE404's AnyKernel script detects OxygenOS from `ro.product.brand` and selects
its OEM DTBO path. Its boot argument family (`e404_args`) also separates
DTBO, refresh-rate, touchscreen and battery options. Xen deliberately uses a
separate namespace (`xen_args`) and does not reuse E404's private ABI.

For an OOS port test, use the **port's matching DTBO/vendor/firmware set** and
record the original boot command line first. Add `xen_args=rom_oos` only if
the installer/boot image can preserve it. Do not replace an OOS DTBO with the
RE404 binary merely because both installers label it OEM.

## Validation checklist (device required)

1. Build `vayu_defconfig` and confirm `CONFIG_XEN_ROM_COMPAT=y`.
2. Boot the baseline AOSP/HyperOS setup without `xen_args`; mode must read
   `auto (0)` and behavior should be unchanged.
3. Boot with `xen_args=rom_oos`; mode must read `oxygenos (3)`.
4. Test the actual OOS port with its matched vendor, firmware and DTBO; capture
   serial/dmesg and Android boot logs.
5. Reboot to the previous ROM and run a regression check.

A successful compile or mode read is **not** proof of OxygenOS boot compatibility.


## Installer-to-kernel argument bridge (experimental)

RE404's installer writes its selected profile into the boot image command line
using `patch_cmdline "e404_args"`. Xen's early parser is separate and expects
`xen_args`. Until a Xen installer explicitly writes this key, selecting an
OxygenOS profile in an installer will **not** activate `xen_rom_is_oos()`.

For a controlled test, append `xen_args=rom_oos` to the existing kernel command
line without removing any existing arguments. Confirm it survives boot by
checking `/sys/kernel/xen_rom/mode` and `dmesg | grep Xen-ROM`.

RE404 installer profiles (OEM DTBO, 120Hz, IR0, default battery, touchscreen
mod disabled) are device/firmware choices, not generic OxygenOS settings.
Do not copy its DTBO or battery profile into Xen by default: use the exact OOS
port's matching DTBO and battery/charger configuration. The RE404 6000mAh
battery selection is an explicit alternate profile and must only be enabled
when the physical battery and fuel-gauge calibration match it.
