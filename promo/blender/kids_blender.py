"""Back-to-school kids short, built entirely in Blender (soft clay / vinyl-toy look).

Run headless:   blender -b --python kids_blender.py -- [--still T ...] [--save]
  --save          write kids_scene.blend next to this script (open it in Blender)
  --still T       render a test still at time T seconds (repeatable)
  --anim          render the full animation to frames/####.png
Also writes overlay_track.json (head positions per frame) for the text/bubble overlay pass.
"""
import bpy, bmesh, math, json, os, sys, random
from mathutils import Vector, Euler
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FPS = 24
DUR = 21.0
NF = int(DUR * FPS)
S = [0, 8.0, 12.5, 17.0, DUR]          # scene boundaries (A street, B walk, C class, D party)
random.seed(4)

# ------------------------------------------------------------------ reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, NF - 1

# ------------------------------------------------------------------ helpers
def hexcol(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4) for x in c) + (1,)

_mats = {}
def mat(name, col, rough=.6, sss=0.0, coat=0.0, emit=0.0, sheen=0.0, img=None, alpha_img=False):
    if name in _mats: return _mats[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexcol(col)
    b.inputs['Roughness'].default_value = rough
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = (1.0, .45, .3)
        b.inputs['Subsurface Scale'].default_value = .04
    if coat:
        b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = .05
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    if emit:
        b.inputs['Emission Color'].default_value = hexcol(col); b.inputs['Emission Strength'].default_value = emit
    if img:
        t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(os.path.join(HERE, img))
        m.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
        if alpha_img:
            m.node_tree.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
            m.blend_method = 'HASHED'; m.shadow_method = 'NONE'
    _mats[name] = m
    return m

def link(o, parent=None):
    bpy.context.scene.collection.objects.link(o) if o.users_collection == () else None
    if parent: o.parent = parent
    return o

def place(o, loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1), parent=None, m=None):
    if parent: o.parent = parent
    o.location = loc; o.rotation_euler = rot; o.scale = scl
    if m:
        o.data.materials.clear(); o.data.materials.append(m)
    return o

def smooth(o):
    for p in o.data.polygons: p.use_smooth = True
    return o

def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); scene.collection.objects.link(o); return o

def sphere(name, r, loc=(0, 0, 0), scl=(1, 1, 1), m=None, parent=None, seg=40, cut=None):
    """cut: keep only verts with z > cut*r (hair caps) or z < cut*r if cut negative-coded via tuple"""
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    if cut is not None:
        mode, val = cut
        kill = [v for v in bm.verts if (v.co.z < val * r if mode == 'top' else v.co.z > val * r)]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    o = smooth(mesh_obj(name, bm)); return place(o, loc, (0, 0, 0), scl, parent, m)

def capsule(name, r, length, loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1), m=None, parent=None, seg=24):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2 + 1, radius=r)
    for v in bm.verts:
        if v.co.z > 1e-5: v.co.z += length / 2
        elif v.co.z < -1e-5: v.co.z -= length / 2
    o = smooth(mesh_obj(name, bm)); return place(o, loc, rot, scl, parent, m)

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), m=None, parent=None, bev=.06, seg=4):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    o = mesh_obj(name, bm); place(o, loc, rot, (1, 1, 1), parent, m)
    if bev:
        md = o.modifiers.new('bev', 'BEVEL'); md.width = bev; md.segments = seg; md.limit_method = 'ANGLE'
        md.harden_normals = False
        smooth(o); o.data.use_auto_smooth = True; o.data.auto_smooth_angle = math.radians(35)
    return o

def cyl(name, r, h, loc=(0, 0, 0), rot=(0, 0, 0), m=None, parent=None, seg=32, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    o = mesh_obj(name, bm); place(o, loc, rot, (1, 1, 1), parent, m)
    smooth(o); o.data.use_auto_smooth = True; o.data.auto_smooth_angle = math.radians(40); return o

def torus(name, R, r, loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1), m=None, parent=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=48, minor_segments=16)
    o = bpy.context.object; o.name = name; smooth(o)
    return place(o, loc, rot, scl, parent, m)

