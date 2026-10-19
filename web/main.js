// Cliff Horse — web remake (three.js) from Unity 4.3 decompiled data.
// Game logic mirrors decompiled Assembly-CSharp: HorseMove + LookAtHorse.

let THREE;
try {
  THREE = await import('three');
} catch (e) {
  try {
    THREE = await import('https://registry.npmmirror.com/three/0.160.0/files/build/three.module.js');
  } catch (e2) {
    THREE = await import('https://cdn.bootcdn.net/ajax/libs/three.js/0.160.0/three.module.js');
  }
}

const DATA = './data/';
const TEX = './tex/';
const $overlay = document.getElementById('overlay');
const $hint = document.getElementById('hint');
$overlay.hidden = false;

function fail(msg) {
  $overlay.textContent = 'error: ' + msg;
  console.error(msg);
}

async function jget(n) {
  const r = await fetch(DATA + n);
  if (!r.ok) throw new Error(n + ' -> HTTP ' + r.status);
  return r.json();
}

// ============================== load data ==============================
let sceneD, terrainD, horseD, palmD, idleD, runD;
try {
  [sceneD, terrainD, horseD, palmD, idleD, runD] = await Promise.all(
    ['scene.json', 'terrain.json', 'horse.json', 'palm.json', 'Horse_Idle.json', 'Horse_Run.json'].map(jget));
} catch (e) {
  fail(e.message);
  throw e;
}

const texLoader = new THREE.TextureLoader();
const texCache = new Map();
const texErrors = [];
// preload every texture the game needs before the first render
const ALL_TEX = [terrainD.splats[0].tex, terrainD.splats[1].tex, horseD.materials[0].tex,
  palmD.materials[0].tex, palmD.materials[1].tex, sceneD.sphere.materials[0].tex];
await Promise.all(ALL_TEX.map(nm =>
  texLoader.loadAsync(TEX + nm + '.png')
    .then(t => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.colorSpace = THREE.SRGBColorSpace; // decode sRGB -> linear (Unity gamma-space assets)
      texCache.set(nm, t);
    })
    .catch(err => {
      texErrors.push(nm + ': ' + err.message);
      texCache.set(nm, null);
    })));
if (texErrors.length) console.warn('texture load failures:', texErrors);

function tex(name) {
  return texCache.get(name);
}
// colors authored in Unity gamma space -> convert to linear working space
function srgbColor(r, g, b) {
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace);
}

// ============================== renderer / scene ==============================
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.useLegacyLights = true; // match Unity 4 lighting units (intensity * pi)
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const fogColor = srgbColor(...sceneD.fog.color);
scene.background = fogColor;
scene.fog = new THREE.FogExp2(fogColor, sceneD.fog.density);

const camD = sceneD.camera;
const camera = new THREE.PerspectiveCamera(camD.fov, window.innerWidth / window.innerHeight, camD.near, camD.far);

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ============================== lights ==============================
scene.add(new THREE.AmbientLight(srgbColor(...sceneD.ambient)));

const sun = new THREE.DirectionalLight(srgbColor(...sceneD.light.color), sceneD.light.intensity);
sun.castShadow = sceneD.light.shadows > 0;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -60; sun.shadow.camera.right = 60;
sun.shadow.camera.top = 60; sun.shadow.camera.bottom = -60;
sun.shadow.camera.near = 0.5; sun.shadow.camera.far = 1200;
sun.shadow.camera.updateProjectionMatrix();
sun.shadow.bias = -0.0005;
sun.shadow.normalBias = 1.0;
scene.add(sun);
scene.add(sun.target);
const sunDir = new THREE.Vector3(0, 0, -1).applyQuaternion(new THREE.Quaternion(...sceneD.light.rot)); // unity light forward -> three

