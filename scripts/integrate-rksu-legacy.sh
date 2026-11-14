#!/usr/bin/env bash
set -euo pipefail

# Xen-Kernel RKSU Legacy integration (Linux 4.14)
RKSU_REPO="https://github.com/rsuntk/KernelSU"
RKSU_REF="v3.2.2-10-legacy"

rm -rf KernelSU
git clone --filter=blob:none --no-checkout "$RKSU_REPO" KernelSU
git -C KernelSU fetch --depth=1 origin "refs/tags/$RKSU_REF:refs/tags/$RKSU_REF"
git -C KernelSU checkout --detach "$RKSU_REF"

echo "RKSU commit: $(git -C KernelSU rev-parse HEAD)"
echo "RKSU source tree:"
find KernelSU -maxdepth 3 -type f | sort | head -200

# Validate upstream source contains expected legacy integration metadata.
test -d KernelSU/kernel
test -s KernelSU/kernel/Kconfig
test -s KernelSU/kernel/Makefile

# The integration point used by legacy KernelSU-family kernels.
# Keep source under kernel/ and expose it through drivers/kernelsu.
rm -rf KernelSU/.git
ln -sfn ../KernelSU/kernel drivers/kernelsu

# Add build and Kconfig references idempotently.
grep -qE '^obj-\$\(CONFIG_KSU\)[[:space:]]*\+= kernelsu/' drivers/Makefile || printf '\nobj-$(CONFIG_KSU) += kernelsu/\n' >> drivers/Makefile
grep -qF 'source "drivers/kernelsu/Kconfig"' drivers/Kconfig || sed -i '/^endmenu/i source "drivers/kernelsu/Kconfig"' drivers/Kconfig

# Do not assume a specific manual-hook symbol: inspect RKSU Kconfig and fail
# visibly if source requires GKI-only/KPROBE-only prerequisites.
echo "=== RKSU Kconfig ==="
sed -n '1,240p' KernelSU/kernel/Kconfig
echo "=== RKSU Makefile ==="
cat KernelSU/kernel/Makefile

git diff --check