def lathe(name, pts, m=None, parent=None, seg=48, sy=1.0):
    bm = bmesh.new(); rings = []
    for (rad, z) in pts:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new((rad * math.cos(a), rad * math.sin(a) * sy, z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = smooth(mesh_obj(name, bm)); return place(o, (0, 0, 0), (0, 0, 0), (1, 1, 1), parent, m)

def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); scene.collection.objects.link(o)
    o.empty_display_size = .1; return place(o, loc, (0, 0, 0), (1, 1, 1), parent)

def subsurf(o, lv=1):
    md = o.modifiers.new('ss', 'SUBSURF'); md.levels = lv; md.render_levels = lv; return o

# ------------------------------------------------------------------ palette (soft pastel)
SKIN = mat('skin', '#FFC29A', .55, sss=.25, sheen=.2)
WHITE_EYE = mat('eyewhite', '#FFFFFF', .08, coat=1)
GLINT = mat('glint', '#FFFFFF', .2, emit=6)
BLACK = mat('pupil', '#15151C', .05, coat=1)
CHEEK = mat('cheek', '#FF9C9C', .7)
MOUTH = mat('mouth', '#7A2630', .6)
TONGUE = mat('tongue', '#EE7C7C', .6)
TEETH = mat('teeth', '#FFFFFF', .3)
LIP = mat('lip', '#E39B8C', .6)

# ------------------------------------------------------------------ character parts
def make_head(prefix, parent, iris_col, brow_col):
    head = empty(prefix + '_head', (0, 0, 1.06), parent)
    sphere(prefix + '_skull', .36, (0, 0, .34), (1, .95, 1), SKIN, head, seg=64)
    for s in (-1, 1):
        sphere(prefix + '_ear', .075, (s * .345, .02, .30), (.6, 1, 1), SKIN, head)
    irisM = mat(prefix + '_iris', iris_col, .15, coat=1)
    eyes = []
    for s in (-1, 1):
        e = empty(prefix + '_eye', (s * .135, -.235, .36), head)
        sphere(prefix + '_ew', .105, (0, 0, 0), (1, 1, 1.12), WHITE_EYE, e)
        sphere(prefix + '_ir', .066, (0, -.085, -.005), (1, .45, 1.1), irisM, e)
        sphere(prefix + '_pu', .036, (0, -.108, -.005), (1, .3, 1.1), BLACK, e)
        sphere(prefix + '_g1', .018, (-.026, -.118, .032), (1, 1, 1), GLINT, e, seg=16)
        sphere(prefix + '_g2', .009, (.022, -.116, -.026), (1, 1, 1), GLINT, e, seg=12)
        eyes.append(e)
    browM = mat(prefix + '_brow', brow_col, .8)
    for s in (-1, 1):
        capsule(prefix + '_brow', .018, .1, (s * .14, -.305, .495), (0, math.pi / 2 + s * .18, 0), (1, 1, 1), browM, head)
    sphere(prefix + '_nose', .04, (0, -.345, .27), (1, 1, .85), SKIN, head)
    for s in (-1, 1):
        sphere(prefix + '_cheek', .065, (s * .215, -.27, .235), (1, .32, .6), CHEEK, head)
    mouth = empty(prefix + '_mouth', (0, -.31, .165), head)
    mouth.rotation_euler = (math.radians(10), 0, 0)
    sphere(prefix + '_mo', .075, (0, 0, 0), (1, .5, 1), MOUTH, mouth, cut=('bottom', 0.0))
    cyl(prefix + '_teeth', .066, .012, (0, -.004, -.006), (0, 0, 0), TEETH, mouth, r2=.058).scale = (1, .45, 1)
    sphere(prefix + '_tongue', .045, (0, -.018, -.05), (1, .4, .42), TONGUE, mouth)
    return head, eyes, mouth

def make_arm(prefix, side, parent, loc, sleeveM, cuffM=None):
    sh = empty(prefix + '_sh' + ('L' if side < 0 else 'R'), loc, parent)
    capsule(prefix + '_up', .058, .2, (0, 0, -.12), m=sleeveM, parent=sh)
    el = empty(prefix + '_el', (0, 0, -.25), sh)
    capsule(prefix + '_fo', .052, .17, (0, 0, -.1), m=sleeveM, parent=el)
    if cuffM:
        torus(prefix + '_cuff', .05, .022, (0, 0, -.2), m=cuffM, parent=el)
    sphere(prefix + '_hand', .068, (0, 0, -.255), (1, .9, 1.08), SKIN, el)
    sphere(prefix + '_thumb', .03, (-side * .055, -.03, -.23), (1, 1, 1), SKIN, el, seg=16)
    return sh, el

def make_boy():
    root = empty('boy_root'); body = empty('boy_body', (0, 0, 0), root)
    robeM = mat('robe', '#F8F8FA', .7, sheen=.6)
    lathe('boy_robe', [(0, .02), (.29, .02), (.30, .08), (.28, .35), (.25, .6), (.22, .82), (.2, .93), (.13, 1.0), (0, 1.01)],
          robeM, body, sy=.82)
    shoeM = mat('shoe', '#3A3F52', .45, coat=.4)
    shoes = [sphere('boy_shoe', .1, (s * .11, -.12, .045), (1, 1.35, .6), shoeM, body) for s in (-1, 1)]
    bagM = mat('bag', '#7EC4EA', .5); strapM = mat('strap', '#5FAFDD', .55)
    box('boy_bag', (.46, .2, .5), (0, .2, .68), m=bagM, parent=body, bev=.07)
    box('boy_pocket', (.32, .08, .18), (0, .33, .55), m=strapM, parent=body, bev=.035)
    for s in (-1, 1):
        capsule('boy_strap', .03, .3, (s * .12, -.19, .8), (math.radians(-10), s * .08, 0), (1, .5, 1), strapM, body)
        torus('boy_strapTop', .07, .028, (s * .13, -.06, .95), (0, math.pi / 2, 0), (1, 1, 1), strapM, body)
    torus('boy_collar', .09, .03, (0, 0, 1.0), m=robeM, parent=body)
    btnM = mat('btn', '#D8DCE6', .3, coat=1)
    for i, z in enumerate((.86, .78, .70)):
        sphere('boy_btn', .014, (0, -.205 + i * .012, z), m=btnM, parent=body, seg=12)
    box('boy_pkt', (.09, .01, .08), (.08, -.19, .82), m=mat('pkt', '#EEF0F5', .8), parent=body, bev=.004, seg=2)
    capsule('boy_neck', .07, .06, (0, 0, 1.04), m=SKIN, parent=body)
    head, eyes, mouth = make_head('boy', body, '#6B3F22', '#3B2419')
    hairM = mat('boyhair', '#4A2C1E', .5, sheen=.4, coat=.15)
    cap1 = sphere('boy_hair', .38, (0, .01, .36), (1.02, .98, 1.02), hairM, head, seg=64, cut=('top', .25))
    cap1.rotation_euler = (math.radians(7), 0, 0)
    back = sphere('boy_hairback', .375, (0, .03, .34), (1.02, .97, 1), hairM, head, seg=48, cut=('top', -.31))
    back.rotation_euler = (math.radians(-43), 0, 0)
    for (x, z, y, rz) in [(-.2, .56, -.2, .5), (-.09, .6, -.25, .25), (.03, .61, -.26, -.05), (.15, .59, -.23, -.35), (.25, .53, -.17, -.6)]:
        t = sphere('boy_tuft', .11, (x, y, z), (1.1, .85, .62), hairM, head, seg=32)
        t.rotation_euler = (-.5, 0, -rz)
    sphere('boy_crown', .22, (0, .03, .64), (1.45, 1.45, .55), hairM, head, seg=40)
    sw = sphere('boy_swoop', .16, (.02, -.16, .66), (1.6, .9, .5), hairM, head, seg=32); sw.rotation_euler = (-.35, 0, .12)
    sl = mat('sleeve', '#F8F8FA', .7, sheen=.6)
    shL, elL = make_arm('boy', -1, body, (-.2, 0, .92), sl)
    shR, elR = make_arm('boy', 1, body, (.2, 0, .92), sl)
    robe = bpy.data.objects['boy_robe']
    return dict(root=root, body=body, head=head, eyes=eyes, mouth=mouth, shL=shL, elL=elL, shR=shR, elR=elR, shoes=shoes, robe=robe)

def make_girl():
    root = empty('girl_root'); body = empty('girl_body', (0, 0, 0), root)
    swM = mat('sweater', '#F27C86', .85, sheen=.8)
    lathe('girl_sweater', [(0, .5), (.255, .5), (.27, .55), (.255, .75), (.22, .9), (.13, .99), (0, 1.0)], swM, body, sy=.82)
    creamM = mat('cream', '#FFF1DC', .85, sheen=.6)
    torus('girl_hem', .262, .04, (0, 0, .52), (0, 0, 0), (1, .82, 1), creamM, body)
    legM = mat('leggings', '#8C93A8', .8); bootM = mat('boot', '#C98557', .5, coat=.3)
    legs = []
    for s in (-1, 1):
        g = empty('girl_leg', (s * .095, 0, .52), body)
        capsule('girl_shin', .062, .3, (0, 0, -.2), m=legM, parent=g)
        box('girl_boot', (.15, .24, .17), (0, -.03, -.44), m=bootM, parent=g, bev=.06)
        torus('girl_bootcuff', .07, .025, (0, 0, -.35), m=creamM, parent=g)
        legs.append(g)
    scM = mat('scarf', '#E8606C', .9, sheen=.8)
    torus('girl_scarf', .13, .06, (0, 0, 1.0), (0, 0, 0), (1, 1, .9), scM, body)
    capsule('girl_scarftail', .045, .2, (.1, -.19, .85), (0, -.15, 0), (1.2, .6, 1), scM, body)
    capsule('girl_neck', .068, .06, (0, 0, 1.04), m=SKIN, parent=body)
    head, eyes, mouth = make_head('girl', body, '#4A92BD', '#C9A060')
    hairM = mat('girlhair', '#F6D47E', .45, sheen=.5, coat=.2)
    c = sphere('girl_hair', .385, (0, .01, .35), (1.02, .98, 1.02), hairM, head, seg=64, cut=('top', .16)); c.rotation_euler = (math.radians(-7), 0, 0)
    b = sphere('girl_hairback', .38, (0, .04, .33), (1.02, .97, 1), hairM, head, seg=48, cut=('top', -.38)); b.rotation_euler = (math.radians(-46), 0, 0)
    f = sphere('girl_fringe', .2, (-.07, -.21, .57), (1.45, .75, .42), hairM, head, seg=40); f.rotation_euler = (-.45, 0, -.32)
    sphere('girl_fringe2', .12, (.17, -.23, .56), (1.2, .7, .5), hairM, head, seg=32)
    scrM = mat('scrunchie', '#E8606C', .8, sheen=1)
    buns = []
    for s in (-1, 1):
        g = empty('girl_bun', (s * .29, .03, .69), head)
        sphere('girl_bunball', .15, (0, 0, 0), m=hairM, parent=g, seg=40)
        torus('girl_scr', .1, .04, (-s * .06, 0, -.07), (0, s * -.7, 0), m=scrM, parent=g)
        buns.append(g)
    for s in (-1, 1):
        capsule('girl_strand', .035, .2, (s * .33, -.08, .2), (0, s * .12, 0), m=hairM, parent=head)
    shL, elL = make_arm('girl', -1, body, (-.2, 0, .9), swM, creamM)
    shR, elR = make_arm('girl', 1, body, (.2, 0, .9), swM, creamM)
    return dict(root=root, body=body, head=head, eyes=eyes, mouth=mouth, shL=shL, elL=elL, shR=shR, elR=elR, legs=legs, buns=buns)

boy = make_boy(); girl = make_girl()

# ------------------------------------------------------------------ sets
def ground(name, col, loc, size=(60, 40)):
    bpy.ops.mesh.primitive_plane_add(size=1); o = bpy.context.object; o.name = name
    return place(o, loc, (0, 0, 0), (size[0], size[1], 1), None, mat(name + 'M', col, .9))

# Street (origin)
STREET = empty('STREET')
ground('grass', '#A8DDA0', (0, 0, 0)).parent = STREET
box('walkway', (60, 2.2, .06), (0, -.3, 0), m=mat('walk', '#F3E6D3', .9), parent=STREET, bev=.02, seg=2)
scroll = empty('scroll', (0, 0, 0), STREET)
tileM = mat('tile', '#E2D2BA', .9)
for i in range(-30, 30):
    box('tile', (.03, 2.2, .065), (i * .8, -.3, 0), m=tileM, parent=scroll, bev=0)
HC = ['#FFC9BE', '#BDE3F5', '#FFE3A6', '#CDEEC0', '#E3D3F7']; RC = ['#F49A86', '#9BB5EE', '#F7B37A']
for i in range(-12, 12):
    h = 1.4 + ((i * 37 + 100) % 7) * .12; g = empty('house', (i * 2.1, 3.4, 0), scroll)
    box('hwall', (1.5, 1.2, h), (0, 0, h / 2), m=mat('h' + str(i % 5), HC[i % 5], .8), parent=g, bev=.08)
    r = cyl('roof', 1.15, .8, (0, 0, h + .4), (0, 0, math.pi / 4), mat('r' + str(i % 3), RC[i % 3], .7), g, seg=4, r2=0)
    r.scale = (1, .8, 1)
    winM = mat('win', '#FFFFFF', .2, emit=.15)
    for x in (-.35, .35):
        box('hwin', (.32, .05, .32), (x, -.61, h - .45), m=winM, parent=g, bev=.03, seg=2)
    box('hdoor', (.34, .05, .55), (0, -.61, .27), m=mat('door', '#B9815A', .6), parent=g, bev=.05, seg=2)
    if i % 2 == 0:
        t = empty('tree', (i * 2.1 + 1.05, 2.2, 0), scroll)
        capsule('trunk', .07, .5, (0, 0, .35), m=mat('trunk', '#B9815A', .8), parent=t)
        sphere('leaf', .42, (0, 0, 1.0), m=mat('leaf', '#8FD39A', .75), parent=t)
        sphere('leaf2', .25, (-.18, -.15, 1.15), m=mat('leaf2', '#A9E3A3', .75), parent=t)
cloudM = mat('cloud', '#FFFFFF', .9, emit=.25)
clouds = []
for i in range(5):
    g = empty('cloud', (-6 + i * 3, 9, 5.4 + random.random() * 1.2), STREET); s = .7 + random.random() * .4; g.scale = (s, s, s)
    for (x, z, r) in [(0, 0, .5), (.5, .15, .6), (1, 0, .5), (.5, -.15, .45)]:
        sphere('cl', r, (x, 0, z), m=cloudM, parent=g, seg=24)
    clouds.append(g)
sun = empty('sun', (1.7, 10, 6.6), STREET)
sphere('sunball', .7, m=mat('sunM', '#FFE79A', .5, emit=2.5), parent=sun)
rays = empty('rays', (0, 0, 0), sun)
for i in range(12):
    a_ = i * math.pi / 6
    capsule('ray', .07, .25, (math.cos(a_) * 1.0, 0, math.sin(a_) * 1.0), (0, math.pi / 2 - a_, 0), m=mat('rayM', '#FFD25E', .5, emit=2), parent=rays)
# school
school = empty('school', (-12, 2.8, 0), STREET)
box('sch', (3.4, 1.6, 2.3), (0, 0, 1.15), m=mat('schW', '#FFB39A', .75), parent=school, bev=.08)
rf = cyl('schRoof', 2.1, 1.0, (0, 0, 2.8), (0, 0, math.pi / 4), mat('schR', '#F08A78', .6), school, seg=4, r2=0); rf.scale = (1.25, .62, 1)
for (x, z) in [(-1.15, 1.45), (1.15, 1.45), (-1.15, .6), (1.15, .6)]:
    box('schFrame', (.7, .04, .65), (x, -.79, z), m=mat('frame', '#FFFFFF', .6), parent=school, bev=.05, seg=2)
    box('schWin', (.6, .06, .55), (x, -.81, z), m=mat('glass', '#CDEBFA', .1, coat=1), parent=school, bev=.04, seg=2)
box('schDoor', (.8, .08, 1.1), (0, -.82, .55), m=mat('sdoor', '#B9815A', .6), parent=school, bev=.08)
clock = empty('clock', (0, -.84, 1.55), school)
cyl('clk', .24, .05, (0, 0, 0), (math.pi / 2, 0, 0), mat('clkM', '#FFFFFF', .3), clock)
torus('clkRing', .24, .035, (0, 0, 0), (math.pi / 2, 0, 0), m=mat('ringM', '#F08A78', .5), parent=clock)
hand = empty('clkHand', (0, -.04, 0), clock)
box('clkH', (.025, .025, .17), (0, 0, .07), m=mat('ink', '#3B4060', .5), parent=hand, bev=0)
box('schSign', (1.3, .08, .34), (0, -.82, 2.05), m=mat('signW', '#FFFFFF', .5), parent=school, bev=.1)
bpy.ops.mesh.primitive_plane_add(size=1); _sg = bpy.context.object; _sg.name = 'signText'
place(_sg, (0, -.865, 2.05), (math.pi / 2, 0, 0), (1.25, .68, 1), school, mat('signTextM', '#FFFFFF', .6, img='sign_text.png', alpha_img=True))
for x in (-1.9, 1.9):
    sphere('bush', .35, (x, -.9, .25), (1.3, 1, .8), mat('bushM', '#8FD39A', .75), school)

# Classroom (x = 100)
CLASS = empty('CLASS', (100, 0, 0))
ground('cfloor', '#E8B47F', (0, 0, 0), (14, 10)).parent = CLASS
bpy.ops.mesh.primitive_plane_add(size=1); w = bpy.context.object; w.name = 'cwall'
place(w, (0, 2.4, 3), (math.pi / 2, 0, 0), (14, 8, 1), CLASS, mat('wallM', '#FFF0DC', .95))
for i in range(-8, 8):
    box('plank', (.02, 10, .005), (i * .7, 0, .003), m=mat('plankM', '#D79E68', .7), parent=CLASS, bev=0)
box('bframe', (3.1, .12, 1.8), (0, 2.32, 2.95), m=mat('bframeM', '#C99367', .6), parent=CLASS, bev=.05)
box('bface', (2.86, .02, 1.56), (0, 2.25, 2.95), m=mat('chalk', '#5E9E7E', .85), parent=CLASS, bev=0)
bpy.ops.mesh.primitive_plane_add(size=1); bt = bpy.context.object; bt.name = 'btext'
place(bt, (0, 2.235, 2.95), (math.pi / 2, 0, 0), (2.8, 1.53, 1), CLASS, mat('btextM', '#FFFFFF', .9, img='board_text.png', alpha_img=True))
coverM = mat('chalk', '#5E9E7E', .85)
cover1 = box('cover1', (2.8, .01, .78), (0, 2.225, 3.33), m=coverM, parent=CLASS, bev=0)   # hides letters (reveal right->left)
cover2 = box('cover2', (2.8, .01, .7), (0, 2.225, 2.55), m=coverM, parent=CLASS, bev=0)    # hides numbers (reveal left->right)
box('ledge', (2.6, .14, .06), (0, 2.22, 2.02), m=mat('ledgeM', '#A87850', .6), parent=CLASS, bev=.02)
FC = ['#FF9AA2', '#FFE08A', '#9CD3FF', '#A8E6B4', '#CDB8FF']
for i in range(11):
    x = -3 + i * .6; z = 4.5 - math.sin(math.pi * i / 10) * .35
    c = cyl('flag', .16, .4, (x, 2.3, z), (math.pi, 0, 0), mat('f' + str(i % 5), FC[i % 5], .7), CLASS, seg=3, r2=0)
def desk(x, y):
    g = empty('desk', (x, y, 0), CLASS)
    box('top', (1.0, .6, .07), (0, 0, .62), m=mat('deskM', '#F5C98A', .5, coat=.3), parent=g, bev=.03)
    for (dx, dy) in [(-.42, -.24), (.42, -.24), (-.42, .24), (.42, .24)]:
        cyl('leg', .03, .6, (dx, dy, .3), (0, 0, 0), mat('deskLeg', '#8FB4F2', .4), g, seg=12)
    box('book', (.3, .22, .05), (.15, 0, .68), (0, 0, .3), mat('bookM', '#A8E6B4', .6), g, bev=.01, seg=2)
    sphere('apple', .07, (-.25, 0, .72), m=mat('appleM', '#F0606A', .3, coat=1), parent=g)
desk(-1.85, 1.2); desk(1.85, 1.2)

# Party (x = 200)
PARTY = empty('PARTY', (200, 0, 0))
ground('pfloor', '#FFEFC2', (0, 0, 0), (30, 20)).parent = PARTY
bpy.ops.mesh.primitive_plane_add(size=1); bg = bpy.context.object; bg.name = 'burst'
place(bg, (0, 5, 2.4), (math.pi / 2, 0, 0), (22, 22, 1), PARTY, mat('burstM', '#FFFFFF', .9, img='party_bg.png', emit=0))
bm_ = bg.active_material.node_tree; bsdf = bm_.nodes['Principled BSDF']
bm_.links.new(bm_.nodes['Image Texture'].outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = .6
confM = [mat('cf' + str(i), FC[i], .5) for i in range(5)]
confetti = []
for i in range(110):
    bpy.ops.mesh.primitive_plane_add(size=1); c = bpy.context.object; c.name = 'conf'
    place(c, (0, 0, -5), (0, 0, 0), (.07, .11, 1), PARTY, confM[i % 5])
    confetti.append(dict(o=c, x=(random.random() - .5) * 4, y=(random.random() - .5) * 2 - .5, d=random.random() * 1.2,
                         v=1.2 + random.random() * 1.2, sw=random.random() * 6.28, r=random.random() * 6))

# stars (pop effect)
starM = [mat('st' + str(i), FC[i], .3, coat=1) for i in range(5)]
def star_mesh():
    bm = bmesh.new(); pts = []
    for i in range(10):
        r = .11 if i % 2 == 0 else .045; a = i * math.pi / 5 + math.pi / 2
        pts.append(bm.verts.new((math.cos(a) * r, 0, math.sin(a) * r)))
    f = bm.faces.new(pts); ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]: v.co.y += .05
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm
stars = []
for i in range(10):
    o = mesh_obj('star', star_mesh()); o.data.materials.append(starM[i % 5]); o.scale = (0, 0, 0)
    stars.append(dict(o=o, a=i * 36 + random.random() * 20, r=.6 + random.random() * .4))

# ------------------------------------------------------------------ lights / world / camera
world = bpy.data.worlds.new('W'); scene.world = world; world.use_nodes = True
_wn = world.node_tree.nodes; _wl = world.node_tree.links
_bgL = _wn['Background']; _bgL.inputs['Color'].default_value = hexcol('#CFE9FF'); _bgL.inputs['Strength'].default_value = .5
_bgC = _wn.new('ShaderNodeBackground'); _bgC.inputs['Color'].default_value = hexcol('#8FD0FF'); _bgC.inputs['Strength'].default_value = 1.0
_lp = _wn.new('ShaderNodeLightPath'); _mx = _wn.new('ShaderNodeMixShader')
_wl.new(_lp.outputs['Is Camera Ray'], _mx.inputs['Fac']); _wl.new(_bgL.outputs['Background'], _mx.inputs[1]); _wl.new(_bgC.outputs['Background'], _mx.inputs[2])
_wl.new(_mx.outputs['Shader'], _wn['World Output'].inputs['Surface'])
def light(name, kind, loc, rot, energy, size, col='#FFFFFF'):
    d = bpy.data.lights.new(name, kind); d.energy = energy; d.color = hexcol(col)[:3]
    if kind == 'AREA': d.size = size
    if kind == 'SUN': d.angle = size
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o); o.location = loc; o.rotation_euler = rot; return o
key = light('key', 'SUN', (0, 0, 10), (math.radians(50), math.radians(-25), math.radians(-30)), 2.6, math.radians(18), '#FFF1DE')
fill = light('fill', 'AREA', (-4, -6, 3), (math.radians(70), 0, math.radians(-35)), 350, 6, '#DDEBFF')
rim = light('rim', 'AREA', (3, 5, 4), (math.radians(-60), 0, math.radians(150)), 300, 4, '#FFFFFF')
for L in (key, fill, rim): L.data.use_shadow = True
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
cam_d.lens = 46; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 24
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 3.2

