import yaml, struct, json, base64, os, math, re, shutil

SRC = r"C:\Users\ysx5\Downloads\新建文件夹\cliffhorse_src\export\ExportedProject\Assets"
OUT = r"C:\Users\ysx5\Downloads\新建文件夹\cliffhorse_src\web\data"
TEXOUT = r"C:\Users\ysx5\Downloads\新建文件夹\cliffhorse_src\web\tex"
os.makedirs(OUT, exist_ok=True)
os.makedirs(TEXOUT, exist_ok=True)

# ============ Unity YAML loading ============
class UnityYamlLoader(yaml.SafeLoader):
    pass

def _unity_multi(loader, suffix, node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    else:
        return loader.construct_scalar(node)

UnityYamlLoader.add_multi_constructor('tag:unity3d.com,2011:', _unity_multi)

def load_objects(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    text = re.sub(r'^%TAG !u!.*\n?', '', text, flags=re.M)
    text = re.sub(r'^(--- !u!)', r'%TAG !u! tag:unity3d.com,2011:\n\1', text, flags=re.M)
    markers = re.findall(r'^--- !u!\d+ &(\S+)', text, re.M)
    docs = list(yaml.load_all(text, Loader=UnityYamlLoader))
    assert len(markers) == len(docs), (path, len(markers), len(docs))
    objs = {}
    for fid, data in zip(markers, docs):
        if isinstance(data, dict) and len(data) == 1:
            (t, f), = data.items()
            try:
                fid = int(fid)
            except (TypeError, ValueError):
                pass
            objs[fid] = (t, f)
    return objs

# ============ matrix helpers (m[row][col], column-vector convention, three.js math) ============
def mat_identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]

def mat_mul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def mat_trs(p, q, s):
    x, y, z, w = q
    x2, y2, z2 = x+x, y+y, z+z
    xx, xy, xz = x*x2, x*y2, x*z2
    yy, yz, zz = y*y2, y*z2, z*z2
    wx, wy, wz = w*x2, w*y2, w*z2
    return [
        [(1-(yy+zz))*s[0], (xy-wz)*s[0],     (xz+wy)*s[0],     p[0]],
        [(xy+wz)*s[1],     (1-(xx+zz))*s[1], (yz-wx)*s[1],     p[1]],
        [(xz-wy)*s[2],     (yz+wx)*s[2],     (1-(xx+yy))*s[2], p[2]],
        [0.0, 0.0, 0.0, 1.0]]

def mat_inv(m):
    n = 4
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col]
                a[r] = [v - f*w for v, w in zip(a[r], a[col])]
    return [row[n:] for row in a]

def decompose(m):
    p = [m[0][3], m[1][3], m[2][3]]
    sx = math.sqrt(m[0][0]**2 + m[1][0]**2 + m[2][0]**2)
    sy = math.sqrt(m[0][1]**2 + m[1][1]**2 + m[2][1]**2)
    sz = math.sqrt(m[0][2]**2 + m[1][2]**2 + m[2][2]**2)
    r = [[m[i][j] / s for j, s in ((0, sx), (1, sy), (2, sz))] for i in range(3)]
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0:
        S = math.sqrt(tr + 1.0) * 2
        w = 0.25 * S
        x = (r[2][1] - r[1][2]) / S
        y = (r[0][2] - r[2][0]) / S
        z = (r[1][0] - r[0][1]) / S
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        S = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2
        w = (r[2][1] - r[1][2]) / S
        x = 0.25 * S
        y = (r[0][1] + r[1][0]) / S
        z = (r[0][2] + r[2][0]) / S
    elif r[1][1] > r[2][2]:
        S = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2
        w = (r[0][2] - r[2][0]) / S
        x = (r[0][1] + r[1][0]) / S
        y = 0.25 * S
        z = (r[1][2] + r[2][1]) / S
    else:
        S = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2
        w = (r[1][0] - r[0][1]) / S
        x = (r[0][2] + r[2][0]) / S
        y = (r[1][2] + r[2][1]) / S
        z = 0.25 * S
    return p, [x, y, z, w], [sx, sy, sz]

