"""Stock Blender startup and presentation updates for the upstream ReShade UI."""
import bpy

state={'redraws':0}

def redraw():
    # ReShade receives input and draws its overlay on presentation. Blender's
    # otherwise idle window must keep presenting, without changing scene data
    # or restarting Cycles accumulation.
    for window in bpy.context.window_manager.windows:
        screen=window.screen
        if screen and screen.areas:
            area=next((a for a in screen.areas if a.type=='VIEW_3D'),screen.areas[0])
            area.tag_redraw()
            state['redraws']+=1
    return .05

if not bpy.app.background:
    previous=getattr(bpy,'_dlss5_ready_redraw',None)
    if previous and bpy.app.timers.is_registered(previous):
        bpy.app.timers.unregister(previous)
    bpy._dlss5_ready_redraw=redraw
    bpy.app.timers.register(redraw,first_interval=.05,persistent=True)
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use=device.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='RENDERED'

