import unittest
import torch
from director.describe import describe_references, description_instruction, normalize_description


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
                assert kwargs == dict(do_sample=False,temperature=0.0,max_length=192,mtp=False)
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

    def test_case_and_colon_variants_preserve_description_prose(self):
        for raw in [
            'Identity: Dark Hair. Outfit_and_scene: A Blue coat.',
            'identity : Dark Hair.\nOutfit_And_Scene： A Blue coat.',
            '<think>analysis</think>\nIDENTITY: Dark Hair. OUTFIT_AND_SCENE: A Blue coat.',
        ]:
            with self.subTest(raw=raw):
                normalized=normalize_description(raw)
                self.assertIn('IDENTITY: Dark Hair.',normalized)
                self.assertIn('OUTFIT_AND_SCENE: A Blue coat.',normalized)
                self.assertNotIn('<think>',normalized)

    def test_error_identifies_missing_label_and_preserves_complete_raw_output(self):
        raw='<think>Hidden reasoning</think>\nIdentity: Dark hair and glasses.\nScene: red coat.'
        with self.assertRaises(ValueError) as error:normalize_description(raw)
        message=str(error.exception)
        self.assertIn('Missing labels: OUTFIT_AND_SCENE:',message)
        self.assertIn(raw,message)
        self.assertIn('Text after cleanup',message)
        self.assertIn('max_length=192',message)

    def test_empty_or_unlabeled_output_is_not_silently_accepted(self):
        for raw in ['', '  ', '<think>analysis</think>\n', 'A complete caption without labels.',
                    'IDENTITY: a person.', 'OUTFIT_AND_SCENE: a coat.']:
            with self.subTest(raw=raw),self.assertRaises(ValueError) as error:
                normalize_description(raw)
            self.assertIn('BEGIN GENERATED TEXT',str(error.exception))

    def test_leading_id_abbreviation_is_accepted_without_rewriting_prose(self):
        result=normalize_description('Id: Dark hair; badge ID: ABC.\nOutfit_and_scene: Blue coat.')
        self.assertEqual(result,'IDENTITY: Dark hair; badge ID: ABC.\nOUTFIT_AND_SCENE: Blue coat.')
        with self.assertRaises(ValueError):
            normalize_description('The badge ID: ABC.\nOUTFIT_AND_SCENE: Blue coat.')
        with self.assertRaises(ValueError):normalize_description('ID: Dark hair.')
