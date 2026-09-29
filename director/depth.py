"""Optional local relative-depth inference; no model download or GPU allocation."""
from functools import lru_cache
from pathlib import Path
import threading
import numpy as np
import torch

_lock = threading.Lock()
CONFIGS = {'vits': (64,[48,96,192,384]), 'vitb': (128,[96,192,384,768]),
           'vitl': (256,[256,512,1024,1024])}


def available_models():
    import folder_paths
    roots = [Path(folder_paths.models_dir)]
    for category in ('diffusion_models','checkpoints','vae'):
        roots.extend(Path(p).parent for p in folder_paths.get_folder_paths(category))
    models = {}
    for root in dict.fromkeys(roots):
        for folder in ('depthanything','depth_anything'):
            for file in (root/folder).glob('depth_anything_v2_*.safetensors'):
                if any('_'+encoder in file.name for encoder in CONFIGS):
                    models.setdefault(file.name, file)
    return models


@lru_cache(maxsize=1)
def _load(path, size, mtime):
    from safetensors.torch import load_file
    from .vendor.depth_anything_v2.dpt import DepthAnythingV2
    encoder = next(e for e in CONFIGS if '_'+e in Path(path).name)
    features, channels = CONFIGS[encoder]
    model = DepthAnythingV2(encoder=encoder, features=features, out_channels=channels)
    model.load_state_dict(load_file(path, device='cpu'), strict=True)
    return model.float().eval().requires_grad_(False)


def estimate_depth(image, name):
    if image is None or image.ndim != 4 or image.shape[0] == 0 or image.shape[-1] < 3:
        raise ValueError('JR Director: automatic depth requires image (the source scene).')
    models = available_models()
    if name not in models:
        raise ValueError('JR Director: depth model not found in models/depthanything. Refresh model lists after installation.')
    rgb = image[0,:,:,:3].detach().float().cpu().numpy()
    if not np.isfinite(rgb).all():
        raise ValueError('JR Director: non-finite source image.')
    bgr = np.ascontiguousarray(np.rint(rgb.clip(0,1)*255).astype(np.uint8)[...,::-1])
    path = models[name];stat=path.stat()
    with _lock, torch.inference_mode():
        threads = torch.get_num_threads()
        try:
            torch.set_num_threads(min(threads,8))
            model = _load(str(path),stat.st_size,stat.st_mtime_ns)
            depth = model.infer_image(bgr,518)
        finally:
            torch.set_num_threads(threads)
    low, high = float(depth.min()), float(depth.max())
    depth = (depth-low)/max(high-low,1e-8)
    return torch.from_numpy(np.repeat(depth[...,None],3,axis=-1).astype(np.float32)).unsqueeze(0)
