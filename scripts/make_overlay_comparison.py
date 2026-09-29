"""Compose the three fixed-seed control experiments into a review sheet."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', required=True, type=Path,
                    help='ComfyUI output directory containing Qwen21Director_test')
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
sheet = Image.new('RGB', (960, 736), '#19212b')
draw = ImageDraw.Draw(sheet)
font_path = Path('C:/Windows/Fonts/arial.ttf')
font = ImageFont.truetype(str(font_path), 19) if font_path.exists() else ImageFont.load_default()
draw.text((16, 8), 'Same seed / walking 45 deg / ControlNet 1.0 / 25 steps', font=font, fill='white')
for col, (suffix, label) in enumerate([('000', 'Original 0%'), ('005', 'Original 5%'), ('010', 'Original 10%')]):
    stem = 'walking-quarter-overlay' + suffix
    draw.text((col * 320 + 12, 42), label, font=font, fill='white')
    for row, ending in enumerate(['-hint_00001_.png', '_00001_.png']):
        file = args.output_dir / 'Qwen21Director_test' / (stem + ending)
        with Image.open(file) as im:
            im = im.convert('RGB').resize((312, 312), Image.Resampling.LANCZOS)
            sheet.paste(im, (col * 320 + 4, 72 + row * 320))
draw.text((12, 711), 'Top: actual ControlNet hint. Bottom: generated image. Qwen image_2 stays pure pose.',
          font=ImageFont.truetype(str(font_path), 15) if font_path.exists() else font, fill='#b7c4d4')
destination = root / 'docs/pose-overlay-comparison.png'
sheet.save(destination)
print(destination)
