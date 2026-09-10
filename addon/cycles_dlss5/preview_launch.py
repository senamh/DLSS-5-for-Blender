"""Compact controls for the current project's existing viewport."""
from pathlib import Path

import bpy
from .styles import draw_styles
from .final_render import draw_final


def viewport_source(context):
    """Prefer the clicked viewport; Render Properties may use another area."""
    if context.area and context.area.type == 'VIEW_3D':
        return context.window, context.area
    windows = [context.window] + [w for w in context.window_manager.windows if w != context.window]
    for window in windows:
        if window and window.scene == context.scene:
            area = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), None)
            if area:
                return window, area
    raise ValueError('Откройте хотя бы один 3D Viewport в текущей сцене')


class CYCLES_DLSS5_PT_preview_launcher(bpy.types.Panel):
    bl_idname = 'CYCLES_DLSS5_PT_preview_launcher'
    bl_label = 'DLSS 5'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DLSS 5'

    def draw(self, context):
        addon = context.preferences.addons.get(__package__)
        if addon is None:
            return
        draw_preview(self.layout, addon.preferences, context)


def draw_preview(layout, prefs, context):
    from . import viewport
    layout.prop(context.scene.dlss5_style, 'intensity', slider=True)
    if viewport._session is None:
        layout.operator('cycles_dlss5.viewport', icon='SHADING_RENDERED')
    else:
        percent = viewport._session.get('progress', 0)
        ready = viewport._session.get('phase') == 'READY'
        if ready:
            label = 'NR: готово — 100%'
        elif viewport._session.get('phase') == 'WAITING':
            label = 'NR: ожидание изменений · предыдущий кадр' if viewport._session.get('image') else 'NR: 0% · ожидание сцены'
        else:
            label = f'NR: {percent}% · этапы обработки'
        layout.progress(factor=percent / 100, type='BAR', text=label)
        layout.operator('cycles_dlss5.viewport_stop', icon='CANCEL')
    draw_final(layout, context)
    layout.prop(prefs, 'show_advanced', text='Дополнительно',
                icon='TRIA_DOWN' if prefs.show_advanced else 'TRIA_RIGHT', emboss=False)
    if not prefs.show_advanced:
        return
    layout = layout.box()
    draw_styles(layout, context, False)
    layout.prop(context.scene.dlss5_style, 'final_enabled')
    root = Path(bpy.app.binary_path).parent
    active = (root / 'opengl32.dll').is_file() and hasattr(bpy.types, 'DLSS5_OT_control')
    if active:
        layout.label(text='Управление DLSS Preview', icon='INFO')
        layout.operator('dlss5.control', text='Включить / выключить DLSS', icon='SHADING_RENDERED').action = 'TOGGLE'
        layout.operator('dlss5.control', text='Обновить после изменения окна', icon='FILE_REFRESH').action = 'RELOAD'
        layout.operator('dlss5.control', text='Открыть / закрыть настройки', icon='PREFERENCES').action = 'OVERLAY'
        layout.operator('dlss5.control', text='Снимок экрана с эффектом', icon='RENDER_STILL').action = 'SCREENSHOT'
        layout.label(text='Снимок сохраняет ReShade в свою папку Screenshots.')
        layout.label(text='Если меню ReShade блокирует кнопки — F8 закрывает его.')
    layout.prop(prefs, 'show_shortcut_help', text='Показать резервные клавиши', toggle=True)
    if prefs.show_shortcut_help:
        box = layout.box()
        for text in ('Курсор должен быть над 3D Viewport:',
                     'F6 — включить / выключить эффект',
                     'F7 — меню рендера с эффектом в файл',
                     'F8 — остановить NR и предпросмотр',
                     'F12 — рендер; затем DLSS, если включён флажок выше',
                     'Esc — отменить рендер; DLSS — кнопкой остановки',
                     'N — боковая панель; также View > Sidebar'):
            box.label(text=text)
        from .shortcuts import conflicts
        for key in conflicts:
            box.label(text=key + ' отключена: конфликт раскладки; используйте кнопку', icon='ERROR')
