"""Optional desktop dialogs; a plain terminal needs only Python's stdlib."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .core import InstallError


class UI:
    def __init__(self, terminal=False, force_gui=False, yes=False):
        self.yes = yes
        self.backend = None
        if not terminal and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            self.backend = shutil.which('kdialog') or shutil.which('zenity')
        if force_gui and not self.backend:
            raise InstallError('No hay diálogos disponibles. Ejecuta bash Instalar.sh --terminal en una terminal.')

    @property
    def kde(self):
        return self.backend and Path(self.backend).name == 'kdialog'

    def dialog(self, args):
        return subprocess.run([self.backend] + args, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)

    def confirm(self, text):
        if self.yes:
            print(text, flush=True)
            return True
        if self.backend:
            if self.kde:
                return self.dialog(['--title', 'DBZK_Fix — Instalador Linux', '--yesno', text,
                    '--yes-label', 'Cerrar Steam e instalar', '--no-label', 'Cancelar']).returncode == 0
            return self.dialog(['--question', '--title=DBZK_Fix — Instalador Linux', '--no-markup',
                '--text=' + text, '--ok-label=Cerrar Steam e instalar', '--cancel-label=Cancelar',
                '--width=650']).returncode == 0
        print(text, flush=True)
        if not sys.stdin.isatty():
            raise InstallError('Se necesita una terminal para confirmar. Usa --yes para una instalación no interactiva.')
        return input('\n¿Continuar? [s/N]: ').strip().lower() in ('s', 'si', 'sí', 'y', 'yes')

    def info(self, text, error=False):
        print(text, file=sys.stderr if error else sys.stdout, flush=True)
        if self.backend:
            if self.kde:
                self.dialog(['--title', 'DBZK_Fix', '--error' if error else '--msgbox', text])
            else:
                self.dialog(['--error' if error else '--info', '--title=DBZK_Fix', '--no-markup',
                    '--text=' + text, '--width=650'])

    def folder(self, text):
        if self.yes:
            return None
        if self.backend:
            if self.kde:
                result = self.dialog(['--title', text, '--getexistingdirectory', str(Path.home())])
            else:
                result = self.dialog(['--file-selection', '--directory', '--title=' + text])
            return result.stdout.strip() if result.returncode == 0 else None
        if not sys.stdin.isatty():
            return None
        return input(text + '\nRuta (vacío para cancelar): ').strip() or None

    @contextmanager
    def progress(self, text):
        print(text, flush=True)
        process = None
        if self.backend:
            if self.kde:
                process = subprocess.Popen([self.backend, '--title', 'DBZK_Fix', '--passivepopup', text, '10'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process = subprocess.Popen([self.backend, '--progress', '--pulsate', '--no-cancel',
                    '--auto-close', '--title=DBZK_Fix', '--text=' + text, '--no-markup'],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            yield
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def launch_terminal(script, arguments):
    """Only used for a desktop double click without optional dialog programs."""
    command = [sys.executable, str(script), '--terminal'] + arguments
    for name, prefix in [('konsole', ['--separate', '-e']), ('gnome-terminal', ['--wait', '--']),
                         ('xfce4-terminal', ['--disable-server', '-x']), ('kitty', []), ('xterm', ['-e'])]:
        executable = shutil.which(name)
        if executable:
            subprocess.run([executable] + prefix + command, check=False)
            return True
    return False
