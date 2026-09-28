import copy
import json
import unittest
import numpy as np
from director.state import default_state, parse_state, apply_preset, RIG
from director.geometry import forward_kinematics, camera_basis
from director.projection import render_pose, projected_joints, clip_segment
from director.prompt import view_label, build_prompt, LABELS


class DirectorTests(unittest.TestCase):
    def test_cardinal_semantics(self):
        for i,label in enumerate(LABELS):
            self.assertEqual(view_label(i*45),label+' view')
        self.assertIn('between',view_label(72))

    def test_wrap(self):
        for raw,expected in [(-10,350),(370,10),(720,0)]:
            s=parse_state({'camera':{'azimuth':raw}})
            self.assertEqual(s['camera']['azimuth'],expected)

    def test_relative_camera_actor(self):
        s=default_state();s['camera']['azimuth']=90
        self.assertEqual(json.loads(build_prompt(s)[1])['relative_azimuth'],90)
        camera=copy.deepcopy(s['camera']);s['actor']['yaw']=90
        info=json.loads(build_prompt(s)[1]);self.assertEqual(info['relative_azimuth'],0)
        self.assertAlmostEqual(info['effective_relative_azimuth'],0)
        self.assertEqual(s['camera'],camera)

    def test_roundtrip_and_constraints(self):
        for name in RIG['presets']:
            s=apply_preset(default_state(),name)
            s['actor'].update(yaw=34,pitch=17,roll=-12,scale=1.3)
            s=parse_state(s);self.assertEqual(parse_state(json.dumps(s)),s)
            p,_=forward_kinematics(s)
            for joint in RIG['joints']:
                if joint['parent']:
                    self.assertAlmostEqual(np.linalg.norm(p[joint['name']]-p[joint['parent']]),np.linalg.norm(joint['offset'])*1.3)

    def test_invalid_input(self):
        for raw in ['[]','null','{"version":2}','{"actor":{"scale":0}}','{"camera":{"fov":180}}',
                    '{"camera":{"azimuth":NaN}}','{"render":{"width":2049}}','{"pose":{"joints":{"unknown":[0,0,0]}}}']:
            with self.subTest(raw=raw),self.assertRaises((ValueError,TypeError)):
                parse_state(raw)

    def test_projection_front_and_aspect(self):
        s=default_state();p=projected_joints(s)
        self.assertAlmostEqual(p['nose']['xy'][0],512)
        self.assertLess(p['right_wrist']['xy'][0],p['left_wrist']['xy'][0])
        self.assertLess(p['nose']['xy'][1],p['left_ankle']['xy'][1])
        s['render']['width']=1536;p2=projected_joints(s)
        self.assertAlmostEqual(p2['left_wrist']['xy'][0]-p['left_wrist']['xy'][0],256)
        self.assertEqual(p2['left_wrist']['xy'][1],p['left_wrist']['xy'][1])

    def test_clipping(self):
        s=default_state()
        self.assertIsNone(clip_segment(np.array([0.,0.,-2]),np.array([0.,0.,-1]),s))
        clipped=clip_segment(np.array([0.,0.,-1]),np.array([0.,0.,1]),s)
        self.assertAlmostEqual(clipped[0][2],.05)
        s['actor']['position']=[0,0,10]
        self.assertTrue(all(not v['visible'] for v in projected_joints(s).values()))
        self.assertEqual(render_pose(s).max(),0)

    def test_camera_views_and_determinism(self):
        s=apply_preset(default_state(),'Asymmetric');s['render'].update(width=256,height=256)
        images=[]
        for azimuth in [0,45,90,180,270]:
            s['camera']['azimuth']=azimuth
            before=copy.deepcopy(s)
            image=render_pose(s);np.testing.assert_array_equal(image,render_pose(s))
            self.assertEqual(s,before);self.assertEqual(image.shape,(256,256,3));self.assertEqual(image.dtype,np.float32)
            self.assertTrue(np.isfinite(image).all());images.append(image)
        for i in range(1,len(images)):
            self.assertFalse(np.array_equal(images[0],images[i]))

    def test_prompt_contract(self):
        s=apply_preset(default_state(),'Right Arm Raised');s['camera']['azimuth']=72
        text,info,pose=build_prompt(s)
        for value in ['<image1>','<image2>','72.0','do not rotate the pose guide a second time']:
            self.assertIn(value,text)
        self.assertNotIn('<sks>',text);self.assertIn('right arm raised',pose)
        s['actor']['position']=[1,0,0]
        self.assertNotEqual(json.loads(build_prompt(s)[1])['effective_relative_azimuth'],72)

if __name__=='__main__': unittest.main()
