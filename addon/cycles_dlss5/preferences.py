"""Persistent extension settings."""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty


class CYCLES_DLSS5_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    preview_blender: StringProperty(name='DLSS Preview Blender', subtype='FILE_PATH',
        description='Existing preview blender.exe; blank uses the known local RTX 5070 installation')
    preview_status: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})
    final_status: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})
    show_shortcut_help: BoolProperty(name='Показать резервные клавиши', default=False)
    experimental_native_session: BoolProperty(name='Постоянная сессия NR (эксперимент)', default=False,
        description='Другая модель runtime, только SDR. Для смены режима остановите и запустите предпросмотр заново')
    setup_status: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})

    frame_host: StringProperty(name='Frame Host', subtype='FILE_PATH',
        description='Compiled dlss5-feed-host64.exe with the --frame adapter')
    frame_runtime_directory: StringProperty(name='Папка runtime', subtype='DIR_PATH',
        description='Existing tested ReShade, RenoDX and NVIDIA runtime set; copied into an isolated job')

    runtime_directory: StringProperty(
        name="NVIDIA NGX Runtime",
        description="Folder containing the legally obtained nvngx_dlssnr.dll",
        subtype="DIR_PATH",
    )

    bridge_path: StringProperty(
        name="Native Bridge DLL",
        description="Absolute path to the locally built dlss5nr_bridge.dll",
        subtype="FILE_PATH",
    )

    allow_unrecognized_runtime: BoolProperty(
        name="Allow Unrecognized Runtime",
        description="Permit a DLL whose SHA-256 fingerprint is not in the project allowlist",
        default=False,
    )

    diagnostic_summary: StringProperty(default="Not checked", options={"HIDDEN"})
    show_advanced: BoolProperty(name="Advanced", default=False)
    preview_auto: BoolProperty(name='Continuous capture (may flicker)', default=False,
        description='Experimental screen capture briefly hides the result on each update')
    preview_width: EnumProperty(name='Preview Width', default='960', items=(
        ('640', '640 px', 'Small preview'), ('960', '960 px', 'Balanced preview size'),
        ('1280', '1280 px', 'Larger preview'), ('0', 'Full', 'Full viewport resolution')))
    preview_compare: EnumProperty(name='Compare', default='SPLIT', items=(
        ('SPLIT', 'Original | DLSS', 'Left: original capture; right: processed same frame'),
        ('DLSS', 'DLSS', 'Processed capture only'), ('ORIGINAL', 'Original', 'Original capture only')))
    output_order: EnumProperty(
        name='Runtime Output Channels',
        items=(('RGB', 'RGB', 'Red, green, blue'), ('BGR', 'BGR', 'Blue, green, red')),
        default='RGB',
    )
    probe_report: StringProperty(name='Runtime Test Report', subtype='FILE_PATH')
    allow_experimental_color: BoolProperty(
        name='Allow Experimental Color Processing', default=False,
        description='Reinhard/sRGB processing may change highlights; not certified for HDR/EXR masters',
    )
    detected_gpu: StringProperty(default="Unknown", options={"HIDDEN"})
    runtime_sha256: StringProperty(default="", options={"HIDDEN"})

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text='Панель: 3D Viewport → DLSS 5. Обработка итогового кадра.')
        layout.prop(self, 'frame_runtime_directory')
        layout.operator('cycles_dlss5.setup_check', icon='CHECKMARK')
        layout.operator('wm.url_open', text='Установка и совместимость').url = 'https://github.com/senamh/DLSS-5-for-Blender/blob/main/docs/QUICK_START.md'
        if self.setup_status:
            import textwrap
            for line in self.setup_status.splitlines():
                for part in textwrap.wrap(line, 85):
                    layout.label(text=part)
        layout.prop(self, 'show_advanced', text='Дополнительно')
        if not self.show_advanced:
            return
        layout.prop(self, 'frame_host')
        layout.prop(self, 'experimental_native_session')
        if self.experimental_native_session:
            layout.prop(self, 'bridge_path')
            layout.prop(self, 'runtime_directory')
            layout.label(text='Только проверенный комплект. После переключения перезапустите предпросмотр.')
        layout.label(text='Пустые пути: комплект аддона или LOCALAPPDATA/DLSS-Blender/runtime.')
