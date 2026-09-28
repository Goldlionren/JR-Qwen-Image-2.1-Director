# Director architecture / review

Target inspected: ComfyUI 0.37.0, git 8d534945; frontend 1.53.6; Python 3.13.12,
PyTorch 2.12.1+cu130. Core contains TextEncodeQwenImage21 and QwenImage21Cache.

The shared chat and task brief agree on independent CAMERA / ACTOR / POSE,
natural language instructions and no model implementation inside Director.
Numeric text is an instruction, not a guarantee of model camera adherence.
Pose maps alone cannot resolve all front/back ambiguities. Model adherence needs real tests.

Implementation is original. References reviewed:
- https://github.com/jtydhr88/ComfyUI-qwenmultiangle (MIT): Vue / TS / Three separation and DOM widgets.
- https://github.com/LLAI-lab/ComfyUI-3D-OpenPose-Editor-DW (no license found): interaction/projection concepts only. No source copied.
- https://chatgpt.com/share/6aba3a2c-c3a4-83ea-b686-4faa2d635055 (design discussion).

## Contract

One versioned JSON string is the execution input and workflow persistence boundary.
Python recomputes FK and perspective projection; a browser screenshot is never an input.
Shared rig JSON defines hierarchy, immutable rest offsets and OpenPose colors/edges.
Joint values are local Euler XYZ degrees; offsets never change, so bone lengths are invariant.
Actor transform uses Three Euler YXZ (pitch, -yaw, roll), then uniform scale and translation.
Coordinates: right-handed, Y up, actor forward +Z, anatomical right -X.
Camera azimuth 0 = +Z front, 90 = -X actor right, 180 = back, 270 = actor left.
Positive azimuth runs clockwise when seen from above with +Z at the top of a plan view.
Camera orbits its target, independent of actor translation. Eye-level semantics must be
derived from actual camera-to-head displacement; orbit elevation is relative to target.
Relative yaw subtraction is exposed as metadata, while view wording uses inverse actor
rotation applied to the camera-to-actor vector (handles translation/pitch/roll).

## Order

0. V3 registration, typed Vue build and safe junction deployment.
1. Shared state + camera + stage.
2. Hierarchical rig, FK controls, constrained manipulation and presets.
3. Matching Python/Three projection and pose map with clipping and depth ordering.
4. Camera/pose semantics and Qwen instruction.
5. Workflow lifecycle, import/export, queue and integration verification.
6. Example based on local Qwen 2.1 workflow; real generation if local models are available.

Persistence and Python geometry are built early so phase 3/5 cannot diverge.
No Core changes, dependency upgrades, inference reimplementation or downloaded model required.
