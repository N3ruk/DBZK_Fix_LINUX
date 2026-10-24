# Linux installer 0.4.2 / Instalador Linux 0.4.2

## English quick start

1. Switch to **Desktop Mode** on SteamOS/Steam Deck or another Gamescope session. Save and close your games.
2. Download **DBZK-Fix-Linux-0.4.2.run** from Releases.
3. Run it, or open a terminal in Downloads and use:

   ```bash
   bash DBZK-Fix-Linux-0.4.2.run
   ```

4. Review detected installations/editions and accept. Steam exits gracefully before files or launch options are changed.
5. Wait for completion, then reopen Steam and launch either edition normally.

Alternatively extract **DBZK-Fix-Linux-0.4.2.zip** and run `Instalar.sh` (or `bash Instalar.sh`). The .run and ZIP contain the same offline installer/payload. Do not extract either into the game directory yourself.

The installer dialogs are in Spanish; a terminal fallback is included. It requires **Linux, Python 3.8+, a local Steam account and the installed Windows game running through Proton**. KDE's kdialog or GNOME's zenity are optional, not mandatory. No sudo, pip, protontricks or package-manager changes are required. Python and Steam/Proton must already be installed.

## Español: instalación sencilla

1. En Steam Deck/SteamOS utiliza **modo Escritorio**. Guarda las partidas y cierra los juegos.
2. Descarga **DBZK-Fix-Linux-0.4.2.run** y ejecútalo. Si tu escritorio no abre scripts, abre una terminal en Descargas y ejecuta `bash DBZK-Fix-Linux-0.4.2.run`.
3. Revisa la ubicación y las ediciones detectadas. Acepta **Cerrar Steam e instalar**.
4. Espera la confirmación. Abre Steam de nuevo y juega a cualquiera de las ediciones instaladas.

También puedes extraer el ZIP y ejecutar **Instalar.sh**. No copies manualmente el paquete entero dentro del juego.

## What is automated / Qué se configura

- Finds Steam through XDG/native paths, `~/.steam` aliases, Flatpak (`com.valvesoftware.Steam`) and Snap (`steam`). Reads both modern and legacy `libraryfolders.vdf`; additional disks, SD cards and directories with spaces are supported.
- Finds **Steam AppID 851850**, not a hardcoded account name or drive. Base and Remastered share this Steam app and its launch options.
- Installs in every detected, present executable directory:

  ```text
  AT/Binaries/Win64/
  dlc/Remaster/AT/Binaries/Win64/
  ```

- Does not create a missing edition. With two installed editions, both receive the original loader, UE4SS and DBZK_Fix.
- Enables `DBZK_Fix` in UE4SS mod lists, retaining other entries. Existing `Config.ini`, UE4SS settings, helper mods and unrelated mod files are preserved. Existing loader DLLs and DBZK_Fix scripts are backed up before replacement.
- Sets only this game's launch options in **all existing local Steam profiles** associated with the detected installations. It never creates invented Steam accounts or edits another game's settings. The plan shows the profile count.
- For empty launch options the result is:

  ```text
  WINEDLLOVERRIDES="dwmapi=n,b" %command%
  ```

- Merges other DLL overrides rather than dropping them. Preserves wrappers (e.g. MangoHud/Gamemode/Gamescope) and game arguments. Ambiguous shell scripts, dynamic expansions, multiple `%command%` placeholders or malformed VDF are rejected with an error instead of guessed.
- Requests `steam -shutdown`, `flatpak run com.valvesoftware.Steam -shutdown` or `snap run steam -shutdown` as applicable, waits for Steam and its web helpers to exit, **re-reads the saved configuration**, then applies changes. It never force-kills Steam. If Steam stays open, no game/config writes occur. It remains closed after installation.
- A running Kakarot game blocks installation. A Gamescope desktop blocks real installation because exiting Steam there could end the session. Run in Desktop Mode instead.
- Copies the original **0.4.1 gameplay payload byte-for-byte**; only packaging, activation lists and installation logic change. The old execution log is excluded. The existing FPS/FOV/camera/graphics defaults are not adjusted by this update.

UE4SS's DLL override is supported by its [official installation documentation](https://docs.ue4ss.com/dev/installation-guide.html) and [maintainer discussion of Proton loading](https://github.com/UE4SS-RE/RE-UE4SS/issues/1189). This installer does not force a Proton version or install Windows redistributables.

