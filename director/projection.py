import math
import numpy as np
from PIL import Image, ImageDraw
from .geometry import camera_points
from .state import RIG, NEAR, FAR


def project_point(point, state):
    w, h = state["render"]["width"], state["render"]["height"]
    focal = h / (2 * math.tan(math.radians(state["camera"]["fov"]) / 2))
    return np.array([w/2 + focal*point[0]/point[2], h/2 - focal*point[1]/point[2]])


def projected_joints(state):
    result = {}
    w, h = state["render"]["width"], state["render"]["height"]
    for name, point in camera_points(state).items():
        valid = NEAR <= point[2] <= FAR
        xy = project_point(point, state) if valid else np.array([0., 0.])
        result[name] = {"xy": xy.tolist(), "depth": float(point[2]),
                        "visible": bool(valid and 0 <= xy[0] <= w and 0 <= xy[1] <= h)}
    return result


def clip_segment(a, b, state):
    """Clip in camera space against all six frustum planes, before division."""
    tan = math.tan(math.radians(state["camera"]["fov"])/2)
    aspect = state["render"]["width"] / state["render"]["height"]
    planes = [(np.array([0,0,1]), -NEAR), (np.array([0,0,-1]), FAR),
              (np.array([1,0,tan*aspect]), 0), (np.array([-1,0,tan*aspect]), 0),
              (np.array([0,1,tan]), 0), (np.array([0,-1,tan]), 0)]
    start, end = 0., 1.
    for normal, offset in planes:
        da, db = np.dot(normal, a)+offset, np.dot(normal, b)+offset
        if da < 0 and db < 0:
            return None
        if da < 0 or db < 0:
            t = da/(da-db)
            if da < 0:
                start = max(start, t)
            else:
                end = min(end, t)
    if start > end:
        return None
    delta = b-a
    return a+delta*start, a+delta*end


def render_pose(state):
    w, h = state["render"]["width"], state["render"]["height"]
    # Supersampling for stable antialiasing. No disk IO or frontend state cache.
    ss = 2
    image = Image.new("RGB", (w*ss, h*ss), "black")
    draw = ImageDraw.Draw(image)
    points = camera_points(state)
    names, colors = RIG["openpose_joints"], RIG["colors"]
    primitives = []
    for i, (a, b) in enumerate(RIG["edges"]):
        segment = clip_segment(points[names[a]], points[names[b]], state)
        if segment is not None:
            p, q = segment
            primitives.append(((p[2]+q[2])/2, "bone", [project_point(p,state), project_point(q,state)], colors[i]))
    for i, name in enumerate(names):
        p = points[name]
        if NEAR <= p[2] <= FAR:
            xy = project_point(p, state)
            if 0 <= xy[0] <= w and 0 <= xy[1] <= h:
                primitives.append((p[2], "joint", [xy], colors[i]))
    radius = max(2, min(w,h)/180)*ss
    for _, kind, ps, color in sorted(primitives, key=lambda p: -p[0]):
        if kind == "bone":
            draw.line([tuple(p*ss) for p in ps], fill=tuple(int(c*0.65) for c in color), width=max(2, round(radius*1.25)))
        else:
            x,y = ps[0]*ss
            draw.ellipse((x-radius,y-radius,x+radius,y+radius), fill=tuple(color))
    return np.asarray(image.resize((w,h), Image.Resampling.LANCZOS), dtype=np.float32)/255.
