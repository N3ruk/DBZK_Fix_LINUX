# DBZK_Fix_LINUX 0.4.2 — Easy Linux installer

**Installation-only update. The mod's gameplay code, DLLs, FPS/FOV/camera/graphics behavior and 0.4.1 compatibility limits are unchanged.**

## Download and install / Descargar e instalar

Download **DBZK-Fix-Linux-0.4.2.run** and run:

```bash
bash DBZK-Fix-Linux-0.4.2.run
```

Or extract **DBZK-Fix-Linux-0.4.2.zip** and run **Instalar.sh**. Use Desktop Mode on Steam Deck/SteamOS. Save and close games before accepting the installation.

## What's new / Novedades

- Detects native, Flatpak and Snap Steam plus libraries on other disks/SD cards.
- Finds Kakarot (AppID 851850), installs and enables DBZK_Fix in the **normal and Remastered editions that are actually installed**.
- **Closes Steam gracefully and waits before saving**, then re-reads its configuration to keep settings written during shutdown.
- Adds the required `WINEDLLOVERRIDES="dwmapi=n,b" %command%`, merging existing overrides, wrappers and arguments.
- Preserves existing mod configuration, other mods and unrelated Steam settings.
- Includes backups, recoverable installation, undo, integrity checks and read-only `--check`.
- Distribution-independent: Python 3.8+, no sudo, pip, protontricks or package-manager changes. Optional desktop dialogs with terminal fallback.
- Original 0.4.1 payload is pinned by SHA256; old runtime logs are not redistributed.

Spanish dialogs guide installation. Steam remains closed when it finishes; reopen it to play. No missing edition is created and no Proton version is forced.

Testing covers simulated Linux/Steam layouts and installer failure/recovery cases, not new gameplay validation across every distribution. The base/non-HD mod runtime remains not fully revalidated, as documented for 0.4.1.

See [installer documentation](https://github.com/N3ruk/DBZK_Fix_LINUX/blob/main/docs/INSTALLER.md) for manual paths, requirements and restoration. Download the .run or .zip **asset**, not GitHub's automatic source-code archive, for an offline installer containing the DLL payload.
