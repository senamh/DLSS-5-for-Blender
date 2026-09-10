"""Appearance values and isolated ReShade profiles; no Blender dependency."""
import configparser
import io
import math
from pathlib import Path
import shutil

# Project presets, NOT settings copied from a video or calibrated quality levels.
PRESETS = {
    'SOFT': (0, .65, .55, .70, -1., True),
    'BALANCED': (0, 1., 1., 1., -1., False),
    'FILM': (0, 1.15, 1.15, 1.10, .75, True),
    'STRONG': (0, 1.50, 1.35, 1.50, 1., True),
}
FIELDS = ('style', 'intensity', 'tone', 'structure', 'skin', 'auto_mask')
KEYS = ('NRStyle', 'NRIntensity', 'NRLocalTone', 'NRLocalStructure', 'NRSkinStructure', 'NRAutoMask')


def native_values(values):
    if set(values) != set(FIELDS):
        raise ValueError('Incomplete style settings')
    if str(values['style']) not in ('0', '1'):
        raise ValueError('This preview supports Default / Natural only; Cinematic is disabled for stability')
    result = {'NRStyle': str(values['style'])}
    for field, key in zip(FIELDS[1:5], KEYS[1:5]):
        value = float(values[field])
        minimum = -1 if field == 'skin' else 0
        if not math.isfinite(value) or not minimum <= value <= 2:
            raise ValueError('Out-of-range style setting: ' + field)
        result[key] = format(value, '.6f')
    if not isinstance(values['auto_mask'], bool):
        raise ValueError('auto_mask must be a boolean')
    result['NRAutoMask'] = '1' if values['auto_mask'] else '0'
    return result


def parse_ini(text):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read_string(text.lstrip('\ufeff'))
    return parser


def build_config(text, runtime, folder, values):
    """Remap relative resources; never edit the installed configuration."""
    runtime, folder = Path(runtime).resolve(), Path(folder).resolve()
    config = parse_ini(text)
    if config.get('INSTALL', 'BasePath', fallback='').strip():
        raise ValueError('ReShade INSTALL BasePath overrides session profiles; use a preview without this override')
    def put(section, key, value):
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, key, str(value))
    put('ADDON', 'AddonPath', runtime)
    for key, fallback in (('EffectSearchPaths', 'reshade-shaders/Shaders/**'),
                          ('TextureSearchPaths', 'reshade-shaders/Textures/**')):
        paths = config.get('GENERAL', key, fallback=fallback).split(',')
        put('GENERAL', key, ','.join(str(runtime / p.strip()) for p in paths if p.strip()))
    put('GENERAL', 'PresetPath', folder / 'ReShadePreset.ini')
    put('GENERAL', 'StartupPresetPath', '')
    put('GENERAL', 'IntermediateCachePath', folder / 'cache')
    put('SCREENSHOT', 'SavePath', folder / 'Screenshots')
    # A source screenshot command must not unexpectedly execute in a new session.
    put('SCREENSHOT', 'PostSaveCommand', '')
    for key, value in {'EnableHooks': '2', 'NeuralUplift': '1', 'NREnableUpscaling': '0', 'NRPreset': '0',
                       **native_values(values)}.items():
        put('RenoDX.DLSS5', key, value)
    output = io.StringIO()
    config.write(output, space_around_delimiters=False)
    return output.getvalue()


def prepare_profile(runtime, folder, values):
    runtime, folder = Path(runtime), Path(folder)
    # Reject unsupported injectors before claiming isolated settings will be used.
    if 'RESHADE_BASE_PATH_OVERRIDE'.encode('utf-16-le') not in (runtime / 'opengl32.dll').read_bytes():
        raise ValueError('This ReShade build does not support isolated style profiles')
    text = build_config((runtime / 'ReShade.ini').read_text(encoding='utf-8-sig'), runtime, folder, values)
    (folder / 'ReShade.ini').write_text(text, encoding='utf-8')
    shutil.copyfile(runtime / 'ReShadePreset.ini', folder / 'ReShadePreset.ini')
    (folder / 'Screenshots').mkdir(exist_ok=True)
    return folder
