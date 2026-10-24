from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

from installer.core import (APP_ID, SOURCE_HASH, InstallError, InstallLock, SteamRoot,
    SteamSession, apply_plan, apply_restore, discover_games, enable_mods_json,
    enable_mods_txt, make_plan, merge_launch_options, payload_files, profiles,
    restore_plan, steam_roots)
from installer.vdf import APP_PATH, Document, VDFError, quote


class VDFTests(unittest.TestCase):
    def test_edit_preserves_every_unrelated_byte(self):
        text = '\ufeff// keep\r\n"A" { /* comment */ "b" "old"  "bigger" "a\\\\b" }\r\n'
        changed = Document(text).set(['a', 'B'], 'new "quoted"')
        self.assertEqual(changed, text.replace('"old"', quote('new "quoted"')))
        self.assertEqual(Document(changed).get(['A', 'b']), 'new "quoted"')

    def test_missing_branch_roundtrip(self):
        for text in ('', '"UserLocalConfigStore" {}', '"UserLocalConfigStore"\r\n{\r\n}\r\n'):
            with self.subTest(text=text):
                changed = Document(text).set(APP_PATH, 'x %command%')
                self.assertEqual(Document(changed).get(APP_PATH), 'x %command%')
                self.assertIsNone(Document(Document(changed).delete(APP_PATH)).get(APP_PATH))

    def test_case_insensitive_and_duplicate_target_rejected(self):
        self.assertEqual(Document('"Software" { "valve" "ok" }').get(['software', 'VALVE']), 'ok')
        with self.assertRaises(VDFError):
            Document('"A" { "b" "1" "B" "2" }').set(['A', 'b'], '3')

    def test_malformed_syntax_rejected(self):
        for text in ('"A" {', '"A"', '"A" "unterminated', '}', '/* unclosed', '"A" "B" [LINUX]'):
            with self.subTest(text=text), self.assertRaises(VDFError):
                Document(text)

    def test_unknown_escapes_remain_literal(self):
        self.assertEqual(Document('"Path" "C:\\Games"').get(['Path']), 'C:\\Games')


class LaunchTests(unittest.TestCase):
    def test_empty_options(self):
        self.assertEqual(merge_launch_options(None), 'WINEDLLOVERRIDES="dwmapi=n,b" %command%')

    def test_existing_wrappers_and_arguments_preserved(self):
        old = 'MANGOHUD=1 gamemoderun gamescope -W 1920 -- %command% -windowed'
        new = merge_launch_options(old)
        self.assertTrue(new.endswith(old))
        self.assertEqual(merge_launch_options(new), new)

    def test_game_arguments_without_marker(self):
        old = '-windowed -foo="two words"'
        self.assertTrue(merge_launch_options(old).endswith('%command% ' + old))

    def test_merge_unrelated_and_shared_dll_overrides(self):
        old = 'env WINEDLLOVERRIDES="dwmapi,dxgi=b;dinput8=n,b" gamemoderun %command% -x'
        new = merge_launch_options(old)
        self.assertIn('dxgi=b;dinput8=n,b;dwmapi=n,b', new)
        self.assertTrue(new.endswith(' gamemoderun %command% -x'))
        self.assertEqual(merge_launch_options(new), new)

    def test_already_enabled_keeps_original_quotes(self):
        for value in ('WINEDLLOVERRIDES="dwmapi=n,b" %command%', "WINEDLLOVERRIDES='dxgi=n;dwmapi=n,b' %command%"):
            self.assertEqual(merge_launch_options(value), value)

    def test_ambiguous_or_executable_shell_not_changed(self):
        values = ['echo hi; %command%', '%command% && echo hi', '%command%\necho hi',
                  'WINEDLLOVERRIDES="$VALUE" %command%', '%command% WINEDLLOVERRIDES=x=y',
                  'WINEDLLOVERRIDES=a=b WINEDLLOVERRIDES=c=d %command%',
                  '"%command% -foo"', '%command% %command%', '%command% # comment', '"unclosed']
        for value in values:
            with self.subTest(value=value), self.assertRaises(InstallError):
                merge_launch_options(value)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='dbzk-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / 'Home with spaces'
        self.home.mkdir()
        self.root = self.home / '.local/share/Steam'
        self.steam = SteamRoot(self.root, 'native')
        self.game = self.root / 'steamapps/common/DRAGON BALL Z KAKAROT'
        self.package = self.base / 'package'
        self.state = self.base / 'state'
        self.config = self.root / 'userdata/123/config/localconfig.vdf'
        self.write(self.root / 'steamapps/appmanifest_851850.acf',
                   '"AppState" { "appid" "851850" "installdir" "DRAGON BALL Z KAKAROT" }')
        self.write(self.config, '"UserLocalConfigStore" { "Other" "keep" } // intact\n')
        for relative in ('AT/Binaries/Win64', 'dlc/Remaster/AT/Binaries/Win64'):
            self.write(self.game / relative / 'AT-Win64-Shipping.exe', b'FAKE-TEST-EXE')
        self.files = {'dwmapi.dll': b'FAKE-TEST-LOADER', 'ue4ss/UE4SS.dll': b'FAKE-TEST-UE4SS',
            'Config.ini': b'[Framerate]\nMaxFPS=180\n', 'ue4ss/UE4SS-settings.ini': b'[Settings]\n',
            'ue4ss/Mods/mods.txt': b'OtherMod : 1\nDBZK_Fix : 0\n',
            'ue4ss/Mods/mods.json': b'[{"mod_name":"OtherMod","mod_enabled":true}]',
            'ue4ss/Mods/DBZK_Fix/Scripts/main.lua': b'-- UNCHANGED TEST MOD',
            'ue4ss/Mods/DBZK_Fix/Scripts/inifile.lua': b'-- test library'}
        for relative, data in self.files.items():
            self.write(self.package / 'payload' / relative, data)
        self.write(self.package / 'payload-manifest.json', json.dumps({'payload_version': '0.4.1',
            'source_sha256': SOURCE_HASH, 'files': {n: hashlib.sha256(d).hexdigest() for n, d in self.files.items()}}))

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)

    def plan(self):
        return make_plan(self.package, discover_games([self.steam]))


