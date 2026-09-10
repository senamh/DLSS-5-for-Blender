"""An owned Image Editor window; never cover or change the source viewport."""
import bpy

_window = None
_area = None


def forget():
    global _window, _area
    _window = _area = None


def show(context, image):
    global _window, _area
    try:
        reuse = (_window in list(context.window_manager.windows)
                 and _area in list(_window.screen.areas) and _area.type == 'IMAGE_EDITOR')
    except (ReferenceError, AttributeError):
        reuse = False
    if not reuse:
        window = context.window
        if window is None:
            raise ValueError('Откройте результат из окна Blender')
        area = context.area or next(iter(window.screen.areas), None)
        if area is None:
            raise ValueError('Откройте результат из окна Blender')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        before = {w.as_pointer() for w in context.window_manager.windows}
        with context.temp_override(window=window, area=area, region=region):
            result = bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        if result != {'FINISHED'}:
            raise ValueError('Не удалось открыть Image Editor')
        created = [w for w in context.window_manager.windows if w.as_pointer() not in before]
        if len(created) != 1:
            raise ValueError('Не удалось определить окно результата')
        _window = created[0]
        _window.scene = context.scene
        _area = _window.screen.areas[0]
        # Only the newly created editor changes type. Original viewport is intact.
        with context.temp_override(window=_window, area=_area):
            _area.type = 'IMAGE_EDITOR'
    with context.temp_override(window=_window, area=_area):
        _area.spaces.active.image = image
        _area.spaces.active.mode = 'VIEW'
        region = next(r for r in _area.regions if r.type == 'WINDOW')
        with context.temp_override(region=region):
            bpy.ops.image.view_all(fit_view=True)
        _area.tag_redraw()
    return True
