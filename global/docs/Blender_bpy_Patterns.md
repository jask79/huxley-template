# Blender Python API (bpy) Patterns

Reference doc for the 3D Developer agent. Covers common headless operations via `bpy` and `bmesh`.

**Blender version:** 4.0.2
**Path on this machine:** `/Applications/Blender.app/Contents/MacOS/Blender`
**Context7 library ID:** `/websites/blender_api_current`

---

## Execution Patterns

### Headless Script Execution
```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender

# Run script on empty scene
$BLENDER -b -P script.py

# Run script on existing .blend file
$BLENDER -b scene.blend -P script.py

# Render single frame
$BLENDER -b scene.blend -o //output/frame_ -F PNG -f 1

# Render animation (all frames)
$BLENDER -b scene.blend -o //output/frame_ -F PNG -a

# Render specific frame range
$BLENDER -b scene.blend -o //output/frame_ -F PNG -s 1 -e 120 -a

# Pass arguments to script (after --)
$BLENDER -b -P script.py -- --my-arg value
```

### Script Boilerplate
```python
import bpy
import sys

# Access arguments after --
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ... your scene setup ...

# Save .blend file
bpy.ops.wm.save_as_mainfile(filepath='/path/to/output.blend')
```

---

## Scene Management

### Clear Scene
```python
# Delete all objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Also clear orphaned data
for block in bpy.data.meshes:
    if block.users == 0:
        bpy.data.meshes.remove(block)
for block in bpy.data.materials:
    if block.users == 0:
        bpy.data.materials.remove(block)
```

### Collections
```python
# Create collection
col = bpy.data.collections.new("MyCollection")
bpy.context.scene.collection.children.link(col)

# Add object to collection
col.objects.link(obj)

# Remove from default collection
bpy.context.scene.collection.objects.unlink(obj)
```

---

## Primitive Creation (bpy.ops)

```python
# Cube
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

# Sphere (UV)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=16, location=(0, 0, 0))

# Sphere (Ico)
bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=3, location=(0, 0, 0))

# Cylinder
bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, vertices=32, location=(0, 0, 0))

# Cone
bpy.ops.mesh.primitive_cone_add(radius1=1, radius2=0, depth=2, vertices=32, location=(0, 0, 0))

# Plane
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))

# Torus
bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.25, major_segments=48, minor_segments=12)

# Grid
bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=2, location=(0, 0, 0))

# Get reference to just-created object
obj = bpy.context.active_object
obj.name = "MyObject"
```

---

## BMesh Operations (Advanced Geometry)

```python
import bmesh
import mathutils

# Create BMesh, manipulate, write to mesh
bm = bmesh.new()

# Create primitives in BMesh
bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=1.0, calc_uvs=True)
bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=1.0, radius2=0.5, depth=2.0, calc_uvs=True)
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0, calc_uvs=True)
bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0, calc_uvs=True)
bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=2.0, calc_uvs=True)

# Modify existing mesh
me = bpy.context.object.data
bm = bmesh.new()
bm.from_mesh(me)

for v in bm.verts:
    v.co.x += 1.0  # translate all verts

bm.to_mesh(me)
bm.free()

# BMesh transforms
bmesh.ops.translate(bm, verts=bm.verts, vec=(1.0, 0.0, 0.0))
bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                 matrix=mathutils.Matrix.Rotation(math.radians(45), 3, 'Z'))
bmesh.ops.scale(bm, verts=bm.verts, vec=(2.0, 2.0, 2.0))

# Boolean-like operations
bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:],
                        plane_co=(0,0,0), plane_no=(0,0,1), clear_outer=True)
bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.1)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bmesh.ops.symmetrize(bm, input=bm.verts[:]+bm.edges[:]+bm.faces[:], direction='X')

# Write BMesh to new mesh object
me = bpy.data.meshes.new("GeneratedMesh")
bm.to_mesh(me)
bm.free()
obj = bpy.data.objects.new("GeneratedObject", me)
bpy.context.collection.objects.link(obj)
```

---

## Modifiers

```python
obj = bpy.context.active_object

# Subdivision Surface
mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
mod.levels = 2          # viewport
mod.render_levels = 3   # render

# Mirror
mod = obj.modifiers.new(name="Mirror", type='MIRROR')
mod.use_axis = (True, False, False)

# Boolean
mod = obj.modifiers.new(name="Bool", type='BOOLEAN')
mod.operation = 'DIFFERENCE'  # UNION, INTERSECT, DIFFERENCE
mod.object = other_obj

# Array
mod = obj.modifiers.new(name="Array", type='ARRAY')
mod.count = 5
mod.relative_offset_displace = (1.0, 0.0, 0.0)

# Solidify
mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
mod.thickness = 0.02

# Bevel
mod = obj.modifiers.new(name="Bevel", type='BEVEL')
mod.width = 0.05
mod.segments = 3

# Decimate (LOD generation)
mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
mod.ratio = 0.5  # 50% reduction

# Apply modifier
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="Subsurf")
```

---

## Materials & Shader Nodes

