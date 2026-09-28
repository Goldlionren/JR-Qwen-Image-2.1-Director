"""Exercise installed capture/detect/fit routes using the bundled benign reference."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--input-dir', type=Path, required=True)
p.add_argument('--base-url', default='http://127.0.0.1:8188')
args = p.parse_args()
root = Path(__file__).resolve().parent.parent
(root / '.local').mkdir(exist_ok=True)

def api(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(args.base_url + path, body, {'Content-Type': 'application/json'})
    with urlopen(request, timeout=180) as response:
        return json.load(response)


def capture(filename):
    queue = api('/queue')
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Queue busy; stopping smoke test')
    request_id = str(time.time_ns())
    graph = {'1': {'class_type': 'LoadImage', 'inputs': {'image': filename}},
             '2': {'class_type': 'JRDirectorImageCapture', 'inputs': {'image': ['1', 0], 'request_id': request_id}}}
    result = api('/prompt', {'prompt': graph})
    for _ in range(300):
        history = api('/history/' + result['prompt_id']).get(result['prompt_id'])
        if history:
            if history['status']['status_str'] != 'success':
                raise RuntimeError(history['status'])
            return history['outputs']['2']['jr_image_token'][0]
        time.sleep(.2)
    raise TimeoutError('Capture timed out')


reference = Image.open(root / 'examples/reference.png').convert('RGB')
# Synthetic two-person test fixture, assembled only from this project's own reference.
pair = Image.new('RGB', (reference.width*2, reference.height), 'white')
pair.paste(reference, (0, 0))
pair.paste(reference, (reference.width, 0))
stamp = time.time_ns()
results = {}
for name, image in [('single', reference), ('pair', pair), ('empty', Image.new('RGB', (512, 512), 'white'))]:
    filename = f'jr_director_import_{name}_{stamp}.png'
    image.save(args.input_dir / filename)
    token = capture(filename)
    start = time.monotonic()
    detected = api('/jr-director/detect', {'token': token})
    count = len(detected['people'])
    print(name, 'people:', count, 'seconds:', round(time.monotonic()-start, 2), flush=True)
    assert count == {'single': 1, 'pair': 2, 'empty': 0}[name], detected['people']
    fitted = []
    for i in range(count):
        result = api('/jr-director/fit', {'token': token, 'person_index': i, 'state': {}})
        assert result['state']['pose']['preset'] == 'Imported image'
        fitted.append(result)
    results[name] = {'filename': filename, 'people': detected['people'], 'fits': fitted}
    # Keep source preview transient, just like the production widget.
(root / '.local/image-import-smoke.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print('Image import API smoke passed', flush=True)
