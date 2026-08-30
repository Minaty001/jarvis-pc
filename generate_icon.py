"""
Generate Jarvis tray icon.
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Cannot generate icon.")
    exit(1)


def create_jarvis_icon(output_path: str = "assets/icons/jarvis.png"):
    """Create a simple Jarvis tray icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([4, 4, 60, 60], fill=(0, 200, 83, 255))

    # Inner circle
    draw.ellipse([12, 12, 52, 52], fill=(0, 0, 0, 255))

    # J letter
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()

    draw.text((22, 14), "J", fill=(0, 200, 83, 255), font=font)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output))
    print(f"Icon saved to {output}")


if __name__ == "__main__":
    create_jarvis_icon()
