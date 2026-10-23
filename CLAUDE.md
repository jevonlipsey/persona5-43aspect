# persona5-43aspect

Native 4:3 for *Persona 5 Royal* (Atlus and SEGA, Steam appid 1687950), part of the nova-43aspect collection.

## Status
- **In progress.** Camera solved (`fit43` + `cam43`). Current build: `build/P5R.t5.exe` = `fit43,cam43,cinemascope` (sha256 `6906b463e5b1e69ac46cbd1c4599e290be5593bc8dd7ce893418b54ca8d91a6e`). It drops `ui_uniform`, which was forcing y scale = W/1920 and squashing the 1080-tall UI into 720px: that was the 240px bottom band and the 16:9 frame line at y=720 in the screenshots. Tradeoff: the UI is stretched 1.333x vertically (0.889 y vs 0.667 x), so circles become ellipses. Not device-verified yet (device offline).
- Engine facts: no DRM on P5R.exe (plain x64 in .xcode). Render area fit (1a19a0), UI scale (1a4390/1a1a80) and camera projection (1b1c30) are the aspect-sensitive spots; see tools/p5r_patch.py for the exact patches.
- The 2D context maps canvas coordinates straight to screen pixels: `screen = canvas * (W/1920, H/1080)`. The engine's own y scale fills a 4:3 render. A native (undistorted) 4:3 UI needs a 1440x1080 canvas (x scale W/1440, uniform 0.889) plus re-anchoring; see the `hud_43` note in CLAUDE.local.md.

## Engine facts (unverified)
- `P5R.exe` + `steam_api64.dll` + `CPK/` archives (~40 GB, on the SD card). Atlus' in-house engine (the GFD engine family).
- Runs well on the Nova: user caps it at 30 fps and uses Lossless Scaling 2x.
- Community tooling: Reloaded-II with the P5R mod loaders (CPK file replacement, code hooks). Flawless Widescreen has a P5R camera/aspect fix to learn from.

## Plan
This is a long project; the user is prepared to put 200 hours into this game on the Nova. **Goal: 4:3 that looks close to the 16:9 experience.** Some compromises are acceptable.

1. **Research spike first:**
   - DRM on `P5R.exe` (Denuvo? SteamStub?). This decides whether a static exe patch is possible or we need a runtime hook.
   - How Flawless Widescreen and any community aspect/ultrawide mods change the camera and aspect (which constants, which functions).
   - How the UI is built: sprite/layout files in the CPKs vs coordinates in code.
2. **Camera:** render 3D at 4:3 with vert+ FOV.
3. **UI fallback:** the engine's own fill scale (16:9 UI stretched to the 4:3 width and height) fills the screen and removes the band. Ship that first; it is the minimum shippable result.
4. **Then native 4:3 UI:** 1440x1080 canvas (x scale W/1440, y H/1080, uniform 0.889) and re-anchor the key screens (battle HUD, date/weather corner, dialogue boxes, menus) one at a time. `hud_43` already retargets the known battle/field/dialogue constants for this.
5. Pre-rendered anime cutscenes stay 16:9 with bars; that's fine.

## Conventions
- Follow the nova-43aspect skill (device access, test workflow, repo conventions, web patcher design contract).
- Patch only the Windows build pulled from the device into `original/` (gitignored, read-only).
- Never commit game files, decompiler output, logs or screenshots.
