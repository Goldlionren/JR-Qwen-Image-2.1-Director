from comfy_api.latest import ComfyExtension
from .nodes import QwenImage21Director
from .image_import import JRDirectorImageCapture, register_routes

WEB_DIRECTORY = "./web/dist"


class DirectorExtension(ComfyExtension):
    async def get_node_list(self):
        return [QwenImage21Director, JRDirectorImageCapture]

    async def on_load(self):
        register_routes()


async def comfy_entrypoint():
    return DirectorExtension()
