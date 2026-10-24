#!/usr/bin/env python3
"""DBZK_Fix Linux: install both detected editions without changing gameplay."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from installer import VERSION
from installer.core import (InstallError, InstallLock, SteamSession, apply_plan,
    apply_restore, discover_games, make_plan, restore_plan, state_directory, steam_roots)
from installer.vdf import VDFError
from installer.ui import UI, launch_terminal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--terminal', action='store_true', help='Usar terminal, sin diálogos')
    parser.add_argument('--gui', action='store_true', help='Exigir kdialog o zenity')
    parser.add_argument('--yes', action='store_true', help='Aceptar el cierre de Steam y la instalación')
    parser.add_argument('--steam-root', action='append', default=[], help='Ruta de Steam adicional')
    parser.add_argument('--game-dir', help='Carpeta raíz del juego (detección manual)')
    parser.add_argument('--check', '--dry-run', dest='check', action='store_true',
                        help='Mostrar el plan sin cerrar Steam ni escribir nada')
    parser.add_argument('--detect', action='store_true', help='Solo mostrar detección, sin necesitar payload')
    parser.add_argument('--restore', nargs='?', const='last', metavar='MANIFEST',
                        help='Restaurar la última instalación o una copia concreta')
    args = parser.parse_args(argv)
    ui = None
    try:
        ui = UI(args.terminal or args.check or args.detect, args.gui, args.yes)
        if not args.terminal and not args.check and not args.detect and not args.yes and not ui.backend and not sys.stdin.isatty():
            if launch_terminal(Path(__file__), list(sys.argv[1:] if argv is None else argv)):
                return 0
            raise InstallError('Abre una terminal en esta carpeta y ejecuta bash Instalar.sh --terminal.')
        if sys.platform != 'linux':
            raise InstallError('Este instalador es para Linux. El mod original no se ha cambiado.')
        desktop = ' '.join(os.environ.get(key, '') for key in ('XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP', 'DESKTOP_SESSION')).lower()
        if 'gamescope' in desktop and not args.check and not args.detect:
            raise InstallError('Ejecuta el instalador en modo Escritorio. En Gaming Mode, cerrar Steam puede cerrar también el instalador.')
        if os.geteuid() == 0 and not args.check and not args.detect:
            raise InstallError('Ejecuta el instalador con tu usuario normal, sin sudo.')
        state = state_directory()
        roots = steam_roots(extra=args.steam_root)
        if args.restore:
            manifest = (state / 'last-backup').read_text().strip() if args.restore == 'last' else args.restore
            if args.check:
                prepared = restore_plan(manifest)
                print('Restauración preparada; archivos: ' + str(len(prepared[2])))
                return 0
            if not ui.confirm('Restaurar los archivos y las opciones de lanzamiento anteriores.\n\nSteam se cerrará antes. Guarda y cierra los juegos.\nCopia: ' + str(manifest)):
                return 0
            with InstallLock(state):
                session = SteamSession(roots)
                with ui.progress('Cerrando Steam y preparando restauración…'):
                    session.close()
                    prepared = restore_plan(manifest)
                    apply_restore(prepared, session.ensure_closed)
            ui.info('Restauración completada. Puedes abrir Steam de nuevo.')
            return 0
        if not roots and not args.check and not args.detect:
            folder = ui.folder('No se detectó Steam. Selecciona su carpeta (contiene steamapps y userdata)')
            if folder:
                roots = steam_roots(extra=args.steam_root + [folder])
        games = discover_games(roots, args.game_dir)
        if args.detect:
            print(json.dumps({'steam': [{'path': str(r.path), 'type': r.kind} for r in roots],
                'games': [{'path': str(g.path), 'editions': [n for n, _ in g.editions()]} for g in games]}, indent=2))
            return 0
        if not games and not args.check:
            folder = ui.folder('Selecciona la carpeta raíz de DRAGON BALL Z KAKAROT')
            if folder:
                games = discover_games(roots, folder)
        plan = make_plan(Path(__file__).resolve().parent, games)
        if args.check:
            print(plan.summary())
            print('\nSolo comprobación: Steam y todos los archivos permanecen sin cambios.')
            return 0
        if not ui.confirm(plan.summary()):
            return 0
        with InstallLock(state):
            session = SteamSession(plan.roots)
            with ui.progress('Cerrando Steam de forma segura. Esperando a que guarde sus ajustes…'):
                session.close()
                # Steam writes localconfig on exit: re-read only AFTER it stops.
                plan = make_plan(Path(__file__).resolve().parent, games)
                backup = apply_plan(plan, state, session.ensure_closed)
        if backup:
            ui.info('Instalación completada para las ediciones detectadas.\n'
                    'Mod activado y opciones de Steam guardadas.\n'
                    'Puedes abrir Steam y jugar.\n\nCopia de seguridad:\n' + str(backup))
        else:
            ui.info('El mod ya está instalado y activado. No fue necesario cambiar archivos. Puedes abrir Steam.')
        return 0
    except (InstallError, VDFError, OSError, ValueError) as exc:
        message = 'No se completó la operación:\n' + str(exc)
        if ui:
            ui.info(message, error=True)
        else:
            print(message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nOperación cancelada.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
