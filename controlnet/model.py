# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from ComfyUI PR #16519 by kijai and ComfyUI contributors.
# Upstream revision: b0ab6a4c662a2e63fe2c0d7779dd06aeb62df3cf
# https://github.com/Comfy-Org/ComfyUI/pull/16519
# JR adaptation, 2026-09-28: project-local classes and instance-scoped compatibility.
# See docs/THIRD_PARTY_NOTICES.md and docs/licenses/ComfyUI-GPL-3.0.txt.
import torch
from torch import nn
from comfy.ldm.qwen_image21.model import QwenImage21TransformerBlock

class QwenImage21FunControlBlock(QwenImage21TransformerBlock):
    def __init__(self, dim, num_attention_heads, attention_head_dim, mlp_ratio=3, eps=1e-6, fused_mlp=True, first=False, dtype=None, device=None, operations=None):
        super().__init__(dim, num_attention_heads, attention_head_dim, mlp_ratio, eps, fused_mlp, dtype=dtype, device=device, operations=operations)
        if first:
            self.before_proj = operations.Linear(dim, dim, dtype=dtype, device=device)
        self.after_proj = operations.Linear(dim, dim, dtype=dtype, device=device)

class QwenImage21FunControl(nn.Module):
    # VACE-style branch: a stream of block copies started from the embedded joint sequence, each skip added after one base block
    def __init__(self, num_blocks=16, control_in_dim=129, inner_dim=4096, attention_head_dim=128, mlp_ratio=3, eps=1e-6, fused_mlp=True, dtype=None, device=None, operations=None):
        super().__init__()
        self.control_img_in = operations.Linear(control_in_dim, inner_dim, dtype=dtype, device=device)
        self.control_blocks = nn.ModuleList([
            QwenImage21FunControlBlock(inner_dim, inner_dim // attention_head_dim, attention_head_dim, mlp_ratio, eps, fused_mlp, first=i == 0, dtype=dtype, device=device, operations=operations)
            for i in range(num_blocks)
        ])

    def init_stream(self, x, control, prefix_len):
        # control latents fill the target rows, text and reference rows stay zero
        joint = torch.zeros_like(x)
        joint[:, prefix_len:] = self.control_img_in(control)
        return self.control_blocks[0].before_proj(joint) + x

    def step(self, index, c, mod, pe, attn_fn, prefix_len, transformer_options={}):
        block = self.control_blocks[index]
        c = block(c, mod, pe, attn_fn, prefix_len, transformer_options)
        return c, block.after_proj(c)
