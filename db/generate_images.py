import os
import shutil
from PIL import Image, ImageDraw, ImageFont


def _find_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def generate_demo_images(output_dir: str = "./media_cache", force: bool = True):
    os.makedirs(output_dir, exist_ok=True)

    # Copy tracked branding assets if available
    possible_assets_dirs = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "branding"),
        os.path.join(os.getcwd(), "assets", "branding"),
        "assets/branding",
    ]
    for adir in possible_assets_dirs:
        if os.path.exists(adir):
            for fname in os.listdir(adir):
                src = os.path.join(adir, fname)
                dst = os.path.join(output_dir, fname)
                if os.path.isfile(src) and (force or not os.path.exists(dst)):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            break

    items = [
        ("demo_jempir_1.png", "Aesthetic Jempir ✨", "#FFE4EC", "#E75480", "🧶 99.000 so'm"),
        ("demo_jempir_2.png", "Jempir Tafsilotlari 💗", "#FFF0F5", "#FF69B4", "Moonlight Pink S-M-L"),
        ("demo_wig_1.png", "Pastel Lolita Wig 💇‍♀️", "#FFF5F7", "#D43F8D", "💇‍♀️ 125.000 so'm"),
        ("demo_wig_2.png", "Parik Ko'rinishi ✨", "#FFEBF2", "#C71585", "Pastel & Binafsha"),
        ("demo_scarf_1.png", "Yulduzli Shoyi Sharf 🧣", "#FFF8F5", "#E75480", "🧣 45.000 so'm"),
        ("demo_scarf_2.png", "Sharf Matosi ✨", "#FFE4EC", "#DB7093", "200x50 sm"),
        ("demo_review_1.png", "Mijoz fikri 💌", "#FFF0F5", "#E75480", "⭐️⭐️⭐️⭐️⭐️ 5/5"),
    ]

    for filename, title, bg_color, accent_color, subtitle in items:
        file_path = os.path.join(output_dir, filename)
        if not force and os.path.exists(file_path):
            continue

        width, height = (800, 800)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Soft aesthetic corners
        draw.ellipse([20, 20, 180, 180], fill="#FFD1DC")
        draw.ellipse([width - 180, 20, width - 20, 180], fill="#FFD1DC")
        draw.ellipse([20, height - 180, 180, height - 20], fill="#FFD1DC")
        draw.ellipse([width - 180, height - 180, width - 20, height - 20], fill="#FFD1DC")

        # Soft inner frame
        draw.rounded_rectangle(
            [40, 40, width - 40, height - 40],
            radius=30,
            outline=accent_color,
            width=6,
        )

        font_title = _find_font(42, bold=True)
        font_sub = _find_font(28, bold=False)

        bbox_title = draw.textbbox((0, 0), title, font=font_title)
        w_title = bbox_title[2] - bbox_title[0]
        draw.text(((width - w_title) // 2, height // 2 - 50), title, fill=accent_color, font=font_title)

        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        w_sub = bbox_sub[2] - bbox_sub[0]
        draw.text(((width - w_sub) // 2, height // 2 + 30), subtitle, fill="#5B3A4A", font=font_sub)

        img.save(file_path, "PNG")

    # Generate Luxury Moonlight Bot Banner if not already copied from assets
    banner_file = os.path.join(output_dir, "bot_banner.png")
    if not os.path.exists(banner_file):
        b_width, b_height = 1000, 500
        banner_img = Image.new("RGB", (b_width, b_height), color="#FFF7F9")
        b_draw = ImageDraw.Draw(banner_img)

        # Delicate double frame
        b_draw.rounded_rectangle([20, 20, b_width - 20, b_height - 20], radius=24, outline="#E8A598", width=3)
        b_draw.rounded_rectangle([28, 28, b_width - 28, b_height - 28], radius=18, outline="#F3D5CE", width=1)

        # Center boutique logo if available
        for logo_name in ["moonlight_logo_minimal.png", "moonlight_profile_pic.png"]:
            logo_p = os.path.join(output_dir, logo_name)
            if os.path.exists(logo_p):
                try:
                    logo = Image.open(logo_p).convert("RGBA")
                    logo = logo.resize((240, 240), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (240, 240), 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, 240, 240), fill=255)
                    banner_img.paste(logo, ((b_width - 240) // 2, 45), mask)
                    break
                except Exception:
                    pass

        b_title = "MOONLIGHT CHINESE SHOP"
        b_sub = "Xitoy brendlari & Go'zal aesthetic kiyimlar do'koni"

        b_font_title = _find_font(36, bold=True)
        b_font_sub = _find_font(20, bold=False)

        bbox_b = b_draw.textbbox((0, 0), b_title, font=b_font_title)
        b_draw.text(((b_width - (bbox_b[2] - bbox_b[0])) // 2, 315), b_title, fill="#2D1B2D", font=b_font_title)

        bbox_s = b_draw.textbbox((0, 0), b_sub, font=b_font_sub)
        b_draw.text(((b_width - (bbox_s[2] - bbox_s[0])) // 2, 375), b_sub, fill="#7D5868", font=b_font_sub)

        banner_img.save(banner_file, "PNG")


if __name__ == "__main__":
    generate_demo_images()