// ============================== terrain field (physics sampling) ==============================
class TerrainField {
  constructor(d) {
    this.W = d.width; this.H = d.height;
    this.sx = d.size[0]; this.sy = d.size[1]; this.sz = d.size[2];
    const bytes = Uint8Array.from(atob(d.heights), c => c.charCodeAt(0));
    const u16 = new Uint16Array(bytes.buffer);
    this.h = new Float32Array(this.W * this.H);
    for (let i = 0; i < this.h.length; i++) this.h[i] = (u16[i] / 65535) * this.sy;
    this.n = new Float32Array(this.W * this.H * 3);
    const stepX = this.sx / (this.W - 1), stepZ = this.sz / (this.H - 1);
    for (let y = 0; y < this.H; y++) {
      for (let x = 0; x < this.W; x++) {
        const xl = Math.max(x - 1, 0), xr = Math.min(x + 1, this.W - 1);
        const yl = Math.max(y - 1, 0), yr = Math.min(y + 1, this.H - 1);
        const dhdx = (this.h[y * this.W + xr] - this.h[y * this.W + xl]) / ((xr - xl) * stepX);
        const dhdz = (this.h[yr * this.W + x] - this.h[yl * this.W + x]) / ((yr - yl) * stepZ);
        const l = Math.hypot(dhdx, 1, dhdz);
        const i3 = (y * this.W + x) * 3;
        this.n[i3] = -dhdx / l; this.n[i3 + 1] = 1 / l; this.n[i3 + 2] = -dhdz / l;
      }
    }
  }
  heightAt(xu, zu) {
    const gx = THREE.MathUtils.clamp(xu / this.sx, 0, 1) * (this.W - 1);
    const gy = THREE.MathUtils.clamp(zu / this.sz, 0, 1) * (this.H - 1);
    const x0 = Math.floor(gx), y0 = Math.floor(gy);
    const x1 = Math.min(x0 + 1, this.W - 1), y1 = Math.min(y0 + 1, this.H - 1);
    const fx = gx - x0, fy = gy - y0;
    const h00 = this.h[y0 * this.W + x0], h10 = this.h[y0 * this.W + x1];
    const h01 = this.h[y1 * this.W + x0], h11 = this.h[y1 * this.W + x1];
    return (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy;
  }
  normalAt(xu, zu, out) {
    const gx = THREE.MathUtils.clamp(xu / this.sx, 0, 1) * (this.W - 1);
    const gy = THREE.MathUtils.clamp(zu / this.sz, 0, 1) * (this.H - 1);
    const x0 = Math.floor(gx), y0 = Math.floor(gy);
    const x1 = Math.min(x0 + 1, this.W - 1), y1 = Math.min(y0 + 1, this.H - 1);
    const fx = gx - x0, fy = gy - y0;
    const a = (y0 * this.W + x0) * 3, b = (y0 * this.W + x1) * 3;
    const c = (y1 * this.W + x0) * 3, d = (y1 * this.W + x1) * 3;
    for (let k = 0; k < 3; k++) {
      const t0 = this.n[a + k] * (1 - fx) + this.n[b + k] * fx;
      const t1 = this.n[c + k] * (1 - fx) + this.n[d + k] * fx;
      out[k] = t0 * (1 - fy) + t1 * fy;
    }
    return out;
  }
}
const field = new TerrainField(terrainD);

// ============================== terrain mesh (splat-blended) ==============================
{
  const W = terrainD.width, H = terrainD.height;
  const sx = terrainD.size[0], sz = terrainD.size[2];
  const pos = new Float32Array(W * H * 3);
  const uv = new Float32Array(W * H * 2);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      pos[i * 3] = (x / (W - 1)) * sx;
      pos[i * 3 + 1] = field.h[i];
      pos[i * 3 + 2] = -(y / (H - 1)) * sz;
      uv[i * 2] = x / (W - 1);
      uv[i * 2 + 1] = y / (H - 1);
    }
  }
  const idx = new Uint32Array((W - 1) * (H - 1) * 6);
  let k = 0;
  for (let y = 0; y < H - 1; y++) {
    for (let x = 0; x < W - 1; x++) {
      const a = y * W + x, b = a + 1, c = a + W, d = c + 1;
      idx[k++] = a; idx[k++] = b; idx[k++] = c;
      idx[k++] = b; idx[k++] = d; idx[k++] = c;
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.computeVertexNormals();

  // splat alpha: Unity ARGB32 raw -> A,R,G,B bytes; R = splat0 (grass), G = splat1 (rock)
  const raw = Uint8Array.from(atob(terrainD.splat), c => c.charCodeAt(0));
  const sw = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 4) {
    sw[i] = raw[i + 1];
    sw[i + 1] = raw[i + 2];
    sw[i + 2] = 0;
    sw[i + 3] = 255;
  }
  const splatTex = new THREE.DataTexture(sw, terrainD.splatWidth, terrainD.splatHeight, THREE.RGBAFormat);
  splatTex.magFilter = THREE.LinearFilter;
  splatTex.minFilter = THREE.LinearFilter;
  splatTex.needsUpdate = true;

  const mat = new THREE.MeshLambertMaterial({ map: tex(terrainD.splats[0].tex) });
  const rockTex = tex(terrainD.splats[1].tex);
  const tileScale = sx / terrainD.splats[0].tileSize;
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.splatMap = { value: splatTex };
    shader.uniforms.map2 = { value: rockTex };
    shader.uniforms.tileScale = { value: tileScale };
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform sampler2D splatMap;\nuniform sampler2D map2;\nuniform float tileScale;')
      .replace('#include <map_fragment>', `
        vec4 sa = texture2D(splatMap, vMapUv);
        float w0 = sa.r / max(sa.r + sa.g, 1e-4);
        vec4 c1 = texture2D(map, vMapUv * tileScale);
        vec4 c2 = texture2D(map2, vMapUv * tileScale);
        vec4 sampledDiffuseColor = mix(c2, c1, w0);
        diffuseColor *= sampledDiffuseColor;
      `);
  };
  const terrainMesh = new THREE.Mesh(geo, mat);
  terrainMesh.receiveShadow = true;
  scene.add(terrainMesh);
}

