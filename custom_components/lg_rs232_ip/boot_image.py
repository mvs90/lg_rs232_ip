"""Prepare a real LG USB boot-logo file in HA Media; never fake remote install."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageOps
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_PIXELS = 20_000_000


def prepare_boot_jpeg(source: bytes) -> bytes:
    """Fit inside UH5F's documented 1920x1080 boot canvas, strip metadata."""
    if not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise ValueError("Boot image must be at most 5 MiB")
    try:
        with Image.open(BytesIO(source)) as image:
            if image.format not in {"JPEG", "PNG", "BMP"}:
                raise ValueError("Unsupported boot image format")
            if image.width * image.height > MAX_SOURCE_PIXELS or min(image.size) < 1:
                raise ValueError("Boot image exceeds pixel limit")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (1920, 1080), "black")
            rgba = image.convert("RGBA")
            canvas.paste(
                rgba, ((1920 - image.width) // 2, (1080 - image.height) // 2), rgba
            )
            output = BytesIO()
            canvas.save(
                output, format="JPEG", quality=90, optimize=True, progressive=False
            )
            return output.getvalue()
    except Exception:
        raise ValueError(
            "Cannot prepare boot image; use PNG/JPEG/BMP up to 5 MiB and 20 megapixels"
        ) from None


def save_boot_image(media_root: str, entry_id: str, image: bytes) -> str:
    """Atomic replacement of this entry's single generated file, no arbitrary path."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", entry_id):
        raise ValueError("Invalid config entry identity")
    root = Path(media_root).resolve()
    relative = Path("lg_rs232_ip") / entry_id / "LG_MONITOR" / "bootlogo.jpg"
    destination = root / relative
    # Do not follow a pre-existing symlink out of the configured media directory.
    if not destination.resolve().is_relative_to(root):
        raise ValueError("Boot image destination is outside configured media")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=".bootlogo-", delete=False
        ) as file:
            temp = Path(file.name)
            file.write(image)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, destination)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return relative.as_posix()


async def async_prepare_boot_image(
    player, media_id: str, media_directory: str = "local"
):
    """Produce a downloadable USB import file, without changing the display."""
    media_root = player.hass.config.media_dirs.get(media_directory)
    if not media_root:
        raise ServiceValidationError(
            "Choose a configured Home Assistant media directory"
        )
    source = await player._async_download_native_image(media_id)
    try:
        image = await player.hass.async_add_executor_job(prepare_boot_jpeg, source)
        relative = await player.hass.async_add_executor_job(
            save_boot_image,
            media_root,
            player._config_entry.entry_id,
            image,
        )
    except (OSError, ValueError):
        raise HomeAssistantError(
            "Cannot prepare boot image; check image format/size and media-directory write access"
        ) from None
    return {
        "media_id": f"media-source://media_source/{media_directory}/{relative}",
        "usb_path": "LG_MONITOR/bootlogo.jpg",
        "width": 1920,
        "height": 1080,
        "installed_on_display": False,
        "next_step": "Download from HA Media, copy LG_MONITOR to USB, then import in LG Background Image / Booting Logo Image.",
    }
