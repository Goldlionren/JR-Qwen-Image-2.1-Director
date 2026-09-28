from comfy_api.latest import ComfyExtension
from .nodes import QwenImage21Director

WEB_DIRECTORY = "./web/dist"


class DirectorExtension(ComfyExtension):
    async def get_node_list(self):
        return [QwenImage21Director]


async def comfy_entrypoint():
    return DirectorExtension()
