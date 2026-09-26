# 3D Blender Development Skill

## Overview
Blender Python (bpy) automation for 3D modeling, scene composition, procedural generation, asset pipelines, and headless batch rendering.

## Blender Binary
```bash
/Applications/Blender.app/Contents/MacOS/Blender
```

## Common Patterns

### Headless Script Execution
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python script.py
```

### Scene Setup Template
```python
import bpy

# Clear default scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Add camera
bpy.ops.object.camera_add(location=(7, -6, 5))
cam = bpy.context.active_object
cam.rotation_euler = (1.1, 0, 0.8)
bpy.context.scene.camera = cam

# Add light
bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

# Set render settings
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.cycles.samples = 128
scene.render.filepath = '/tmp/render_output.png'
```

### Batch Rendering
```bash
# Render single frame
/Applications/Blender.app/Contents/MacOS/Blender --background scene.blend -o /tmp/output_ -f 1

# Render animation range
/Applications/Blender.app/Contents/MacOS/Blender --background scene.blend -o /tmp/output_ -s 1 -e 250 -a
```

### Export Formats
```python
# glTF export (web/game)
bpy.ops.export_scene.gltf(filepath='/tmp/model.glb', export_format='GLB')

# FBX export (interchange)
bpy.ops.export_scene.fbx(filepath='/tmp/model.fbx')

# USD export (production pipeline)
bpy.ops.wm.usd_export(filepath='/tmp/model.usd')
```

## Reference Documentation
- `global/docs/Blender_bpy_Patterns.md` — Core bpy patterns and conventions
- Context7 library: `/blender/blender` (10,999 snippets, trust score 10)

## Key Capabilities
- Procedural mesh generation (BMesh API)
- Geometry Nodes Python control
- Material/shader node creation
- Physics simulation setup (cloth, fluid, rigid body)
- Camera animation and keyframing
- Compositor node setup
- Asset library management
- LOD generation via decimate modifier
