"""Run the file host in a disposable directory using already installed runtimes."""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from verify_frame_result import validate_payload,verify


def main():
    out=Path('frame-gpu-evidence').resolve();out.mkdir(exist_ok=False)
    report={'nr_confirmed':False}
    root=None
    try:
        payload=Path('frame-payload').resolve();meta=validate_payload(payload);w,h=meta['size']
        gpu=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],
            capture_output=True,text=True,timeout=10,check=True)
        report['gpu']=gpu.stdout.strip()
        source=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'preview-5070-34216277728'
        # Use the already-tested local runtime set; never overwrite the working copy.
        expected={
            'opengl32.dll':('dxgi.dll','0cee63f9c9f13f3ac909c5b4903f4dbb4b719a7ab3b4f13b0deaf83c814b94f7'),
            'renodx-dlss5.addon64':('renodx-dlss5.addon64','a8b5e164cbc3222a5d62bbddf44a2cc68d359b0caf729e55f2877c49e73e9aac'),
            'nvngx_dlss.dll':('nvngx_dlss.dll','c85f971ce023c9f3492fc7455f0b01a24ba18ea39636407a846902c4360b0b7e'),
            'nvngx_dlssnr.dll':('nvngx_dlssnr.dll','4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05')}
        root=Path(tempfile.mkdtemp(prefix='cycles-frame-',dir=os.environ['RUNNER_TEMP']))
        for name,(dest,digest) in expected.items():
            if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Installed runtime version differs from validated set: '+name)
            shutil.copyfile(source/name,root/dest)
        shutil.copyfile(Path('compiled/host/dlss5-feed-host64.exe').resolve(),root/'dlss5-feed-host64.exe')
        work=root/'frame';shutil.copytree(payload,work)
        # Never allow a previous output or inherited log to pass verification.
        for name in ('ngx_output.rgba8','before.png','after.png','verified-result.json'):
            (work/name).unlink(missing_ok=True)
        (root/'ReShade.ini').write_text('[ADDON]\nAddonPath=.\\\n[RenoDX.DLSS5]\nEnableHooks=2\nNeuralUplift=1\nNREnableUpscaling=0\n')
        with (out/'console.log').open('w') as log:
            run=subprocess.run([str(root/'dlss5-feed-host64.exe'),'--frame',str(w),str(h),str(work)],
                cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=60)
        report.update(verify(work,root/'ReShade.log',run.returncode))
        for name in ('before.png','after.png','verified-result.json'):
            shutil.copyfile(work/name,out/name)
    except Exception as error:
        report['error']=str(error)
    finally:
        if root:
            for log in root.glob('*.log'):shutil.copyfile(log,out/log.name)
            shutil.rmtree(root,ignore_errors=True)
        (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    return 0 if report['nr_confirmed'] else 1

if __name__=='__main__':sys.exit(main())

