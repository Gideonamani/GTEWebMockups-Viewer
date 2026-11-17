"""Restore a checksum-pinned, locally validated static viewer for GitHub Pages.

This standalone script also works in a viewer-only hosting repository. It never
downloads native CAD or research sources, and needs only Python's standard library.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile

REQUIRED_CHECKS = {'npm test', 'npm run test:cad', 'npm run test:freecad', 'npm run e2e'}
ROOT_FILES = {
    'index.html', 'viewer.css', 'viewer.js', 'workspace.js', 'viewer-math.mjs',
    'teaching.mjs', 'learn.js', 'flow.js', 'perf.mjs', 'catalog.json',
    '.nojekyll', 'release-validation.json', 'site-files.json',
}
MAX_SITE_BYTES = 1_000_000_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def allowed_path(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or '\\' in name or '..' in path.parts or str(path) != name:
        return False
    if name in ROOT_FILES:
        return True
    if name.startswith('vendor/'):
        return path.suffix in {'.js', '.wasm'}
    return bool(re.fullmatch(r'engines/[a-z0-9-]+/(part-info\.json|[A-Za-z0-9_.-]+\.glb)', name))


def validate_archive(archive: Path, descriptor: dict) -> dict:
    if descriptor.get('schema_version') != 1:
        raise ValueError('Unsupported Pages release descriptor')
    if archive.stat().st_size != descriptor['bytes'] or sha256(archive) != descriptor['sha256']:
        raise ValueError('Pages archive checksum/size mismatch')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or not all(allowed_path(name) for name in names):
            raise ValueError('Pages archive contains duplicate, private, or unsafe paths')
        if sum(member.file_size for member in members) > MAX_SITE_BYTES:
            raise ValueError('Pages site exceeds 1 GB')
        if any(stat.S_ISLNK(member.external_attr >> 16) for member in members):
            raise ValueError('Pages archive cannot contain symlinks')
        inventory = json.loads(bundle.read('site-files.json'))
        if set(inventory) != set(names) - {'site-files.json'}:
            raise ValueError('Pages archive does not match its file inventory')
        for name, expected in inventory.items():
            data = bundle.read(name)
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError(f'Pages file checksum mismatch: {name}')
        validation = json.loads(bundle.read('release-validation.json'))
        passed = {check['name'] for check in validation['checks'] if check.get('passed') is True}
        if validation.get('passed') is not True or not REQUIRED_CHECKS <= passed:
            raise ValueError('Pages archive lacks passing release checks')
        catalog = json.loads(bundle.read('catalog.json'))
        ready = [entry for entry in catalog['engines'] if entry['status'] == 'ready']
        engine_ids = sorted(entry['id'] for entry in ready)
        if not ready or engine_ids != sorted(descriptor['engines']) or engine_ids != sorted(validation['engines']):
            raise ValueError('Pages catalog does not match the validated engines')
        expected_models = set()
        for entry in ready:
            expected_info = f"engines/{entry['id']}/part-info.json"
            glb = entry['glb_path'].removeprefix('./')
            if entry['info_path'].removeprefix('./') != expected_info or not glb.startswith(f"engines/{entry['id']}/"):
                raise ValueError('Pages catalog must use local engine assets')
            if expected_info not in inventory or glb not in inventory or not glb.endswith('.glb'):
                raise ValueError('Pages catalog references a missing asset')
            expected_models.update((expected_info, glb))
        if {name for name in names if name.startswith('engines/')} != expected_models:
            raise ValueError('Pages archive contains unlisted engine assets')
    return {'passed': True, 'engines': len(ready), 'files': len(names), 'site_bytes': sum(m.file_size for m in members)}


def restore(archive: Path, descriptor: dict, output: Path) -> dict:
    result = validate_archive(archive, descriptor)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Restore destination must be empty')
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            target = output.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, default=Path('docs/github-pages-release.json'))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--output', type=Path, default=Path('build/github-pages/site'))
    args = parser.parse_args()
    descriptor = json.loads(args.descriptor.read_text(encoding='utf-8'))
    if args.archive:
        print(json.dumps(restore(args.archive, descriptor, args.output)))
        return
    if not args.repo:
        parser.error('--repo is required when downloading a release')
    with tempfile.TemporaryDirectory(prefix='gte-pages-download-') as download:
        subprocess.run([
            'gh', 'release', 'download', descriptor['release_tag'], '--repo', args.repo,
            '--pattern', descriptor['asset_name'], '--dir', download,
        ], check=True)
        print(json.dumps(restore(Path(download) / descriptor['asset_name'], descriptor, args.output)))


if __name__ == '__main__':
    main()
