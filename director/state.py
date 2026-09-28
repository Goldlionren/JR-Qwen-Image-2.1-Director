"""Versioned, bounded input contract shared with frontend/state.ts."""
import copy
import json
import math
from pathlib import Path

RIG = json.loads((Path(__file__).resolve().parent.parent / "shared" / "rig.json").read_text())
JOINTS = {j["name"]: j for j in RIG["joints"]}
NEAR, FAR = 0.05, 200.0


def default_state():
    return {"version": 1,
            "camera": {"azimuth": 0, "elevation": 0, "distance": 3.1, "fov": 40,
                       "roll": 0, "target": [0, 0.95, 0]},
            "actor": {"position": [0, 0, 0], "yaw": 0, "pitch": 0, "roll": 0, "scale": 1},
            "pose": {"skeleton_type": "director_body_v1", "preset": "Neutral Standing",
                     "joints": {name: [0, 0, 0] for name in JOINTS}},
            "render": {"width": 1024, "height": 1024, "background": "black"},
            "ui": {"mode": "CAMERA", "selected_joint": "right_shoulder", "view": "stage"}}


def number(v, lo, hi, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f"{name} must be a finite number in [{lo}, {hi}]")
    return float(v)


def vector(v, limit, name):
    if not isinstance(v, list) or len(v) != 3:
        raise ValueError(f"{name} must contain three numbers")
    return [number(x, -limit, limit, name) for x in v]


def parse_state(raw):
    if isinstance(raw, str):
        if len(raw) > 100_000:
            raise ValueError("Director state is too large")
        raw = json.loads(raw or "{}")
    if not isinstance(raw, dict):
        raise ValueError("Director state must be a JSON object")
    if raw.get("version", 1) != 1:
        raise ValueError("Unsupported Director state version")
    s = default_state()
    for section in ("camera", "actor", "pose", "render", "ui"):
        supplied = raw.get(section, {})
        if not isinstance(supplied, dict):
            raise ValueError(f"{section} must be an object")
        s[section].update(copy.deepcopy(supplied))
    c, a, p, r = s["camera"], s["actor"], s["pose"], s["render"]
    c["azimuth"] = number(c["azimuth"], -1e6, 1e6, "azimuth") % 360
    for k, lo, hi in [("elevation", -89, 89), ("distance", 0.2, 50), ("fov", 10, 120), ("roll", -180, 180)]:
        c[k] = number(c[k], lo, hi, k)
    c["target"] = vector(c["target"], 50, "target")
    a["position"] = vector(a["position"], 50, "position")
    for k in ("yaw", "pitch", "roll"):
        a[k] = number(a[k], -1e6, 1e6, k)
    a["scale"] = number(a["scale"], 0.1, 5, "scale")
    if p["skeleton_type"] != "director_body_v1" or not isinstance(p["joints"], dict):
        raise ValueError("Unsupported skeleton or invalid joints")
    if set(p["joints"]) - set(JOINTS):
        raise ValueError("Unknown joint names")
    p["joints"] = {name: vector(p["joints"].get(name, [0, 0, 0]), 36000, name) for name in JOINTS}
    if not isinstance(p["preset"], str) or len(p["preset"]) > 80:
        raise ValueError("Invalid pose preset label")
    for key in ("width", "height"):
        value = number(r[key], 64, 2048, key)
        if value != int(value):
            raise ValueError("Render dimensions must be integers")
        r[key] = int(value)
    if r["background"] != "black":
        raise ValueError("Pose control background must be black")
    if s["ui"]["mode"] not in ("CAMERA", "ACTOR", "POSE") or s["ui"]["view"] not in ("stage", "camera"):
        raise ValueError("Invalid editor mode/view")
    if s["ui"]["selected_joint"] not in JOINTS:
        raise ValueError("Invalid selected joint")
    return s


def apply_preset(state, name):
    s = copy.deepcopy(state)
    s["pose"]["joints"] = {key: RIG["presets"][name].get(key, [0, 0, 0])[:] for key in JOINTS}
    s["pose"]["preset"] = name
    return s
