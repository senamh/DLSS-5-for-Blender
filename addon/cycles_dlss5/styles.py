"""Scene-saved appearance controls for the installed neural consumer."""
import bpy
from .style_config import PRESETS, FIELDS


def values(settings):
    return {field: getattr(settings, field) for field in FIELDS}


class CYCLES_DLSS5_Style(bpy.types.PropertyGroup):
    final_enabled: bpy.props.BoolProperty(name='Применять DLSS после F12 (один кадр)', default=True,
        description='Отдельный SDR результат с настройками стиля; исходный Render Result и файл не заменяются')
    style: bpy.props.EnumProperty(name='Модельный стиль', default='0', items=(
        ('0', 'Default', 'Стандартный стиль runtime'),
        ('1', 'Natural (эксперимент)', 'Может заметно менять яркость и материалы')))
    intensity: bpy.props.FloatProperty(name='Сила эффекта', default=1, min=0, max=2,
        description='NRIntensity: параметр модели, не процент смешивания с оригиналом')
    tone: bpy.props.FloatProperty(name='Локальный тон', default=1, min=0, max=2)
    structure: bpy.props.FloatProperty(name='Структура', default=1, min=0, max=2)
    skin: bpy.props.FloatProperty(name='Структура кожи', default=-1, min=-1, max=2,
        description='-1 — значение по умолчанию библиотеки; не маска объектов Blender')
    auto_mask: bpy.props.BoolProperty(name='Автоматическая маска', default=False)
    show_details: bpy.props.BoolProperty(name='Ручные настройки', default=False)


class CYCLES_DLSS5_OT_style_preset(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.style_preset'
    bl_label = 'Выбрать пресет DLSS'
    bl_description = 'Общие параметры NR для предпросмотра и итогового рендера'
    bl_options = {'REGISTER', 'UNDO'}
    preset: bpy.props.EnumProperty(items=[(key, key, '') for key in PRESETS])

    def execute(self, context):
        settings = context.scene.dlss5_style
        for field, value in zip(FIELDS, PRESETS[self.preset]):
            setattr(settings, field, str(value) if field == 'style' else value)
        self.report({'INFO'}, 'Пресет выбран для viewport и рендера')
        return {'FINISHED'}


def draw_styles(layout, context, active):
    settings = context.scene.dlss5_style
    box = layout.box()
    box.label(text='Общий стиль: viewport и рендер')
    box.label(text='Одни параметры NR для обоих режимов.')
    for pair in ((('SOFT', 'Мягкий'), ('BALANCED', 'Сброс / базовый')),
                 (('FILM', 'Кино-тон'), ('STRONG', 'Выразительный'))):
        row = box.row(align=True)
        for key, label in pair:
            row.operator('cycles_dlss5.style_preset', text=label).preset = key
    box.prop(settings, 'show_details', toggle=True)
    if settings.show_details:
        box.prop(settings, 'style')
        for field in ('tone', 'structure', 'skin'):
            box.prop(settings, field, slider=True)
        box.prop(settings, 'auto_mask')
        box.label(text='Кожа: -1 = по умолчанию runtime')
        box.label(text='Cinematic отключён: риск сбоя runtime.')