class DiscoveryTests(Fixture):
    def test_native_and_symlink_deduplication(self):
        alias = self.home / '.steam/steam'
        alias.parent.mkdir()
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(steam_roots(self.home, {}), [self.steam])
        self.assertEqual([n for n, _ in discover_games([self.steam])[0].editions()], ['Normal', 'Remastered'])

    def test_flatpak_snap_and_xdg_roots(self):
        for relative in ('.var/app/com.valvesoftware.Steam/.local/share/Steam', 'snap/steam/common/.local/share/Steam'):
            (self.home / relative / 'steamapps').mkdir(parents=True)
        xdg = self.home / 'custom data'
        (xdg / 'Steam/steamapps').mkdir(parents=True)
        roots = steam_roots(self.home, {'XDG_DATA_HOME': str(xdg)})
        self.assertEqual({r.kind for r in roots}, {'native', 'flatpak', 'snap'})
        self.assertIn(xdg / 'Steam', [r.path for r in roots])

    def test_external_library_modern_and_legacy_formats(self):
        library = self.base / 'External drive with spaces'
        moved = library / 'steamapps/common/Renamed Game'
        moved.parent.mkdir(parents=True)
        self.game.rename(moved)
        self.write(library / 'steamapps/appmanifest_851850.acf', '"AppState" { "appid" "851850" "installdir" "Renamed Game" }')
        for value in (quote(str(library)), '{ "path" ' + quote(str(library)) + ' "apps" { "851850" "1" } }'):
            self.write(self.root / 'steamapps/libraryfolders.vdf', '"libraryfolders" { "1" ' + value + ' }')
            self.assertEqual(discover_games([self.steam])[0].path, moved)

    def test_single_edition(self):
        (self.game / 'AT/Binaries/Win64/AT-Win64-Shipping.exe').unlink()
        games = discover_games([self.steam])
        self.assertEqual([n for n, _ in games[0].editions()], ['Remastered'])

    def test_wrong_appid_and_traversal_rejected(self):
        manifest = self.root / 'steamapps/appmanifest_851850.acf'
        for text in ('"AppState" { "appid" "123" }', '"AppState" { "appid" "851850" "installdir" "../../escape" }'):
            self.write(manifest, text)
            with self.assertRaises(InstallError):
                discover_games([self.steam])

    def test_all_real_profiles_and_no_anonymous(self):
        for account in ('456', '0', 'not-an-account'):
            self.write(self.root / 'userdata' / account / 'config/localconfig.vdf', self.config.read_bytes())
        self.assertEqual(len(profiles([self.steam])), 2)


