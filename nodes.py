import json
import torch
import folder_paths
from comfy_api.latest import io
from .director.state import parse_state
from .director.projection import render_pose
from .director.prompt import build_prompt


class QwenImage21Director(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        controls = ['disabled'] + [f'{kind}/{name}' for kind in ('model_patches', 'controlnet')
            for name in folder_paths.get_filename_list(kind) if name.endswith('.safetensors')]
        return io.Schema(
            node_id="QwenImage21Director",
            display_name="JR Qwen Image 2.1 Director",
            category="image/director",
            description="Direct a camera and a body rig; render pose guides without a model or browser.",
            inputs=[
                io.String.Input("director_state", default="{}", multiline=True),
                io.Int.Input("width", default=1024, min=64, max=2048, step=32),
                io.Int.Input("height", default=1024, min=64, max=2048, step=32),
                io.Combo.Input("subject_type", options=["character", "person"], default="character"),
                io.Combo.Input("background_mode", options=["preserve", "plain white", "neutral"], default="preserve"),
                io.Combo.Input("framing", options=["auto", "full body", "medium full", "upper body", "headshot", "close-up"], default="auto"),
                io.String.Input("prompt_prefix", default="", multiline=True, optional=True),
                io.String.Input("prompt_suffix", default="", multiline=True, optional=True),
                io.Image.Input("image", optional=True, tooltip="Connect an image, then click 从图片导入姿态 in the Director. Import is explicit and never overwrites edits during normal execution. Connect the identity reference separately to Qwen image_1."),
                io.Combo.Input('controlnet_name', options=controls, default='disabled', optional=True,
                    tooltip='Qwen Image 2.1 Fun Union only. INT8 convrot is recommended for 12GB GPUs. Bundled support requires no Core PR installation.'),
                io.Float.Input('control_strength', default=0.75, min=0, max=2, step=0.05, optional=True),
                io.Float.Input('control_start', default=0, min=0, max=1, step=0.05, optional=True),
                io.Float.Input('control_end', default=1, min=0, max=1, step=0.05, optional=True),
                io.Boolean.Input('pose_image_reference', default=True, optional=True,
                    tooltip='Keep pose_control connected to Qwen image_2 for dual-reference + ControlNet. Turn off only when image_2 is not connected.'),
                io.Model.Input('model', optional=True),
                io.Vae.Input('vae', optional=True),
                io.Float.Input('reference_opacity', default=0, min=0, max=0.1, step=0.01, optional=True,
                    tooltip='Experimental: dim original image under bones (0 disables; try 0.05 or 0.10). Can conflict with edited poses/cameras. Uses the first image frame, fitted without cropping. control_image shows the actual ControlNet hint.'),
            ],
            outputs=[io.String.Output("director_prompt"), io.Image.Output("pose_control"),
                     io.Image.Output("pose_preview"), io.String.Output("camera_info"),
                     io.String.Output("pose_text"), io.String.Output("director_state"),
                     io.Model.Output('controlled_model'), io.Image.Output('control_image')],
        )

    @classmethod
    def execute(cls, director_state="{}", width=1024, height=1024, subject_type="character",
                background_mode="preserve", framing="auto", prompt_prefix="", prompt_suffix="", image=None,
                controlnet_name='disabled', control_strength=0.75, control_start=0, control_end=1,
                model=None, vae=None, pose_image_reference=True, reference_opacity=0):
        controlnet_name = controlnet_name or 'disabled'
        if controlnet_name != 'disabled':
            from .controlnet.integration import validate_settings
            validate_settings(control_strength, control_start, control_end)
        use_control = controlnet_name != 'disabled' and control_strength > 0
        if use_control and (model is None or vae is None):
            raise ValueError('JR Director: connect MODEL and Qwen Image 2.1 VAE to enable ControlNet.')
        state = parse_state(director_state)
        state["render"].update(width=width, height=height)
        state = parse_state(state)
        pixels = torch.from_numpy(render_pose(state)).unsqueeze(0)
        from .director.conditioning import reference_overlay
        control_image = reference_overlay(pixels, image, reference_opacity)
        prompt, info, pose = build_prompt(state, subject_type, background_mode, framing,
                                         controlnet=controlnet_name != 'disabled' and not pose_image_reference)
        prompt = "\n\n".join(p for p in [prompt_prefix.strip(), prompt, prompt_suffix.strip()] if p)
        if use_control:
            from .controlnet.loader import load_controlnet
            from .controlnet.integration import apply_control
            model = apply_control(model, load_controlnet(controlnet_name), vae, control_image,
                                  control_strength, control_start, control_end)
        return io.NodeOutput(prompt, pixels, pixels.clone(), info, pose, json.dumps(state, separators=(",", ":")), model, control_image)