# ------------------------------------------------------------------ render settings
r = scene.render; r.engine = 'BLENDER_EEVEE'
r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, 100
ee = scene.eevee
ee.taa_render_samples = 24; ee.use_gtao = True; ee.gtao_distance = .6; ee.use_soft_shadows = True
ee.shadow_cube_size = '1024'; ee.shadow_cascade_size = '2048'; ee.use_bloom = False
ee.use_ssr = False
scene.view_settings.view_transform = 'Filmic'; scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = .3; scene.view_settings.gamma = 1

# ------------------------------------------------------------------ animation
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def P(t, a, b): return clamp((t - a) / (b - a))
def eOut(x): return 1 - (1 - x) ** 3
def eIn(x): return x ** 3
def eIO(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def lerp(a, b, x): return a + (b - a) * x

def set_arm(sh, el, side, z=.12, x=0., elbow=.15):
    # sideways raise outward is +rotY for left arm (side=-1), -rotY for right; forward is -rotX
    sh.rotation_euler = (-x, -side * z, 0); el.rotation_euler = (-elbow, 0, 0)

def pose(c, t, x=0., y=0., rz=0., bob=0., tilt=0., nod=0., look=0., armL=None, armR=None, talk=False,
         blinkOff=0., legL=0., legR=0., squash=1., base=(0, 0, 0)):
    c['root'].location = (base[0] + x, base[1] + y, base[2]); c['root'].rotation_euler = (0, 0, rz)
    c['body'].location = (0, 0, bob); sq = 1 / math.sqrt(squash); c['body'].scale = (sq, sq, squash)
    c['head'].rotation_euler = (nod, tilt, look)
    set_arm(c['shL'], c['elL'], -1, **(armL or {})); set_arm(c['shR'], c['elR'], 1, **(armR or {}))
    blink = ((t + blinkOff) % 3.3) < .12
    for e in c['eyes']: e.scale = (1, 1, .1 if blink else 1)
    m = (.45 + .75 * abs(math.sin(t * 13))) if talk else .78
    c['mouth'].scale = (1, 1, m)
    if 'legs' in c:
        c['legs'][0].rotation_euler = (-legL, 0, 0); c['legs'][1].rotation_euler = (-legR, 0, 0)
        c['buns'][0].rotation_euler = (0, math.sin(t * 6) * .05, 0); c['buns'][1].rotation_euler = (0, -math.sin(t * 6) * .05, 0)
    if 'shoes' in c:
        c['shoes'][0].location.y = -.12 - legL * .25; c['shoes'][1].location.y = -.12 - legR * .25
        c['robe'].rotation_euler = (0, legL * .08, 0)

def walk(t, sp=1.):
    ph = t * 7.2 * sp
    return dict(bob=abs(math.sin(ph)) * .05, armL=dict(z=.12, x=math.sin(ph) * .5, elbow=.3), armR=dict(z=.12, x=-math.sin(ph) * .5, elbow=.3),
                legL=math.sin(ph) * .45, legR=-math.sin(ph) * .45, tilt=math.sin(ph) * .04)
def WAVE(t): return dict(z=2.5, x=.2, elbow=.5 + math.sin(t * 12) * .35)
HOLD = dict(z=-.05, x=.35, elbow=1.9)
FACE_L = math.radians(-60)   # facing toward -X (walking left on screen)
FACE_R = math.radians(60)

def set_cam(pos, target, focus_obj_pos):
    cam.location = pos
    d = Vector(target) - Vector(pos); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam_d.dof.focus_distance = (Vector(focus_obj_pos) - Vector(pos)).length

def stars_at(t, a, center):
    lt = t - a
    for i, s in enumerate(stars):
        p = P(lt, i * .05, .9 + i * .05); vis = lt > 0 and p < 1
        k = math.sin(p * math.pi) * 1.3 if vis else 0
        rr = eOut(p) * s['r']; ang = math.radians(s['a'])
        s['o'].location = (center[0] + math.cos(ang) * rr, center[1], center[2] + math.sin(ang) * rr)
        s['o'].scale = (k, k, k); s['o'].rotation_euler = (0, p * 3, p * 4)

def apply(t):
    for s in stars: s['o'].scale = (0, 0, 0)
    for c in confetti: c['o'].location = (0, 0, -5)
    rays.rotation_euler = (0, t * .4, 0)
    for i, c in enumerate(clouds): c.location.x = ((-6 + i * 3 + t * .25) % 15 + 15) % 15 - 7.5
    if t < S[1]:   # ---------- A: meet on the street
        scroll.location.x = 0; school.location.x = -12
        set_cam((lerp(.4, 0, eOut(P(t, 0, 4))), lerp(-9.6, -8.8, eIO(P(t, 0, 8))), 2.0), (0, 0, 1.55), (0, 0, 1.3))
        bx = lerp(3.4, .62, eOut(P(t, .4, 2.6))) if t < 2.6 else .62
        bp = dict(x=bx, armR=HOLD, rz=0)
        if t < 2.6:
            bp.update(walk(t)); bp['armR'] = HOLD; bp['rz'] = lerp(FACE_L, 0, eIO(P(t, 2.0, 2.7)))
        if 2.6 < t < 4.1:
            bp['armL'] = WAVE(t); bp['tilt'] = math.sin(t * 4) * .06; bp['talk'] = 2.7 < t < 3.9
        if 4.3 < t < 6.2:
            bp['rz'] = math.radians(-20); bp['look'] = -.15
        if 6.3 < t < 7.8:
            bp['talk'] = t < 7.4; bp['bob'] = abs(math.sin((t - 6.3) * 6)) * .18 if t < 7.4 else 0
            bp['armL'] = dict(z=.6, x=.3, elbow=1.2); bp['rz'] = math.radians(-15)
        pose(boy, t, **bp)
        gx = -4.5 if t < 3.6 else lerp(-3.4, -.62, eOut(P(t, 3.6, 5.2)))
        gp = dict(x=gx, blinkOff=1.4, rz=0)
        if 3.6 <= t < 5.2:
            gp.update(walk(t, 1.05)); gp['rz'] = lerp(FACE_R, math.radians(20), eIO(P(t, 4.7, 5.2)))
        if t >= 5.2: gp['rz'] = math.radians(20); gp['look'] = .15
        if 5.2 <= t < 6.4:
            gp['armR'] = WAVE(t); gp['talk'] = 5.3 < t < 6.3; gp['tilt'] = math.sin(t * 4) * .06
        pose(girl, t, **gp)
    elif t < S[2]:  # ---------- B: walk to school
        lt = t - S[1]; stop = 3.0; sp = eOut(P(lt, 0, stop))
        scroll.location.x = sp * 6.5; school.location.x = lerp(-9, 0, sp)
        hand.rotation_euler = (0, -lt * 2, 0)
        set_cam((lerp(1.0, 0, eIO(P(lt, 0, stop))), -9.2, 2.0), (0, 0, 1.6), (0, 0, 1.3))
        bp = dict(x=.55, armR=HOLD); gp = dict(x=-.55, y=-.15, blinkOff=1.4)
        if lt < stop:
            bp.update(walk(t)); bp['armR'] = HOLD; bp['rz'] = lerp(FACE_L, 0, eIO(P(lt, stop - .4, stop + .1)))
            gp.update(walk(t + .2)); gp['rz'] = bp['rz']
        else:
            j = P(lt, stop + .2, stop + .8); j2 = P(lt, stop + .35, stop + .95)
            bp['bob'] = math.sin(j * math.pi) * .35; gp['bob'] = math.sin(j2 * math.pi) * .35
            bp['armL'] = dict(z=2.6, x=.1, elbow=.3); gp['armR'] = dict(z=2.6, x=.1, elbow=.3)
            if lt > stop + .2: stars_at(t, S[1] + stop + .2, (0, -.4, 2.1))
        pose(boy, t, **bp); pose(girl, t, **gp)
    elif t < S[3]:  # ---------- C: classroom
        lt = t - S[2]; B = (100, 0, 0)
        set_cam((100 + lerp(-.4, .3, eIO(P(lt, 0, 4.5))), -8.6, 2.0), (100, 0, 1.75), (100, 0, 1.3))
        a = eIO(P(lt, .4, 2.0)); cover1.scale = (1 - a, 1, 1); cover1.location.x = -1.4 * a     # right->left reveal
        n = eIO(P(lt, 1.9, 2.9)); cover2.scale = (1 - n, 1, 1); cover2.location.x = 1.4 * n      # left->right reveal
        gp = dict(x=-.62, blinkOff=1.4, rz=math.radians(10), base=B); bp = dict(x=.62, armR=HOLD, rz=math.radians(-10), base=B)
        gp['bob'] = (1 - eOut(P(lt, 0, .6))) * 2.5; bp['bob'] = (1 - eOut(P(lt, .15, .75))) * 2.5
        if .9 < lt < 2.4:
            gp['talk'] = lt < 2.2; gp['armR'] = dict(z=1.2, x=.4, elbow=1.0 + math.sin(lt * 10) * .2); gp['tilt'] = math.sin(lt * 4) * .06
        if lt > 2.6:
            bp['armL'] = dict(z=2.3, x=.35, elbow=.35 + math.sin(lt * 14) * .15); bp['bob'] = abs(math.sin(lt * 7)) * .05
            bp['talk'] = 2.7 < lt < 4.0; bp['tilt'] = -.08; gp['look'] = .3; gp['rz'] = math.radians(25)
        pose(girl, t, **gp); pose(boy, t, **bp)
        if lt > 3.4: stars_at(t, S[2] + 3.4, (100.62, -.4, 2.3))
    else:           # ---------- D: celebration
        lt = t - S[3]; B = (200, 0, 0)
        set_cam((200 + math.sin(lt * .6) * .6, lerp(-9.6, -8.8, eOut(P(lt, 0, 4))), 2.0), (200, 0, 1.6), (200, 0, 1.3))
        jb = abs(math.sin(lt * 5.2)) * .45 if lt > .5 else 0; jg = abs(math.sin(lt * 5.2 + 1.4)) * .45 if lt > .6 else 0
        sqb = 1 - .1 * max(0, 1 - jb / .08); sqg = 1 - .1 * max(0, 1 - jg / .08)
        up = dict(z=2.7, x=.15, elbow=.25)
        pose(boy, t, x=.62, bob=jb, squash=sqb, armL=up, armR=up, rz=math.radians(-10), base=B)
        pose(girl, t, x=-.62, bob=jg, squash=sqg, armL=up, armR=up, blinkOff=1.4, legL=.25, legR=-.25, rz=math.radians(10), base=B)
        for c in confetti:
            l2 = lt - c['d']
            if l2 <= 0: continue
            c['o'].location = (c['x'] + math.sin(l2 * 3 + c['sw']) * .2, c['y'], 4.4 - l2 * c['v'])
            c['o'].rotation_euler = (l2 * 4 + c['r'], l2 * 3, l2 * 2)

# objects whose transforms are keyed every frame
def animated_objects():
    objs = [cam, scroll, school, hand, rays, cover1, cover2] + clouds
    for c in (boy, girl):
        objs += [c['root'], c['body'], c['head'], c['shL'], c['elL'], c['shR'], c['elR'], c['mouth']] + c['eyes']
        objs += c.get('legs', []) + c.get('buns', []) + c.get('shoes', []) + ([c['robe']] if 'robe' in c else [])
    objs += [s['o'] for s in stars] + [c['o'] for c in confetti]
    return objs

def bake():
    objs = animated_objects(); last = {}
    def key(o, prop, f):
        v = tuple(round(x, 5) for x in getattr(o, prop))
        k = (o.name, prop)
        if last.get(k) != v or f == 0:
            if k in last and f > 0 and last[k + ('f',)] != f - 1:
                o.keyframe_insert(prop, frame=f - 1)  # not needed with CONSTANT, kept for clarity
            o.keyframe_insert(prop, frame=f); last[k] = v
        last[k + ('f',)] = f if last.get(k) == v else last.get(k + ('f',), f)
    for f in range(NF):
        apply(f / FPS)
        for o in objs:
            for prop in ('location', 'rotation_euler', 'scale'):
                v = tuple(round(x, 5) for x in getattr(o, prop)); k = (o.name, prop)
                if f == 0 or last.get(k) != v:
                    o.keyframe_insert(prop, frame=f); last[k] = v
        cam_d.dof.keyframe_insert('focus_distance', frame=f)
    for o in objs + [cam_d]:
        ad = o.animation_data
        if ad and ad.action:
            for fc in ad.action.fcurves:
                for k in fc.keyframe_points: k.interpolation = 'CONSTANT'

def track():
    out = []
    for f in range(NF):
        scene.frame_set(f)
        row = {}
        for nm, c in (('boy', boy), ('girl', girl)):
            p = c['head'].matrix_world @ Vector((0, 0, .85))
            v = world_to_camera_view(scene, cam, p); row[nm] = [round(v.x, 4), round(1 - v.y, 4)]
        out.append(row)
    json.dump(dict(fps=FPS, dur=DUR, scenes=S, frames=out), open(os.path.join(HERE, 'overlay_track.json'), 'w'))

bake()
track()
if '--save' in ARGS:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'kids_scene.blend'))
    print('SAVED blend')
i = 0
while i < len(ARGS):
    if ARGS[i] == '--still':
        t = float(ARGS[i + 1]); scene.frame_set(int(round(t * FPS)))
        pct = int(os.environ.get('PCT', '50')); r.resolution_percentage = pct
        r.filepath = os.path.join(os.environ.get('OUT', HERE), 'still_%05.2f.png' % t)
        bpy.ops.render.render(write_still=True); i += 2; continue
    if ARGS[i] == '--anim':
        r.resolution_percentage = int(os.environ.get('PCT', '67'))
        r.filepath = os.path.join(os.environ.get('OUT', HERE), 'f')
        r.image_settings.file_format = 'PNG'
        scene.frame_start = int(os.environ.get('START', '0')); scene.frame_end = int(os.environ.get('END', str(NF - 1)))
        bpy.ops.render.render(animation=True)
    i += 1