class InstallationTests(Fixture):
    def test_installs_both_editions_and_is_idempotent(self):
        original_config = self.config.read_bytes()
        closed_calls = []
        manifest = apply_plan(self.plan(), self.state, lambda: closed_calls.append(True))
        self.assertGreater(len(closed_calls), 2)
        for _, target in discover_games([self.steam])[0].editions():
            self.assertEqual((target / 'dwmapi.dll').read_bytes(), self.files['dwmapi.dll'])
            self.assertEqual((target / 'ue4ss/Mods/DBZK_Fix/Scripts/main.lua').read_bytes(), self.files['ue4ss/Mods/DBZK_Fix/Scripts/main.lua'])
            self.assertIn('DBZK_Fix : 1', (target / 'ue4ss/Mods/mods.txt').read_text())
            self.assertTrue(next(e for e in json.loads((target / 'ue4ss/Mods/mods.json').read_text()) if e['mod_name'] == 'DBZK_Fix')['mod_enabled'])
        self.assertEqual(Document(self.config.read_text()).get(['UserLocalConfigStore', 'Other']), 'keep')
        self.assertTrue(self.config.read_text().endswith('// intact\n'))
        self.assertEqual(Document(self.config.read_text()).get(APP_PATH), 'WINEDLLOVERRIDES="dwmapi=n,b" %command%')
        self.assertEqual(self.plan().changes, [])
        self.assertTrue(any((manifest.parent / e['backup']).read_bytes() == original_config
                            for e in json.loads(manifest.read_text())['entries'] if e['backup']))

    def test_preserves_user_configuration_and_other_mods(self):
        target = self.game / 'AT/Binaries/Win64'
        self.write(target / 'Config.ini', '[Framerate]\nMaxFPS=90\n')
        self.write(target / 'ue4ss/UE4SS-settings.ini', 'User=custom\n')
        self.write(target / 'ue4ss/Mods/MyMod/Scripts/main.lua', 'custom mod')
        self.write(target / 'ue4ss/Mods/mods.txt', '; keep\nMyMod : 1\nDBZK_Fix : 0\nKeybinds : 1\n')
        apply_plan(self.plan(), self.state, lambda: None)
        self.assertIn('MaxFPS=90', (target / 'Config.ini').read_text())
        self.assertEqual((target / 'ue4ss/UE4SS-settings.ini').read_text(), 'User=custom\n')
        self.assertEqual((target / 'ue4ss/Mods/MyMod/Scripts/main.lua').read_text(), 'custom mod')
        self.assertEqual((target / 'ue4ss/Mods/mods.txt').read_text(), '; keep\nMyMod : 1\nDBZK_Fix : 1\nKeybinds : 1\n')

    def test_no_target_write_while_steam_running(self):
        before = self.config.read_bytes()
        def reject():
            raise InstallError('Steam sigue abierto')
        with self.assertRaises(InstallError):
            apply_plan(self.plan(), self.state, reject)
        self.assertEqual(before, self.config.read_bytes())
        self.assertFalse((self.game / 'AT/Binaries/Win64/dwmapi.dll').exists())
        self.assertFalse(self.state.exists())

    def test_concurrent_config_change_not_overwritten(self):
        plan = self.plan()
        current = self.config.read_bytes() + b'// changed by Steam\n'
        self.config.write_bytes(current)
        with self.assertRaises(InstallError):
            apply_plan(plan, self.state, lambda: None)
        self.assertEqual(self.config.read_bytes(), current)
        self.assertFalse((self.game / 'AT/Binaries/Win64/dwmapi.dll').exists())

    def test_replan_after_shutdown_keeps_last_saved_settings(self):
        self.plan()
        self.write(self.config, Document(self.config.read_text()).set(APP_PATH, 'gamemoderun %command% -windowed'))
        apply_plan(self.plan(), self.state, lambda: None)
        self.assertTrue(Document(self.config.read_text()).get(APP_PATH).endswith('gamemoderun %command% -windowed'))

    def test_symlinked_destination_rejected(self):
        target = self.game / 'AT/Binaries/Win64'
        other = self.base / 'outside.dll'
        self.write(other, b'keep')
        (target / 'dwmapi.dll').symlink_to(other)
        with self.assertRaises(InstallError):
            self.plan()
        self.assertEqual(other.read_bytes(), b'keep')

    def test_corrupt_or_traversal_payload_rejected(self):
        self.write(self.package / 'payload/dwmapi.dll', b'corrupt')
        with self.assertRaises(InstallError):
            payload_files(self.package)
        self.write(self.package / 'payload-manifest.json', json.dumps({'source_sha256': SOURCE_HASH,
            'payload_version': '0.4.1', 'files': {'../escape': 'x'}}))
        with self.assertRaises(InstallError):
            payload_files(self.package)

    def test_partial_failure_rolls_back_targets(self):
        from installer import core
        original = self.config.read_bytes()
        real_write = core.atomic_write
        failure = [False]
        def failing(path, data, mode=0o644):
            if path.name == 'dwmapi.dll' and not failure[0]:
                failure[0] = True
                raise OSError('simulated disk error')
            return real_write(path, data, mode)
        with patch('installer.core.atomic_write', side_effect=failing), self.assertRaises(OSError):
            apply_plan(self.plan(), self.state, lambda: None)
        self.assertEqual(self.config.read_bytes(), original)
        for relative in self.files:
            self.assertFalse((self.game / 'AT/Binaries/Win64' / relative).exists())
        manifests = list((self.state / 'backups').glob('*/manifest.json'))
        self.assertEqual(json.loads(manifests[0].read_text())['status'], 'rolled-back')

    def test_reopened_steam_preserves_recoverable_backup(self):
        counter = [0]
        def guard():
            counter[0] += 1
            if counter[0] > 2:
                raise InstallError('Steam reopened')
        with self.assertRaisesRegex(InstallError, 'Copia:'):
            apply_plan(self.plan(), self.state, guard)
        manifest = Path((self.state / 'last-backup').read_text())
        self.assertEqual(json.loads(manifest.read_text())['status'], 'recovery-required')
        apply_restore(restore_plan(manifest), lambda: None)
        self.assertEqual(json.loads(manifest.read_text())['status'], 'restored')
        self.assertFalse((self.game / 'AT/Binaries/Win64/Config.ini').exists())

    def test_restore_preserves_new_unrelated_steam_settings(self):
        self.write(self.config, Document(self.config.read_text()).set(APP_PATH, '-windowed'))
        manifest = apply_plan(self.plan(), self.state, lambda: None)
        self.config.write_bytes(self.config.read_bytes() + b'// NEW STEAM SETTING\n')
        prepared = restore_plan(manifest)
        apply_restore(prepared, lambda: None)
        self.assertEqual(Document(self.config.read_text()).get(APP_PATH), '-windowed')
        self.assertTrue(self.config.read_text().endswith('// NEW STEAM SETTING\n'))
        self.assertFalse((self.game / 'AT/Binaries/Win64/dwmapi.dll').exists())
        self.assertEqual(json.loads(manifest.read_text())['status'], 'restored')

    def test_restore_refuses_user_edits(self):
        manifest = apply_plan(self.plan(), self.state, lambda: None)
        target = self.game / 'AT/Binaries/Win64/Config.ini'
        target.write_bytes(b'User changed config')
        with self.assertRaises(InstallError):
            restore_plan(manifest)
        self.assertEqual(target.read_bytes(), b'User changed config')

    def test_exclusive_installer_lock(self):
        with InstallLock(self.state):
            with self.assertRaises(InstallError):
                with InstallLock(self.state):
                    self.fail('second lock was acquired')


