"""Brand images (black / white / a touch of green). Run `python -m bekstyle.visuals` to regenerate."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BANNER = ASSETS_DIR / "banner.png"
AVATAR = ASSETS_DIR / "avatar.png"

BLACK = "#0A0A0A"
WHITE = "#FFFFFF"
GREY = "#9A9A9A"
FRAME = "#262626"
GREEN = "#22C55E"
BOLD_FONTS = ["impact.ttf", "Impact.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
TEXT_FONTS = ["arialbd.ttf", "DejaVuSans-Bold.ttf"]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def make_banner(path: Path = BANNER) -> None:
    w, h = 1280, 640
    img = Image.new("RGB", (w, h), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle([32, 32, w - 32, h - 32], outline=FRAME, width=2)
    d.text((96, 150), "BEK STYLE", font=_font(BOLD_FONTS, 200), fill=WHITE)
    d.rectangle([100, 395, 300, 409], fill=GREEN)
    d.text((100, 440), "STREETWEAR  •  CASUAL", font=_font(TEXT_FONTS, 40), fill=WHITE)
    d.text(
        (100, 520),
        "BUYURTMA ASOSIDA · O'ZBEKISTON BO'YLAB",
        font=_font(TEXT_FONTS, 24),
        fill=GREY,
    )
    d.ellipse([w - 120, 80, w - 96, 104], fill=GREEN)
    img.save(path, "PNG")


def make_avatar(path: Path = AVATAR) -> None:
    size = 640
    img = Image.new("RGB", (size, size), BLACK)
    d = ImageDraw.Draw(img)
    font = _font(BOLD_FONTS, 300)
    d.text(((size - _text_width(d, "BS", font)) // 2, 120), "BS", font=font, fill=WHITE)
    d.rectangle([size // 2 - 90, 470, size // 2 + 90, 484], fill=GREEN)
    img.save(path, "PNG")


def ensure_visuals(force: bool = False) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if force or not BANNER.is_file():
        make_banner()
    if force or not AVATAR.is_file():
        make_avatar()


if __name__ == "__main__":
    ensure_visuals(force=True)
