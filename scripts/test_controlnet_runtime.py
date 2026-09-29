"""CPU regression checks against the installed ComfyUI, no checkpoints required.

python scripts/test_controlnet_runtime.py --comfy-root /path/to/ComfyUI
"""
import argparse
import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
import copy

parser = argparse.ArgumentParser()
parser.add_argument('--comfy-root', required=True)
args = parser.parse_args()
sys.path[:0] = [args.comfy_root, str(Path(__file__).resolve().parent.parent)]
sys.argv = [sys.argv[0], '--cpu']
import comfy.options
comfy.options.enable_args_parsing()
import torch
import comfy.ops
import comfy.model_management
import comfy.model_patcher
from comfy.ldm.qwen_image21.model import QwenImage21Transformer2DModel
from controlnet.loader import checkpoint_config
from controlnet.integration import apply_control, validate_settings
from controlnet.patch import QwenImage21FunControlPatch, QwenImage21FunControlBlockPatch
from controlnet.compat import _forward
from director.prompt import build_prompt
from director.state import default_state
from director.conditioning import reference_overlay


class ControlTests(unittest.TestCase):
    def test_reference_hint_keeps_bones_and_aspect_and_zero_bypass(self):
        pose=torch.zeros(1,8,8,3);pose[0,4,4,0]=1
        ref=torch.ones(2,4,8,3)
        self.assertIs(reference_overlay(pose,None,0),pose)
        result=reference_overlay(pose,ref,.1)
        torch.testing.assert_close(result[0,4,4],pose[0,4,4])
        torch.testing.assert_close(result[0,3,3],torch.full((3,),.1))
        self.assertEqual(result[:,0].sum().item(),0)
        self.assertEqual(ref.sum().item(),192)
        self.assertEqual(pose.sum().item(),1)
        for opacity in [float('nan'),-.1,.11]:
            with self.assertRaises(ValueError):reference_overlay(pose,ref,opacity)
        with self.assertRaises(ValueError):reference_overlay(pose,None,.05)

    def test_wrong_checkpoint_and_partial_checkpoint_rejected(self):
        shape = lambda *s: SimpleNamespace(shape=s)
        sd = {'control_img_in.weight': shape(4096,129),
              'control_blocks.0.img_mlp.out.weight': shape(4096,12288),
              'control_blocks.0.img_mlp.gate_up.weight': shape(24576,4096),
              'control_blocks.0.attn.norm_q.weight': shape(128),
              'control_blocks.0.before_proj.weight': shape(4096,4096)}
        sd.update({f'control_blocks.{i}.after_proj.weight':shape(4096,4096) for i in range(16)})
        self.assertEqual(checkpoint_config(sd)['num_blocks'],16)
        sd['control_img_in.weight']=shape(4096,132)
        with self.assertRaises(ValueError): checkpoint_config(sd)
        with self.assertRaises(ValueError): checkpoint_config({})

    def test_settings_and_control_prompt(self):
        for values in [(1,.7,.3), (float('nan'),0,1), (-1,0,1), (1,0,0)]:
            with self.assertRaises(ValueError): validate_settings(*values)
        self.assertNotIn('<image2>',build_prompt(default_state(),controlnet=True)[0])
        self.assertIn('<image2>',build_prompt(default_state())[0])
        base=object()
        self.assertIs(apply_control(base,None,None,None,0,0,1),base)

    def test_patch_registration_clone_and_restore(self):
        diffusion=QwenImage21Transformer2DModel(num_attention_heads=1,attention_head_dim=8,
            context_in_dim=8,axes_dims_rope=(2,2,4),operations=comfy.ops.manual_cast,
            dtype=torch.float32,device='cpu')
        root=torch.nn.Module();root.diffusion_model=diffusion
        root.model_sampling=SimpleNamespace(percent_to_sigma=lambda p:1-p)
        base=comfy.model_patcher.ModelPatcher(root,torch.device('cpu'),torch.device('cpu'))
        original=diffusion._forward.__func__
        control=SimpleNamespace(model=SimpleNamespace(control_blocks=[None]*16))
        vae=SimpleNamespace(latent_channels=64,spacial_compression_encode=lambda:16)
        result=apply_control(base,control,vae,torch.zeros(1,32,32,3),.75,.1,.9)
        self.assertNotIn('diffusion_model._forward',base.object_patches)
        self.assertIs(diffusion._forward.__func__,original)
        hooks=result.model_options['transformer_options']['patches_replace']['dit']
        self.assertEqual(list(hooks),[('single_block',i) for i in range(0,32,2)])
        result.patch_model(load_weights=False)
        self.assertIs(diffusion._forward.__func__,_forward)
        result.unpatch_model(unpatch_weights=False)
        self.assertIs(diffusion._forward.__func__,original)

    def test_inactive_patch_preserves_previous_and_exception_cleans_stream(self):
        patch=QwenImage21FunControlPatch(None,None,None,1,sigma_range=(.8,.2))
        previous=object()
        hook=QwenImage21FunControlBlockPatch(patch,0,previous)
        options={'sigmas':torch.tensor([.9]),'patches_replace':{'dit':{('single_block',0):hook}}}
        def execute(x,t,c,r,s,opts):
            self.assertIs(opts['patches_replace']['dit'][('single_block',0)],previous)
            patch.stream=object();patch.pristine=object()
            raise RuntimeError('test exception')
        with self.assertRaisesRegex(RuntimeError,'test exception'):
            patch.diffusion_model_wrapper(execute,None,None,None,None,None,options)
        self.assertIsNone(patch.stream);self.assertIsNone(patch.pristine)
        self.assertIs(options['patches_replace']['dit'][('single_block',0)],hook)


if __name__=='__main__': unittest.main(argv=[sys.argv[0]],verbosity=2)
