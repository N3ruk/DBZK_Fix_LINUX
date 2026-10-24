# Installer maintenance

- This update is installation-only. Do not change `Mods/`, `DefaultConfig.ini`, or the gameplay behavior.
- Package the original LINUX-V0.4.1 payload, pinned by SHA256 in `scripts/build.py`. Do not include old logs, saves, account data or machine paths.
- Runtime requires Python 3.8+ and no third-party Python packages, sudo, package-manager or system-service changes.
- Discover Steam via native/XDG, Flatpak, Snap and libraryfolders.vdf; app ID is 851850 for both base and Remastered.
- Steam must exit gracefully before any game/config write. Never kill Steam forcibly. `--check`/`--dry-run` must be read-only and never close Steam.
- Preserve unrelated Steam settings byte-for-byte and merge existing launch options/DLL overrides. Back up before writes; reject ambiguous VDF and concurrent changes. Never execute launch-option strings.
- Tests must use temporary homes, fake process runners and fake game binaries, not the real Steam or game.
- Verify with `python3 -m unittest discover -s tests -v`, `bash -n Instalar.sh`, `python3 scripts/build.py --archive <0.4.1.zip>`, and checksums/extracted package smoke tests.
- Document the distinction between installer simulations and actual game compatibility tests. Do not claim all Linux distributions or base gameplay were physically tested.