def flat_colmajor(m):
    return [m[i][j] for j in range(4) for i in range(4)]

def ref_fid(ref):
    if isinstance(ref, dict):
        v = ref.get('fileID', 0)
        return v if v else None
    return None

def guid_of(ref):
    if isinstance(ref, dict):
        return ref.get('guid')
    return None

def slug(name):
    return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_').lower() or 'tex'

# Unity -> three.js conversions:
#   position/vertex/normal: (x, y, -z)
#   quaternion: (-x, -y, z, w)
#   matrix: S*M*S with S = diag(1,1,-1)
#   triangle winding: (i, i+2, i+1)

# ============ guid map + textures ============
GUIDS = {}
for root, dirs, files in os.walk(SRC):
    for fn in files:
        if fn.endswith('.meta'):
            p = os.path.join(root, fn)
            try:
                with open(p, encoding='utf-8', errors='ignore') as f:
                    txt = f.read(400)
            except OSError:
                continue
            g = re.search(r'guid: ([0-9a-f]{32})', txt)
            if g:
                GUIDS[g.group(1)] = os.path.join(root, fn[:-5])

TEX_MAP = {}
def tex_name(g):
    if not g:
        return None
    if g in TEX_MAP:
        return TEX_MAP[g]
    path = GUIDS.get(g)
    if not path or not path.lower().endswith('.png'):
        TEX_MAP[g] = None
        return None
    nm = slug(os.path.splitext(os.path.basename(path))[0])
    shutil.copy(path, os.path.join(TEXOUT, nm + '.png'))
    TEX_MAP[g] = nm
    return nm

def kv_entries(v):
    if isinstance(v, dict):
        v = v.get('data')
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict) and ('first' in v or 'second' in v):
        return [v]
    return [{'first': {'name': k}, 'second': val} for k, val in v.items()]

def material_info(g):
    path = GUIDS.get(g)
    if not path or not path.endswith('.mat'):
        return None
    out = {'tex': None, 'color': None}
    for t, f in load_objects(path).values():
        if t != 'Material':
            continue
        sp = f.get('m_SavedProperties', {})
        for te in kv_entries(sp.get('m_TexEnvs')):
            if (te.get('first') or {}).get('name') == '_MainTex':
                tg = guid_of((te.get('second') or {}).get('m_Texture'))
                if tg:
                    out['tex'] = tex_name(tg)
        for ce in kv_entries(sp.get('m_Colors')):
            if (ce.get('first') or {}).get('name') == '_Color':
                c = ce.get('second') or {}
                out['color'] = [c.get('r', 1), c.get('g', 1), c.get('b', 1)]
    return out

# ============ generic mesh conversion ============
def decode_vertices(vd):
    chs = vd['m_Channels']
    streams = vd['m_Streams']
    data = bytes.fromhex(vd['_typelessdata'])
    n = vd['m_VertexCount']
    names = ('pos', 'normal', 'color', 'uv', 'uv2', 'tangent')
    out = {k: [] for k in names}
    for i in range(n):
        for idx in range(min(6, len(chs))):
            ch = chs[idx]
            if ch['dimension'] == 0:
                continue
            st = streams[ch['stream']]
            base = st['offset'] + ch['offset'] + i * st['stride']
            nm = names[idx]
            if ch['format'] == 0:
                dim = ch['dimension']
                out[nm].extend(struct.unpack_from('<%df' % dim, data, base))
            elif ch['format'] == 2:
                out[nm].extend(data[base:base+4])
    return out

