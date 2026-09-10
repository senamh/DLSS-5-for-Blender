"""Blender output settings, explicit destination selection, no silent HDR downgrade."""
from pathlib import Path
import tempfile
import bpy

FORMATS = {'PNG', 'JPEG', 'TIFF', 'BMP', 'TARGA', 'TARGA_RAW', 'WEBP'}
FIELDS = ('file_format', 'color_mode', 'color_depth', 'compression', 'quality', 'tiff_codec')


def snapshot(scene, destination='VIEWPORT'):
    image = scene.render.image_settings
    if destination not in {'VIEWPORT', 'BOTH', 'DISK'}:
        raise ValueError('Неизвестное назначение вывода')
    if scene.render.filepath.startswith('//') and not bpy.data.filepath and destination != 'VIEWPORT':
        raise ValueError('Для относительного пути // сначала сохраните .blend или выберите абсолютную папку')
    if scene.render.is_movie_format or scene.render.use_multiview:
        raise ValueError('Поддерживается один кадр; видео и multiview пока не поддержаны')
    if image.file_format not in FORMATS or image.media_type != 'IMAGE':
        raise ValueError('NR пока SDR: выберите PNG, JPEG, TIFF, BMP, Targa или WebP; HDR/EXR не поддержаны')
    if scene.display_settings.display_device != 'sRGB':
        raise ValueError('NR пока поддерживает только sRGB SDR')
    result = {field: getattr(image, field) for field in FIELDS if hasattr(image, field)}
    result.update(destination=destination, path=bpy.path.abspath(scene.render.frame_path(frame=scene.frame_current)))
    if destination in {'BOTH', 'DISK'}:
        target = Path(result['path'])
        if not target.is_absolute():
            raise ValueError('Выберите абсолютную папку вывода; для // сначала сохраните .blend')
        if target.exists():
            raise ValueError('Файл уже существует: выберите другое имя или папку')
        if not target.parent.is_dir():
            raise ValueError('Папка вывода не существует: выберите её кнопкой папки')
    return result


def save(image, config, path=None):
    """Encode already display-mapped NR with Blender's format/quality/alpha settings."""
    destination = Path(path or config['path'])
    if not destination.is_absolute() or not destination.parent.is_dir():
        raise ValueError('Выберите существующую абсолютную папку вывода')
    # A disposable settings scene prevents edits to the artist's color management.
    scene = bpy.data.scenes.new('DLSS Output Settings (temporary)')
    try:
        scene.render.image_settings.media_type = 'IMAGE'
        for field in FIELDS:
            if field in config:
                setattr(scene.render.image_settings, field, config[field])
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.view_settings.use_curve_mapping = False
        with tempfile.TemporaryDirectory(prefix='dlss5-encoded-', ignore_cleanup_errors=True) as folder:
            temporary = Path(folder) / ('result' + scene.render.file_extension)
            image.save_render(str(temporary), scene=scene)
            data = temporary.read_bytes()
            # Exclusive creation also protects against a file appearing during NR.
            with destination.open('xb') as stream:
                stream.write(data)
        return destination
    finally:
        bpy.data.scenes.remove(scene)


class CYCLES_DLSS5_OT_output_folder(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.output_folder'
    bl_label = 'Выбрать папку рендера'
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context, event):
        self.directory = str(Path(bpy.path.abspath(context.scene.render.filepath)).parent)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        folder = Path(bpy.path.abspath(self.directory))
        if not folder.is_absolute() or not folder.is_dir():
            self.report({'ERROR'}, 'Выберите существующую папку')
            return {'CANCELLED'}
        previous = context.scene.render.filepath
        prefix = Path(previous).name if not previous.endswith(('/', '\\')) else 'DLSS-'
        if prefix in {'', '.', '..'}:
            prefix = 'DLSS-'
        context.scene.render.filepath = str(folder / prefix)
        return {'FINISHED'}


def draw(layout, scene):
    layout.label(text='Вывод: только файл')
    row = layout.row(align=True)
    row.prop(scene.render, 'filepath', text='Путь / имя')
    row.operator_context = 'INVOKE_DEFAULT'
    row.operator('cycles_dlss5.output_folder', text='Папка')
    layout.label(text='Файл: ' + Path(scene.render.frame_path(frame=scene.frame_current)).name)
    layout.prop(scene.render.image_settings, 'file_format', text='Формат Blender')
    layout.prop(scene.render.image_settings, 'color_mode', text='Каналы')
    layout.prop(scene.render.image_settings, 'color_depth', text='Глубина')
    if scene.render.image_settings.file_format in {'JPEG', 'WEBP'}:
        layout.prop(scene.render.image_settings, 'quality', text='Качество')
    elif scene.render.image_settings.file_format == 'PNG':
        layout.prop(scene.render.image_settings, 'compression', text='Сжатие')
    layout.label(text='NR: SDR 8-bit; HDR/EXR и видео не поддержаны.')