// ============================== palms (terrain trees, instanced) ==============================
// NOTE: the Palm prefab has no collider (MeshFilter/MeshRenderer/Animation only),
// and Unity only builds tree colliders from prefab colliders -> the horse walks
// through palms, matching the original game.
{
  function subGeo(first, count) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(palmD.vertices, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(palmD.normals, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(palmD.uvs, 2));
    g.setIndex(palmD.indices.slice(first, first + count));
    return g;
  }
  const barkGeo = subGeo(palmD.submeshes[0].first, palmD.submeshes[0].count);
  const branchGeo = subGeo(palmD.submeshes[1].first, palmD.submeshes[1].count);
  const barkMat = new THREE.MeshLambertMaterial({ map: tex(palmD.materials[0].tex) });
  const branchTex = tex(palmD.materials[1].tex);
  const branchMat = new THREE.MeshLambertMaterial({
    map: branchTex, alphaTest: 0.5, side: THREE.DoubleSide,
  });
  const branchDepth = new THREE.MeshDepthMaterial({
    depthPacking: THREE.RGBADepthPacking, map: branchTex, alphaTest: 0.5,
  });
  const N = terrainD.trees.length;
  const barkIM = new THREE.InstancedMesh(barkGeo, barkMat, N);
  const branchIM = new THREE.InstancedMesh(branchGeo, branchMat, N);
  branchIM.customDepthMaterial = branchDepth;
  barkIM.castShadow = branchIM.castShadow = true;
  barkIM.receiveShadow = branchIM.receiveShadow = true;
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3();
  const Y = new THREE.Vector3(0, 1, 0);
  terrainD.trees.forEach((t, i) => {
    const [nx, nz, w, h] = t;
    const xu = nx * terrainD.size[0], zu = nz * terrainD.size[2];
    const y = field.heightAt(xu, zu);
    p.set(xu, y, -zu);
    const a = Math.sin(nx * 127.1 + nz * 311.7) * 43758.5453;
    q.setFromAxisAngle(Y, (a - Math.floor(a)) * Math.PI * 2);
    s.set(w, h, w);
    m.compose(p, q, s);
    barkIM.setMatrixAt(i, m);
    branchIM.setMatrixAt(i, m);
  });
  scene.add(barkIM);
  scene.add(branchIM);
}

