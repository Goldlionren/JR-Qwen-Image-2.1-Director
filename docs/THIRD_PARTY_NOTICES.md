# Third-party notices

## ComfyUI Qwen Image 2.1 Fun ControlNet backport

`controlnet/model.py`, `controlnet/patch.py`, `controlnet/compat.py` and loader logic
are adapted from [ComfyUI PR #16519](https://github.com/Comfy-Org/ComfyUI/pull/16519)
by kijai and the ComfyUI contributors, pinned at
`b0ab6a4c662a2e63fe2c0d7779dd06aeb62df3cf`.
Upstream files: `comfy/ldm/qwen_image21/model.py` and
`comfy_extras/nodes_model_patch.py`.

Distributed under GNU GPL version 3 or later; complete license text is included in
[licenses/ComfyUI-GPL-3.0.txt](licenses/ComfyUI-GPL-3.0.txt) and the root LICENSE.
JR modifications (2026-09-28): project-local control classes, instance-scoped
ModelPatcher compatibility method, strict 2.1 checkpoint validation, a bounded
loader cache, and integration into the Director node. No Core files are replaced.

The combined v0.3.0 distribution is GPL-3.0-or-later. Original Director components
retain their MIT permissions and notice in [licenses/Director-MIT.txt](licenses/Director-MIT.txt).
Third-party components retain their respective licenses. Model weights are not
bundled; Qwen Research License applies to the Fun Union weights separately.

## DWPose / ONNX preprocessing reference

The YOLOX decode and DWPose affine crop / SimCC conventions in
`director/detection.py` are adapted from the official
[IDEA-Research/DWPose ONNX reference](https://github.com/IDEA-Research/DWPose/tree/onnx/ControlNet-v1-1-nightly/annotator/dwpose).
Copyright (c) OpenMMLab and the DWPose contributors. Licensed under Apache 2.0;
the license is distributed in [licenses/DWPose-APACHE-2.0.txt](licenses/DWPose-APACHE-2.0.txt).
JR modifications: compact body-only inference, CPU session management, bounded person
selection, explicit no-person handling, and local editable-rig integration.
Model weights are not bundled. Their upstream distribution and applicable licenses
remain with their respective authors.

## AnyAngle model integration

[QI_2.1_AnyAngle by lilylilith](https://huggingface.co/lilylilith/QI_2.1_AnyAngle)
is loaded through ComfyUI's native LoRA loader, with no model weights bundled in this repository.
The model card declares Apache-2.0. The tested revision is
`e42ac7827e2cad7ce22dc099109ae29681239eba`.
The short camera-edit instruction and reference image order follow the author's model card.
The experimental shaded rig renderer is JR code, not the author's image-to-3D workflow.

## Vue

The MIT License (MIT)

Copyright (c) 2018-present, Yuxi (Evan) You

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.


## Three.js

The MIT License

Copyright © 2010-2025 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

