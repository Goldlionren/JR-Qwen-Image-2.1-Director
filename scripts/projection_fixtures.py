"""Generate Python results consumed by the independent Three.js projection tests."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from director.state import default_state, apply_preset
from director.projection import projected_joints

cases=[]
for az in [0,45,90,135,180,225,270,315]:
    s=apply_preset(default_state(),'Asymmetric')
    s['camera'].update(azimuth=az,elevation=18,roll=-13)
    s['actor'].update(position=[.2,.1,-.3],yaw=27,pitch=-12,roll=6,scale=1.1)
    s['render'].update(width=768,height=1024)
    cases.append({'state':s,'points':projected_joints(s)})
Path('tests/projection-fixtures.json').write_text(json.dumps(cases,indent=2))
print('Wrote',len(cases),'projection fixtures')