### Basic PBR Material
```python
mat = bpy.data.materials.new(name="PBR_Material")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Clear defaults
nodes.clear()

# Create Principled BSDF + Output
output = nodes.new(type='ShaderNodeOutputMaterial')
output.location = (300, 0)

bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)

# Set PBR values
bsdf.inputs['Base Color'].default_value = (0.8, 0.2, 0.1, 1.0)  # RGBA
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.4
bsdf.inputs['IOR'].default_value = 1.45

# Link
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# Assign to object
obj.data.materials.append(mat)
```

### Image Texture
```python
tex_node = nodes.new(type='ShaderNodeTexImage')
tex_node.location = (-400, 0)
tex_node.image = bpy.data.images.load('/path/to/texture.png')
links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
```

### Procedural Noise Texture
```python
noise = nodes.new(type='ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 5.0
noise.inputs['Detail'].default_value = 2.0

coord = nodes.new(type='ShaderNodeTexCoord')
links.new(coord.outputs['Object'], noise.inputs['Vector'])
links.new(noise.outputs['Fac'], bsdf.inputs['Roughness'])
```

### Emission Material
```python
emission = nodes.new(type='ShaderNodeEmission')
emission.inputs['Color'].default_value = (1.0, 0.5, 0.0, 1.0)
emission.inputs['Strength'].default_value = 5.0
links.new(emission.outputs['Emission'], output.inputs['Surface'])
```

### Glass Material
```python
glass = nodes.new(type='ShaderNodeBsdfGlass')
glass.inputs['Color'].default_value = (0.9, 0.95, 1.0, 1.0)
glass.inputs['Roughness'].default_value = 0.0
glass.inputs['IOR'].default_value = 1.5
links.new(glass.outputs['BSDF'], output.inputs['Surface'])
```

---

## Lighting

```python
# Sun light
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.active_object.data
sun.energy = 3.0
sun.angle = 0.01  # sharpness

# Area light
bpy.ops.object.light_add(type='AREA', location=(3, -3, 5))
area = bpy.context.active_object.data
area.energy = 200
area.size = 2.0
area.shape = 'RECTANGLE'  # SQUARE, RECTANGLE, DISK, ELLIPSE

# Point light
bpy.ops.object.light_add(type='POINT', location=(0, 0, 3))
point = bpy.context.active_object.data
point.energy = 100
point.shadow_soft_size = 0.5

# Spot light
bpy.ops.object.light_add(type='SPOT', location=(0, -5, 5))
spot = bpy.context.active_object.data
spot.energy = 500
spot.spot_size = 0.785  # radians (45 degrees)
spot.spot_blend = 0.15

# HDRI environment
world = bpy.context.scene.world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()
bg = wnodes.new(type='ShaderNodeBackground')
env_tex = wnodes.new(type='ShaderNodeTexEnvironment')
env_tex.image = bpy.data.images.load('/path/to/hdri.hdr')
output = wnodes.new(type='ShaderNodeOutputWorld')
wlinks.new(env_tex.outputs['Color'], bg.inputs['Color'])
wlinks.new(bg.outputs['Background'], output.inputs['Surface'])
bg.inputs['Strength'].default_value = 1.0
```

### Three-Point Lighting Setup
```python
import math

def three_point_lighting(target=(0, 0, 0), distance=5, key_energy=300, fill_ratio=0.5, rim_ratio=0.8):
    """Standard three-point lighting rig."""
    # Key light (main, 45deg up and left)
    bpy.ops.object.light_add(type='AREA', location=(
        target[0] - distance * 0.7,
        target[1] - distance * 0.7,
        target[2] + distance * 0.7
    ))
    key = bpy.context.active_object
    key.name = "Key_Light"
    key.data.energy = key_energy
    key.data.size = 2.0
    constraint = key.constraints.new(type='TRACK_TO')
    constraint.target = bpy.data.objects.get("Target") or None

    # Fill light (opposite side, softer)
    bpy.ops.object.light_add(type='AREA', location=(
        target[0] + distance * 0.7,
        target[1] - distance * 0.5,
        target[2] + distance * 0.3
    ))
    fill = bpy.context.active_object
    fill.name = "Fill_Light"
    fill.data.energy = key_energy * fill_ratio
    fill.data.size = 3.0

    # Rim/back light (behind and above)
    bpy.ops.object.light_add(type='AREA', location=(
        target[0],
        target[1] + distance * 0.8,
        target[2] + distance * 0.6
    ))
    rim = bpy.context.active_object
    rim.name = "Rim_Light"
    rim.data.energy = key_energy * rim_ratio
    rim.data.size = 1.5
```

---

## Camera

```python
# Add camera
bpy.ops.object.camera_add(location=(7, -7, 5))
cam_obj = bpy.context.active_object
cam_obj.name = "MainCamera"

# Point at target
constraint = cam_obj.constraints.new(type='TRACK_TO')
constraint.target = bpy.data.objects["MyObject"]
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

# Camera settings
cam = cam_obj.data
cam.lens = 50           # focal length mm
cam.sensor_width = 36   # sensor size mm
cam.clip_start = 0.1
cam.clip_end = 1000

# Depth of field
cam.dof.use_dof = True
cam.dof.focus_object = bpy.data.objects["MyObject"]
cam.dof.aperture_fstop = 2.8

# Set as active camera
bpy.context.scene.camera = cam_obj
```

