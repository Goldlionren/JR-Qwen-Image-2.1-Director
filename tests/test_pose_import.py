import unittest
import numpy as np
from director.state import default_state, apply_preset, JOINTS
from director.geometry import camera_points, forward_kinematics
from director.pose_import import fit_pose, COCO
from director.detection import nms, find_models


def landmarks(state, width=768, height=1024):
    points = camera_points(state)
    factor = height / (2 * np.tan(np.radians(state["camera"]["fov"] / 2)))
    return [[width/2 + points[n][0]*factor/points[n][2],
             height/2 - points[n][1]*factor/points[n][2], .95] for n in COCO]


class PoseImportTests(unittest.TestCase):
    def test_asymmetric_pose_preserves_geometry_and_arm_side(self):
        source = apply_preset(default_state(), "Asymmetric")
        source["camera"]["distance"] = 4
        result = fit_pose(landmarks(source), 768, 1024)
        state = result["state"]
        self.assertEqual(state["pose"]["preset"], "Imported image")
        self.assertEqual((state["render"]["width"], state["render"]["height"]), (768, 1024))
        xyz, _ = forward_kinematics(state)
        self.assertGreater(xyz["right_wrist"][1], xyz["left_wrist"][1])
        for name, joint in JOINTS.items():
            if joint["parent"]:
                self.assertAlmostEqual(np.linalg.norm(xyz[name]-xyz[joint["parent"]]),
                                       np.linalg.norm(joint["offset"]), places=10)
        self.assertLess(result["fit_error_pixels"], 12)

    def test_partial_body_warns_and_keeps_unobserved_leg_rotations(self):
        points = landmarks(default_state())
        for i in range(11, 17):
            points[i][2] = .05
        result = fit_pose(points, 768, 1024)
        self.assertTrue(any("left_ankle" in w for w in result["warnings"]))
        for side in ("left", "right"):
            self.assertEqual(result["state"]["pose"]["joints"][side+"_knee"], [0, 0, 0])

    def test_invalid_or_inadequate_detections_fail(self):
        for points in ([], np.full((17, 3), np.nan), np.zeros((17, 3))):
            with self.assertRaises(ValueError):
                fit_pose(points, 512, 512)
        with self.assertRaises(FileNotFoundError):
            find_models([])

    def test_person_nms_keeps_separate_subjects(self):
        boxes = np.array([[0, 0, 100, 200], [2, 2, 102, 202], [130, 0, 230, 200]])
        self.assertEqual(nms(boxes, np.array([.9, .8, .7])), [0, 2])


if __name__ == "__main__":
    unittest.main()