class ActivationTests(unittest.TestCase):
    def test_original_windows_line_endings(self):
        text = 'OtherMod : 1\r\nDBZK_Fix : 0\r\n\r\n; keybinds\r\nKeybinds : 1\r\n'
        expected = text.replace('DBZK_Fix : 0', 'DBZK_Fix : 1')
        self.assertEqual(enable_mods_txt(text), expected)
        self.assertEqual(enable_mods_txt(expected), expected)

    def test_mod_lists_merge_without_disabling_others(self):
        self.assertEqual(enable_mods_txt('; comment\r\nOtherMod : 1\r\n'), 'DBZK_Fix : 1\r\n; comment\r\nOtherMod : 1\r\n')
        entries = json.loads(enable_mods_json('[{"mod_name":"DBZK_Fix","mod_enabled":false,"custom":1},{"mod_name":"OtherMod","mod_enabled":true}]'))
        self.assertEqual(entries[0], {'mod_name': 'DBZK_Fix', 'mod_enabled': True, 'custom': 1})
        self.assertTrue(entries[1]['mod_enabled'])

    def test_invalid_lists_rejected(self):
        for text in ('DBZK_Fix : 1\nDBZK_Fix : 0', 'DBZK_Fix : false'):
            with self.assertRaises(InstallError):
                enable_mods_txt(text)
        with self.assertRaises(InstallError):
            enable_mods_json('{}')


