import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
import torch
from director.depth import estimate_depth


class DepthTests(unittest.TestCase):
    def test_normalization_channel_order_and_thread_restore(self):
        with tempfile.NamedTemporaryFile(suffix='.safetensors') as file:
            image=torch.zeros(1,2,3,3);image[...,0]=1
            class Model:
                def infer_image(self,bgr,size):
                    np.testing.assert_array_equal(bgr[0,0],[0,0,255])
                    return np.arange(6,dtype=np.float32).reshape(2,3)
            before=torch.get_num_threads()
            with patch('director.depth.available_models',return_value={'test':Path(file.name)}),patch('director.depth._load',return_value=Model()):
                depth=estimate_depth(image,'test')
            self.assertEqual(depth.shape,(1,2,3,3))
            self.assertEqual(float(depth.min()),0)
            self.assertEqual(float(depth.max()),1)
            torch.testing.assert_close(depth[...,0],depth[...,2])
            self.assertEqual(torch.get_num_threads(),before)
            with patch('director.depth.available_models',return_value={'test':Path(file.name)}),patch('director.depth._load',side_effect=ValueError('bad weight')):
                with self.assertRaises(ValueError):estimate_depth(image,'test')
            self.assertEqual(torch.get_num_threads(),before)
