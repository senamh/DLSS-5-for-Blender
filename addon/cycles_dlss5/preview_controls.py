"""Button transport and narrow migration of the preview's ReShade bindings.

F22-F24 are internal button transports, not advertised user shortcuts. The native
ReShade bridge still uses synthetic window messages; this is not a direct GPU API.
"""
import re

ACTION_KEYS = {'TOGGLE': 135, 'RELOAD': 134, 'SCREENSHOT': 133, 'OVERLAY': 119}


def _replace_key(text, section, key, value):
    lines = text.splitlines()
    start = 0 if section is None else next((i + 1 for i, line in enumerate(lines)
                                         if line.strip() == '[' + section + ']'), None)
    if start is None:
        lines.extend(['', '[' + section + ']'])
        start = len(lines)
    end = next((i for i in range(start, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
    pattern = re.compile(r'^\s*' + re.escape(key) + r'\s*=')
    matches = [i for i in range(start, end) if pattern.match(lines[i])]
    if matches:
        for i in reversed(matches[1:]):
            del lines[i]
        lines[matches[0]] = key + '=' + value
    else:
        lines.insert(end, key + '=' + value)
    return '\n'.join(lines) + '\n'


def migrate_bindings(config, preset):
    for key, action in (('KeyReload', 'RELOAD'), ('KeyScreenshot', 'SCREENSHOT'), ('KeyOverlay', 'OVERLAY')):
        config = _replace_key(config, 'INPUT', key, f'{ACTION_KEYS[action]},0,0,0')
    preset = _replace_key(preset, None, 'KeyDLSS5_Feed@DLSS5_Feed.fx', f'{ACTION_KEYS["TOGGLE"]},0,0,0')
    return config, preset