// ============================== horse ==============================
const horseGroup = new THREE.Group();
let mixer, actions;
{
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(horseD.vertices, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(horseD.normals, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(horseD.uvs, 2));
  g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(horseD.boneIndices, 4));
  g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(horseD.boneWeights, 4));
  g.setIndex(horseD.indices);

  const mat = new THREE.MeshLambertMaterial({ map: tex(horseD.materials[0].tex) });
  const mesh = new THREE.SkinnedMesh(g, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  const byName = new Map();
  const nameCount = new Map();
  const bones = [];
  for (const b of horseD.bones) {
    const o = new THREE.Bone();
    o.name = b.name;
    o.position.fromArray(b.local[0]);
    o.quaternion.fromArray(b.local[1]);
    o.scale.fromArray(b.local[2]);
    byName.set(b.name, o);
    nameCount.set(b.name, (nameCount.get(b.name) || 0) + 1);
    bones.push(o);
  }
  const uniqueNames = [...nameCount.values()].every(c => c === 1);
  if (!uniqueNames) console.warn('duplicate bone names — using uuid tracks');
  let root = null;
  horseD.bones.forEach((b, i) => {
    if (b.parent && byName.has(b.parent)) byName.get(b.parent).add(bones[i]);
    else { root = bones[i]; mesh.add(root); }
  });

  const modelLocal = sceneD.horse.model.local;
  mesh.position.fromArray(modelLocal[0]);
  mesh.quaternion.fromArray(modelLocal[1]);
  mesh.scale.fromArray(modelLocal[2]);
  horseGroup.add(mesh);

  const ctrl = sceneD.horse.controller;
  horseGroup.position.fromArray(ctrl.pos);
  horseGroup.quaternion.fromArray(ctrl.rot);
  scene.add(horseGroup);
  scene.updateMatrixWorld(true);

  // scene pose == bind pose (verified during conversion) -> auto-computed inverses are correct
  const skeleton = new THREE.Skeleton(bones);
  mesh.bind(skeleton);

  mixer = new THREE.AnimationMixer(mesh);
  const pathToName = new Map(horseD.bones.map(b => [b.path, b.name]));
  const nodeId = (path) => uniqueNames ? pathToName.get(path) : byName.get(pathToName.get(path)).uuid;
  function clipFrom(d) {
    const tracks = [];
    for (const [path, keys] of Object.entries(d.rot)) {
      const nm = nodeId(path);
      if (!nm) continue;
      const times = new Float32Array(keys.length);
      const vals = new Float32Array(keys.length * 4);
      keys.forEach((kk, i) => { times[i] = kk[0]; vals[i * 4] = kk[1]; vals[i * 4 + 1] = kk[2]; vals[i * 4 + 2] = kk[3]; vals[i * 4 + 3] = kk[4]; });
      tracks.push(new THREE.QuaternionKeyframeTrack(nm + '.quaternion', times, vals));
    }
    for (const [path, keys] of Object.entries(d.pos)) {
      const nm = nodeId(path);
      if (!nm) continue;
      const times = new Float32Array(keys.length);
      const vals = new Float32Array(keys.length * 3);
      keys.forEach((kk, i) => { times[i] = kk[0]; vals[i * 3] = kk[1]; vals[i * 3 + 1] = kk[2]; vals[i * 3 + 2] = kk[3]; });
      tracks.push(new THREE.VectorKeyframeTrack(nm + '.position', times, vals));
    }
    for (const [path, keys] of Object.entries(d.scale)) {
      const nm = nodeId(path);
      if (!nm) continue;
      const times = new Float32Array(keys.length);
      const vals = new Float32Array(keys.length * 3);
      keys.forEach((kk, i) => { times[i] = kk[0]; vals[i * 3] = kk[1]; vals[i * 3 + 1] = kk[2]; vals[i * 3 + 2] = kk[3]; });
      tracks.push(new THREE.VectorKeyframeTrack(nm + '.scale', times, vals));
    }
    return new THREE.AnimationClip(d.name, d.duration, tracks);
  }
  actions = {
    idle: mixer.clipAction(clipFrom(idleD)),
    run: mixer.clipAction(clipFrom(runD)),
  };
  actions.idle.play();
}