def convert_mesh(meshf):
    vd = meshf['m_VertexData']
    dec = decode_vertices(vd)
    n = vd['m_VertexCount']
    pos, nrm, uv = [], [], []
    for i in range(n):
        pos += [dec['pos'][3*i], dec['pos'][3*i+1], -dec['pos'][3*i+2]]
        if dec['normal']:
            nrm += [dec['normal'][3*i], dec['normal'][3*i+1], -dec['normal'][3*i+2]]
        if dec['uv']:
            uv += [dec['uv'][2*i], dec['uv'][2*i+1]]
    ib = bytes.fromhex(meshf['m_IndexBuffer'])
    idx = struct.unpack('<%dH' % (len(ib)//2), ib)
    tris = []
    for i in range(0, len(idx), 3):
        tris += [idx[i], idx[i+2], idx[i+1]]
    submeshes = [{'first': sm['firstByte']//2, 'count': sm['indexCount']} for sm in meshf['m_SubMeshes']]
    out = {'vertices': pos, 'normals': nrm, 'uvs': uv, 'indices': tris, 'submeshes': submeshes}
    if meshf.get('m_Skin'):
        bi, bw = [], []
        for s in meshf['m_Skin']:
            bi += [s.get('boneIndex[0]', 0), s.get('boneIndex[1]', 0), s.get('boneIndex[2]', 0), s.get('boneIndex[3]', 0)]
            bw += [s.get('weight[0]', 0), s.get('weight[1]', 0), s.get('weight[2]', 0), s.get('weight[3]', 0)]
        out['boneIndices'] = bi
        out['boneWeights'] = bw
    if meshf.get('m_BindPose'):
        bp = []
        S = [1, 1, -1, 1]
        for mm in meshf['m_BindPose']:
            e = [[mm['e00'], mm['e01'], mm['e02'], mm['e03']],
                 [mm['e10'], mm['e11'], mm['e12'], mm['e13']],
                 [mm['e20'], mm['e21'], mm['e22'], mm['e23']],
                 [mm['e30'], mm['e31'], mm['e32'], mm['e33']]]
            c = [[S[i]*e[i][j]*S[j] for j in range(4)] for i in range(4)]
            bp += flat_colmajor(c)
        out['bindposes'] = bp
    return out

def find_mesh_by_guid(g):
    path = GUIDS.get(g)
    if not path or not path.endswith('.asset'):
        return None
    for t, f in load_objects(path).values():
        if t == 'Mesh':
            return f
    return None

# ============ SCENE ============
print('parsing scene...')
scene_objs = load_objects(os.path.join(SRC, 'Default.unity'))
gos = {fid: f for fid, (t, f) in scene_objs.items() if t == 'GameObject'}
trs = {fid: f for fid, (t, f) in scene_objs.items() if t == 'Transform'}
comps = {fid: (t, f) for fid, (t, f) in scene_objs.items() if t not in ('GameObject', 'Transform')}

tid_by_go = {}
for fid, t in trs.items():
    g = ref_fid(t.get('m_GameObject'))
    if g is not None:
        tid_by_go[g] = fid

def comps_of(gid):
    out = []
    for c in gos[gid].get('m_Component', []):
        if isinstance(c, dict):
            for ctype, ref in c.items():
                fid = ref_fid(ref)
                if fid in comps:
                    out.append((fid,) + comps[fid])
    return out

def get_comp(gid, tname):
    for fid, t, f in comps_of(gid):
        if t == tname:
            return f
    return None

def go_by_name(nm):
    for fid, f in gos.items():
        if f.get('m_Name') == nm:
            return fid
    return None

def go_name(tid):
    g = ref_fid(trs[tid].get('m_GameObject'))
    return gos[g].get('m_Name') if g in gos else '?'

def local_three(t):
    p, r, s = t['m_LocalPosition'], t['m_LocalRotation'], t['m_LocalScale']
    return ([p['x'], p['y'], -p['z']],
            [-r['x'], -r['y'], r['z'], r['w']],
            [s['x'], s['y'], s['z']])

def world_matrix_three(tid):
    chain = []
    cur = tid
    while cur is not None and cur in trs:
        chain.append(trs[cur])
        cur = ref_fid(trs[cur].get('m_Father'))
    M = mat_identity()
    for t in reversed(chain):
        M = mat_mul(M, mat_trs(*local_three(t)))
    return M

# debug: print GO tree
print('--- scene tree ---')
def print_tree(tid, depth=0):
    t = trs[tid]
    g = ref_fid(t.get('m_GameObject'))
    nm = gos[g].get('m_Name') if g in gos else '?'
    cs = ','.join(sorted({ct for _, ct, _ in comps_of(g)})) if g in gos else ''
    print('  ' * depth + f'{nm} [{cs}]')
    for ch in t.get('m_Children', []):
        cf = ref_fid(ch)
        if cf in trs:
            print_tree(cf, depth + 1)
root_tids = [fid for fid, t in trs.items() if ref_fid(t.get('m_Father')) is None]
for rt in root_tids:
    print_tree(rt)

scene_out = {}

# camera
cam_gid = go_by_name('Main Camera')
cam = get_comp(cam_gid, 'Camera')
camM = world_matrix_three(tid_by_go[cam_gid])
cpos, crot, _ = decompose(camM)
scene_out['camera'] = {'pos': cpos, 'rot': crot, 'fov': cam['field of view'],
                       'near': cam.get('near clip plane', 0.3), 'far': cam.get('far clip plane', 1000)}
print('camera:', scene_out['camera'])

# camera hierarchy up to horse controller (for exact parenting)
ctrl_gid_pre = None
for fid, (t, f) in comps.items():
    if t == 'CharacterController':
        ctrl_gid_pre = ref_fid(f.get('m_GameObject'))
ctrl_tid_pre = tid_by_go[ctrl_gid_pre]
cam_hier = []
cur = tid_by_go[cam_gid]
while cur is not None and cur != ctrl_tid_pre:
    cam_hier.append({'name': go_name(cur), 'local': local_three(trs[cur])})
    cur = ref_fid(trs[cur].get('m_Father'))
scene_out['cameraHierarchy'] = list(reversed(cam_hier))
print('camera hierarchy:', [(h['name'], h['local'][0]) for h in scene_out['cameraHierarchy']])

# light
lgid = go_by_name('Directional light')
light = get_comp(lgid, 'Light')
lM = world_matrix_three(tid_by_go[lgid])
lpos, lrot, _ = decompose(lM)
sh = light.get('m_Shadows', {})
scene_out['light'] = {'rot': lrot, 'intensity': light.get('m_Intensity', 1),
                      'color': [light['m_Color']['r'], light['m_Color']['g'], light['m_Color']['b']],
                      'shadows': sh.get('m_Type', 0)}
print('light:', scene_out['light'])

# render settings
for fid, (t, f) in scene_objs.items():
    if t == 'RenderSettings':
        scene_out['fog'] = {'color': [f['m_FogColor']['r'], f['m_FogColor']['g'], f['m_FogColor']['b']],
                            'density': f.get('m_FogDensity', 0.001), 'mode': f.get('m_FogMode', 3)}
        scene_out['ambient'] = [f['m_AmbientLight']['r'], f['m_AmbientLight']['g'], f['m_AmbientLight']['b']]
        scene_out['fogEnabled'] = bool(f.get('m_Fog', 0))
print('fog:', scene_out.get('fog'), 'ambient:', scene_out.get('ambient'))

# terrain
ter_gid = go_by_name('Terrain')
terM = world_matrix_three(tid_by_go[ter_gid])
tpos, trot, tscl = decompose(terM)
tcomp = get_comp(ter_gid, 'Terrain') or get_comp(ter_gid, 'TerrainCollider')
ter_guid = guid_of(tcomp.get('m_TerrainData'))
scene_out['terrain'] = {'pos': tpos}
print('terrain pos:', tpos, 'guid:', ter_guid)

# horse: controller GO has CharacterController; model GO has SkinnedMeshRenderer
ctrl_gid = model_gid = smr = cc = None
for fid, (t, f) in comps.items():
    if t == 'CharacterController':
        cc = f
        ctrl_gid = ref_fid(f.get('m_GameObject'))
    elif t == 'SkinnedMeshRenderer':
        smr = f
        model_gid = ref_fid(f.get('m_GameObject'))
print('controller GO:', gos[ctrl_gid]['m_Name'], ' model GO:', gos[model_gid]['m_Name'],
      'parent of model:', go_name(ref_fid(trs[tid_by_go[model_gid]].get('m_Father'))))

ctrlM = world_matrix_three(tid_by_go[ctrl_gid])
hpos, hrot, _ = decompose(ctrlM)
ctrl_local = local_three(trs[tid_by_go[ctrl_gid]])
model_local = local_three(trs[tid_by_go[model_gid]])
scene_out['horse'] = {
    'controller': {'pos': hpos, 'rot': hrot, 'local': ctrl_local,
                   'height': cc['m_Height'], 'radius': cc['m_Radius'],
                   'center': [cc['m_Center']['x'], cc['m_Center']['y'], -cc['m_Center']['z']],
                   'slopeLimit': cc.get('m_SlopeLimit', 45), 'skinWidth': cc.get('m_SkinWidth', 0.08)},
    'model': {'local': model_local,
              'materials': [material_info(g) for g in (guid_of(m) for m in smr.get('m_Materials', []))]},
}
print('horse controller:', scene_out['horse']['controller'])
print('horse model local:', model_local, 'materials:', scene_out['horse']['model']['materials'])

# bones
model_tid = tid_by_go[model_gid]
# animation root: the GO whose Animator drives the clips = parent of the SMR GO
# (contains the skeleton: SMR GO 'Horse' and bone root 'Root' are siblings)
anim_root_tid = ref_fid(trs[model_tid].get('m_Father'))
bone_tids = [ref_fid(r) for r in smr.get('m_Bones', [])]
bones_out = []
bone_paths = []
for bt in bone_tids:
    if bt not in trs:
        bones_out.append(None)
        bone_paths.append(None)
        continue
    t = trs[bt]
    parent = ref_fid(t.get('m_Father'))
    # path up to animation root GO (matches AnimationClip curve paths)
    chain = []
    cur = bt
    while cur is not None and cur != anim_root_tid:
        chain.append(go_name(cur))
        cur = ref_fid(trs[cur].get('m_Father'))
    path = '/'.join(reversed(chain))
    bone_paths.append(path)
    bones_out.append({'name': go_name(bt), 'path': path,
                      'parent': (go_name(parent) if parent != anim_root_tid and parent in trs else None),
                      'local': local_three(t)})
print('bones:', len(bones_out), 'first:', bones_out[0], 'last:', bones_out[-1])

# add non-skinned skeleton ancestors (e.g. Root) that clips animate;
# appended after skin bones so skinIndices stay valid
skel_tids = set(t for t in bone_tids if t)
extra_tids = []
for bt in bone_tids:
    if bt is None:
        continue
    cur = ref_fid(trs[bt].get('m_Father'))
    while cur is not None and cur != anim_root_tid:
        if cur not in skel_tids and cur not in extra_tids:
            extra_tids.append(cur)
        cur = ref_fid(trs[cur].get('m_Father'))
for at in extra_tids:
    chain = []
    cur = at
    while cur is not None and cur != anim_root_tid:
        chain.append(go_name(cur))
        cur = ref_fid(trs[cur].get('m_Father'))
    path = '/'.join(reversed(chain))
    ptid = ref_fid(trs[at].get('m_Father'))
    bones_out.append({'name': go_name(at), 'path': path,
                      'parent': (go_name(ptid) if ptid != anim_root_tid and ptid in trs else None),
                      'local': local_three(trs[at])})
    bone_paths.append(path)
print('extra skeleton bones (not in skin list):', [b['name'] for b in bones_out[len(bone_tids):]])

# verify bind poses: BP_u == inverse of bone transform relative to SMR GO object space
meshf = find_mesh_by_guid(guid_of(smr.get('m_Mesh')))
maxdiff = 0.0
for i, bt in enumerate(bone_tids):
    if bt is None:
        continue
    # compose unity-space matrix from animation root down to bone
    chain = []
    cur = bt
    while cur is not None and cur != anim_root_tid:
        chain.append(trs[cur])
        cur = ref_fid(trs[cur].get('m_Father'))
    Lu = mat_identity()
    for t in reversed(chain):
        p = t['m_LocalPosition']; r = t['m_LocalRotation']; s = t['m_LocalScale']
        Lu = mat_mul(Lu, mat_trs([p['x'], p['y'], p['z']], [r['x'], r['y'], r['z'], r['w']],
                                 [s['x'], s['y'], s['z']]))
    # bone relative to SMR GO: inv(SMR local) * chain (both live under animation root)
    smrt = trs[model_tid]
    p = smrt['m_LocalPosition']; r = smrt['m_LocalRotation']; s = smrt['m_LocalScale']
    smr_local_u = mat_trs([p['x'], p['y'], p['z']], [r['x'], r['y'], r['z'], r['w']],
                          [s['x'], s['y'], s['z']])
    Lu = mat_mul(mat_inv(smr_local_u), Lu)
    Luinv = mat_inv(Lu)
    bp = meshf['m_BindPose'][i]
    B = [[bp['e00'], bp['e01'], bp['e02'], bp['e03']],
         [bp['e10'], bp['e11'], bp['e12'], bp['e13']],
         [bp['e20'], bp['e21'], bp['e22'], bp['e23']],
         [bp['e30'], bp['e31'], bp['e32'], bp['e33']]]
    for r_ in range(4):
        for c_ in range(4):
            maxdiff = max(maxdiff, abs(Luinv[r_][c_] - B[r_][c_]))
print('bindpose verification max diff (expect ~0 if scene pose == bind pose):', maxdiff)

# horse mesh
horse_out = convert_mesh(meshf)
horse_out['bones'] = bones_out
horse_out['materials'] = scene_out['horse']['model']['materials']
with open(os.path.join(OUT, 'horse.json'), 'w') as f:
    json.dump(horse_out, f)
print('horse.json:', len(horse_out['vertices'])//3, 'verts,', len(horse_out['indices'])//3, 'tris,',
      len(bones_out), 'bones,', len(horse_out['submeshes']), 'submeshes')

# palms are terrain tree instances (prototype = Palm prefab), NOT scene rigidbodies.
# the only pushable physics object in the scene is the decorative Sphere.
# decorative sphere (Rigidbody + SphereCollider + built-in sphere mesh)
sph = None
sgid = go_by_name('Sphere')
if sgid is not None:
    tid = tid_by_go[sgid]
    M = world_matrix_three(tid)
    p, q, s = decompose(M)
    mf = get_comp(sgid, 'MeshFilter')
    mr = get_comp(sgid, 'MeshRenderer')
    rb = get_comp(sgid, 'Rigidbody')
    sc = get_comp(sgid, 'SphereCollider')
    sph = {'pos': p, 'rot': q, 'scale': s,
           'mass': rb.get('m_Mass', 1) if rb else 1,
           'drag': rb.get('m_Drag', 0) if rb else 0,
           'angularDrag': rb.get('m_AngularDrag', 0.05) if rb else 0.05,
           'useGravity': bool(rb.get('m_UseGravity', 1)) if rb else True,
           'colliderRadius': (sc['m_Radius'] if sc else 0.5),
           'meshFileID': (ref_fid(mf.get('m_Mesh')) if mf else None),
           'materials': ([material_info(g) for g in (guid_of(m) for m in mr.get('m_Materials', []))]
                         if mr else [])}
    scene_out['sphere'] = sph
    print('sphere:', sph)

# ============ TERRAIN DATA ============
print('parsing terrain data...')
ter_objs = load_objects(os.path.join(SRC, 'TerrainData', 'New Terrain.asset'))
ter = None
splat = None
for fid, (t, f) in ter_objs.items():
    if t == 'TerrainData':
        ter = f
    elif t == 'Texture2D' and f.get('m_Name', '').startswith('SplatAlpha'):
        splat = f
hm = ter['m_Heightmap']
W, H = hm['m_Width'], hm['m_Height']
scale = hm['m_Scale']
heights_hex = hm['m_Heights']
assert len(heights_hex) == W * H * 4, (len(heights_hex), W * H * 4)
sw, sh = splat['m_Width'], splat['m_Height']
splat_bytes = bytes.fromhex(splat['_typelessdata'])[:sw * sh * 4]
splats = []
for sp in ter.get('m_SplatDatabase', {}).get('m_Splats', []):
    splats.append({'tex': tex_name(guid_of(sp.get('texture'))),
                   'tileSize': sp.get('m_TileSize') or sp.get('tileSize', {}).get('x', 15)})
print('splats:', splats)
trees = []
# Unity 4.3: tree instances live under m_DetailDatabase
for ti in ter.get('m_DetailDatabase', {}).get('m_TreeInstances', []):
    pos = ti['position']
    # normalized [0,1]: x/z across terrain, y = fraction of terrain height
    trees.append([pos['x'], pos['z'], ti.get('widthScale', 1), ti.get('heightScale', 1)])
terr_out = {
    'width': W, 'height': H,
    'size': [scale['x'] * (W - 1), scale['y'], scale['z'] * (H - 1)],
    'heights': base64.b64encode(bytes.fromhex(heights_hex)).decode(),
    'splatWidth': sw, 'splatHeight': sh,
    'splat': base64.b64encode(splat_bytes).decode(),
    'splats': splats,
    'trees': trees,
}
with open(os.path.join(OUT, 'terrain.json'), 'w') as f:
    json.dump(terr_out, f)
print('terrain.json:', W, 'x', H, 'size', terr_out['size'], 'trees', len(trees))

# ============ ANIMATIONS ============
def parse_anim(path):
    objs = load_objects(path)
    d = None
    for fid, (t, f) in objs.items():
        if t == 'AnimationClip':
            d = f
    out = {'rot': {}, 'pos': {}, 'scale': {}, 'name': d.get('m_Name'), 'wrapMode': d.get('m_WrapMode', 2)}
    dur = 0.0
    for rc in d.get('m_RotationCurves', []):
        keys = []
        for k in rc['curve']['m_Curve']:
            v = k['value']
            keys.append([k['time'], -v['x'], -v['y'], v['z'], v['w']])
            dur = max(dur, k['time'])
        out['rot'][rc.get('path', '')] = keys
    for pc in d.get('m_PositionCurves', []):
        keys = []
        for k in pc['curve']['m_Curve']:
            v = k['value']
            keys.append([k['time'], v['x'], v['y'], -v['z']])
            dur = max(dur, k['time'])
        out['pos'][pc.get('path', '')] = keys
    for sc in d.get('m_ScaleCurves', []):
        keys = []
        for k in sc['curve']['m_Curve']:
            v = k['value']
            keys.append([k['time'], v['x'], v['y'], v['z']])
            dur = max(dur, k['time'])
        out['scale'][sc.get('path', '')] = keys
    out['duration'] = dur
    return out

for nm in ['Horse_Idle', 'Horse_Run']:
    a = parse_anim(os.path.join(SRC, 'AnimationClip', nm + '.anim'))
    with open(os.path.join(OUT, nm + '.json'), 'w') as f:
        json.dump(a, f)
    paths = set(a['rot']) | set(a['pos']) | set(a['scale'])
    bone_path_set = set(p for p in bone_paths if p)
    missing = paths - bone_path_set
    print(nm, 'rot:', len(a['rot']), 'pos:', len(a['pos']), 'scale:', len(a['scale']),
          'dur:', a['duration'], 'unmatched paths:', sorted(missing) if missing else 'none')

# ============ PALM MESH (tree prototype) ============
print('parsing palm...')
palm_prefab_path = GUIDS.get('93d6053b47572a9478b9a0c1ca7e72ff')
pmeshf = None
pmats = []
for t, f in (load_objects(palm_prefab_path).values() if palm_prefab_path else []):
    if t == 'MeshFilter':
        pmeshf = find_mesh_by_guid(guid_of(f.get('m_Mesh')))
    elif t == 'MeshRenderer':
        pmats = [material_info(g) for g in (guid_of(m) for m in f.get('m_Materials', []))]
palm_out = convert_mesh(pmeshf)
palm_out['materials'] = pmats
with open(os.path.join(OUT, 'palm.json'), 'w') as f:
    json.dump(palm_out, f)
print('palm.json:', len(palm_out['vertices'])//3, 'verts,', len(palm_out['indices'])//3, 'tris,',
      'submeshes:', palm_out['submeshes'], 'mats:', pmats)

# scene.json
with open(os.path.join(OUT, 'scene.json'), 'w') as f:
    json.dump(scene_out, f)
print('scene.json written')
print('DONE')
