"""One bounded offline-only design bundle, with its selected local background."""

import asyncio
import base64
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json

from PIL import Image

MAX_IMAGE_BYTES = 768 * 1024
ELEMENT_FIELDS = (
    "id", "kind", "x", "y", "width", "height", "label", "text", "font_size",
    "color", "background", "opacity", "radius", "align", "font", "show_label",
)
SCENE_FIELDS = (
    "background", "color", "accent", "image_id", "image_fit", "image_dim",
    "gradient_angle",
)


def compact_image(source):
    """Keep 4K when feasible; bound the one-time local-storage footprint."""
    with Image.open(BytesIO(source)) as original:
        image = original.convert("RGB")
        for size in ((3840, 2160), (2560, 1440), (1920, 1080), (1280, 720)):
            image.thumbnail(size, Image.Resampling.LANCZOS)
            for quality in (88, 75, 60):
                output = BytesIO()
                image.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= MAX_IMAGE_BYTES:
                    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    raise ValueError("Startup background cannot fit the offline image budget")


class StartupDesign:
    def __init__(self, layouts):
        self.layouts = layouts
        self._lock = asyncio.Lock()
        self._bundle = None

    def document(self):
        source = self.layouts.config["scenes"]["startup"]
        scene = {key: deepcopy(source[key]) for key in SCENE_FIELDS}
        scene["elements"] = [
            {key: deepcopy(item[key]) for key in ELEMENT_FIELDS}
            for item in source["elements"]
        ]
        return {
            "schema": 1,
            "scene": scene,
            "timezone": str(self.layouts.hass.config.time_zone),
        }

    @property
    def version(self):
        return sha256(json.dumps(self.document(), sort_keys=True).encode()).hexdigest()

    async def async_bundle(self):
        async with self._lock:
            document = self.document()
            version = sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
            if self._bundle and self._bundle["version"] == version:
                return self._bundle
            image = None
            scene = document["scene"]
            if scene["background"] == "image" and scene["image_id"]:
                source = await self.layouts.backgrounds.async_read(scene["image_id"])
                image = await self.layouts.hass.async_add_executor_job(compact_image, source)
            self._bundle = {**document, "version": version, "image": image}
            return self._bundle
