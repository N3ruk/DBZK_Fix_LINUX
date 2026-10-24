"""Detection, graceful Steam shutdown and recoverable installation.

No commands from Steam configuration are ever executed. Production writes are
only made by apply_plan(), after its Steam-closed guard has succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
import uuid

from . import VERSION
from .vdf import APP_PATH, Document, VDFError

APP_ID = '851850'
EDITIONS = (('Normal', 'AT/Binaries/Win64'), ('Remastered', 'dlc/Remaster/AT/Binaries/Win64'))
SOURCE_HASH = 'e102d42460386c3e5703dd0ed67bd3ddd7e5217e592b97bd86945088782bd9d4'


class InstallError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_vdf(path):
    return Document(path.read_bytes().decode('utf-8', errors='surrogateescape'))


@dataclass(frozen=True)
class SteamRoot:
    path: Path
    kind: str


@dataclass
class Game:
    path: Path
    roots: list = field(default_factory=list)

    def editions(self):
        result = []
        for label, relative in EDITIONS:
            target = self.path / relative
            executables = {'at-win64-shipping.exe', 'at.exe'}
            if target.is_dir() and any(p.is_file() and p.name.casefold() in executables for p in target.iterdir()):
                if not is_within(target.resolve(), self.path):
                    raise InstallError('La carpeta de una edición sale del juego: ' + str(target))
                result.append((label, target.resolve()))
        return result


def is_within(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def steam_roots(home=None, environ=None, extra=()):
    home = Path(home) if home is not None else Path.home()
    env = os.environ if environ is None else environ
    data = Path(env.get('XDG_DATA_HOME') or home / '.local/share')
    candidates = [(data / 'Steam', 'native')]
    candidates += [(home / p, 'native') for p in ('.steam/steam', '.steam/root', '.steam/debian-installation', '.steam/steam-installation')]
    candidates += [(home / '.var/app/com.valvesoftware.Steam' / p, 'flatpak') for p in ('.local/share/Steam', '.steam/steam', '.steam/root')]
    candidates += [(home / 'snap/steam/common' / p, 'snap') for p in ('.local/share/Steam', '.steam/steam', '.steam/root')]
    candidates += [(Path(p).expanduser(), 'custom') for p in extra]
    roots = {}
    for path, kind in candidates:
        resolved = path.resolve()
        if resolved in roots or not resolved.is_dir():
            continue
        if (resolved / 'steamapps').is_dir() or (resolved / 'userdata').is_dir():
            # Canonical paths distinguish sandbox installs even through ~/.steam.
            if 'com.valvesoftware.Steam' in str(resolved):
                kind = 'flatpak'
            elif is_within(resolved, home / 'snap/steam'):
                kind = 'snap'
            roots[resolved] = SteamRoot(resolved, kind)
    return list(roots.values())


def libraries(root):
    result = {root.path}
    for relative in ('steamapps/libraryfolders.vdf', 'config/libraryfolders.vdf'):
        path = root.path / relative
        if not path.is_file():
            continue
        doc = read_vdf(path)
        section = doc.find(['libraryfolders'])
        if section is None or section.value is not None:
            raise InstallError('libraryfolders.vdf no válido: ' + str(path))
        for node in section.children:
            if not node.key.value.isdecimal():
                continue
            value = node.value.value if node.value else doc.get(['libraryfolders', node.key.value, 'path'])
            if value:
                lib = Path(value).expanduser()
                if not lib.is_absolute():
                    raise InstallError('Biblioteca Steam con ruta relativa: ' + value)
                if lib.is_dir():
                    result.add(lib.resolve())
    return sorted(result)


def discover_games(roots, manual=None):
    games = {}
    for root in roots:
        for library in libraries(root):
            manifest = library / 'steamapps' / ('appmanifest_' + APP_ID + '.acf')
            if not manifest.is_file():
                continue
            doc = read_vdf(manifest)
            if doc.get(['AppState', 'appid']) != APP_ID:
                raise InstallError('AppID inesperado: ' + str(manifest))
            dirname = doc.get(['AppState', 'installdir'])
            if not dirname or Path(dirname).name != dirname or dirname in ('.', '..'):
                raise InstallError('Directorio de juego no válido: ' + str(manifest))
            path = (library / 'steamapps/common' / dirname).resolve()
            game = games.setdefault(path, Game(path))
            if root not in game.roots:
                game.roots.append(root)
    if manual is not None:
        path = Path(manual).expanduser().resolve()
        game = games.get(path, Game(path, list(roots)))
        if not game.editions():
            raise InstallError('No hay ejecutables en AT/Binaries/Win64 ni dlc/Remaster/AT/Binaries/Win64. Selecciona la carpeta raíz del juego.')
        return [game]
    return [game for game in games.values() if game.editions()]


def profiles(roots):
    result = set()
    for root in roots:
        for user in (root.path / 'userdata').glob('*'):
            path = user / 'config/localconfig.vdf'
            if user.name.isdecimal() and user.name != '0' and path.is_file():
                # Validate the actual per-user format, never invent an account.
                if read_vdf(path).find(['UserLocalConfigStore']) is None:
                    raise InstallError('Perfil Steam no válido: ' + str(path))
                result.add(path)
    return sorted(result)


def shell_words(text):
    """Return shell-word spans without executing, expanding or reformatting."""
    words = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        start = pos
        quote_char = None
        while pos < len(text):
            ch = text[pos]
            if quote_char == "'":
                if ch == "'":
                    quote_char = None
            elif ch == '\\':
                pos += 1
                if pos == len(text):
                    raise InstallError('Opciones de lanzamiento con escape incompleto')
            elif quote_char == '"':
                if ch == '"':
                    quote_char = None
                elif ch in '$`':
                    raise InstallError('Opciones con expansión dinámica; simplifícalas antes de instalar.')
            elif ch in "'\"":
                quote_char = ch
            elif ch.isspace():
                break
            elif ch in ';|&<>`$()#\n':
                raise InstallError('Opciones de lanzamiento con sintaxis shell compleja; no se han cambiado.')
            pos += 1
        if quote_char:
            raise InstallError('Opciones de lanzamiento con comillas sin cerrar')
        raw = text[start:pos]
        try:
            value = shlex.split(raw)
        except ValueError as exc:
            raise InstallError(str(exc)) from exc
        if len(value) != 1:
            raise InstallError('Opción de lanzamiento ambigua')
        words.append((start, pos, value[0]))
    return words


def merge_overrides(value):
    rules = []
    for rule in value.split(';'):
        rule = rule.strip()
        if not rule:
            continue
        names, sep, setting = rule.partition('=')
        if not sep:
            raise InstallError('WINEDLLOVERRIDES no válido: no se ha sobrescrito')
        remaining = [name.strip() for name in names.split(',') if re.sub(r'\.dll$', '', name.strip().lower()) != 'dwmapi']
        if remaining:
            rules.append(','.join(remaining) + '=' + setting)
    return ';'.join(rules + ['dwmapi=n,b'])


def merge_launch_options(value):
    value = value or ''
    if '\n' in value or '\r' in value:
        raise InstallError('Opciones de lanzamiento multilínea; no se han cambiado.')
    words = shell_words(value)
    commands = [w for w in words if w[2] == '%command%']
    if value.count('%command%') != len(commands) or len(commands) > 1:
        raise InstallError('Marcador %command% ambiguo; revisa las opciones de lanzamiento.')
    overrides = [w for w in words if w[2].startswith('WINEDLLOVERRIDES=')]
    if len(overrides) > 1:
        raise InstallError('Hay varias variables WINEDLLOVERRIDES; no se han sobrescrito.')
    if overrides:
        start, end, word = overrides[0]
        # An assignment is meaningful only in the environment/wrapper prefix.
        if not commands or start > commands[0][0]:
            raise InstallError('WINEDLLOVERRIDES debe estar antes de %command%.')
        new = merge_overrides(word.partition('=')[2])
        if new == word.partition('=')[2]:
            return value
        replacement = 'WINEDLLOVERRIDES=' + shlex.quote(new)
        return value[:start] + replacement + value[end:]
    prefix = 'WINEDLLOVERRIDES="dwmapi=n,b" '
    if commands:
        return prefix + value
    # With no %command%, Steam treats the original text as game arguments.
    return prefix + '%command%' + (' ' + value if value else '')


def enable_mods_txt(text):
    pattern = re.compile(r'^([^\S\r\n]*DBZK_Fix[^\S\r\n]*:[^\S\r\n]*)([01])([^\r\n]*)(\r?)$', re.I | re.M)
    matches = list(pattern.finditer(text))
    declarations = re.findall(r'^[^\S\r\n]*DBZK_Fix[^\S\r\n]*:', text, re.I | re.M)
    if len(declarations) > 1 or len(declarations) != len(matches):
        raise InstallError('Entrada DBZK_Fix duplicada o no válida en mods.txt')
    if matches:
        return pattern.sub(lambda m: m[1] + '1' + m[3] + m[4], text)
    newline = '\r\n' if '\r\n' in text else '\n'
    return 'DBZK_Fix : 1' + newline + text


def enable_mods_json(text):
    entries = json.loads(text)
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise InstallError('mods.json no es una lista válida')
    found = [entry for entry in entries if str(entry.get('mod_name', '')).casefold() == 'dbzk_fix']
    if len(found) > 1:
        raise InstallError('DBZK_Fix duplicado en mods.json')
    if found:
        if found[0].get('mod_enabled') is True:
            return text
        found[0]['mod_enabled'] = True
    else:
        entries.append({'mod_name': 'DBZK_Fix', 'mod_enabled': True})
    return json.dumps(entries, indent=4, ensure_ascii=False) + '\n'


def safe_file(path, anchor):
    """Allow legitimate Steam-root links, not symlinked managed destinations."""
    if not anchor.is_absolute() or anchor.resolve() != anchor:
        raise InstallError('La carpeta de destino cambió o contiene enlaces: ' + str(anchor))
    path.relative_to(anchor)
    current = path
    while current != anchor:
        if current.is_symlink():
            raise InstallError('No se sobrescribirá un enlace simbólico: ' + str(current))
        if current.exists() and current != path and not current.is_dir():
            raise InstallError('Se esperaba una carpeta: ' + str(current))
        current = current.parent
    if path.exists() and not path.is_file():
        raise InstallError('Se esperaba un archivo: ' + str(path))


@dataclass
class Change:
    path: Path
    anchor: Path
    before: bytes | None
    after: bytes
    kind: str = 'file'
    old_option: str | None = None
    new_option: str | None = None
    mode: int = 0o644


@dataclass
class Plan:
    games: list
    configs: list
    changes: list
    roots: list

    def summary(self):
        lines = ['DBZK_Fix Linux ' + VERSION + ' — solo instalación', '']
        for game in self.games:
            lines.append(str(game.path))
            lines.append('  Ediciones: ' + ', '.join(name for name, _ in game.editions()))
        lines += ['', 'Perfiles locales de Steam: ' + str(len(self.configs)),
                  'Archivos que cambiarán: ' + str(len(self.changes)),
                  'Se conserva Config.ini y los ajustes existentes.',
                  'Se guardará una copia de seguridad antes de escribir.',
                  '', 'Steam se cerrará antes de instalar. Guarda y cierra los juegos.',
                  'Steam permanecerá cerrado al finalizar.']
        return '\n'.join(lines)


def payload_files(package):
    package = Path(package)
    try:
        manifest = json.loads((package / 'payload-manifest.json').read_text())
    except (OSError, ValueError) as exc:
        raise InstallError('Falta el payload verificado. Usa el paquete de la release o ejecuta scripts/build.py.') from exc
    if manifest.get('source_sha256') != SOURCE_HASH or manifest.get('payload_version') != '0.4.1':
        raise InstallError('La procedencia del payload no coincide con 0.4.1')
    if not isinstance(manifest.get('files'), dict) or not manifest['files']:
        raise InstallError('Manifiesto de payload incompleto')
    files = {}
    for relative, checksum in manifest['files'].items():
        if not isinstance(relative, str) or not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise InstallError('Entrada no válida en el manifiesto del payload')
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or relative.endswith('.log'):
            raise InstallError('Ruta no válida en payload-manifest.json')
        path = package / 'payload' / rel
        safe_file(path, package)
        data = path.read_bytes()
        if digest(data) != checksum:
            raise InstallError('Checksum incorrecto: ' + relative)
        files[relative] = data
    required = {'dwmapi.dll', 'ue4ss/UE4SS.dll', 'Config.ini', 'ue4ss/Mods/mods.txt',
                'ue4ss/Mods/mods.json', 'ue4ss/Mods/DBZK_Fix/Scripts/main.lua'}
    if not required.issubset(files):
        raise InstallError('Payload incompleto')
    return files


def make_plan(package, games):
    if not games:
        raise InstallError('No se ha encontrado DRAGON BALL Z: KAKAROT instalado.')
    roots = list({root.path: root for game in games for root in game.roots}.values())
    configs = profiles(roots)
    if not configs:
        raise InstallError('No hay perfiles locales de Steam. Inicia sesión en Steam una vez y vuelve a ejecutar el instalador.')
    payload = payload_files(package)
    changes = []
    for game in games:
        for _, target in game.editions():
            for relative, original in sorted(payload.items()):
                path = target / relative
                safe_file(path, target)
                before = path.read_bytes() if path.exists() else None
                data = original
                if relative == 'ue4ss/Mods/mods.txt':
                    data = enable_mods_txt((before if before is not None else data).decode('utf-8-sig')).encode('utf-8')
                elif relative == 'ue4ss/Mods/mods.json':
                    data = enable_mods_json((before if before is not None else data).decode('utf-8-sig')).encode('utf-8')
                elif before is not None and relative not in ('dwmapi.dll', 'ue4ss/UE4SS.dll',
                       'ue4ss/Mods/DBZK_Fix/Scripts/main.lua', 'ue4ss/Mods/DBZK_Fix/Scripts/inifile.lua'):
                    # Keep user configuration, helper mods and unrelated runtime data.
                    continue
                if before != data:
                    mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o644
                    changes.append(Change(path, target, before, data, mode=mode))
    for config in configs:
        anchor = next(root.path for root in roots if is_within(config, root.path))
        safe_file(config, anchor)
        before = config.read_bytes()
        doc = Document(before.decode('utf-8', errors='surrogateescape'))
        old = doc.get(APP_PATH)
        new = merge_launch_options(old)
        after = doc.set(APP_PATH, new).encode('utf-8', errors='surrogateescape') if old != new else before
        if before != after:
            changes.append(Change(config, anchor, before, after, 'steam', old, new,
                                  stat.S_IMODE(config.stat().st_mode)))
    return Plan(games, configs, changes, roots)


def own_processes(proc=Path('/proc')):
    result = []
    for path in proc.glob('[0-9]*'):
        try:
            if path.stat().st_uid != os.getuid():
                continue
            status = (path / 'stat').read_text()
            # Ignore zombies; they cannot write configuration.
            if status.rsplit(')', 1)[1].lstrip().startswith('Z'):
                continue
            comm = (path / 'comm').read_text().strip()
            args = (path / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            result.append((int(path.name), comm, args))
        except (OSError, IndexError):
            continue
    return result


class SteamSession:
    def __init__(self, roots, process_reader=own_processes, runner=subprocess.run,
                 which=shutil.which, clock=time.monotonic, sleep=time.sleep):
        self.roots = roots
        self.process_reader = process_reader
        self.runner = runner
        self.which = which
        self.clock = clock
        self.sleep = sleep

    def running(self):
        return [p for p in self.process_reader() if p[1] in ('steam', 'steam.sh', 'steamwebhelper')]

    def ensure_closed(self):
        if self.running():
            raise InstallError('Steam sigue abierto o se ha vuelto a abrir. No se escribirán archivos.')

    def close(self, timeout=60):
        for _, _, args in self.process_reader():
            if any(re.search(r'(?i)(?:^|[/\\])(?:AT(?:-Win64-Shipping)?|Kakarot)\.exe$', arg) for arg in args if arg):
                raise InstallError('Kakarot está en ejecución. Guarda y cierra el juego antes de instalar.')
        if not self.running():
            return
        commands = []
        for root in self.roots:
            kind = root.kind
            if kind == 'flatpak' and self.which('flatpak'):
                commands.append([self.which('flatpak'), 'run', 'com.valvesoftware.Steam', '-shutdown'])
            elif kind == 'snap' and self.which('snap'):
                commands.append([self.which('snap'), 'run', 'steam', '-shutdown'])
            else:
                steam = self.which('steam') or self.which('steam-native')
                if steam:
                    commands.append([steam, '-shutdown'])
                elif (root.path / 'steam.sh').is_file():
                    commands.append(['bash', str(root.path / 'steam.sh'), '-shutdown'])
        seen = set()
        for command in commands:
            key = tuple(command)
            if key in seen:
                continue
            seen.add(key)
            try:
                self.runner(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if not self.running():
                self.sleep(1)  # Let the final shutdown writes settle.
                self.ensure_closed()
                return
            self.sleep(0.5)
        raise InstallError('Steam no ha terminado de cerrar. Ciérralo desde Steam → Salir y vuelve a intentarlo. No se ha escrito ningún archivo.')


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.dbzk-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def state_directory(home=None, environ=None):
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    return Path(env.get('XDG_STATE_HOME') or home / '.local/state') / 'dbzk-fix-linux'


class InstallLock:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.handle = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / 'installer.lock'
        if path.is_symlink():
            raise InstallError('El bloqueo del instalador es un enlace simbólico')
        self.handle = path.open('a')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise InstallError('Ya hay otro instalador de DBZK_Fix abierto.') from exc
        return self

    def __exit__(self, *args):
        self.handle.close()


def apply_plan(plan, state, ensure_closed):
    ensure_closed()
    if not plan.changes:
        return None
    backup = Path(state) / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, mode=0o700)
    manifest = {'version': VERSION, 'status': 'prepared', 'entries': []}
    for index, change in enumerate(plan.changes):
        safe_file(change.path, change.anchor)
        current = change.path.read_bytes() if change.path.exists() else None
        if current != change.before:
            raise InstallError('Un archivo cambió durante la preparación: ' + str(change.path))
        name = str(index) + '.bin'
        if change.before is not None:
            atomic_write(backup / name, change.before, 0o600)
        manifest['entries'].append({'path': str(change.path), 'anchor': str(change.anchor),
            'backup': name if change.before is not None else None, 'kind': change.kind,
            'before_sha256': digest(change.before) if change.before is not None else None,
            'after_sha256': digest(change.after), 'mode': change.mode,
            'old_option': change.old_option, 'new_option': change.new_option})
    manifest_path = backup / 'manifest.json'
    atomic_write(manifest_path, json.dumps(manifest, indent=2).encode(), 0o600)
    applied = []
    try:
        for change in plan.changes:
            ensure_closed()
            safe_file(change.path, change.anchor)
            current = change.path.read_bytes() if change.path.exists() else None
            if current != change.before:
                raise InstallError('Cambio concurrente detectado: ' + str(change.path))
            atomic_write(change.path, change.after, change.mode)
            applied.append(change)
            if change.path.read_bytes() != change.after:
                raise InstallError('Fallo al verificar: ' + str(change.path))
        ensure_closed()
        manifest['status'] = 'installed'
        atomic_write(manifest_path, json.dumps(manifest, indent=2).encode(), 0o600)
    except BaseException as exc:
        # If Steam reappeared, do not race its writes during rollback.
        try:
            ensure_closed()
        except InstallError:
            manifest['status'] = 'recovery-required'
        else:
            manifest['status'] = 'rolled-back'
            for change in reversed(applied):
                try:
                    ensure_closed()
                    safe_file(change.path, change.anchor)
                    if change.path.read_bytes() != change.after:
                        raise InstallError('Cambio concurrente durante rollback')
                    if change.before is None:
                        change.path.unlink()
                    else:
                        atomic_write(change.path, change.before, change.mode)
                except (OSError, InstallError):
                    manifest['status'] = 'recovery-required'
        atomic_write(manifest_path, json.dumps(manifest, indent=2).encode(), 0o600)
        if manifest['status'] == 'recovery-required':
            atomic_write(Path(state) / 'last-backup', str(manifest_path).encode(), 0o600)
            raise InstallError('Se detuvo la instalación y se conservaron los backups. Cierra Steam y restaura con --restore.\nCopia: ' + str(manifest_path)) from exc
        raise
    atomic_write(Path(state) / 'last-backup', str(manifest_path).encode(), 0o600)
    return manifest_path


def restore_plan(manifest_path):
    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != VERSION or manifest.get('status') not in ('installed', 'recovery-required'):
        raise InstallError('La copia no corresponde a una instalación restaurable.')
    changes = []
    for entry in manifest['entries']:
        path, anchor = Path(entry['path']), Path(entry['anchor'])
        if not path.is_absolute() or not anchor.is_absolute():
            raise InstallError('Ruta no absoluta en la copia')
        safe_file(path, anchor)
        current = path.read_bytes() if path.exists() else None
        old = None
        if entry['backup'] is not None:
            name = entry['backup']
            if Path(name).name != name:
                raise InstallError('Ruta de backup no válida')
            old = (manifest_path.parent / name).read_bytes()
            if digest(old) != entry['before_sha256']:
                raise InstallError('Backup dañado: ' + name)
        if current == old:
            continue
        if entry['kind'] == 'steam':
            if current is None:
                raise InstallError('Ha desaparecido localconfig.vdf')
            doc = Document(current.decode('utf-8', errors='surrogateescape'))
            if doc.get(APP_PATH) != entry['new_option']:
                raise InstallError('Las opciones de lanzamiento cambiaron después de instalar; no se sobrescribirán.')
            restored = doc.set(APP_PATH, entry['old_option']) if entry['old_option'] is not None else doc.delete(APP_PATH)
            old = restored.encode('utf-8', errors='surrogateescape')
        elif current is None or digest(current) != entry['after_sha256']:
            raise InstallError('Archivo editado después de instalar; se conserva: ' + str(path))
        # None means remove only a newly installed, unchanged file.
        changes.append((path, anchor, current, old, entry['mode']))
    return manifest_path, manifest, changes


def apply_restore(prepared, ensure_closed):
    manifest_path, manifest, changes = prepared
    ensure_closed()
    applied = []
    try:
        for path, anchor, current, old, mode in changes:
            ensure_closed()
            safe_file(path, anchor)
            if (path.read_bytes() if path.exists() else None) != current:
                raise InstallError('Un archivo cambió durante la restauración: ' + str(path))
            if old is None:
                path.unlink()
            else:
                atomic_write(path, old, mode)
            applied.append((path, anchor, current, old, mode))
    except BaseException:
        ensure_closed()
        for path, anchor, current, old, mode in reversed(applied):
            safe_file(path, anchor)
            if (path.read_bytes() if path.exists() else None) == old:
                atomic_write(path, current, mode)
        raise
    manifest['status'] = 'restored'
    atomic_write(manifest_path, json.dumps(manifest, indent=2).encode(), 0o600)
