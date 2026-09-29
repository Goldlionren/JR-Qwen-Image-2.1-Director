"""Experimental shaded rig guide, not image-to-3D reconstruction.

Ray/ellipsoid intersections share the Director's FK and perspective camera.
The guide has volume and occlusion, but no source texture or scene geometry.
"""
import math
import numpy as np
from PIL import Image
from .geometry import camera_basis, forward_kinematics
from .state import NEAR, FAR


def render_coarse(state):
    width, height = state['render']['width'], state['render']['height']
    scale = min(1., 768 / max(width, height))
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    p, rotations = forward_kinematics(state)
    size = state['actor']['scale']
    parts = []

    def ellipsoid(center, radii, rotation=None, color=(.70, .72, .75)):
        matrix = (np.eye(3) if rotation is None else rotation) @ np.diag(np.array(radii) * size)
        parts.append((center, np.linalg.inv(matrix), np.array(color)))

    def limb(a, b, radius):
        delta = p[b] - p[a]
        length = np.linalg.norm(delta)
        axis = delta / length
        helper = np.array([0., 0., 1.]) if abs(axis[2]) < .9 else np.array([1., 0., 0.])
        x = np.cross(axis, helper); x /= np.linalg.norm(x)
        z = np.cross(x, axis)
        ellipsoid((p[a] + p[b]) / 2, (radius, length / (2 * size) + radius * .3, radius), np.column_stack((x, axis, z)))

    ellipsoid(p['pelvis'], (.17, .15, .12), rotations['pelvis'])
    ellipsoid((p['spine'] + p['chest']) / 2, (.21, .26, .12), rotations['spine'])
    limb('chest', 'neck', .065)
    ellipsoid(p['head'], (.105, .145, .105), rotations['head'])
    ellipsoid(p['nose'], (.023, .027, .035), rotations['head'])
    for side in ('left', 'right'):
        ellipsoid(p[side + '_eye'], (.011, .009, .013), rotations['head'], (.18, .18, .18))
        for a, b, r in [('shoulder','elbow',.055), ('elbow','wrist',.043), ('hip','knee',.08), ('knee','ankle',.058)]:
            limb(side + '_' + a, side + '_' + b, r)
        for joint, r in [('shoulder',.066),('elbow',.048),('knee',.065)]:
            ellipsoid(p[side + '_' + joint], (r,r,r))
        ellipsoid(p[side + '_wrist'], (.045,.072,.027), rotations[side + '_wrist'])
        foot = p[side + '_ankle'] + rotations[side + '_ankle'] @ (np.array([0., -.015, .06]) * size)
        ellipsoid(foot, (.058,.048,.13), rotations[side + '_ankle'])

    camera, right, up, back = camera_basis(state)
    focal = h / (2 * math.tan(math.radians(state['camera']['fov']) / 2))
    light = np.array([-3., 5., 4.]); light /= np.linalg.norm(light)
    result = np.full((h, w, 3), .92, dtype=np.float32)
    # Bound scratch memory even for large canvases.
    for start in range(0, h, 48):
        end = min(h, start + 48)
        yy, xx = np.mgrid[start:end, :w]
        rays = ((xx[..., None] + .5 - w/2) / focal * right
                - (yy[..., None] + .5 - h/2) / focal * up - back)
        depth = np.full((end-start, w), FAR, dtype=np.float64)
        tile = result[start:end]
        for center, inverse, color in parts:
            origin = inverse @ (camera - center)
            direction = rays @ inverse.T
            aa = np.sum(direction * direction, axis=-1)
            bb = np.sum(direction * origin, axis=-1)
            cc = np.dot(origin, origin) - 1
            disc = bb*bb - aa*cc
            root = np.sqrt(np.maximum(disc, 0))
            near = (-bb - root) / aa
            far = (-bb + root) / aa
            distance = np.where(near >= NEAR, near, far)
            visible = (disc >= 0) & (distance >= NEAR) & (distance < depth)
            if not visible.any():
                continue
            normal = (origin + direction[visible] * distance[visible, None]) @ inverse
            normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
            shade = .35 + .65 * np.maximum(normal @ light, 0)
            tile[visible] = color * shade[:, None]
            depth[visible] = distance[visible]
    if (w,h) != (width,height):
        result = np.asarray(Image.fromarray((result*255).astype(np.uint8)).resize((width,height), Image.Resampling.LANCZOS), dtype=np.float32)/255
    return result
