#!/usr/bin/env bash
set -euo pipefail
KOWSU_REPO="https://github.com/KOWX712/KernelSU"
KOWSU_REF="d4873310a2738c4c5726a804ed58f1b473799a92"
rm -rf KernelSU
git clone --filter=blob:none --no-checkout "$KOWSU_REPO" KernelSU
git -C KernelSU fetch --depth=1 origin "$KOWSU_REF"
git -C KernelSU checkout --detach FETCH_HEAD
echo "KowSU commit: $(git -C KernelSU rev-parse HEAD)"
echo "=== KowSU kernel Kconfig ==="
sed -n '1,200p' KernelSU/kernel/Kconfig
test -s KernelSU/kernel/Kconfig
test -s KernelSU/kernel/Kbuild
test -s KernelSU/kernel/Makefile
rm -rf KernelSU/.git
ln -sfn ../KernelSU/kernel drivers/kernelsu
grep -qE '^obj-\$\(CONFIG_KSU\)[[:space:]]*\+= kernelsu/' drivers/Makefile || printf '\nobj-$(CONFIG_KSU) += kernelsu/\n' >> drivers/Makefile
grep -qF 'source "drivers/kernelsu/Kconfig"' drivers/Kconfig || sed -i '/^endmenu/i source "drivers/kernelsu/Kconfig"' drivers/Kconfig
git diff --check