// camera rig: horse controller -> holder -> camera (matches original hierarchy)
{
  const hier = sceneD.cameraHierarchy;
  let parent = horseGroup;
  for (let i = 0; i < hier.length; i++) {
    let node = (i === hier.length - 1) ? camera : new THREE.Group();
    node.position.fromArray(hier[i].local[0]);
    node.quaternion.fromArray(hier[i].local[1]);
    node.scale.fromArray(hier[i].local[2]);
    parent.add(node);
    parent = node;
  }
}

// ============================== pushable sphere ==============================
const sphere = new THREE.Mesh(
  new THREE.SphereGeometry(0.5, 24, 16),
  new THREE.MeshLambertMaterial({ map: tex(sceneD.sphere.materials[0].tex) }));
sphere.position.fromArray(sceneD.sphere.pos);
sphere.quaternion.fromArray(sceneD.sphere.rot);
sphere.scale.fromArray(sceneD.sphere.scale);
sphere.castShadow = true;
sphere.receiveShadow = true;
scene.add(sphere);
const sphVel = new THREE.Vector3();

// ============================== input ==============================
const keys = {};
window.addEventListener('keydown', e => { keys[e.code] = true; });
window.addEventListener('keyup', e => { keys[e.code] = false; });
window.addEventListener('blur', () => { for (const k in keys) keys[k] = false; });

// ============================== game logic (HorseMove, decompiled) ==============================
// horse state in UNITY space (x, y, z); three.js placement: (x, y, -z), quat (-x,-y,z,w)
const ctrlD = sceneD.horse.controller;
const horse = {
  x: ctrlD.pos[0], y: ctrlD.pos[1], z: -ctrlD.pos[2],
  rotation: 0, // degrees, matches private field in HorseMove
  mv: { x: 0, z: 0 },
  halfHeight: ctrlD.height / 2,
  radius: ctrlD.radius,
};
const CAP_SAMPLING = [[0.7, 0], [-0.7, 0], [0, 0.7], [0, -0.7]];

function lookRotationU(fx, fy, fz, ux, uy, uz) {
  let zx = fx, zy = fy, zz = fz;
  const fl = Math.hypot(zx, zy, zz) || 1;
  zx /= fl; zy /= fl; zz /= fl;
  let xx = uy * zz - uz * zy, xy = uz * zx - ux * zz, xz = ux * zy - uy * zx;
  const xl = Math.hypot(xx, xy, xz) || 1;
  xx /= xl; xy /= xl; xz /= xl;
  const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
  const m = new THREE.Matrix4().set(xx, yx, zx, 0, xy, yy, zy, 0, xz, yz, zz, 0, 0, 0, 0, 1);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}

let playing = 'idle';
function playAnim(name) {
  if (playing === name) return;
  playing = name;
  for (const k in actions) actions[k].stop();
  actions[name].reset().play();
}

