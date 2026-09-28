import json
import math
import numpy as np
from .geometry import actor_rotation, camera_basis, forward_kinematics
from .projection import projected_joints

LABELS = ["front", "front-right three-quarter", "right side", "back-right three-quarter",
          "back", "back-left three-quarter", "left side", "front-left three-quarter"]


def view_label(angle):
    angle %= 360
    lower = int(angle // 45)
    fraction = angle % 45
    if fraction < 0.05:
        return LABELS[lower] + " view"
    return f"between a {LABELS[lower]} view and a {LABELS[(lower+1)%8]} view"


def pose_description(state):
    p, r = forward_kinematics(state, world=False)
    phrases = []
    def bend(a,b,c):
        u,v = p[a]-p[b], p[c]-p[b]
        return 180-math.degrees(math.acos(float(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))
    for side in ("left", "right"):
        shoulder, wrist = p[f"{side}_shoulder"], p[f"{side}_wrist"]
        dy = wrist[1]-shoulder[1]
        phrases.append(f"{side} arm " + ("raised above the shoulder" if dy > .12 else "extended near shoulder height" if dy > -.12 else "lowered"))
        bent = bend(f"{side}_shoulder", f"{side}_elbow", f"{side}_wrist")
        if bent > 25:
            phrases.append(f"{side} elbow bent approximately {bent:.0f} degrees from straight")
        knee = bend(f"{side}_hip", f"{side}_knee", f"{side}_ankle")
        if knee > 25:
            phrases.append(f"{side} knee bent approximately {knee:.0f} degrees from straight")
        dz = p[f"{side}_ankle"][2] - p[f"{side}_hip"][2]
        if abs(dz) > .15:
            phrases.append(f"{side} leg " + ("forward" if dz > 0 else "back"))
    if abs(p["left_ankle"][0]-p["right_ankle"][0]) > .45:
        phrases.append("wide stance")
    head_forward = r["head"] @ np.array([0,0,1])
    head_yaw = math.degrees(math.atan2(-head_forward[0],head_forward[2]))
    if abs(head_yaw) > 10:
        phrases.append(f"head turned {abs(head_yaw):.0f} degrees to the " + ("right" if head_yaw > 0 else "left"))
    torso = p["neck"]-p["pelvis"]
    lean = math.degrees(math.acos(float(np.clip(torso[1]/np.linalg.norm(torso),-1,1))))
    if lean > 10:
        phrases.append(f"torso leaning {lean:.0f} degrees")
    if max(abs(p[f"{side}_ankle"][1]) for side in ("left","right")) < .15 and lean < 20:
        phrases.insert(0, "standing")
    return "; ".join(phrases) + "."


def infer_framing(state):
    p = projected_joints(state)
    if all(p[n]["visible"] for n in ("nose","left_ankle","right_ankle","left_wrist","right_wrist")):
        return "full body"
    if all(p[n]["visible"] for n in ("nose","left_knee","right_knee")):
        return "medium full"
    if p["pelvis"]["visible"]:
        return "upper body"
    if p["left_shoulder"]["visible"] and p["right_shoulder"]["visible"]:
        return "headshot"
    return "close-up"


def build_prompt(state, subject_type="character", background_mode="preserve", framing="auto"):
    c,a = state["camera"],state["actor"]
    pos, *_ = camera_basis(state)
    points,_ = forward_kinematics(state)
    local = actor_rotation(state).T @ (pos-points["pelvis"])
    relative = math.degrees(math.atan2(-local[0],local[2])) % 360
    eye = pos-points["head"]
    eye_angle = math.degrees(math.atan2(eye[1], math.hypot(eye[0],eye[2])))
    label = view_label(relative)
    frame = infer_framing(state) if framing == "auto" else framing
    pose = pose_description(state)
    background = {"preserve":"Preserve the environment from <image1>, reconstructing it consistently for the new view.",
                  "plain white":"Use a plain white background.", "neutral":"Use a simple neutral gray background."}[background_mode]
    prompt = (f"Use <image1> as the strict identity and appearance reference. Re-render the same {subject_type}.\n\n"
              "Use <image2> only as the final projected body pose and framing reference. Match its limb positions and body orientation. "
              "It already represents the requested camera view; do not rotate the pose guide a second time. "
              "Do not copy its skeleton colors, lines or black background.\n\n"
              f"View the subject from {label}, approximately {relative:.1f} degrees around the subject from their forward direction toward their right. "
              f"The camera is {abs(eye_angle):.1f} degrees {'above' if eye_angle >= 0 else 'below'} the subject's eye level. "
              f"Use a {frame} composition and {c['fov']:.1f}-degree vertical field of view. "
              f"Camera roll: {c['roll']:.1f} degrees.\n\n"
              f"The body pose is: {pose} Actor root pitch: {a['pitch']:.1f} degrees; roll: {a['roll']:.1f} degrees.\n\n"
              "Reconstruct newly visible geometry consistently. Preserve identity, facial structure, hairstyle, body proportions, "
              "clothing, accessories, colors, materials and visual style from <image1>. Do not redesign or replace the subject "
              "or change the outfit. " + background)
    info = json.dumps({"azimuth": c["azimuth"], "elevation": c["elevation"], "distance": c["distance"], "fov": c["fov"],
                       "relative_azimuth": (c["azimuth"]-a["yaw"]) % 360, "effective_relative_azimuth": round(relative,3),
                       "eye_level_elevation": round(eye_angle,3), "view": label, "framing": frame}, indent=2)
    return prompt, info, pose
