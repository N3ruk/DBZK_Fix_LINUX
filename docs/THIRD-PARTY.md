# Third-party components and provenance

## Original payload

Installer 0.4.2 packages the existing [LINUX-V0.4.1 release](https://github.com/N3ruk/DBZK_Fix_LINUX/releases/tag/LINUX-V0.4.1), asset `DRAGON.BALL.FPS.UNCAP.LINUX.zip`, without changing its Lua or DLL bytes. The only excluded upstream file is the old `ue4ss/UE4SS.log`. Activation lists are merged at installation time and are not gameplay changes.

- Source archive SHA256: `e102d42460386c3e5703dd0ed67bd3ddd7e5217e592b97bd86945088782bd9d4`.
- DBZK_Fix: MIT, Bryce Q. / KingKrouch and fork contributors. Original notice is in the repository and package `LICENSE`. Lua source is supplied in the payload.
- UE4SS, including `dwmapi.dll`, `UE4SS.dll`, helper Lua mods and auxiliary data: existing bundled release, reported by the original upstream log as **v3.0.1 Beta #0, Git SHA 1033902**. MIT notice is retained at `payload/ue4ss/LICENSE`. Sources: [UE4SS-RE/RE-UE4SS](https://github.com/UE4SS-RE/RE-UE4SS), [reported source revision](https://github.com/UE4SS-RE/RE-UE4SS/tree/1033902). This installer does not rebuild or upgrade those binaries.
- inifile 1.0: Copyright 2011–2015 Bart van Strien, 2-clause BSD-style license. The full notice and disclaimer are embedded in `payload/ue4ss/Mods/DBZK_Fix/Scripts/inifile.lua`. Source: [bartbes/inifile](https://github.com/bartbes/inifile).

The original project's runtime code also appears under `Mods/` for source review. Line endings of that repository's inifile.lua may differ from the original release; the installed copy comes from the pinned release, not a rewritten copy.

## Installer

The installer sources use the repository's MIT license. They depend only on Python's standard library. The system's optional kdialog/zenity, terminal emulator, Steam and Proton are **not redistributed**. Their names identify compatibility targets, not endorsement or a new license over those projects. No game binaries, saves, user accounts, tokens or screenshots are included.