const nrm = [0, 0, 0];
const lookTarget = new THREE.Vector3();
const SUN_DIST = 500;

function updateHorse(dt) {
  // movement damping: movement *= Mathf.Pow(0.01f, dt * 10f)
  const damp = Math.pow(0.01, dt * 10);
  horse.mv.x *= damp;
  horse.mv.z *= damp;
  const rad = horse.rotation * Math.PI / 180;
  let moving = false;
  if (keys.KeyW) {
    horse.mv.x += Math.sin(rad);
    horse.mv.z += Math.cos(rad);
    moving = true;
  } else if (keys.KeyS) {
    horse.mv.x -= Math.sin(rad);
    horse.mv.z -= Math.cos(rad);
    moving = true;
  }
  playAnim(moving ? 'run' : 'idle');
  if (keys.KeyA) horse.rotation -= 80 * dt;
  if (keys.KeyD) horse.rotation += 80 * dt;

  // terrain-normal aligned orientation (unity space)
  field.normalAt(horse.x, horse.z, nrm);
  const lx = Math.cos(rad), lz = -Math.sin(rad);
  const fx = -lz * nrm[1];
  const fy = lz * nrm[0] - lx * nrm[2];
  const fz = lx * nrm[1];
  const q = lookRotationU(fx, fy, fz, nrm[0], nrm[1], nrm[2]);

  // Move(movement * dt * 10) with gravity -10
  horse.mv.y = -10;
  const step = dt * 10;
  horse.x += horse.mv.x * step;
  horse.y += horse.mv.y * step;
  horse.z += horse.mv.z * step;

  // terrain collision (capsule bottom vs heightfield)
  let ground = field.heightAt(horse.x, horse.z);
  for (const [ox, oz] of CAP_SAMPLING) {
    ground = Math.max(ground, field.heightAt(horse.x + ox, horse.z + oz));
  }
  const bottom = horse.y - horse.halfHeight;
  if (bottom < ground) horse.y = ground + horse.halfHeight;

  // keep on the map
  horse.x = THREE.MathUtils.clamp(horse.x, 1, terrainD.size[0] - 1);
  horse.z = THREE.MathUtils.clamp(horse.z, 1, terrainD.size[2] - 1);

  // OnControllerColliderHit: push rigidbody sphere with horizontal move direction * 50.2
  {
    const dxs = sphere.position.x - horse.x;
    const dys = sphere.position.y - horse.y;
    const dzs = -sphere.position.z - horse.z;
    const minD = horse.radius + sceneD.sphere.scale[0] * sceneD.sphere.colliderRadius;
    if (dxs * dxs + dys * dys + dzs * dzs < minD * minD) {
      const hl = Math.hypot(horse.mv.x, horse.mv.z);
      if (hl > 1e-4) {
        const vx = horse.mv.x / hl * 50.2;
        const vz = horse.mv.z / hl * 50.2;
        sphVel.set(vx, 0, -vz);
      }
    }
  }

  horseGroup.position.set(horse.x, horse.y, -horse.z);
  horseGroup.quaternion.set(-q.x, -q.y, q.z, q.w);

  // sun follows horse so the shadow camera stays around the action
  sun.target.position.set(horse.x, horse.y, -horse.z);
  sun.position.set(horse.x, horse.y, -horse.z).addScaledVector(sunDir, -SUN_DIST);
  sun.target.updateMatrixWorld();
}

function updateSphere(dt) {
  sphVel.y -= 9.81 * dt;
  sphere.position.addScaledVector(sphVel, dt);
  const xu = sphere.position.x, zu = -sphere.position.z;
  const r = sceneD.sphere.scale[0] * sceneD.sphere.colliderRadius;
  const ground = field.heightAt(xu, zu);
  if (sphere.position.y - r < ground) {
    sphere.position.y = ground + r;
    if (sphVel.y < 0) sphVel.y = 0;
    const f = Math.max(0, 1 - 8 * dt);
    sphVel.x *= f;
    sphVel.z *= f;
  }
  const hv = Math.hypot(sphVel.x, sphVel.z);
  if (hv > 1e-3) {
    const axis = new THREE.Vector3(sphVel.z, 0, -sphVel.x).normalize();
    sphere.rotateOnWorldAxis(axis, (hv * dt) / r);
  }
}

