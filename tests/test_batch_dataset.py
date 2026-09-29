import json
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
from PIL import Image
from scripts.batch_replace_dataset import plan,graph_for,save,run
from director.state import default_state


class BatchDatasetTests(unittest.TestCase):
    def test_queued_resume_downloads_existing_result_without_submitting_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'A';source.mkdir();identity=root/'B.png';out=root/'out'
            Image.new('RGB',(64,64),'red').save(identity)
            Image.new('RGB',(64,64),'blue').save(source/'a.png')
            manifest=plan(source,identity,out,'B')
            manifest['jobs'][0].update(status='queued',prompt_id='existing',fit={'state':default_state()})
            png=BytesIO();Image.new('RGB',(64,64),'green').save(png,format='PNG')
            class FakeClient:
                def __init__(self,url):self.url=url
                def wait(self,pid):
                    if pid!='existing':raise AssertionError('wrong prompt')
                    return {'outputs':{'10':{'images':[{'filename':'result.png','subfolder':'','type':'output'}]}}}
            with patch('scripts.batch_replace_dataset.Client',FakeClient),patch('urllib.request.urlopen',return_value=BytesIO(png.getvalue())):
                run(manifest,out,'http://localhost:8188',root/'unused-models')
            self.assertEqual(manifest['jobs'][0]['status'],'generated_pending_review')
            with patch('scripts.batch_replace_dataset.Client',FakeClient):
                run(manifest,out,'http://localhost:8188',root/'unused-models')
            self.assertEqual(len(list((out/'pending').glob('*.png'))),1)

    def test_resume_preserves_jobs_and_rejects_changed_identity_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'A';source.mkdir();out=root/'run';identity=root/'B.png'
            Image.new('RGB',(64,64),'red').save(identity)
            Image.new('RGB',(64,64),'blue').save(source/'pose.png')
            first=plan(source,identity,out,'B short dark hair')
            job=first['jobs'][0];job.update(status='queued',prompt_id='recorded-prompt')
            save(out/'manifest.json',first)
            resumed=plan(source,identity,out,'B short dark hair')
            self.assertEqual(resumed['jobs'],first['jobs'])
            self.assertEqual(resumed['config']['identity_scope'],'identity_only')
            with self.assertRaises(ValueError):plan(source,identity,out,'A different identity')
            with self.assertRaises(ValueError):plan(source,identity,source/'output','B')
            self.assertEqual(len(list(source.iterdir())),1)

    def test_batch_graph_does_not_inherit_example_clothing_or_description(self):
        config={'identity_scope':'identity_only','identity_description':'B with curly hair',
                'reference_opacity':0.,'control_strength':.25,'control_end':.6}
        state=default_state();state['render'].update(width=768,height=512)
        graph=graph_for({'id':'sample','seed':14,'scene_description':'yellow coat, raising left hand'},config,'B.png','A.png',state,'run')
        args=graph['6']['inputs']
        self.assertEqual(graph['5']['inputs']['image'],'A.png')
        self.assertEqual(graph['12']['inputs']['image'],'B.png')
        self.assertEqual(args['identity_scope'],'identity_only')
        self.assertIn('curly hair',args['prompt_prefix'])
        self.assertNotIn('burgundy',args['prompt_prefix'])
        self.assertIn('yellow coat, raising left hand',args['prompt_prefix'])
        self.assertFalse(args['pose_image_reference'])
        self.assertNotIn('images.image_3',graph['7']['inputs'])
        self.assertEqual(args['width'],768)
        self.assertEqual(graph['7']['inputs']['resolution'],0)
        self.assertEqual(graph['8']['inputs']['seed'],14)


if __name__=='__main__':unittest.main()
