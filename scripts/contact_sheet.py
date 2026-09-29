"""Assemble locally generated test outputs into a review sheet (no source image edits)."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser();p.add_argument('output_dir',type=Path);args=p.parse_args()
cases=['reference','front','right','back','quarter','raised','walking','asymmetric']
tile=320;header=70;label=44
sheet=Image.new('RGB',(4*tile,header+2*(tile+label)), '#10202e')
draw=ImageDraw.Draw(sheet)
try:font=ImageFont.truetype('segoeui.ttf',20);small=ImageFont.truetype('segoeui.ttf',15)
except OSError:font=small=ImageFont.load_default()
draw.text((20,12),'JR Qwen Image 2.1 Director | Local generation tests',font=font,fill='#ccebe8')
draw.text((20,42),'512px / 25 steps / same identity reference / pose guide as <image2>',font=small,fill='#83a9b8')
for i,name in enumerate(cases):
    path=args.output_dir/(name+'_00001_.png')
    image=Image.open(path).convert('RGB');image.thumbnail((tile,tile))
    x=(i%4)*tile;y=header+(i//4)*(tile+label)
    sheet.paste(image,(x+(tile-image.width)//2,y))
    draw.text((x+12,y+tile+10),name.replace('_',' ').title(),font=small,fill='#d8e7f0')
destination=Path(__file__).resolve().parents[1]/'_private/reports/generation-contact-sheet.png'
destination.parent.mkdir(parents=True,exist_ok=True)
sheet.save(destination)
print('Wrote',destination)