## Read-only check / Comprobación sin instalar

```bash
bash DBZK-Fix-Linux-0.4.2.run --check
# Or, from an extracted ZIP:
bash Instalar.sh --check
python3 install.py --detect
```

`--check` and `--dry-run` neither close Steam nor alter Steam/game files. A .run must unpack its own contents into a temporary directory to run the check; that extraction is not a game installation.

## Manual paths / Rutas manuales

If automatic detection fails, the graphical installer offers a folder picker. Select the **game root**, not Win64. The terminal equivalents are:

```bash
bash Instalar.sh --terminal --game-dir "/mnt/Games/steamapps/common/DRAGON BALL Z KAKAROT"
bash Instalar.sh --terminal --steam-root "/path/to/Steam"
```

`--steam-root` can be repeated. A real `userdata/<account>/config/localconfig.vdf` must exist. If none exists, sign into Steam once, close it and retry. For unattended installs, `--yes` explicitly accepts closing Steam; it does not bypass any safety or integrity checks.

## Backups and undo / Copias y restauración

Backups live under `$XDG_STATE_HOME/dbzk-fix-linux`, or `~/.local/state/dbzk-fix-linux`. The installer displays the exact manifest path on success. Backups are never included in downloadable packages or removed automatically. Installation is locked against concurrent installer runs and file contents are rechecked before replacing them.

```bash
# Restore latest installation (closes Steam first):
bash Instalar.sh --restore
# Choose an older backup explicitly:
bash Instalar.sh --restore "/path/to/backup/manifest.json"
# Validate undo without closing Steam or writing:
bash Instalar.sh --restore --check
```

Undo restores overwritten files and removes only newly created files that still match the installed bytes. It refuses to overwrite a mod file edited afterward. For Steam, it restores **only Kakarot's launch-option value**, preserving unrelated settings saved since installation. If the launch options themselves changed, it refuses to overwrite them. Empty directories may remain after undo; no unrelated mod directories are deleted.

On a normal write failure, already written files are rolled back. If Steam reappears or files change concurrently, the backup is retained and recovery is required rather than racing another process's writes. In that case close Steam, inspect the retained manifest and use `--restore <manifest>`; no guarantee is made against an application being relaunched by an external program during installation.

## Compatibility and verification limits

The installer is distribution-independent and makes no assumptions about apt, rpm, pacman, systemd, mutable root filesystems or SteamOS hardware. Native Steam, Flatpak/Snap layouts, separate libraries, both editions, backups and option merging are covered by **temporary-directory simulations**. The real development host was checked using read-only detection only. This update does **not** claim that every distribution or either game edition has been gameplay-tested anew. Existing 0.4.1 compatibility limits, including the previously unvalidated base edition, still apply. This is not an ARM port of the game.

## Build and verify (maintainers)

```bash
python3 -m unittest discover -s tests -v
bash -n Instalar.sh
python3 scripts/build.py --archive "/path/to/DRAGON.BALL.FPS.UNCAP.LINUX.zip"
# If omitted, the original pinned archive is downloaded from GitHub.
cd dist
sha256sum -c SHA256SUMS
```

The upstream archive must match SHA256 `e102d42460386c3e5703dd0ed67bd3ddd7e5217e592b97bd86945088782bd9d4`. Builds use fixed archive metadata and a positive source-file list. Repeat a build with the same Python/zlib toolchain to compare hashes. `.run --extract NEW_DIRECTORY` inspects the complete contents without installing; it refuses an already existing destination.

Before a release: run all tests; build; extract both packages; verify their internal SHA256SUMS; smoke-test `--check` with temporary Steam/game trees; confirm DLL/Lua bytes match 0.4.1 and that no logs or account data are included. Do not close a real user's Steam as a packaging test.

### Existing-solutions preflight

The project was already a mod fork; this adds an installer, not a replacement mod. Generic bulk launch-option tools do not also detect both Kakarot executable directories or package the fixed UE4SS payload. ValvePython/vdf was considered; a small position-preserving editor is used instead of serializing the whole localconfig tree, so unrelated comments, casing, duplicate non-target keys and bytes remain untouched. Runtime uses only Python's standard library; users do not need to install Python packages or download a mod manager.
