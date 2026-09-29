"""Use ComfyUI's native LoRA path; never modify the supplied base patcher."""
import math


def apply_anyangle(model, name, strength):
    strength = float(strength)
    if not math.isfinite(strength) or not 0 <= strength <= 2:
        raise ValueError('JR Director: AnyAngle strength must be between 0 and 2.')
    if not name or name == 'disabled' or strength == 0:
        return model
    if model is None:
        raise ValueError('JR Director: connect MODEL to load AnyAngle.')
    from comfy.ldm.qwen_image21.model import QwenImage21Transformer2DModel
    if not isinstance(model.model.diffusion_model, QwenImage21Transformer2DModel):
        raise ValueError('JR Director: AnyAngle requires a Qwen Image 2.1 MODEL.')
    import folder_paths
    import comfy.utils
    import comfy.sd
    path = folder_paths.get_full_path_or_raise('loras', name)
    lora = comfy.utils.load_torch_file(path, safe_load=True)
    patched, _ = comfy.sd.load_lora_for_models(model, None, lora, strength, 0)
    if sum(map(len, patched.patches.values())) <= sum(map(len, model.patches.values())):
        raise ValueError('JR Director: LoRA has no matching Qwen Image 2.1 weights.')
    return patched
