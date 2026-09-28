# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from ComfyUI PR #16519 by kijai and ComfyUI contributors.
# Upstream revision: b0ab6a4c662a2e63fe2c0d7779dd06aeb62df3cf
# https://github.com/Comfy-Org/ComfyUI/pull/16519
# JR adaptation, 2026-09-28: project-local classes and instance-scoped compatibility.
# See docs/THIRD_PARTY_NOTICES.md and docs/licenses/ComfyUI-GPL-3.0.txt.
import torch
import comfy.utils
import comfy.model_management
import comfy.model_prefetch
import comfy.patcher_extension
import comfy.latent_formats

def in_sigma_range(transformer_options, sigma_range):
    sigma = float(transformer_options["sigmas"].flatten()[0])
    return sigma_range[1] <= sigma <= sigma_range[0]

class QwenImage21FunControlPatch:
    def __init__(self, model_patch, vae, image, strength, inpaint_image=None, mask=None, sigma_range=(float("inf"), 0.0)):
        self.model_patch = model_patch
        self.vae = vae
        self.image = image
        self.inpaint_image = inpaint_image
        self.mask = mask
        self.strength = strength
        self.sigma_range = sigma_range
        self.active = False
        self.injection_layers = None
        self.control = None
        self.stream = None
        self.pristine = None

    def prepare(self, h, w):
        # 129 channels per target token: control latents | keep mask | masked-image latents, zeros where not given
        if self.control is not None and self.control.shape[-2:] == (h, w):
            return
        width, height = w * self.vae.spacial_compression_encode(), h * self.vae.spacial_compression_encode()
        latent_format = comfy.latent_formats.QwenImage21()
        loaded_models = comfy.model_management.loaded_models(only_currently_used=True)
        try:
            control = torch.zeros(1, latent_format.latent_channels, h, w)
            if self.image is not None:
                image = comfy.utils.common_upscale(self.image[:1].movedim(-1, 1), width, height, "bicubic", "disabled")
                control = latent_format.process_in(self.vae.encode(image.movedim(1, -1))).float().cpu()
            regen = torch.ones(1, 1, height, width)
            if self.mask is not None:
                mask = self.mask.reshape(-1, 1, *self.mask.shape[-2:])[:1].float().cpu()
                regen = (comfy.utils.common_upscale(mask, width, height, "bilinear", "disabled") >= 0.5).float()
            inpaint = torch.zeros_like(control)
            if self.inpaint_image is not None:
                # regenerated pixels at mid-gray, the zero of the VAE's [-1, 1] input
                image = comfy.utils.common_upscale(self.inpaint_image[:1].movedim(-1, 1), width, height, "bicubic", "disabled").float().cpu()
                inpaint = latent_format.process_in(self.vae.encode((image * (1 - regen) + 0.5 * regen).movedim(1, -1))).float().cpu()
            keep = 1 - torch.nn.functional.interpolate(regen, size=(h, w), mode="nearest")
        finally:
            comfy.model_management.load_models_gpu(loaded_models)
        self.control = torch.cat([control, keep, inpaint], dim=1)

    def diffusion_model_wrapper(self, executor, x, timestep, context, ref_latents, image_slots, transformer_options, **kwargs):
        self.active = in_sigma_range(transformer_options, self.sigma_range)
        if self.active:
            with comfy.model_prefetch.pause_malloc_graph():
                self.prepare(*x.shape[-2:])
        else:
            # outside the range the block patches are dropped so the model can use its prefix cache
            dit = transformer_options.get("patches_replace", {}).get("dit", {})
            dit = {k: p.previous if isinstance(p, QwenImage21FunControlBlockPatch) and p.control_patch is self else p for k, p in dit.items()}
            dit = {k: p for k, p in dit.items() if p is not None}
            transformer_options = {**transformer_options, "patches_replace": {**transformer_options["patches_replace"], "dit": dit}}
        try:
            return executor(x, timestep, context, ref_latents, image_slots, transformer_options, **kwargs)
        finally:
            self.stream = None
            self.pristine = None

    def before_block(self, block_index, args):
        if self.active and block_index == self.injection_layers[0]:
            # the base block updates its input in place
            self.pristine = args["img"].clone()

    def after_block(self, block_index, args, out):
        if not self.active:
            return out
        model = self.model_patch.model
        index = self.injection_layers.index(block_index)
        if index == 0:
            self.control = self.control.to(out["img"].device, out["img"].dtype)
            self.stream = model.init_stream(self.pristine, self.control.flatten(2).transpose(1, 2), args["prefix_len"])
            self.pristine = None
        self.stream, skip = model.step(index, self.stream, args["mod"], args["pe"], args["attn_fn"], args["prefix_len"], args["transformer_options"])
        out["img"].add_(skip, alpha=self.strength)
        return out

    def to(self, device_or_dtype):
        if isinstance(device_or_dtype, torch.device):
            if self.control is not None:
                self.control = self.control.to(device_or_dtype)
            self.stream = None
        return self

    def cleanup(self):
        self.control = None
        self.stream = None
        self.pristine = None
        self.active = False

    def models(self):
        return [self.model_patch]

    def register(self, model):
        # the control blocks pair with every (num_base / num_control)-th base block
        num_base = len(model.get_model_object("diffusion_model").transformer_blocks)
        num_control = len(self.model_patch.model.control_blocks)
        if num_base != 32 or num_control != 16:
            raise ValueError('JR Director requires 32 base blocks and 16 Fun Union control blocks.')
        self.injection_layers = list(range(0, 32, 2))
        model.add_wrapper(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, self.diffusion_model_wrapper)
        blocks_replace = model.model_options.get("transformer_options", {}).get("patches_replace", {}).get("dit", {})
        for block_index in self.injection_layers:
            previous = blocks_replace.get(("single_block", block_index))
            model.set_model_patch_replace(QwenImage21FunControlBlockPatch(self, block_index, previous), "dit", "single_block", block_index)

class QwenImage21FunControlBlockPatch:
    def __init__(self, control_patch, block_index, previous):
        self.control_patch = control_patch
        self.block_index = block_index
        self.previous = previous

    def __call__(self, args, extra_args):
        # control state stays outside the base block's allocation scope
        with comfy.model_prefetch.pause_malloc_graph():
            self.control_patch.before_block(self.block_index, args)
        out = extra_args["original_block"](args) if self.previous is None else self.previous(args, extra_args)
        with comfy.model_prefetch.pause_malloc_graph():
            return self.control_patch.after_block(self.block_index, args, out)

    def to(self, device_or_dtype):
        self.control_patch.to(device_or_dtype)
        if hasattr(self.previous, "to"):
            self.previous = self.previous.to(device_or_dtype)
        return self

    def cleanup(self):
        self.control_patch.cleanup()
        if hasattr(self.previous, "cleanup"):
            self.previous.cleanup()

    def models(self):
        models = self.control_patch.models()
        if hasattr(self.previous, "models"):
            models += self.previous.models()
        return models
