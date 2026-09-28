"""Fit detected 2D body landmarks to the editable, fixed-length Director rig.

This is a regularized 2D fit, not monocular metric 3D reconstruction. Depth and
occluded joints remain ambiguous. No image geometry is stored as a new bone length.
"""
import copy
import math
import warnings
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .geometry import forward_kinematics
from .state import default_state, parse_state, JOINTS

COCO = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee",
        "right_knee", "left_ankle", "right_ankle"]
LIMBS = [(f"{side}_{a}", f"{side}_{b}") for side in ("right", "left")
         for a, b in (("shoulder", "elbow"), ("elbow", "wrist"), ("hip", "knee"), ("knee", "ankle"))]


def euler(matrix):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return Rotation.from_matrix(matrix).as_euler("XYZ", degrees=True).tolist()


def align(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    axis = np.cross(a, b)
    dot = float(np.clip(a @ b, -1, 1))
    if np.linalg.norm(axis) < 1e-8:
        if dot > 0:
            return np.eye(3)
        axis = np.cross(a, [1, 0, 0] if abs(a[0]) < .8 else [0, 1, 0])
    axis /= np.linalg.norm(axis)
    return Rotation.from_rotvec(axis * math.acos(dot)).as_matrix()


def fit_pose(keypoints, width, height, base_state=None):
    points = np.asarray(keypoints, dtype=float)
    if points.shape != (17, 3) or not np.isfinite(points).all():
        raise ValueError("Expected 17 finite COCO (x, y, confidence) landmarks")
    if not (32 <= width <= 8192 and 32 <= height <= 8192):
        raise ValueError("Unsupported source image dimensions")
    valid = ((points[:, 2] >= .3) & (points[:, 0] >= 0) & (points[:, 0] < width)
             & (points[:, 1] >= 0) & (points[:, 1] < height))
    visible = {name for name, yes in zip(COCO, valid) if yes}
    if not {"left_shoulder", "right_shoulder"} <= visible or valid[5:].sum() < 4:
        raise ValueError("肩部或躯干关键点不足，无法建立可靠骨架。请换用人物更清晰的图片。")
    state = default_state()
    base = parse_state(base_state or {})
    longest = max(base["render"]["width"], base["render"]["height"])
    state["render"].update(width=max(64, round(width / max(width, height) * longest / 32) * 32),
                           height=max(64, round(height / max(width, height) * longest / 32) * 32))
    image = {name: np.array([p[0], -p[1], 0.]) for name, p in zip(COCO, points)}
    shoulder_mid = (image["left_shoulder"] + image["right_shoulder"]) / 2
    hip_ok = {"left_hip", "right_hip"} <= visible
    hip_mid = (image["left_hip"] + image["right_hip"]) / 2 if hip_ok else shoulder_mid - [0, 1, 0]
    # Use shoulder left/right labels to preserve a detected back-facing body.
    x = image["left_shoulder"] - image["right_shoulder"]
    if np.linalg.norm(x) < 2:
        x = np.array([1., 0, 0])
    x /= np.linalg.norm(x)
    y = shoulder_mid - hip_mid
    y -= x * (x @ y)
    if np.linalg.norm(y) < 1e-5:
        y = np.array([-x[1], x[0], 0.])
    y /= np.linalg.norm(y)
    frame = np.column_stack((x, y, np.cross(x, y)))
    state["pose"]["joints"]["pelvis"] = euler(frame)
    for parent, child in LIMBS:
        if {parent, child} <= visible:
            desired = image[child] - image[parent]
            if np.linalg.norm(desired) < 2:
                continue
            _, rotations = forward_kinematics(state)
            upstream = JOINTS[parent]["parent"]
            current = rotations[parent] @ np.array(JOINTS[child]["offset"])
            global_rotation = align(current, desired) @ rotations[parent]
            state["pose"]["joints"][parent] = euler(rotations[upstream].T @ global_rotation)
    # Estimate framing from visible bone lengths; hidden/foreshortened bones do
    # not get stretched to match the photograph's proportions.
    scales = [np.linalg.norm(image[b] - image[a]) / np.linalg.norm(JOINTS[b]["offset"])
              for a, b in LIMBS if {a, b} <= visible and np.linalg.norm(image[b] - image[a]) > 2]
    scales.append(np.linalg.norm(image["left_shoulder"] - image["right_shoulder"]) / .38)
    px_per_unit = max(10, float(np.percentile(scales, 75)))
    c = state["camera"]
    c.update(fov=20, distance=float(np.clip(height / (2 * math.tan(math.radians(10)) * px_per_unit), .5, 45)))
    names = [name for i, name in enumerate(COCO) if valid[i]]
    target = np.array([points[COCO.index(n), :2] for n in names])
    weight = np.sqrt([np.clip(points[COCO.index(n), 2], .1, 1) for n in names])
    weight[:sum(COCO.index(n) < 5 for n in names)] *= .35  # coarse rig facial anchors
    initial_world, _ = forward_kinematics(state)
    mean = np.mean([initial_world[n] for n in names], axis=0)
    pixel = np.mean(target, axis=0)
    c["target"] = [float(mean[0] - (pixel[0] - width / 2) / px_per_unit),
                   float(mean[1] + (pixel[1] - height / 2) / px_per_unit), 0.]
    joints = ["pelvis", "spine", "chest"]
    if "nose" in visible:
        joints += ["neck", "head"]
    joints += [a for a, b in LIMBS if {a, b} <= visible]
    initial = np.radians([state["pose"]["joints"][n] for n in joints]).ravel()
    x0 = np.concatenate((initial, [math.log(c["distance"]), *c["target"][:2]]))
    factor = height / (2 * math.tan(math.radians(10)))
    norm = max(width, height)

    def project(parameters):
        for i, name in enumerate(joints):
            state["pose"]["joints"][name] = np.degrees(parameters[i*3:i*3+3]).tolist()
        world, _ = forward_kinematics(state)
        xyz = np.array([world[n] for n in names])
        distance, tx, ty = math.exp(parameters[-3]), parameters[-2], parameters[-1]
        depth = np.maximum(distance - xyz[:, 2], .1)
        return np.column_stack((width / 2 + factor * (xyz[:, 0] - tx) / depth,
                                height / 2 - factor * (xyz[:, 1] - ty) / depth)), xyz

    def residual(parameters):
        projected, xyz = project(parameters)
        return np.concatenate((((projected - target) * weight[:, None] / norm).ravel(),
                               (parameters[:-3] - initial) * .006,
                               xyz[:, 2] * .002))

    lower = np.r_[initial - math.pi, math.log(.5), -20, -20]
    upper = np.r_[initial + math.pi, math.log(50), 20, 20]
    solution = least_squares(residual, np.clip(x0, lower + 1e-8, upper - 1e-8),
                             bounds=(lower, upper), max_nfev=80, ftol=1e-5, xtol=1e-5)
    projected, _ = project(solution.x)
    c["distance"] = math.exp(solution.x[-3])
    c["target"] = [float(solution.x[-2]), float(solution.x[-1]), 0.]
    state["pose"]["preset"] = "Imported image"
    state["ui"].update(mode="POSE", view="camera")
    missing = [n for n in COCO[5:] if n not in visible]
    messages = ["深度为近似拟合；遮挡和前后关系需要手动检查。"]
    if missing:
        messages.append("未可靠检测的关节保留默认姿态：" + ", ".join(missing))
    error = float(np.sqrt(np.mean(np.sum((projected - target) ** 2, axis=1))))
    if error / norm > .045:
        messages.append("图片人物比例或透视与固定骨架差异较大，请手动校正。")
    return {"state": parse_state(copy.deepcopy(state)), "warnings": messages,
            "fit_error_pixels": round(error, 2), "visible_keypoints": int(valid.sum())}
