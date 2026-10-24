#!/usr/bin/env python3
"""Build offline ZIP and self-extracting .run from pinned 0.4.1 payload."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from installer import VERSION
from installer.core import SOURCE_HASH

URL = 'https://github.com/N3ruk/DBZK_Fix_LINUX/releases/download/LINUX-V0.4.1/DRAGON.BALL.FPS.UNCAP.LINUX.zip'
PREFIX = 'DRAGON BALL FPS UNCAP LINUX/'
NAME = 'DBZK-Fix-Linux-' + VERSION


def archive_payload(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_HASH:
        raise ValueError('El ZIP 0.4.1 no coincide con el SHA256 publicado')
    payload = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            if not item.filename.startswith(PREFIX):
                raise ValueError('Ruta inesperada en el archivo original')
            relative = item.filename[len(PREFIX):]
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Ruta o enlace no seguro en el archivo original')
            if path.suffix.lower() == '.log':
                continue
            payload['payload/' + relative] = archive.read(item)
    return payload


def package_files(archive_data):
    files = archive_payload(archive_data)
    manifest = {'installer_version': VERSION, 'payload_version': '0.4.1',
                'source_url': URL, 'source_sha256': SOURCE_HASH,
                'files': {key[len('payload/'):]: hashlib.sha256(data).hexdigest()
                          for key, data in sorted(files.items())}}
    files['payload-manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    for relative in ('install.py', 'Instalar.sh', 'README.md', 'README_ES.md', 'LICENSE', 'DefaultConfig.ini',
                     'docs/INSTALLER.md', 'docs/RELEASE-0.4.2.md', 'docs/THIRD-PARTY.md',
                     'scripts/build.py', 'AGENTS.md'):
        files[relative] = (ROOT / relative).read_bytes()
    for directory in ('installer', 'tests'):
        for path in sorted((ROOT / directory).glob('*.py')):
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for path in sorted((ROOT / 'Mods').rglob('*.lua')):
        files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + path + '\n'
                                for path, data in sorted(files.items())).encode()
    return files


def is_executable(name):
    return name in ('Instalar.sh', 'install.py', 'scripts/build.py')


def make_zip(files):
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((0o100755 if is_executable(name) else 0o100644) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return target.getvalue()


def make_run(files):
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if is_executable(name) else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    compressed = gzip.compress(tar_bytes.getvalue(), compresslevel=9, mtime=0)
    checksum = hashlib.sha256(compressed).hexdigest()
    header = '''#!/usr/bin/env bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\\n' 'Se necesita Python 3.8 o posterior para este instalador.' >&2
    exit 1
fi
exec python3 - "$0" "$@" <<'DBZK_PYTHON'
import gzip, hashlib, io, pathlib, runpy, sys, tarfile, tempfile
if sys.version_info < (3, 8):
    sys.exit('Se necesita Python 3.8 o posterior.')
script = pathlib.Path(sys.argv[1])
arguments = sys.argv[2:]
data = script.read_bytes().split(b'\\n__DBZK_PAYLOAD__\\n', 1)[1]
if hashlib.sha256(data).hexdigest() != '__CHECKSUM__':
    sys.exit('El instalador está dañado: checksum incorrecto.')
def extract(destination):
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data)), mode='r:') as archive:
        for item in archive.getmembers():
            relative = pathlib.PurePosixPath(item.name)
            if relative.is_absolute() or '..' in relative.parts or not item.isfile():
                sys.exit('Ruta no válida en el instalador.')
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(archive.extractfile(item).read())
            target.chmod(item.mode & 0o777)
if arguments and arguments[0] == '--extract':
    if len(arguments) != 2:
        sys.exit('Uso: instalador.run --extract CARPETA_NUEVA')
    destination = pathlib.Path(arguments[1]).expanduser().absolute()
    destination.mkdir(parents=True, exist_ok=False)
    extract(destination)
    print('Extraído en: ' + str(destination))
else:
    with tempfile.TemporaryDirectory(prefix='dbzk-fix-') as temporary:
        destination = pathlib.Path(temporary)
        extract(destination)
        sys.path.insert(0, str(destination))
        sys.argv = [str(destination / 'install.py')] + arguments
        runpy.run_path(str(destination / 'install.py'), run_name='__main__')
DBZK_PYTHON
exit 0
__DBZK_PAYLOAD__
'''.replace('__CHECKSUM__', checksum)
    return header.encode() + compressed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='ZIP original 0.4.1; se verifica antes de usar')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    data = args.archive.read_bytes() if args.archive else urllib.request.urlopen(URL, timeout=60).read()
    files = package_files(data)
    if files['payload/ue4ss/Mods/DBZK_Fix/Scripts/main.lua'] != (ROOT / 'Mods/DBZK_Fix/Scripts/main.lua').read_bytes():
        raise ValueError('El código del mod ya no coincide con el payload original')
    args.output.mkdir(parents=True, exist_ok=True)
    products = {NAME + '.zip': make_zip(files), NAME + '.run': make_run(files)}
    for name, contents in products.items():
        path = args.output / name
        path.write_bytes(contents)
        path.chmod(0o755 if path.suffix == '.run' else 0o644)
        print(name + ': ' + str(len(contents)) + ' bytes')
    (args.output / 'SHA256SUMS').write_text(''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                                                for name, data in sorted(products.items())))


if __name__ == '__main__':
    main()
