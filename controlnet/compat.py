# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from ComfyUI PR #16519 by kijai and ComfyUI contributors.
# Upstream revision: b0ab6a4c662a2e63fe2c0d7779dd06aeb62df3cf
# https://github.com/Comfy-Org/ComfyUI/pull/16519
# JR adaptation, 2026-09-28: project-local classes and instance-scoped compatibility.
# See docs/THIRD_PARTY_NOTICES.md and docs/licenses/ComfyUI-GPL-3.0.txt.
import torch
import comfy.model_prefetch
from comfy.ldm.qwen_image21.model import (
    _split_rows, prefix_cache_key, block_causal_attention, prefix_cached_attention,
)

def _forward(self, x, timesteps, context, ref_latents=None, image_slots=None, transformer_options={}, **kwargs):
    B, C, H, W = x.shape
    dtype = x.dtype
    ref_latents = list(ref_latents or [])
    image_slots = list(image_slots or [])

    hidden_states, pe, segments = self.build_sequence(x, context, ref_latents, image_slots)
    prefix_len = hidden_states.shape[1] - H * W
    patches = transformer_options.get("patches", {})
    for p in patches.get("post_input", []):
        out = p({"img": hidden_states, "pe": pe, "transformer_options": transformer_options})
        hidden_states, pe = out["img"], out.get("pe", pe)

    # pipeline rounds t*1000 and t to the compute dtype; text and reference tokens modulate from t = 0
    t = ((timesteps * 1000).to(dtype) / 1000).to(dtype)
    temb = self.time_text_embed(torch.cat([t, t.new_zeros(1)]), dtype)
    scale1, gate1, scale2, gate2 = self.modulation(temb).chunk(4, dim=-1)
    mod = (_split_rows(scale1), _split_rows(gate1.tanh()), _split_rows(scale2), _split_rows(gate2.tanh()), torch.zeros_like(scale1[:1, None]))

    blocks_replace = transformer_options.get("patches_replace", {}).get("dit", {})
    cache, cached = None, False
    # a cached step runs target rows only, so anything hooked into a block would see a different sequence from step 2
    hooked = blocks_replace or patches.get("post_input") or patches.get("single_block") or patches.get("attn1_patch")
    if self.prefix_cache_enabled and prefix_len > 0 and not hooked:
        key = prefix_cache_key(x, context, ref_latents, image_slots)
        cache_bytes = 2 * len(self.transformer_blocks) * B * prefix_len * self.inner_dim * hidden_states.element_size()
        cache, cached = self.select_prefix_cache(key, cache_bytes, x.device, transformer_options.get("qwen_image21_cache", {}))
    if cached:
        hidden_states, pe, prefix_len = hidden_states[:, prefix_len:], pe[:, prefix_len:], 0
    elif cache is not None:
        prefix_states, hidden_states = hidden_states[:, :prefix_len], hidden_states[:, prefix_len:]
        prefix_pe, pe = pe[:, :prefix_len], pe[:, prefix_len:]
        prefix_len = 0

    transformer_options["total_blocks"] = len(self.transformer_blocks)
    transformer_options["block_type"] = "single"
    prefetch_queue = comfy.model_prefetch.make_prefetch_queue(list(self.transformer_blocks), x.device, transformer_options)
    comfy.model_prefetch.malloc_graph_begin(x.device)
    for i, block in enumerate(self.transformer_blocks):
        comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, x.device, block, dtype, malloc_scope="block")
        transformer_options["block_index"] = i
        if cache is not None:
            if not cached:
                with comfy.model_prefetch.pause_malloc_graph():
                    prefix_attn = block_causal_attention(segments[:-1], transformer_options, cache, i, prefix_states.shape[1])
                    prefix_states = block(prefix_states, mod, prefix_pe, prefix_attn, prefix_states.shape[1], transformer_options)
            prefix_k, prefix_v = cache.take(i, x.device, dtype, B).unbind(1)
            if cached:
                cache.prefetch(i + 1, x.device, dtype)  # queue the next block before the compute it should overlap
            attn_fn = prefix_cached_attention(prefix_k, prefix_v, transformer_options)
        else:
            attn_fn = block_causal_attention(segments, transformer_options, cache, i, prefix_len)
        if ("single_block", i) in blocks_replace:
            def block_wrap(args):
                return {"img": block(args["img"], mod, args["pe"], attn_fn, prefix_len, args["transformer_options"])}
            args = {"img": hidden_states, "vec": temb, "pe": pe, "mod": mod, "attn_fn": attn_fn, "prefix_len": prefix_len, "transformer_options": transformer_options}
            hidden_states = blocks_replace[("single_block", i)](args, {"original_block": block_wrap})["img"]
        else:
            hidden_states = block(hidden_states, mod, pe, attn_fn, prefix_len, transformer_options)
        for p in patches.get("single_block", []):
            hidden_states = p({"img": hidden_states, "x": x, "block_index": i, "transformer_options": transformer_options})["img"]

    comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, x.device, None, malloc_scope="block")
    comfy.model_prefetch.malloc_graph_end()
    hidden_states = self.norm_out(hidden_states[:, prefix_len:], temb[:-1])
    hidden_states = self.proj_out(hidden_states)
    return hidden_states.transpose(1, 2).reshape(B, self.out_channels, H, W)
