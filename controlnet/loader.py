# SPDX-License-Identifier: GPL-3.0-or-later
# Loader adapted from ComfyUI PR #16519 (kijai), revision b0ab6a4.
# JR changes: restricted format checks, named paths, bounded shared loader cache.
from functools import lru_cache
from pathlib import Path
import torch
import folder_paths
import comfy.utils
import comfy.ops
import comfy.storage
import comfy.model_management
import comfy.model_patcher
from .model import QwenImage21FunControl


def checkpoint_config(sd):
    required = ('control_img_in.weight', 'control_blocks.0.img_mlp.out.weight',
                'control_blocks.0.attn.norm_q.weight', 'control_blocks.0.before_proj.weight')
    if any(k not in sd for k in required):
        raise ValueError('JR Director: select a Qwen Image 2.1 Fun Union checkpoint; older Qwen ControlNets are incompatible.')
    dim, channels = sd['control_img_in.weight'].shape
    indices = {int(k.split('.')[1]) for k in sd if k.startswith('control_blocks.') and k.endswith('.after_proj.weight')}
    if channels != 129 or dim != 4096 or indices != set(range(16)):
        raise ValueError('JR Director: unsupported Fun Union architecture; expected 129 input channels, 4096 hidden size and 16 blocks.')
    fused = 'control_blocks.0.img_mlp.gate_up.weight' in sd
    mlp_key = 'control_blocks.0.img_mlp.gate_up.weight' if fused else 'control_blocks.0.img_mlp.proj.weight'
    if mlp_key not in sd:
        raise ValueError('JR Director: checkpoint is missing its MLP weights.')
    hidden = sd[mlp_key].shape[0] // (2 if fused else 1)
    head = sd['control_blocks.0.attn.norm_q.weight'].shape[0]
    if hidden != 12288 or head != 128:
        raise ValueError('JR Director: unsupported Fun Union attention/MLP dimensions.')
    return dict(num_blocks=16, control_in_dim=129, inner_dim=dim,
                attention_head_dim=head, mlp_ratio=3, fused_mlp=fused)


def load_controlnet(name):
    category, separator, filename = name.partition('/')
    if not separator or category not in ('model_patches', 'controlnet'):
        raise ValueError('JR Director: select a ControlNet from the model dropdown.')
    # Resolve only listed files inside ComfyUI's configured model roots.
    if filename not in folder_paths.get_filename_list(category):
        raise ValueError(f'JR Director: ControlNet file not found: {name}. Refresh model lists after installing it.')
    path = folder_paths.get_full_path_or_raise(category, filename)
    stat = Path(path).stat()
    return _load(path, stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=1)
def _load(path, size, mtime_ns):
    sd = comfy.utils.load_torch_file(path, safe_load=True)
    config = checkpoint_config(sd)
    quant = comfy.utils.detect_layer_quantization(sd, '')
    device = comfy.model_management.get_torch_device()
    if quant is not None:
        dtype = torch.bfloat16
        operations = comfy.ops.mixed_precision_ops(quant, dtype)
    else:
        dtype = comfy.model_management.unet_dtype(model_params=-1,
            supported_dtypes=[torch.bfloat16, torch.float32], weight_dtype=comfy.utils.weight_dtype(sd))
        cast = comfy.model_management.unet_manual_cast(dtype, device,
            supported_dtypes=[torch.bfloat16, torch.float32])
        operations = comfy.ops.pick_operations(dtype, cast, load_device=device)
    model = QwenImage21FunControl(**config, dtype=dtype, operations=operations,
        device=comfy.model_management.unet_offload_device())
    model.requires_grad_(False).eval()
    patcher = comfy.model_patcher.CoreModelPatcher(model, load_device=device,
        offload_device=comfy.model_management.unet_offload_device(),
        fast_disk=comfy.storage.state_dict_fast_disk(sd))
    # Never accept silently missing layers: that can produce plausible but uncontrolled images.
    model.load_state_dict(sd, strict=True, assign=patcher.is_dynamic())
    return patcher