function updateCamera() {
  // LookAtHorse: camera.LookAt(horse.TransformPoint(0, 3, 1)) — unity offset -> three (0,3,-1)
  lookTarget.set(0, 3, -1);
  horseGroup.localToWorld(lookTarget);
  camera.lookAt(lookTarget);
}

// ============================== main loop ==============================
const clock = new THREE.Clock();
const params = new URLSearchParams(location.search);
const DEBUG = params.has('debug');
const AUTOTEST = params.has('autotest');
let frames = 0;
let testPhase = 0; // 0 settle, 1 W, 2 A+D, 3 S, 4 done
let testTimer = 0;
function autotestStep(dt) {
  testTimer += dt;
  if (testPhase === 0 && testTimer > 1) { testPhase = 1; testTimer = 0; keys.KeyW = true; }
  else if (testPhase === 1 && testTimer > 3) { testPhase = 2; testTimer = 0; keys.KeyW = false; keys.KeyD = true; }
  else if (testPhase === 2 && testTimer > 2) { testPhase = 3; testTimer = 0; keys.KeyD = false; keys.KeyS = true; }
  else if (testPhase === 3 && testTimer > 2) { testPhase = 4; testTimer = 0; keys.KeyS = false; }
}
function tick() {
  if (AUTOTEST) setTimeout(tick, 16); else requestAnimationFrame(tick);
  const dt = Math.min(clock.getDelta(), 0.05);
  if (AUTOTEST) autotestStep(dt);
  updateHorse(dt);
  updateSphere(dt);
  mixer.update(dt);
  updateCamera();
  frames++;
  const doRender = !AUTOTEST || frames % 60 === 0 || (testPhase === 4 && testTimer < 0.1);
  if (doRender) renderer.render(scene, camera);
  if (DEBUG && frames % 60 === 1) {
    const sm = horseGroup.children[0];
    const wp = new THREE.Vector3();
    sm.getWorldPosition(wp);
    const sp = wp.clone().project(camera);
    console.log('frame', frames, 'tris', renderer.info.render.triangles,
      'calls', renderer.info.render.calls, 'tex', renderer.info.memory.textures,
      'horse', JSON.stringify(horseGroup.position), 'rot', horse.rotation.toFixed(1),
      'smNDC', JSON.stringify([sp.x, sp.y, sp.z]), 'mixer', mixer.time.toFixed(2),
      'action', playing, 'phase', testPhase);
  }
  if (AUTOTEST && testPhase === 4 && testTimer > 1) {
    renderer.render(scene, camera);
    console.log('AUTOTEST-DONE horse', JSON.stringify(horseGroup.position), 'rot', horse.rotation.toFixed(1),
      'sphere', JSON.stringify(sphere.position));
    try { console.log('SNAP ' + canvas.toDataURL('image/png')); } catch (e) { console.log('SNAP-FAIL ' + e); }
    testPhase = 5;
  }
}

scene.updateMatrixWorld(true);
updateCamera();
tick();

// hide loading overlay after the first frame is actually on screen
// (double-rAF for real browsers; setTimeout fallback for virtual-time captures where rAF never fires)
let overlayHidden = false;
function hideOverlay() {
  if (overlayHidden) return;
  overlayHidden = true;
  $overlay.hidden = true;
  $hint.hidden = false;
  if (DEBUG) console.log('overlay display', getComputedStyle($overlay).display);
}
requestAnimationFrame(() => requestAnimationFrame(hideOverlay));
setTimeout(hideOverlay, 500);
