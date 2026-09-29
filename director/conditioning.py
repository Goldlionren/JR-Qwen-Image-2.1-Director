"""Experimental RGB hints. This is not a depth estimator or a pose warp."""
import math
import torch
import torch.nn.functional as F


def fit_reference(reference, canvas):
    """Fit first RGB frame to a target canvas without stretching or cropping."""
    if reference is None or reference.ndim != 4 or reference.shape[0] < 1 or reference.shape[-1] < 3:
        raise ValueError('JR Director: reference must be a non-empty RGB IMAGE.')
    height, width = canvas.shape[1:3]
    rh, rw = reference.shape[1:3]
    if rh < 1 or rw < 1:
        raise ValueError('JR Director: reference image has an empty dimension.')
    scale = min(height / rh, width / rw)
    h, w = max(1, round(rh * scale)), max(1, round(rw * scale))
    rgb = reference[:1, :, :, :3].to(device=canvas.device, dtype=canvas.dtype)
    rgb = F.interpolate(rgb.movedim(-1, 1), size=(h, w), mode='bilinear',
                        align_corners=False, antialias=True).movedim(1, -1).clamp(0, 1)
    result = torch.zeros_like(canvas)
    top, left = (height - h) // 2, (width - w) // 2
    result[:, top:top + h, left:left + w] = rgb
    return result


def scenario_references(mode, pose, source, identity=None):
    if mode not in ('director', 'edit_pose', 'replace_person'):
        raise ValueError('JR Director: unknown task_mode.')
    if mode == 'director':
        return None, None, None
    if source is None:
        raise ValueError('JR Director: connect image (source scene / pose) for this task_mode.')
    source = fit_reference(source, pose)
    if mode == 'edit_pose':
        return source, pose, None
    if identity is None:
        raise ValueError('JR Director: replace_person requires identity_image (the replacement person).')
    return fit_reference(identity, pose), source, pose


def reference_overlay(pose, reference, opacity=0.0):
    """Preserve colored bones over a dim, aspect-fitted first reference frame."""
    opacity = float(opacity)
    if not math.isfinite(opacity) or not 0 <= opacity <= 0.1:
        raise ValueError('JR Director: reference opacity must be between 0 and 0.10.')
    if opacity == 0:
        return pose
    if reference is None:
        raise ValueError('JR Director: connect image to use reference_opacity.')
    background = fit_reference(reference, pose) * opacity
    # The renderer antialiases on black. Max RGB approximates stroke coverage;
    # keep full-intensity OpenPose joint/limb colors unchanged.
    coverage = pose.amax(dim=-1, keepdim=True).clamp(0, 1)
    return (pose + background * (1 - coverage)).clamp(0, 1)
