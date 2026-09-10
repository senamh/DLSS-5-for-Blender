"""Require intact inputs, correctly sized output and explicit NVIDIA NR evidence."""
import hashlib,json,re,struct,zlib
from pathlib import Path


def validate_payload(root):
    root=Path(root);meta=json.loads((root/'payload.json').read_text())
    if meta.get('schema')!=1:raise ValueError('Unsupported payload schema')
    w,h=meta['size']
    if type(w)!=int or type(h)!=int or not (96<=w<=4096 and 96<=h<=4096):
        raise ValueError('Invalid frame dimensions')
    if meta.get('origin')!='top-left' or meta.get('reset') is not True:
        raise ValueError('Unsupported frame origin/history contract')
    required={'color.rgba8','depth.f32','motion.f16'}
    if set(meta['files'])!=required:raise ValueError('Unexpected payload files')
    for name in required:
        data=(root/name).read_bytes();entry=meta['files'][name]
        if len(data)!=w*h*4 or entry['bytes']!=len(data):raise ValueError('Invalid byte count: '+name)
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Input checksum mismatch: '+name)
    return meta


def write_rgba_png(path,data,w,h):
    if len(data)!=w*h*4:raise ValueError('Wrong RGBA size')
    def chunk(kind,value):
        return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
    rows=b''.join(b'\0'+data[y*w*4:(y+1)*w*4] for y in range(h))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+
        chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


def verify(root,log_path,exit_code):
    root=Path(root);meta=validate_payload(root);w,h=meta['size']
    if exit_code!=0:raise ValueError(f'Host failed with exit code {exit_code}')
    output=(root/'ngx_output.rgba8').read_bytes()
    if len(output)!=w*h*4:raise ValueError('Output dimensions/byte count mismatch')
    log=Path(log_path).read_text(errors='replace')
    confirmations=re.findall(r'inline feature 18 evaluation succeeded[^\r\n]*',log)
    if not confirmations:raise ValueError('No explicit successful DLSS 5 NR evaluation in this run')
    source=(root/'color.rgba8').read_bytes()
    differences=[abs(a-b) for i,(a,b) in enumerate(zip(source,output)) if i%4!=3]
    report={'nr_confirmed':True,'size':[w,h],'mean_absolute_rgb_difference_8bit':sum(differences)/len(differences),
        'changed_rgb_channels':sum(d!=0 for d in differences),'confirmation':confirmations[-1],
        'input_sha256':hashlib.sha256(source).hexdigest(),'output_sha256':hashlib.sha256(output).hexdigest(),
        'quality_improvement_confirmed':False}
    # Preserve returned bytes exactly; no sharpening, grading or alpha replacement.
    write_rgba_png(root/'before.png',source,w,h);write_rgba_png(root/'after.png',output,w,h)
    (root/'verified-result.json').write_text(json.dumps(report,indent=2))
    return report

