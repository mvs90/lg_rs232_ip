"""Private, bounded, content-addressed background images for one display."""

import asyncio
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import os
import tempfile

from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 24
IMAGE_ID = re.compile(r"[a-f0-9]{64}")


def prepare_background(source):
    if not 0 < len(source) <= MAX_BYTES:
        raise ValueError("Use a JPEG or PNG up to 5 MiB")
    try:
        with Image.open(BytesIO(source)) as image:
            if (
                image.format not in {"JPEG", "PNG"}
                or image.width * image.height > 20_000_000
            ):
                raise ValueError
            image = ImageOps.exif_transpose(image)
            image.thumbnail((3840, 2160), Image.Resampling.LANCZOS)
            rgb = Image.new("RGB", image.size, "#101827")
            rgba = image.convert("RGBA")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
            out = BytesIO()
            rgb.save(out, format="JPEG", quality=95, subsampling=0, optimize=True)
            return out.getvalue()
    except Exception:
        raise ValueError(
            "Use a valid JPEG or PNG up to 5 MiB and 20 megapixels"
        ) from None


class LayoutBackgrounds:
    def __init__(self, hass, entry_id):
        self.hass = hass
        self.root = Path(
            hass.config.path(".storage", f"lg_rs232_ip.{entry_id}.backgrounds")
        )
        self._lock = asyncio.Lock()

    def path(self, identifier):
        if not isinstance(identifier, str) or not IMAGE_ID.fullmatch(identifier):
            raise ValueError("Invalid image ID")
        path = self.root / (identifier + ".jpg")
        if path.is_symlink() or self.root.is_symlink():
            raise ValueError("Invalid image storage")
        return path

    async def async_list(self):
        return await self.hass.async_add_executor_job(self._list)

    def _list(self):
        if self.root.is_symlink():
            raise ValueError("Invalid image storage")
        return sorted(
            p.stem
            for p in self.root.glob("*.jpg")
            if IMAGE_ID.fullmatch(p.stem) and not p.is_symlink()
        )

    async def async_upload(self, source):
        async with self._lock:
            return await self.hass.async_add_executor_job(self._upload, source)

    def _upload(self, source):
        image = prepare_background(source)
        identifier = sha256(image).hexdigest()
        path = self.path(identifier)
        if path.exists():
            return identifier
        if len(self._list()) >= MAX_IMAGES:
            raise ValueError(
                "Image library full (24). Remove an unused background first"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as file:
                temporary = Path(file.name)
                file.write(image)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return identifier

    async def async_read(self, identifier):
        return await self.hass.async_add_executor_job(
            lambda: self.path(identifier).read_bytes()
        )

    async def async_delete(self, identifier):
        async with self._lock:
            await self.hass.async_add_executor_job(
                lambda: self.path(identifier).unlink()
            )
