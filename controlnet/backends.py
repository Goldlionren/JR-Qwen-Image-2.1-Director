"""Prefer merged Core support, retaining an explicit bundled comparison path."""
from functools import lru_cache
from pathlib import Path


def native_available():
    try:
        from comfy.ldm.qwen_image21 import model
        from comfy_extras import nodes_model_patch
    except ImportError:
        return False
    return (hasattr(model, 'QwenImage21FunControl') and
            hasattr(nodes_model_patch, 'QwenImage21FunControlPatch'))


def resolve_backend(requested, name):
    if requested not in ('auto', 'native', 'bundled'):
        raise ValueError('JR Director: unknown control_backend.')
    if requested == 'bundled':
        return requested
    available = native_available()
    # Core's ModelPatchLoader searches model_patches, not the older controlnet folder.
    supported_folder = name.startswith('model_patches/')
    if requested == 'native' and not available:
        raise ValueError('JR Director: this ComfyUI does not include native Qwen 2.1 Fun ControlNet; use auto or bundled.')
    if requested == 'native' and not supported_folder:
        raise ValueError('JR Director: native ControlNet must be selected from models/model_patches.')
    return ('native' if available and supported_folder else 'bundled') if requested == 'auto' else requested


@lru_cache(maxsize=1)
def _native_load(name, path, size, mtime):
    from comfy_extras.nodes_model_patch import ModelPatchLoader
    from comfy.ldm.qwen_image21.model import QwenImage21FunControl
    patcher = ModelPatchLoader().load_model_patch(name)[0]
    if not isinstance(patcher.model, QwenImage21FunControl):
        raise ValueError('JR Director: select a Qwen Image 2.1 Fun Union model patch.')
    return patcher


def apply_backend(model, name, vae, image, strength, start, end, backend='auto'):
    from .integration import validate_settings
    validate_settings(strength, start, end)
    selected = resolve_backend(backend, name)
    if selected == 'bundled':
        from .loader import load_controlnet
        from .integration import apply_control
        return apply_control(model, load_controlnet(name), vae, image, strength, start, end), selected
    import folder_paths
    from comfy.ldm.qwen_image21.model import QwenImage21Transformer2DModel
    from comfy_extras.nodes_model_patch import ZImageFunControlnet
    if not isinstance(model.get_model_object('diffusion_model'), QwenImage21Transformer2DModel):
        raise ValueError('JR Director: ControlNet requires a Qwen Image 2.1 MODEL.')
    if getattr(vae, 'latent_channels', None) != 64 or vae.spacial_compression_encode() != 16:
        raise ValueError('JR Director: select the Qwen Image 2.1 VAE.')
    filename = name.partition('/')[2]
    if filename not in folder_paths.get_filename_list('model_patches'):
        raise ValueError('JR Director: selected ControlNet is not in the model list.')
    path = folder_paths.get_full_path_or_raise('model_patches', filename)
    stat = Path(path).stat()
    patcher = _native_load(filename, path, stat.st_size, stat.st_mtime_ns)
    result = ZImageFunControlnet().diffsynth_controlnet(model, patcher, vae, image=image,
        strength=strength, start_percent=start, end_percent=end)[0]
    return result, selected
