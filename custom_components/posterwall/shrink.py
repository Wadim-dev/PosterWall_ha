"""Photos are made display-sized before they leave Home Assistant.

A phone photo is several megabytes; a wall shows it at most 720 pixels wide. Sending the full file to
every screen costs network, decoding and - in a long-running browser like the TECHO5 dashboard server -
memory that is given back late. So every photo goes out as a small JPEG of the size the card draws.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

#: the box a photo is shrunk into: the card draws photos at most 720 pixels wide (WIDTH in the card)
BOX = (720, 1280)
QUALITY = 82
#: a photo already this small is sent as it is
SMALL = 250_000


def shrink(source: bytes | Path, content_type: str = "image/jpeg") -> tuple[bytes, str]:
    """A display-sized JPEG of a photo (bytes or a file). Runs in the executor.

    A photo that cannot be read as an image is sent unchanged when it came as bytes; a file that
    cannot be read raises OSError.
    """
    raw = source.read_bytes() if isinstance(source, Path) else source
    if len(raw) <= SMALL and content_type.startswith(("image/jpeg", "image/png", "image/webp")):
        return raw, content_type
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.draft("RGB", BOX)  # JPEG: decodes at 1/2, 1/4 or 1/8 size right away - fast, little memory
            out = ImageOps.exif_transpose(img)
            if out.mode in ("RGBA", "LA", "P"):
                out = out.convert("RGBA")
                flat = Image.new("RGB", out.size, (255, 255, 255))
                flat.paste(out, mask=out.getchannel("A"))
                out = flat
            elif out.mode != "RGB":
                out = out.convert("RGB")
            out.thumbnail(BOX, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            out.save(buf, "JPEG", quality=QUALITY)
    except (OSError, ValueError, Image.DecompressionBombError):
        return raw, content_type
    return buf.getvalue(), "image/jpeg"
