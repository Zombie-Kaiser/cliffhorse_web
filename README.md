# Cliff Horse — Web

A web port of the Unity game *Cliff Horse* (Unity 4.3.4f1, 2014). The original game
data was decompiled with AssetRipper, converted to JSON/PNG by `convert.py`, and
rebuilt as a three.js r160 web app. Gameplay logic is a 1:1 port of the two original
scripts (`HorseMove`, `LookAtHorse`), quirks included.

## Run

```bash
cd web
python serve.py 8137
# open http://localhost:8137/
```

A custom server is used because Windows `http.server` serves `.js` as `text/plain`.

**Controls:** `W`/`S` gallop forward/back, `A`/`D` turn.

## Layout

```
convert.py          Unity YAML -> JSON/PNG converter (meshes, terrain, animations, scene)
cs/                 Decompiled game logic (reference, not used at runtime)
export/             AssetRipper output (gitignored, regenerated from the original game)
web/
  index.html        Entry point, importmap
  main.js           Game: terrain splat shader, instanced palms, skinned horse, physics
  serve.py          Dev server with correct MIME types
  lib/three.module.js  Vendored three.js r160 (CDNs unreachable in dev env)
  data/*.json       Converted assets (scene, terrain, horse, palm, animation clips)
  tex/*.png         Textures (horse, grass, rock, palm bark/branch)
```

## Regenerating assets from the original game

1. Run AssetRipper CLI on the game's `_Data` folder, export as "ExportedProject"
   into `export/` (default location `convert.py` expects).
2. `python convert.py` — rewrites `web/data/` and `web/tex/`.

## Porting notes

- Unity (left-handed) → three.js (right-handed): positions `(x,y,-z)`, quaternions
  `(-x,-y,z,w)`, triangle winding flipped, bind poses `S·M·S` with `S=diag(1,1,-1,1)`.
- Terrain: 513×513 heightfield, ARGB32 splat map blended in-shader (`onBeforeCompile`).
- Palms: 3322 instances × 2 InstancedMeshes; fronds use alphaTest + custom depth
  material for shadow cutout. No colliders — as in the original.
- Horse: 44-bone SkinnedMesh + AnimationMixer (idle 4s / run 0.8s clips); scene pose
  equals bind pose, so three.js auto bone inverses are valid.
- Lighting matches Unity 4 units (`useLegacyLights`, intensity × π); sRGB textures,
  exp2 fog, camera rig replicating the original hierarchy.
- Spawn is 70 units above terrain — the horse falls on start, exactly like the original.

## Testing

URL params: `?debug=1` logs per-frame stats; `?autotest=1` runs a scripted
W→D→S drive (settles, gallops, turns 160°, backs up) via a setTimeout loop so it
works under headless Chrome `--virtual-time-budget`. On completion it logs
`AUTOTEST-DONE` with final positions and a `SNAP` canvas dataURL capture.
