from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST.json').read_text())
for item in manifest:
    target = root / item['name']
    if not target.exists():
        parts = sorted(root.glob(item['name'] + '.part*'))
        if parts:
            with target.open('wb') as out:
                for part in parts:
                    out.write(part.read_bytes())
    if not target.exists():
        raise SystemExit('Missing: ' + item['name'])
    data = target.read_bytes()
    if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise SystemExit('Verification failed: ' + item['name'])
print('Verified all 40 original project source files.')
