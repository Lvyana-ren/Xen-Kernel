# Xen-Kernel OxygenOS Beta build

Target: Xiaomi Poco X3 Pro (vayu), OxygenOS/ColorOS port bring-up.

The GitHub Actions workflow builds the kernel Image and requests the device-tree targets (`dtbs`). It explicitly checks and exports:
- `vayu-sm8150-base.dtb` from `sm8150-xiaomi.dtb`
- `vayu-sm8150-overlay.dtbo` from `vayu-sm8150-overlay.dtbo`

These are raw DTB and DTBO compiler outputs, not an Android `dtbo.img` partition image. Do not flash these raw files to the DTBO partition. Packaging/validation against the target ROM's boot-chain format is a separate step.

Build success is not proof of OxygenOS boot compatibility; runtime testing on the exact ROM build remains mandatory.
