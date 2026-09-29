import unittest
import torch
from director.describe import describe_references, description_instruction


class DescriptionTests(unittest.TestCase):
    def test_image_roles_are_preserved_and_clothing_scope_changes(self):
        identity=torch.ones(1,8,8,3)
        scene=torch.zeros(1,8,8,3)
        class FakeClip:
            def tokenize(self,prompt,**kwargs):
                torch.testing.assert_close(kwargs['image'][0:1],identity)
                torch.testing.assert_close(kwargs['image'][1:2],scene)
                return prompt
            def generate(self,tokens,**kwargs):
                return 'IDENTITY: visible identity. OUTFIT_AND_SCENE: scene outfit.'
            def decode(self,ids):return ids
        result=describe_references(FakeClip(),identity,scene,'identity_only')
        self.assertIn('IDENTITY:',result)
        self.assertIn('exclude their outfit',description_instruction('identity_only'))
        self.assertNotIn('exclude their outfit',description_instruction('full_appearance'))
        self.assertIn('eyewear',description_instruction('identity_only'))
        with self.assertRaises(ValueError):describe_references(None,identity,scene,'identity_only')

    def test_incomplete_response_is_not_silently_sent_to_diffusion(self):
        class IncompleteClip:
            def tokenize(self,*args,**kwargs):return None
            def generate(self,*args,**kwargs):return None
            def decode(self,*args):return '<think>unfinished'
        with self.assertRaises(ValueError):
            describe_references(IncompleteClip(),torch.zeros(1,8,8,3),torch.zeros(1,8,8,3),'identity_only')
