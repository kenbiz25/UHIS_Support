"""
One-off generator: derives favicon / apple-touch-icon / Open Graph link-preview
images from static/images/brand-icon.png so social/chat link unfurls (Slack,
WhatsApp, Teams, Twitter/X, LinkedIn, iMessage) show a properly-sized brand
image instead of a squashed/cropped square icon.

Usage:  python scripts/generate_brand_assets.py
Re-run after changing brand-icon.png or the app name/tagline baked into the
OG card.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "static", "images")
SRC_ICON = os.path.join(IMG_DIR, "brand-icon.png")

BRAND_NAVY = (37, 20, 190)
BRAND_NAVY_DARK = (26, 46, 108)
PERIWINKLE = (188, 181, 247)

APP_NAME = "Bangladesh UHIS"
TAGLINE = "SUPPORT PORTAL"

FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"


def _gradient_bg(size):
    """Diagonal navy -> periwinkle gradient, matching the login page promo panel."""
    w, h = size
    base = Image.new("RGB", (w, h), BRAND_NAVY)
    top = Image.new("RGB", (w, h), BRAND_NAVY_DARK)
    mask = Image.new("L", (w, h))
    mask_data = []
    diag = w + h
    for y in range(h):
        for x in range(w):
            mask_data.append(int(255 * (x + y) / diag))
    mask.putdata(mask_data)
    return Image.composite(base, top, mask)


def make_favicon(icon, out_name, px):
    canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    resized = icon.resize((px, px), Image.LANCZOS)
    canvas.paste(resized, (0, 0), resized)
    canvas.save(os.path.join(IMG_DIR, out_name))
    print(f"  {out_name} ({px}x{px})")


def make_apple_touch_icon(icon, px=180):
    """Apple ignores alpha and can render transparent areas as black - use a solid bg."""
    canvas = Image.new("RGB", (px, px), BRAND_NAVY)
    pad = int(px * 0.16)
    inner = px - 2 * pad
    resized = icon.resize((inner, inner), Image.LANCZOS)
    canvas.paste(resized, (pad, pad), resized)
    canvas.save(os.path.join(IMG_DIR, "apple-touch-icon.png"))
    print(f"  apple-touch-icon.png ({px}x{px})")


def make_og_image(icon, out_name="og-image.png", size=(1200, 630)):
    """Open Graph / Twitter card image - the standard 1.91:1 link-preview size."""
    w, h = size
    canvas = _gradient_bg(size).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Soft decorative circles, echoing the login page promo panel
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse([w - 340, -220, w + 160, 280], fill=(255, 255, 255, 13))
    odraw.ellipse([-180, h - 260, 220, h + 140], fill=(255, 255, 255, 13))
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    icon_px = 260
    icon_resized = icon.resize((icon_px, icon_px), Image.LANCZOS)
    icon_x, icon_y = 100, (h - icon_px) // 2
    canvas.paste(icon_resized, (icon_x, icon_y), icon_resized)

    text_x = icon_x + icon_px + 60
    try:
        font_tag = ImageFont.truetype(FONT_BOLD, 30)
        font_title = ImageFont.truetype(FONT_BOLD, 72)
    except OSError:
        font_tag = ImageFont.load_default()
        font_title = ImageFont.load_default()

    draw.text((text_x, h // 2 - 70), TAGLINE, font=font_tag, fill=PERIWINKLE + (255,))
    draw.text((text_x, h // 2 - 20), APP_NAME, font=font_title, fill=(255, 255, 255, 255))

    canvas.convert("RGB").save(os.path.join(IMG_DIR, out_name), quality=92)
    print(f"  {out_name} ({w}x{h})")


def main():
    icon = Image.open(SRC_ICON).convert("RGBA")
    print("Generating brand assets from", SRC_ICON)
    make_favicon(icon, "favicon-16.png", 16)
    make_favicon(icon, "favicon-32.png", 32)
    make_favicon(icon, "favicon-192.png", 192)
    make_apple_touch_icon(icon, 180)
    make_og_image(icon)
    print("Done.")


if __name__ == "__main__":
    main()
