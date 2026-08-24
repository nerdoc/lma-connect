"""Re-encode sponsor images as WebP.

Sponsors send print-sized JPEGs and PNGs (one logo arrived as a 1.9 MB CMYK
JPEG); the app shows them in a phone-wide carousel or as a 40 px avatar.
Everything that is an image is therefore stored as WebP, capped at a width
that still looks sharp on a high-DPI phone — a 3 MB headshot becomes 40 kB.
Used by `import_sponsor` on the way in and by `optimize_sponsor_images` for
what was uploaded through the admin.
"""

import io
from pathlib import Path

from PIL import Image

WEBP_QUALITY = 82
MAX_WIDTH = {"logo": 800, "banner": 1600, "image": 1600, "photo": 600}


def to_webp(source, kind: str) -> bytes:
    """Return `source` (path or file object) as WebP bytes, downscaled to
    MAX_WIDTH[kind]. Alpha survives (logos), CMYK is converted to RGB.
    Raises OSError when Pillow cannot read the file."""
    with Image.open(source) as img:
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "transparency" in img.info or img.mode == "P" else "RGB")
        if img.width > MAX_WIDTH[kind]:
            ratio = MAX_WIDTH[kind] / img.width
            img = img.resize((MAX_WIDTH[kind], round(img.height * ratio)),
                             Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


def webp_name(name: str) -> str:
    """`sponsors/logos/Foo_Bar.png` -> `Foo_Bar.webp` (basename only; the
    field's upload_to puts it back into the right folder)."""
    return Path(name).stem + ".webp"
