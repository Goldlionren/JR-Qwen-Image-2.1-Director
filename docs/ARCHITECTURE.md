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
No Core changes, dependency upgrades or Qwen inference reimplementation required.

## Image import (v0.2.0)

The frontend serializes the current graph and extracts just the connected IMAGE
source and its ancestors. A transient `JRDirectorImageCapture` output sink receives
the real evaluated tensor, so Load Image, resizing and other upstream transforms
use ComfyUI's own execution semantics. Downstream Director/Qwen nodes are excluded.
Capture requests have unique IDs and publish an opaque token through UI output.
Tokens expire after ten minutes; at most eight images (longest edge 1024) are kept
in RAM. The hidden capture helper is never added to the saved workflow.

`image_import.py` exposes bounded detect/fit routes and serializes heavy operations
off the event loop. `director/detection.py` runs existing YOLOX/DWPose ONNX weights
on CPU and returns COCO body landmarks. `director/pose_import.py` initializes a
planar articulated pose and minimizes weighted image-plane reprojection error with
angle/depth regularization. FK rest offsets never change. Depth is approximate.

Detection does not mutate the editor. Only explicit application of a selected
person changes state, with an undo snapshot, native size synchronization and graph
dirty notification. Normal Director execution continues to use only serialized
state, preventing later image changes/runs from overwriting manual edits. Source
images, thumbnails and tokens are not persisted in Director state. Optional model
files and detector dependencies are required for this feature on a new install.
