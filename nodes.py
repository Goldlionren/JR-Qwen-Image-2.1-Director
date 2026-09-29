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
        from .director.depth import available_models
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
                io.Combo.Input('task_mode', options=['director', 'edit_pose', 'replace_person', 'any_angle'], default='director', optional=True,
                    tooltip='director: original camera workflow. edit_pose: same person and scene, change pose. replace_person: identity_image supplies the person; image supplies scene/pose. any_angle: coarse target view is <image1>, original image is <image2>. Use the corresponding example for reference wiring.'),
                io.Image.Input('identity_image', optional=True,
                    tooltip='Replacement person for replace_person only. image is the target scene/pose source; import pose from image, not identity_image.'),
                io.Combo.Input('identity_scope', options=['identity_only','full_appearance'], default='identity_only', optional=True,
                    tooltip='identity_only: B face, hair and body; keep A scene clothing. full_appearance: also copy B clothing and accessories. Applies to replace_person.'),
                io.Combo.Input('anyangle_lora', options=['disabled'] + folder_paths.get_filename_list('loras'), default='disabled', optional=True,
                    tooltip='Only used in any_angle mode. Select QI2.1_AnyAngle.safetensors. Author recommends strength 1, sampler CFG 3 and 20+ steps.'),
                io.Float.Input('anyangle_strength', default=1, min=0, max=2, step=.05, optional=True),
                io.Combo.Input('angle_guide', options=['external', 'director_proxy'], default='external', optional=True,
                    tooltip='external: connect a target-view 3D/splat render to angle_reference. director_proxy: experimental shaded rig, without source texture or scene geometry.'),
                io.Image.Input('angle_reference', optional=True,
                    tooltip='AnyAngle external coarse 3D render at the TARGET camera view. Used as <image1>; image is the original <image2>. It is not rotated by the Director. If adding ControlNet, align the rig with this guide.'),
                io.Combo.Input('control_backend', options=['auto','native','bundled'], default='auto', optional=True,
                    tooltip='auto: use merged ComfyUI Fun ControlNet when available, otherwise bundled compatibility. native/bundled allow reproducible comparisons. Native weights belong in models/model_patches.'),
                io.Boolean.Input('auto_describe', default=False, optional=True,
                    tooltip='replace_person only: use the connected Qwen3-VL CLIP to describe identity and retained outfit/scene locally. Saves manual per-image prompt edits. Review reference_description for mistakes.'),
                io.Clip.Input('clip', optional=True),
                io.Combo.Input('depth_model', options=['disabled','external']+list(available_models()), default='disabled', optional=True,
                    tooltip='Optional SECOND ControlNet branch. Automatic depth reads image on CPU; external reads depth_image. Source depth may conflict with edited poses in edit_pose. Disabled by default.'),
                io.Float.Input('depth_strength', default=.25, min=0, max=2, step=.05, optional=True),
                io.Image.Input('depth_image', optional=True, tooltip='Relative depth RGB/grayscale hint when depth_model=external. White is near. Must align with the target scene/pose.'),
            ],
            outputs=[io.String.Output("director_prompt"), io.Image.Output("pose_control"),
                     io.Image.Output("pose_preview"), io.String.Output("camera_info"),
                     io.String.Output("pose_text"), io.String.Output("director_state"),
                     io.Model.Output('controlled_model'), io.Image.Output('control_image'),
                     io.Image.Output('reference_image_1'), io.Image.Output('reference_image_2'),
                     io.Image.Output('reference_image_3'), io.Image.Output('angle_preview'),
                     io.String.Output('reference_description'), io.Image.Output('depth_preview')],
        )

    @classmethod
    def execute(cls, director_state="{}", width=1024, height=1024, subject_type="character",
                background_mode="preserve", framing="auto", prompt_prefix="", prompt_suffix="", image=None,
                controlnet_name='disabled', control_strength=0.75, control_start=0, control_end=1,
                model=None, vae=None, pose_image_reference=True, reference_opacity=0,
                task_mode='director', identity_image=None, identity_scope='identity_only',
                anyangle_lora='disabled', anyangle_strength=1, angle_guide='external', angle_reference=None,
                control_backend='auto', auto_describe=False, clip=None,
                depth_model='disabled', depth_strength=.25, depth_image=None):
        controlnet_name = controlnet_name or 'disabled'
        if controlnet_name != 'disabled':
            from .controlnet.integration import validate_settings
            validate_settings(control_strength, control_start, control_end)
        use_control = controlnet_name != 'disabled' and control_strength > 0
        use_depth = depth_model not in (None,'disabled') and depth_strength > 0
        if use_depth:
            from .controlnet.integration import validate_settings
            validate_settings(depth_strength,control_start,control_end)
            if controlnet_name == 'disabled':
                raise ValueError('JR Director: select a Fun Union ControlNet to enable depth.')
        if (use_control or use_depth) and (model is None or vae is None):
            raise ValueError('JR Director: connect MODEL and Qwen Image 2.1 VAE to enable ControlNet.')
        state = parse_state(director_state)
        state["render"].update(width=width, height=height)
        state = parse_state(state)
        pixels = torch.from_numpy(render_pose(state)).unsqueeze(0)
        from .director.conditioning import reference_overlay, scenario_references
        task_mode = task_mode or 'director'
        angle_preview = None
        if task_mode == 'any_angle':
            if image is None:
                raise ValueError('JR Director: AnyAngle requires image (the original image).')
            if angle_guide == 'director_proxy':
                from .director.coarse import render_coarse
                angle_reference = torch.from_numpy(render_coarse(state)).unsqueeze(0)
            elif angle_guide != 'external':
                raise ValueError('JR Director: unknown angle_guide.')
            elif angle_reference is None:
                raise ValueError('JR Director: connect angle_reference, or choose the experimental director_proxy guide.')
            from .director.anyangle import apply_anyangle
            model = apply_anyangle(model, anyangle_lora, anyangle_strength)
        references = scenario_references(task_mode, pixels, image, identity_image, angle_reference)
        if task_mode == 'any_angle':
            angle_preview = references[0]
        control_image = reference_overlay(pixels, image, reference_opacity)
        prompt, info, pose = build_prompt(state, subject_type, background_mode, framing,
                                         controlnet=controlnet_name != 'disabled' and not pose_image_reference,
                                         task_mode=task_mode, identity_scope=identity_scope or 'identity_only')
        description = ''
        if task_mode == 'replace_person' and auto_describe:
            from .director.describe import describe_references
            description = describe_references(clip, references[0], references[1], identity_scope or 'identity_only')
            description_roles = ('Replacement identity and outfit from <image1>, retained scene from <image2>'
                                 if identity_scope == 'full_appearance' else
                                 'Replacement identity from <image1> and retained outfit/scene from <image2>')
            prompt = description_roles + ', automatically described:\n' + description + '\n\n' + prompt
        prompt = "\n\n".join(p for p in [prompt_prefix.strip(), prompt, prompt_suffix.strip()] if p)
        selected_backend = 'disabled'
        if use_control:
            from .controlnet.backends import apply_backend
            model, selected_backend = apply_backend(model, controlnet_name, vae, control_image,
                control_strength, control_start, control_end, control_backend or 'auto')
        depth_preview = None
        if use_depth:
            from .director.conditioning import fit_reference
            from .controlnet.backends import apply_backend
            if depth_model != 'external':
                from .director.depth import estimate_depth
                depth_image = estimate_depth(image,depth_model)
            if depth_image is None:
                raise ValueError('JR Director: connect depth_image for external depth.')
            depth_preview = fit_reference(depth_image,pixels)
            model, selected_backend = apply_backend(model,controlnet_name,vae,depth_preview,
                depth_strength,control_start,control_end,control_backend or 'auto')
        info = json.loads(info)
        info['control_backend'] = selected_backend
        info['depth_model'] = depth_model if use_depth else 'disabled'
        if task_mode == 'any_angle':
            info.update(angle_guide=angle_guide, anyangle_lora=anyangle_lora,
                        anyangle_strength=anyangle_strength, image_order=['coarse_target_view', 'original'])
        return io.NodeOutput(prompt, pixels, pixels.clone(), json.dumps(info, indent=2), pose,
                             json.dumps(state, separators=(",", ":")), model, control_image, *references, angle_preview, description, depth_preview)
