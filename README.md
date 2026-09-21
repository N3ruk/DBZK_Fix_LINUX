# DBZK_Fix for Linux / Steam Deck — Dragon Ball Z: Kakarot FPS & Ultrawide Fix

**DBZK_Fix** is a maintained **Dragon Ball Z: Kakarot mod/fix** focused on **Linux, Proton and Steam Deck** compatibility while preserving the original Windows feature set.

This fork removes the **60 FPS cap**, supports **21:9 ultrawide / 16:10 / 4:3 aspect ratios**, provides FOV and camera tweaks, and reworks the **UE4SS** initialization flow to reduce crashes caused by accessing Unreal Engine objects before they are ready.

If you are looking for a **Dragon Ball Z: Kakarot Linux fix**, **Kakarot Steam Deck mod**, **Kakarot FPS unlock**, **Kakarot ultrawide fix** or a more stable DBZK_Fix build under Proton, this repository is intended for that use case.

## Key features

- Removes the game's **60 FPS cap** during gameplay.
- **21:9 ultrawide**, **16:10** and **4:3** aspect-ratio support.
- Optional motion-blur disable.
- Temporal AA / upscaling tweaks.
- FOV and camera adjustments.
- Reapplies framerate-related settings during game/cutscene transitions.
- Safer UObject validation.
- Deferred Unreal Engine object initialization.
- Safer UE4SS hook and callback handling.
- Improved **Linux / Proton / Steam Deck** stability.

## Compatibility

### Tested

- **Steam Deck / SteamOS**
- **Linux + Proton**

### Expected compatible

- Windows 10
- Windows 11

Windows support is expected because the mod still uses standard UE4SS Lua APIs and does not depend on Linux- or SteamOS-specific paths or commands. It should still be considered **not yet revalidated on Windows** until tested there directly.

## Why this fork exists

The original DBZK_Fix could perform several Unreal Engine operations very early during startup. Under **Proton and Steam Deck**, some required Unreal objects may not yet exist or may not be valid, which can lead to access violations and crashes.

This fork changes that behavior by:

- Waiting for relevant Unreal Engine objects before modifying them.
- Validating UObjects before use.
- Delaying FPS changes until a valid `ATCheatManager` is available.
- Avoiding the original immediate `Fix()` call during startup.
- Running sensitive changes at safer points in the Unreal lifecycle.
- Correcting UE4SS hook parameter handling where required.
- Preserving the original framerate, FOV, camera and graphics functionality.

The goal is to keep DBZK_Fix useful on Windows while making it more robust on **Linux, Proton and Steam Deck**.

## Installation

Download the latest build from the repository's **Releases** section.

### Dragon Ball Z: Kakarot HD / Remaster Update

Extract the release ZIP into:

```text
DRAGON BALL Z KAKAROT/dlc/Remaster/AT/Binaries/Win64/
```

### Base game version

For the original non-HD version, extract the release ZIP into:

```text
DRAGON BALL Z KAKAROT/AT/Binaries/Win64/
```

The base version has not yet been revalidated with this fork.

### Proton / Steam Deck

No extra DBZK_Fix-specific setup should normally be required.

The mod is designed to wait for the required Unreal Engine objects instead of assuming they are already available during startup.

## Configuration

Configuration continues to use the existing `Config.ini`.

The framerate section controls FPS-unlock behavior, including:

- Maximum FPS.
- Fixed or variable framerate mode.
- VSync interval.

Other graphics options remain available where supported by the game.

## Known issues

Limitations inherited from the original project may still apply:

- Some UI elements can use incorrect widget anchors on non-16:9 aspect ratios.
- Certain menus and HUD elements may not always be perfectly centered.
- Some pre-rendered or real-time cutscenes may still display incorrectly at ultrawide aspect ratios.
- Some FOV behavior can vary by scene.

When reporting an issue, please include:

- Operating system.
- Proton / Wine version, if applicable.
- Dragon Ball Z: Kakarot game version.
- UE4SS version.
- Relevant `UE4SS.log`.
- Crash dump, if one was generated.

## Search-friendly project summary

This project is a **Dragon Ball Z: Kakarot UE4SS mod** for **Steam Deck and Linux/Proton** that combines the original DBZK_Fix functionality with safer initialization. Its main user-facing features are **FPS unlock**, **ultrawide support**, **aspect-ratio fixes**, **FOV tweaks** and improved stability under Proton.

## Credits

This repository is a modified fork of the original **DBZK_Fix**.

Special thanks to:

- [KingKrouch](https://github.com/KingKrouch) / Bryce Q. for the original DBZK_Fix project and implementation.
- [NicNamed](https://github.com/NicNamed) for later work on the project and HD Update support.
- [Special Week (real)](https://steamcommunity.com/sharedfiles/filedetails/?id=3527702022) for identifying UE4SS update-related fixes for the HD Update.
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) contributors for the Unreal Engine scripting/modding framework.

## Fork goals

This fork focuses on:

- Proton compatibility.
- Steam Deck stability.
- Safer UE4SS initialization.
- Preserving the original DBZK_Fix feature set.
- Maintaining Windows compatibility where possible.

Future changes should keep platform-specific workarounds out of gameplay logic whenever possible so the same Lua mod can be shared across Windows and Proton.

## License

DBZK_Fix is derived from the original project by Bryce Q. and remains distributed under the MIT License.

### Original copyright

**DBZK_Fix (C) 2024 Bryce Q.**

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Additional bundled dependencies may use their own licenses:

- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) — MIT License.
- [inifile](https://github.com/bartbes/inifile/) — Simplified BSD License.

See the repository's `LICENSE` file for the complete license text.
