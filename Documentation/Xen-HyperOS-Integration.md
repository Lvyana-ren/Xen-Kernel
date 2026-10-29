# Xen-Kernel HyperOS Compatibility Integration

Status: initial, conservative integration; requires device testing.

## Goal

Keep the Xen-Kernel `HyperOS` branch independently buildable and introduce a targeted MIUI/HyperOS display compatibility adjustment without replacing the entire AOSP-derived kernel tree with another kernel's source.

## Branch and baseline audit

- Target branch: `HyperOS`.
- Baseline commit before this integration: `b6bfad7181b7262551022335c196b5d06aa36760` (same commit as branch `16` at audit time).
- Reference AOSP tree: `Lvyana-ren/Xen-kernel_PocoX3pro_vayu:16`.
- Reference MIUI tree: `Lvyana-ren/hyperOS-Debug:16-miui`.
- The reference trees are not identical upstream snapshots. A raw tree-hash comparison showed about 1,347 differing common file blobs, including unrelated upstream/vendor changes. Therefore, copying whole files or merging the whole MIUI branch wholesale is unsafe.
- Relevant display-path differences identified in the previous audit include `drivers/gpu/drm/msm/dsi-staging/dsi_panel.c`, `dsi_display.c`, `dsi_drm.c`, `msm_drv.c`, `msm_drv.h`, `sde/sde_kms.c`, and `dsi_clk.h`. Only the panel PPS delay parsing is changed in this first pass; other differences require separate review before transplantation.

## Change applied

File: `drivers/gpu/drm/msm/dsi-staging/dsi_panel.c`

The AOSP-derived code attempted to read `qcom,mdss-pps-delay-ms`. When the property was absent, it set the field to zero, but then unconditionally assigned `data` to the field anyway. Since the read failed, `data` may not contain a valid value. The MIUI reference uses a fixed 10 ms value in the PPS command header.

The HyperOS branch now preserves a valid device-tree value when present, but explicitly sets `data = 10` when the property is missing. The existing PPS builder continues to use `dsc->pps_delay_ms`. This fixes the uninitialized-value path and adopts the MIUI/HyperOS-compatible fallback without hardcoding the command builder itself.

This is a plausible display compatibility fix, not proof that it is the sole cause of a boot stuck at the POCO logo. A display failure can look like a bootloop even when the kernel is running.

## Build workflow

The workflow previously hardcoded checkout of branch `16`, meaning dispatching it from `HyperOS` could still build the AOSP branch. The workflow is updated to check out `${{ github.ref_name }}`, label its artifact `Xen-Kernel-HyperOS`, and run on pushes to `HyperOS` as well as manual dispatches. The artifact should contain the kernel image, effective configuration, build log, and any DTB/DTBO outputs produced by the build.

## Audit checklist

1. Confirm the workflow source commit is the `HyperOS` branch commit, not branch `16`.
2. Check `git diff --check` and confirm only the intended PPS parsing block changed in the kernel source.
3. Confirm `olddefconfig` completes and inspect the final `.config`.
4. Confirm the kernel `Image` exists and is non-empty; inspect build logs for warnings/errors.
5. Compare DTB/DTBO hashes against the exact ROM/installer combination. Do not assume DTBO bundled by an installer is the same as a separately inspected DTBO.
6. Test with a recovery/fastboot rollback path available. Do not test on the only usable device without a known-good boot image.
7. If the device still hangs, collect `pstore/ramoops`, `dmesg` or recovery logs and identify whether the kernel reaches userspace. Do not add unrelated driver changes blindly.

## Not yet verified

- This integration has not yet been confirmed to boot on a physical HyperOS device.
- A GitHub Actions workflow result and downloadable artifact must be checked after the workflow trigger executes.
- Other MIUI-specific driver changes have not been transplanted. They should be reviewed one file/patch at a time, with particular attention to DSI/DSC/PPS, display power sequencing, KGSL/Adreno, and device-tree assumptions.
