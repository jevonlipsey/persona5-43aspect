# persona5-43aspect

Native 4:3 for *Persona 5 Royal* (Atlus and SEGA, Steam appid 1687950), part of the nova-43aspect collection.

## Status
- **Planned.** Scaffold only, nothing verified yet. Engine facts below are first impressions from the install folder; confirm each one before relying on it.

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
3. **UI fallback first:** draw the 16:9 UI scaled to the 4:3 width (UI letterboxed, 3D fills the screen). That is the minimum shippable result.
4. **Then re-anchor the key screens** (battle HUD, date/weather corner, dialogue boxes, menus) one at a time.
5. Pre-rendered anime cutscenes stay 16:9 with bars; that's fine.

## Conventions
- Follow the nova-43aspect skill (device access, test workflow, repo conventions, web patcher design contract).
- Patch only the Windows build pulled from the device into `original/` (gitignored, read-only).
- Never commit game files, decompiler output, logs or screenshots.
