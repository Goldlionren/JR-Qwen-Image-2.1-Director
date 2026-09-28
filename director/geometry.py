"""FK and camera math: equivalent to Three.js Euler/Matrix4/PerspectiveCamera."""
import math
import numpy as np
from .state import RIG


def rotation(x, y, z, order="XYZ"):
    x, y, z = np.radians([x, y, z])
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    axes = {"X": np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]),
            "Y": np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]),
            "Z": np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])}
    result = np.eye(3)
    for axis in order:
        result = result @ axes[axis]
    return result


def actor_rotation(state):
    a = state["actor"]
    return rotation(a["pitch"], -a["yaw"], a["roll"], "YXZ")


def forward_kinematics(state, world=True):
    points, rotations = {}, {}
    root_r = actor_rotation(state) if world else np.eye(3)
    root_p = np.array(state["actor"]["position"]) if world else np.zeros(3)
    scale = state["actor"]["scale"] if world else 1
    for joint in RIG["joints"]:
        name, parent = joint["name"], joint["parent"]
        pr, pp = (rotations[parent], points[parent]) if parent else (root_r, root_p)
        points[name] = pp + pr @ (np.array(joint["offset"]) * scale)
        rotations[name] = pr @ rotation(*state["pose"]["joints"][name])
    return points, rotations


def camera_basis(state):
    c = state["camera"]
    az, el, roll = np.radians([c["azimuth"], c["elevation"], c["roll"]])
    backward = np.array([-math.sin(az)*math.cos(el), math.sin(el), math.cos(az)*math.cos(el)])
    position = np.array(c["target"]) + c["distance"] * backward
    right = np.cross([0, 1, 0], backward)
    right /= np.linalg.norm(right)
    up = np.cross(backward, right)
    return position, right*math.cos(roll)+up*math.sin(roll), -right*math.sin(roll)+up*math.cos(roll), backward


def camera_points(state):
    points, _ = forward_kinematics(state)
    position, right, up, back = camera_basis(state)
    basis = np.array([right, up, -back])
    return {key: basis @ (value-position) for key, value in points.items()}
