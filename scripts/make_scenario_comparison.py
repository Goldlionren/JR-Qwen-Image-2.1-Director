"""Build a contact sheet of the scenario validation examples (not an approval score)."""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

p=argparse.ArgumentParser();p.add_argument('--comfy-output',required=True,type=Path);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
font_path=Path('C:/Windows/Fonts/arial.ttf')
font=ImageFont.truetype(str(font_path),18) if font_path.exists() else ImageFont.load_default()
sheet=Image.new('RGB',(960,730),'#17212b');draw=ImageDraw.Draw(sheet)
panels=[
    ('1: Source person + classroom',root/'examples/scenarios/jr_director_classroom_source.png'),
    ('1: Edited pose',root/'.local/scenario-edit_pose-pose.png'),
    ('1: Same person, raised arm',args.comfy_output/'Qwen21Director_test/scenario-edit025_00001_.png'),
    ('2: Identity B',root/'examples/reference.png'),
    ('2: A pose / clothes / scene',root/'examples/scenarios/jr_director_classroom_raised.png'),
    ('2: B identity, A clothes (review)',args.comfy_output/'JR_Director_replace_person_00002_.png')]
for index,(title,path) in enumerate(panels):
    x,y=index%3*320,index//3*365
    draw.text((x+7,y+10),title,font=font,fill='white')
    with Image.open(path) as im:
        im=im.convert('RGB');im.thumbnail((312,312),Image.Resampling.LANCZOS)
        sheet.paste(im,(x+(320-im.width)//2,y+44+(312-im.height)//2))
sheet.save(root/'docs/scenario-comparison.png')
print(root/'docs/scenario-comparison.png')
