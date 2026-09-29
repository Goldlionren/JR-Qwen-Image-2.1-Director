"""Experimental RGB hints. This is not a depth estimator or a pose warp."""
import math
import torch
import torch.nn.functional as F


def reference_overlay(pose, reference, opacity=0.0):
    """Preserve colored bones over a dim, aspect-fitted first reference frame."""
    opacity = float(opacity)
    if not math.isfinite(opacity) or not 0 <= opacity <= 0.1:
        raise ValueError('JR Director: reference opacity must be between 0 and 0.10.')
    if opacity == 0:
        return pose
    if reference is None:
        raise ValueError('JR Director: connect image to use reference_opacity.')
    if reference.ndim != 4 or reference.shape[0] < 1 or reference.shape[-1] < 3:
        raise ValueError('JR Director: reference must be a non-empty RGB IMAGE.')
    height, width = pose.shape[1:3]
    rh, rw = reference.shape[1:3]
    if rh < 1 or rw < 1:
        raise ValueError('JR Director: reference image has an empty dimension.')
    scale = min(height / rh, width / rw)
    h, w = max(1, round(rh * scale)), max(1, round(rw * scale))
    rgb = reference[:1, :, :, :3].to(device=pose.device, dtype=pose.dtype)
    rgb = F.interpolate(rgb.movedim(-1, 1), size=(h, w), mode='bilinear',
                        align_corners=False, antialias=True).movedim(1, -1).clamp(0, 1)
    background = torch.zeros_like(pose)
    top, left = (height - h) // 2, (width - w) // 2
    background[:, top:top + h, left:left + w] = rgb * opacity
    # The renderer antialiases on black. Max RGB approximates stroke coverage;
    # keep full-intensity OpenPose joint/limb colors unchanged.
    coverage = pose.amax(dim=-1, keepdim=True).clamp(0, 1)
    return (pose + background * (1 - coverage)).clamp(0, 1)
