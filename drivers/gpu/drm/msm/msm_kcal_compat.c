// SPDX-License-Identifier: GPL-2.0
#define pr_fmt(fmt) "msm_kcal_compat: " fmt

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

#include "sde_hw_kcal_ctrl.h"

extern struct sde_hw_kcal *sde_hw_kcal_get(void);
extern void kcal_force_update(void);

static struct sde_hw_kcal *kcal;

static unsigned int kcal_red;
static unsigned int kcal_green;
static unsigned int kcal_blue;

static int kcal_hue;
static int kcal_sat;
static int kcal_val;
static int kcal_cont;

static inline bool kcal_ready(void)
{
	return kcal != NULL;
}

static void kcal_apply_pcc(void)
{
	if (!kcal_ready())
		return;
    
    kcal->pcc.red   = clamp_t(int, kcal_red,   (int)kcal->min_value, 256);
    kcal->pcc.green = clamp_t(int, kcal_green, (int)kcal->min_value, 256);
    kcal->pcc.blue  = clamp_t(int, kcal_blue,  (int)kcal->min_value, 256);
}

static void kcal_apply_hsic(void)
{
	if (!kcal_ready())
		return;

	kcal->hsic.hue        = clamp(kcal_hue, 0, 1536);
	kcal->hsic.saturation = clamp(kcal_sat, 128, 383);
	kcal->hsic.value      = clamp(kcal_val, 128, 383);
	kcal->hsic.contrast   = clamp(kcal_cont, 128, 383);
}

#define DEFINE_KCAL_PARAM(_name, _field, _apply_fn)                     \
static int set_##_name(const char *val, const struct kernel_param *kp)  \
{                                                                      \
	int ret = param_set_int(val, kp);                                  \
	if (ret)                                                           \
		return ret;                                                    \
                                                                       \
	if (!kcal_ready())                                                 \
		return -ENODEV;                                                \
                                                                       \
	_apply_fn();                                                       \
	kcal_force_update();                                               \
                                                                       \
	return 0;                                                          \
}                                                                      \
                                                                       \
static int get_##_name(char *buf, const struct kernel_param *kp)        \
{                                                                      \
	if (!kcal_ready())                                                 \
		return -ENODEV;                                                \
                                                                       \
	return scnprintf(buf, PAGE_SIZE, "%d\n", _field);                 \
}                                                                      \
                                                                       \
static const struct kernel_param_ops _name##_ops = {                   \
	.set = set_##_name,                                                \
	.get = get_##_name,                                                \
};                                                                     \
                                                                       \
module_param_cb(_name, &_name##_ops, &_name, 0644)


DEFINE_KCAL_PARAM(kcal_red,   kcal->pcc.red,   kcal_apply_pcc);
DEFINE_KCAL_PARAM(kcal_green, kcal->pcc.green, kcal_apply_pcc);
DEFINE_KCAL_PARAM(kcal_blue,  kcal->pcc.blue,  kcal_apply_pcc);

DEFINE_KCAL_PARAM(kcal_hue,  kcal->hsic.hue,        kcal_apply_hsic);
DEFINE_KCAL_PARAM(kcal_sat,  kcal->hsic.saturation, kcal_apply_hsic);
DEFINE_KCAL_PARAM(kcal_val,  kcal->hsic.value,      kcal_apply_hsic);
DEFINE_KCAL_PARAM(kcal_cont, kcal->hsic.contrast,   kcal_apply_hsic);

static int __init msm_kcal_compat_init(void)
{
	kcal = sde_hw_kcal_get();
	if (!kcal) {
		pr_err("failed to get kcal struct\n");
		return -ENODEV;
	}

	kcal_red   = kcal->pcc.red;
	kcal_green = kcal->pcc.green;
	kcal_blue  = kcal->pcc.blue;

	kcal_hue  = kcal->hsic.hue;
	kcal_sat  = kcal->hsic.saturation;
	kcal_val  = kcal->hsic.value;
	kcal_cont = kcal->hsic.contrast;

	pr_info("KCAL compatibility layer initialized\n");

	return 0;
}
late_initcall(msm_kcal_compat_init);