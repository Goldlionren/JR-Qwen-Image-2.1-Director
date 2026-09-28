# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the bundled ControlNet without editing or globally monkey-patching Core."""
import math
from types import MethodType
from .patch import QwenImage21FunControlPatch


def validate_settings(strength, start, end):
    if not all(math.isfinite(v) for v in (strength, start, end)):
        raise ValueError('JR Director: ControlNet settings must be finite numbers.')
    if not 0 <= strength <= 2 or not 0 <= start < end <= 1:
        raise ValueError('JR Director: strength must be 0–2 and 0 <= start < end <= 1.')


def apply_control(model, patcher, vae, image, strength, start, end):
    validate_settings(strength, start, end)
    if strength == 0:
        return model
    from comfy.ldm.qwen_image21.model import QwenImage21Transformer2DModel
    diffusion = model.get_model_object('diffusion_model')
    if not isinstance(diffusion, QwenImage21Transformer2DModel):
        raise ValueError('JR Director: ControlNet requires a Qwen Image 2.1 MODEL.')
    if getattr(vae, 'latent_channels', None) != 64 or vae.spacial_compression_encode() != 16:
        raise ValueError('JR Director: select the Qwen Image 2.1 VAE (64 channels, 16× compression).')
    if len(diffusion.transformer_blocks) != 32:
        raise ValueError('JR Director: expected the 32-block Qwen Image 2.1 base model.')
    result = model.clone()
    original = model.get_model_object('diffusion_model._forward')
    # Older Core already supports replacement blocks, but omits their attention/modulation arguments.
    # Patch this clone through ModelPatcher so ComfyUI restores the original when unpatching.
    consts = getattr(getattr(original, '__func__', original), '__code__', None)
    complete = consts is not None and any(
        isinstance(c, tuple) and all(isinstance(v, str) for v in c)
        and {'mod', 'attn_fn', 'prefix_len'}.issubset(c) for c in consts.co_consts)
    if not complete:
        from .compat import _forward
        result.add_object_patch('diffusion_model._forward', MethodType(_forward, diffusion))
    sampling = model.get_model_object('model_sampling')
    sigma_range = (float(sampling.percent_to_sigma(start)), float(sampling.percent_to_sigma(end)))
    patch = QwenImage21FunControlPatch(patcher, vae, image[..., :3], strength, sigma_range=sigma_range)
    patch.register(result)
    return result