---

## Render Settings

### Cycles (Path Tracing)
```python
scene = bpy.context.scene
scene.render.engine = 'CYCLES'

# Device
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'  # macOS GPU
scene.cycles.device = 'GPU'

# Quality
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# Resolution
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

# Output
scene.render.filepath = '/path/to/output.png'
scene.render.image_settings.file_format = 'PNG'  # PNG, JPEG, OPEN_EXR, TIFF
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.compression = 15  # PNG compression 0-100

# Transparent background (for compositing)
scene.render.film_transparent = True

# Render
bpy.ops.render.render(write_still=True)
```

### EEVEE (Real-Time)
```python
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 64
scene.eevee.use_gtao = True           # ambient occlusion
scene.eevee.use_bloom = True          # bloom effect
scene.eevee.use_ssr = True            # screen space reflections
scene.eevee.use_ssr_refraction = True
```

### Animation Render
```python
scene.frame_start = 1
scene.frame_end = 250
scene.frame_step = 1
scene.render.fps = 24

# Output as image sequence
scene.render.filepath = '/path/to/frames/frame_'
scene.render.image_settings.file_format = 'PNG'

# Render animation
bpy.ops.render.render(animation=True)

# Or output as video
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
bpy.ops.render.render(animation=True)
```

---

## Animation & Keyframes

```python
obj = bpy.data.objects["MyObject"]

# Insert keyframes
obj.location = (0, 0, 0)
obj.keyframe_insert(data_path="location", frame=1)

obj.location = (5, 0, 3)
obj.keyframe_insert(data_path="location", frame=60)

obj.rotation_euler = (0, 0, 0)
obj.keyframe_insert(data_path="rotation_euler", frame=1)

obj.rotation_euler = (0, 0, 3.14159)
obj.keyframe_insert(data_path="rotation_euler", frame=60)

# Scale keyframes
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path="scale", frame=1)
obj.scale = (2, 2, 2)
obj.keyframe_insert(data_path="scale", frame=30)

# Material property keyframe
mat = obj.data.materials[0]
mat.node_tree.nodes["Principled BSDF"].inputs['Alpha'].default_value = 1.0
mat.node_tree.nodes["Principled BSDF"].inputs['Alpha'].keyframe_insert("default_value", frame=1)
mat.node_tree.nodes["Principled BSDF"].inputs['Alpha'].default_value = 0.0
mat.node_tree.nodes["Principled BSDF"].inputs['Alpha'].keyframe_insert("default_value", frame=60)
```

---

## Import / Export

```python
# Import
bpy.ops.import_scene.fbx(filepath='/path/to/model.fbx')
bpy.ops.import_scene.gltf(filepath='/path/to/model.glb')
bpy.ops.import_scene.obj(filepath='/path/to/model.obj')
bpy.ops.wm.usd_import(filepath='/path/to/model.usd')
bpy.ops.import_mesh.stl(filepath='/path/to/model.stl')

# Export
bpy.ops.export_scene.fbx(filepath='/path/to/output.fbx', use_selection=True)
bpy.ops.export_scene.gltf(filepath='/path/to/output.glb', export_format='GLB')  # GLB or GLTF_SEPARATE
bpy.ops.export_scene.obj(filepath='/path/to/output.obj', use_selection=True)
bpy.ops.wm.usd_export(filepath='/path/to/output.usdc')
bpy.ops.export_mesh.stl(filepath='/path/to/output.stl', use_selection=True)

# Export selected objects only
bpy.ops.export_scene.gltf(
    filepath='/path/to/output.glb',
    export_format='GLB',
    use_selection=True,
    export_apply=True  # apply modifiers
)
```

---

## Common Gotchas

1. **Context errors in headless mode**: Many `bpy.ops` require specific context. Use `bpy.context.view_layer.objects.active = obj` and `obj.select_set(True)` before operators that need selection.

2. **GPU rendering on macOS**: Use `'METAL'` not `'CUDA'` or `'OPTIX'` for `compute_device_type`. If GPU fails, fall back: `prefs.compute_device_type = 'NONE'` (CPU).

3. **BMesh must be freed**: Always call `bm.free()` after `bm.to_mesh()`. Forgetting this leaks memory.

4. **Modifier apply needs active object**: Set `bpy.context.view_layer.objects.active = obj` before `bpy.ops.object.modifier_apply()`.

5. **File paths in headless**: Use absolute paths. Relative `//` prefix resolves relative to `.blend` file location.

6. **Node tree access**: Always check `mat.use_nodes = True` before accessing `mat.node_tree`.

7. **Blender not in PATH**: Always use full path: `/Applications/Blender.app/Contents/MacOS/Blender`

8. **Image loading**: `bpy.data.images.load()` will raise if file doesn't exist. Check first.

9. **Addon availability**: Some operations require addons. Enable with: `bpy.ops.preferences.addon_enable(module='addon_name')`

10. **Render from script**: `bpy.ops.render.render(write_still=True)` writes a single frame. Use `animation=True` for sequences.
