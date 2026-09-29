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
                io.Image.Input("image", optional=True, tooltip="Pose/scene source. edit_pose: the original person and scene. replace_person: image2, the target scene and pose. Click 从图片导入姿态 to import; normal runs never overwrite edited joints."),
                io.Combo.Input('controlnet_name', options=controls, default='disabled', optional=True,
                    tooltip='Qwen Image 2.1 Fun Union only. INT8 convrot is recommended for 12GB GPUs. Bundled support requires no Core PR installation.'),
                io.Float.Input('control_strength', default=0.75, min=0, max=2, step=0.05, optional=True),
                io.Float.Input('control_start', default=0, min=0, max=1, step=0.05, optional=True),
                io.Float.Input('control_end', default=1, min=0, max=1, step=0.05, optional=True),
                io.Boolean.Input('pose_image_reference', default=True, optional=True,
                    tooltip='Enable when the encoder receives a pose guide: image_2 in director/edit_pose, image_3 in replace_person. Disable only when pose is supplied exclusively through ControlNet; source scene references stay connected.'),
                io.Model.Input('model', optional=True),
                io.Vae.Input('vae', optional=True),
                io.Float.Input('reference_opacity', default=0, min=0, max=0.1, step=0.01, optional=True,
                    tooltip='Experimental: dim original image under bones (0 disables; try 0.05 or 0.10). Can conflict with edited poses/cameras. Uses the first image frame, fitted without cropping. control_image shows the actual ControlNet hint.'),
                io.Combo.Input('task_mode', options=['director', 'edit_pose', 'replace_person'], default='director', optional=True,
                    tooltip='director: original camera workflow. edit_pose: same person and scene, change pose. replace_person: identity_image supplies the person; image supplies the target scene and imported pose. Use the corresponding example to connect reference_image outputs.'),
                io.Image.Input('identity_image', optional=True,
                    tooltip='Replacement person for replace_person only. image is the target scene/pose source; import pose from image, not identity_image.'),
                io.Combo.Input('identity_scope', options=['identity_only','full_appearance'], default='identity_only', optional=True,
                    tooltip='identity_only: B face, hair and body; keep A scene clothing. full_appearance: also copy B clothing and accessories. Applies to replace_person.'),
            ],
            outputs=[io.String.Output("director_prompt"), io.Image.Output("pose_control"),
                     io.Image.Output("pose_preview"), io.String.Output("camera_info"),
                     io.String.Output("pose_text"), io.String.Output("director_state"),
                     io.Model.Output('controlled_model'), io.Image.Output('control_image'),
                     io.Image.Output('reference_image_1'), io.Image.Output('reference_image_2'),
                     io.Image.Output('reference_image_3')],
        )

    @classmethod
    def execute(cls, director_state="{}", width=1024, height=1024, subject_type="character",
                background_mode="preserve", framing="auto", prompt_prefix="", prompt_suffix="", image=None,
                controlnet_name='disabled', control_strength=0.75, control_start=0, control_end=1,
                model=None, vae=None, pose_image_reference=True, reference_opacity=0,
                task_mode='director', identity_image=None, identity_scope='identity_only'):
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
        from .director.conditioning import reference_overlay, scenario_references
        task_mode = task_mode or 'director'
        references = scenario_references(task_mode, pixels, image, identity_image)
        control_image = reference_overlay(pixels, image, reference_opacity)
        prompt, info, pose = build_prompt(state, subject_type, background_mode, framing,
                                         controlnet=controlnet_name != 'disabled' and not pose_image_reference,
                                         task_mode=task_mode, identity_scope=identity_scope or 'identity_only')
        prompt = "\n\n".join(p for p in [prompt_prefix.strip(), prompt, prompt_suffix.strip()] if p)
        if use_control:
            from .controlnet.loader import load_controlnet
            from .controlnet.integration import apply_control
            model = apply_control(model, load_controlnet(controlnet_name), vae, control_image,
                                  control_strength, control_start, control_end)
        return io.NodeOutput(prompt, pixels, pixels.clone(), info, pose, json.dumps(state, separators=(",", ":")), model, control_image, *references)
