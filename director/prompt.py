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
    stride = abs(p['left_ankle'][2]-p['right_ankle'][2])
    if stride > .25:
        phrases.insert(0, "a walking-like stride, with the legs separated in depth; change the leg positions from the reference image")
    elif max(abs(p[f"{side}_ankle"][1]) for side in ("left","right")) < .15 and lean < 20:
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


def build_prompt(state, subject_type="character", background_mode="preserve", framing="auto", controlnet=False,
                 task_mode="director", identity_scope="identity_only"):
    if identity_scope not in ('identity_only', 'full_appearance'):
        raise ValueError('JR Director: unknown identity_scope.')
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
    pose_source = ("Follow the supplied pose control for the final body pose and framing. " if controlnet else
                   "Use <image2> only as the final projected body pose and framing reference. ")
    prompt = (f"Use <image1> as the strict identity and appearance reference. Re-render the same {subject_type}.\n\n"
              + pose_source + "Match its limb positions and body orientation. "
              "It already represents the requested camera view; do not rotate the pose guide a second time. "
              "Do not copy its skeleton colors, lines or black background.\n\n"
              f"View the subject from {label}, approximately {relative:.1f} degrees around the subject from their forward direction toward their right. "
              f"The camera is {abs(eye_angle):.1f} degrees {'above' if eye_angle >= 0 else 'below'} the subject's eye level. "
              f"Use a {frame} composition and {c['fov']:.1f}-degree vertical field of view. "
              f"Camera roll: {c['roll']:.1f} degrees.\n\n"
              f"The body pose is: {pose} Actor root pitch: {a['pitch']:.1f} degrees; roll: {a['roll']:.1f} degrees. "
              "Replace the source pose with this target pose, including the legs and head, while preserving the subject's appearance.\n\n"
              "Reconstruct newly visible geometry consistently. Preserve identity, facial structure, hairstyle, body proportions, "
              "clothing, accessories, colors, materials and visual style from <image1>. Do not redesign or replace the subject "
              "or change the outfit. " + background)
    if frame == "full body":
        prompt += " Include the entire head, both hands and both feet inside the frame, with clear margin around all limbs. Do not crop raised hands."
    if task_mode == 'edit_pose':
        guide = 'the supplied pose control' if controlnet else '<image2>'
        prompt = ('Edit <image1>: keep the same person in the same scene. '
                  'Preserve this person\'s identity, facial features, hairstyle, body proportions, clothing and accessories. '
                  f'Change the body pose and orientation according to {guide}, including limb positions and head direction. '
                  'The target pose guide takes priority over the original pose. '
                  'Preserve the background, objects, camera position, framing, perspective, lighting and visual style from <image1>. '
                  'Adapt clothing folds, contact shadows and occlusions naturally to the new pose, and fill areas revealed by the movement. '
                  'Keep unrelated people and objects unchanged. Do not render the pose guide\'s lines, colors or background.')
    elif task_mode == 'replace_person':
        guide = 'the supplied pose control' if controlnet else '<image3>'
        identity = ('Use the identity, face, hairstyle and body proportions from <image1>. '
                    'Keep the outfit, shoes and clothing accessories from <image2>; preserve their design, colors and materials, '
                    'while fitting them naturally to the replacement body. Do not transfer clothing from <image1>. '
                    if identity_scope == 'identity_only' else
                    'Use the identity, face, hairstyle, body proportions, outfit and accessories from <image1>. ')
        prompt = ('Edit <image2>: replace the person indicated by the target pose guide with the person from <image1>. '
                  + identity +
                  f'Use {guide} for the final pose, orientation, position and scale, taking priority over either reference person\'s original pose. '
                  'Preserve the scene, background objects, camera, framing, perspective, lighting and visual style from <image2>. '
                  'The replacement must be recognizable as the person from <image1>, without blending in the original person\'s facial features. '
                  'Replace that person rather than adding another. Adapt clothing folds, shadows and occlusions naturally. '
                  'Keep unrelated people and objects unchanged. Do not render the pose guide\'s lines, colors or background.')
    elif task_mode == 'any_angle':
        # Author's exact two-image instruction; order differs from other modes.
        prompt = 'Change the camera angle from <image2> to <image1>.'
    elif task_mode != 'director':
        raise ValueError('JR Director: unknown task_mode.')
    info = json.dumps({"azimuth": c["azimuth"], "elevation": c["elevation"], "distance": c["distance"], "fov": c["fov"],
                       "relative_azimuth": (c["azimuth"]-a["yaw"]) % 360, "effective_relative_azimuth": round(relative,3),
                       "eye_level_elevation": round(eye_angle,3), "view": label, "framing": frame,
                       "task_mode": task_mode, "identity_scope": identity_scope}, indent=2)
    return prompt, info, pose
