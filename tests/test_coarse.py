import copy
import unittest
import numpy as np
from director.coarse import render_coarse
from director.state import default_state
from director.prompt import build_prompt


class CoarseTests(unittest.TestCase):
    def test_camera_pose_and_occlusion_are_rendered_deterministically(self):
        state = default_state(); state['render'].update(width=128, height=160)
        original = copy.deepcopy(state)
        front = render_coarse(state)
        np.testing.assert_array_equal(front, render_coarse(state))
        self.assertEqual(state, original)
        self.assertEqual(front.shape, (160,128,3))
        self.assertTrue(np.isfinite(front).all())
        self.assertGreater(np.sum(front < .8), 100)
        state['camera']['azimuth'] = 90
        side = render_coarse(state)
        self.assertGreater(np.mean(np.abs(front-side)), .01)
        state['pose']['joints']['right_shoulder'][2] = -150
        raised = render_coarse(state)
        self.assertGreater(np.mean(np.abs(side-raised)), .001)
        state['actor']['position'] = [0,0,20]
        self.assertAlmostEqual(float(render_coarse(state).min()), .92, places=5)

    def test_anyangle_prompt_does_not_preserve_old_camera(self):
        text,_,_ = build_prompt(default_state(), task_mode='any_angle')
        self.assertEqual(text, 'Change the camera angle from <image2> to <image1>.')