class ShutdownTests(unittest.TestCase):
    def test_native_graceful_exit_waits_for_helpers(self):
        processes = [(1, 'steam', []), (2, 'steamwebhelper', [])]
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            processes[:] = [(2, 'steamwebhelper', [])]
        def sleep(seconds):
            processes.clear()
        session = SteamSession([SteamRoot(Path('/test/steam'), 'native')], lambda: list(processes),
            run, lambda name: '/bin/steam' if name == 'steam' else None, sleep=sleep)
        session.close()
        self.assertEqual(calls, [['/bin/steam', '-shutdown']])
        session.ensure_closed()

    def test_flatpak_and_snap_shutdown(self):
        for kind, expected in [('flatpak', ['flatpak', 'run', 'com.valvesoftware.Steam', '-shutdown']),
                               ('snap', ['snap', 'run', 'steam', '-shutdown'])]:
            processes = [(1, 'steam', [])]
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                processes.clear()
            session = SteamSession([SteamRoot(Path('/test/steam'), kind)], lambda: list(processes),
                run, lambda name: name, sleep=lambda _: None)
            session.close()
            self.assertEqual(calls, [expected])

    def test_timeout_does_not_force_kill(self):
        calls = []
        session = SteamSession([SteamRoot(Path('/test/steam'), 'native')],
            lambda: [(1, 'steam', [])], lambda command, **kwargs: calls.append(command),
            lambda name: name, sleep=lambda _: None)
        with self.assertRaises(InstallError):
            session.close(timeout=0)
        self.assertEqual(calls, [['steam', '-shutdown']])

    def test_running_game_blocks_shutdown(self):
        calls = []
        session = SteamSession([], lambda: [(1, 'steam', []), (2, 'wine', ['Z:\\game\\AT-Win64-Shipping.exe'])],
            lambda *args, **kwargs: calls.append(args))
        with self.assertRaises(InstallError):
            session.close()
        self.assertEqual(calls, [])


class CLITests(Fixture):
    def test_check_never_closes_steam_or_writes(self):
        import install
        env = {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / '.local/share'),
               'XDG_STATE_HOME': str(self.state), 'XDG_CURRENT_DESKTOP': 'KDE'}
        original = self.config.read_bytes()
        with patch.dict(os.environ, env), patch.object(install, '__file__', str(self.package / 'install.py')), \
             patch('install.SteamSession') as session, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(['--check']), 0)
            session.assert_not_called()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(self.state.exists())

    def test_full_cli_reloads_configuration_after_shutdown(self):
        import install
        env = {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / '.local/share'),
               'XDG_STATE_HOME': str(self.state), 'XDG_CURRENT_DESKTOP': 'KDE',
               'XDG_SESSION_DESKTOP': 'KDE', 'DESKTOP_SESSION': 'plasma'}
        def close():
            self.write(self.config, Document(self.config.read_text()).set(APP_PATH, 'gamemoderun %command% -latest'))
        with patch.dict(os.environ, env), patch.object(install, '__file__', str(self.package / 'install.py')), \
             patch('install.SteamSession') as session, patch('install.os.geteuid', return_value=1000), \
             contextlib.redirect_stdout(io.StringIO()):
            session.return_value.close.side_effect = close
            self.assertEqual(install.main(['--terminal', '--yes']), 0)
            session.return_value.close.assert_called_once()
            self.assertTrue(Document(self.config.read_text()).get(APP_PATH).endswith('gamemoderun %command% -latest'))
            self.assertTrue((self.game / 'dlc/Remaster/AT/Binaries/Win64/dwmapi.dll').is_file())

    def test_gaming_session_blocked_before_shutdown(self):
        import install
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'gamescope'}), patch('install.SteamSession') as session, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(['--terminal', '--yes']), 1)
            session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
