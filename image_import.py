"""Transient IMAGE capture and local pose-import routes. Never saves source images."""
import asyncio
import base64
from collections import OrderedDict
from io import BytesIO
import os
from pathlib import Path
import secrets
import threading
import time
import numpy as np
from PIL import Image, ImageDraw
from aiohttp import web
from comfy_api.latest import io

_cache = OrderedDict()
_cache_lock = threading.Lock()
_detector = None
_registered = False
TTL = 600
MAX_IMAGES = 8


def capture(image):
    import torch.nn.functional as F
    if image.ndim != 4 or image.shape[0] < 1 or image.shape[-1] not in (3, 4):
        raise ValueError("Expected IMAGE [B,H,W,3/4]")
    frame = image[:1, :, :, :3].detach().movedim(-1, 1)
    h, w = frame.shape[-2:]
    if min(h, w) < 32:
        raise ValueError("Image must be at least 32 pixels on each side")
    if max(h, w) > 1024:
        scale = 1024 / max(h, w)
        frame = F.interpolate(frame, size=(max(32, round(h*scale)), max(32, round(w*scale))), mode="bilinear", align_corners=False)
    array = frame[0].movedim(0, -1).float().cpu().numpy()
    if not np.isfinite(array).all():
        raise ValueError("Image contains non-finite pixels")
    rgb = np.rint(np.clip(array, 0, 1) * 255).astype(np.uint8)
    token = secrets.token_urlsafe(24)
    with _cache_lock:
        _expire()
        _cache[token] = {"created": time.monotonic(), "rgb": rgb, "people": None,
                         "batch_size": int(image.shape[0])}
        while len(_cache) > MAX_IMAGES:
            _cache.popitem(last=False)
    return token


def _expire():
    for token in list(_cache):
        if time.monotonic() - _cache[token]["created"] > TTL:
            del _cache[token]


def cached(token):
    if not isinstance(token, str) or len(token) > 64:
        raise ValueError("Invalid image token")
    with _cache_lock:
        _expire()
        item = _cache.get(token)
        if item is None:
            raise ValueError("图片缓存已过期，请重新点击「从图片导入姿态」。")
        return item


def model_roots():
    import folder_paths
    roots = []
    if os.environ.get("JR_DIRECTOR_POSE_MODELS"):
        roots.append(Path(os.environ["JR_DIRECTOR_POSE_MODELS"]))
    roots.append(Path(folder_paths.models_dir))
    # Extra model paths can put the models directory outside the ComfyUI root.
    for category in ("checkpoints", "diffusion_models", "vae", "controlnet"):
        for path in folder_paths.get_folder_paths(category):
            roots.append(Path(path).parent)
    return list(dict.fromkeys(root.resolve() for root in roots if root.is_dir()))


def detect(token):
    global _detector
    item = cached(token)
    if item["people"] is None:
        if _detector is None:
            from .director.detection import PoseDetector
            _detector = PoseDetector(model_roots())
        item["people"] = _detector(item["rgb"])
    people = item["people"]
    preview = Image.fromarray(item["rgb"])
    # Numbered boxes use source pixels so selecting a person is unambiguous.
    draw = ImageDraw.Draw(preview)
    for person in people:
        box = person["bbox"]
        draw.rectangle(box, outline=(60, 235, 160), width=3)
        x, y = max(0, box[0]), max(0, box[1])
        draw.rectangle((x, y, x+26, y+24), fill=(10, 45, 35))
        draw.text((x+8, y+5), str(person["index"]+1), fill="white")
    preview.thumbnail((640, 480))
    stream = BytesIO()
    preview.save(stream, format="JPEG", quality=85)
    return {"token": token, "people": [{"index": p["index"], "score": p["score"], "bbox": p["bbox"]} for p in people],
            "preview": "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode("ascii"),
            "width": item["rgb"].shape[1], "height": item["rgb"].shape[0], "batch_size": item["batch_size"]}


def fit(token, person_index, state):
    from .director.pose_import import fit_pose
    item = cached(token)
    people = item["people"]
    if isinstance(person_index, bool) or not isinstance(person_index, int) or people is None or not 0 <= person_index < len(people):
        raise ValueError("Invalid person selection")
    return fit_pose(people[person_index]["keypoints"], item["rgb"].shape[1], item["rgb"].shape[0], state)


def register_routes():
    global _registered
    if _registered:
        return
    from server import PromptServer
    gate = asyncio.Semaphore(1)

    async def handle(request, fitting=False):
        if request.content_length is None or request.content_length > 120_000:
            return web.json_response({"error": "Request too large"}, status=413)
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            async with gate:
                if fitting:
                    result = await asyncio.to_thread(fit, data.get("token"), data.get("person_index"), data.get("state", {}))
                else:
                    result = await asyncio.to_thread(detect, data.get("token"))
            return web.json_response(result)
        except (ValueError, KeyError, TypeError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception as error:
            # A useful dependency/model error reaches the widget, without crashing ComfyUI.
            return web.json_response({"error": str(error)}, status=500)

    @PromptServer.instance.routes.post("/jr-director/detect")
    async def detect_route(request):
        return await handle(request)

    @PromptServer.instance.routes.post("/jr-director/fit")
    async def fit_route(request):
        return await handle(request, fitting=True)

    _registered = True


class JRDirectorImageCapture(io.ComfyNode):
    """Internal output sink for an isolated upstream execution, never a saved editor node."""
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="JRDirectorImageCapture", display_name="JR Director Image Capture (internal)",
                         category="_JR/internal", is_output_node=True,
                         inputs=[io.Image.Input("image"), io.String.Input("request_id")], outputs=[])

    @classmethod
    def execute(cls, image, request_id):
        return io.NodeOutput(ui={"jr_image_token": [capture(image)], "request_id": [request_id]})
