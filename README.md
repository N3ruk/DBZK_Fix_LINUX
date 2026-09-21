# DBZK_Fix

A maintained fork of **DBZK_Fix** focused on stability and compatibility across **Windows, Linux/Proton, and Steam Deck**.

This fork keeps the original goals of the project while reworking parts of the UE4SS initialization flow to avoid crashes caused by accessing Unreal Engine objects before they are ready.

## Features

- Removes the game's 60 FPS cap during gameplay
- 21:9, 16:10 and 4:3 aspect-ratio support
- Optional motion blur disable
- Temporal AA / upscaling tweaks
- FOV and camera adjustments
- Reapplies framerate-related settings during relevant game/cutscene transitions
- Safer UObject validation
- Deferred initialization for Unreal Engine objects
- Safer handling of UE4SS hooks and callbacks
- Improved Linux / Proton / Steam Deck stability

## Compatibility

### Tested

- Steam Deck / SteamOS
- Linux + Proton

### Expected compatible

- Windows 10
- Windows 11

Windows support is expected because the mod still uses standard UE4SS Lua APIs and does not rely on SteamOS- or Linux-specific paths or commands. However, this fork should be considered **not yet revalidated on Windows** until it has been tested there directly.

## What changed in this fork

The original mod could execute several Unreal Engine operations very early during startup. Under Proton / Steam Deck, some Unreal objects may not yet exist or may not be valid at that point, which could lead to access violations and crashes.

This fork changes that behavior by:

- Waiting for relevant Unreal Engine objects before modifying them
- Validating UObjects before use
- Delaying FPS changes until a valid `ATCheatManager` is available
- Avoiding the original immediate `Fix()` execution during startup
- Running sensitive game-side changes at safer points in the Unreal lifecycle
- Correcting UE4SS hook parameter handling where required
- Keeping the original framerate, FOV, camera and graphics functionality while using a safer initialization model

The goal is to retain the behavior of DBZK_Fix while making it more robust under Proton and Steam Deck.

## Known Issues

The following limitations from the original project may still apply:

- Some UI elements can use incorrect widget anchors on non-16:9 aspect ratios.
- Certain menus and HUD elements may not always be perfectly centered.
- Some pre-rendered or real-time cutscenes may still display incorrectly at ultrawide aspect ratios.
- Some game-specific FOV behavior may still vary depending on the scene.

Please report reproducible issues in this repository's **Issues** section and include:

- Operating system
- Proton / Wine version, if applicable
- Game version
- UE4SS version
- Relevant `UE4SS.log`
- Crash dump, if one was generated

## Setup

### HD / Remaster Update

Extract the contents of the release `.zip` into:

```text
DRAGON BALL Z KAKAROT/dlc/Remaster/AT/Binaries/Win64/
```

### Base version

For the original non-HD version, extract the contents into:

```text
DRAGON BALL Z KAKAROT/AT/Binaries/Win64/
```

The base version has not yet been revalidated with this fork.

### Proton / Steam Deck

No additional DBZK_Fix configuration should normally be required.

The mod is designed to wait for the required Unreal Engine objects instead of assuming they already exist during startup.

## Configuration

Configuration continues to use the existing `Config.ini`.

The framerate section controls the FPS unlock behavior, including:

- Maximum FPS
- Fixed or variable framerate mode
- VSync interval

Other existing graphics options remain available where supported by the game.

## Download

Download the latest build from the **Releases** section of this repository.

## Credits

This project is a modified fork of the original **DBZK_Fix**.

Special thanks to:

- [KingKrouch](https://github.com/KingKrouch) / Bryce Q. for the original DBZK_Fix project and implementation
- [NicNamed](https://github.com/NicNamed) for later work on the project and HD Update support
- [Special Week (real)](https://steamcommunity.com/sharedfiles/filedetails/?id=3527702022) for identifying UE4SS update-related fixes for the HD Update
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) contributors for the Unreal Engine scripting/modding framework

## Fork goals

This fork currently focuses on:

- Proton compatibility
- Steam Deck stability
- safer UE4SS initialization
- preserving the original DBZK_Fix feature set
- maintaining compatibility with Windows where possible

Future changes should continue to keep platform-specific workarounds out of the gameplay logic whenever possible so the same Lua mod can be shared across Windows and Proton.

## Licensing

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

- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) — MIT License
- [inifile](https://github.com/bartbes/inifile/) — Simplified BSD License

See the repository's `LICENSE` file for the complete license text.
