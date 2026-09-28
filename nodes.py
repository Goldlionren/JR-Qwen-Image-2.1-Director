import json
import torch
from comfy_api.latest import io
from .director.state import parse_state
from .director.projection import render_pose
from .director.prompt import build_prompt


class QwenImage21Director(io.ComfyNode):
    @classmethod
    def define_schema(cls):
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
                io.Image.Input("image", optional=True, tooltip="Optional identity reference; connect the same image to Qwen image_1."),
            ],
            outputs=[io.String.Output("director_prompt"), io.Image.Output("pose_control"),
                     io.Image.Output("pose_preview"), io.String.Output("camera_info"),
                     io.String.Output("pose_text"), io.String.Output("director_state")],
        )

    @classmethod
    def execute(cls, director_state="{}", width=1024, height=1024, subject_type="character",
                background_mode="preserve", framing="auto", prompt_prefix="", prompt_suffix="", image=None):
        state = parse_state(director_state)
        state["render"].update(width=width, height=height)
        state = parse_state(state)
        pixels = torch.from_numpy(render_pose(state)).unsqueeze(0)
        prompt, info, pose = build_prompt(state, subject_type, background_mode, framing)
        prompt = "\n\n".join(p for p in [prompt_prefix.strip(), prompt, prompt_suffix.strip()] if p)
        return io.NodeOutput(prompt, pixels, pixels.clone(), info, pose, json.dumps(state, separators=(",", ":")))
