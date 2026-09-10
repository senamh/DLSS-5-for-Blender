"""Patch only OpenGL resource lookup; neural/color/shader algorithms stay upstream."""
from pathlib import Path
import sys

path=Path(sys.argv[1])
text=path.read_text()
start=text.index('static void FeedFrameGl(')
end=text.find('\nstatic ',start+10)
assert end>start
section=text[start:end]
for old,new in [
    ('const resource mv_res    =','resource mv_res    ='),
    ('const resource depth_res =','resource depth_res ='),
    ('const resource_desc md =','resource_desc md ='),
    ('const resource_desc dd =','resource_desc dd ='),
]:
    assert section.count(old)==1,old
    section=section.replace(old,new,1)
needle='    const UINT w = cd.texture.width, h = cd.texture.height;'
assert section.count(needle)==1
patch='''
    // Compatibility guard for stale view-to-parent associations in the OpenGL
    // interposer. Effect-owned GL_TEXTURE_2D views are texture objects themselves.
    // Use the actual view object only when its dimensions AND formats match the
    // exact upstream full-resolution MV/depth contract. Never rescale or invent
    // guides to get past validation. Other APIs and valid mappings are unchanged.
    if (md.texture.width != w || md.texture.height != h ||
        dd.texture.width != w || dd.texture.height != h ||
        md.texture.format != format::r16g16_float || dd.texture.format != format::r32_float)
    {
        const resource raw_mv = { mv_srv.handle };
        const resource raw_depth = { d_srv.handle };
        if (FeedGlHandleType(raw_mv.handle) == GL_TEXTURE_2D &&
            FeedGlHandleType(raw_depth.handle) == GL_TEXTURE_2D)
        {
            const resource_desc rm = dev_api->get_resource_desc(raw_mv);
            const resource_desc rd = dev_api->get_resource_desc(raw_depth);
            static bool reported_view_probe = false;
            if (!reported_view_probe)
            {
                reported_view_probe = true;
                Log("[gl-view-probe] mapped MV %ux%u fmt=%u depth %ux%u fmt=%u; raw MV %ux%u fmt=%u depth %ux%u fmt=%u",
                    md.texture.width, md.texture.height, (unsigned)md.texture.format,
                    dd.texture.width, dd.texture.height, (unsigned)dd.texture.format,
                    rm.texture.width, rm.texture.height, (unsigned)rm.texture.format,
                    rd.texture.width, rd.texture.height, (unsigned)rd.texture.format);
            }
            if (rm.texture.width == w && rm.texture.height == h &&
                rd.texture.width == w && rd.texture.height == h &&
                rm.texture.format == format::r16g16_float && rd.texture.format == format::r32_float &&
                rm.texture.samples == 1 && rd.texture.samples == 1)
            {
                mv_res = raw_mv;
                depth_res = raw_depth;
                md = rm;
                dd = rd;
                static bool reported_view_fix = false;
                if (!reported_view_fix)
                {
                    reported_view_fix = true;
                    Log("[gl-view-fix] using validated full-size OpenGL effect views; stale parent mapping bypassed");
                }
            }
        }
    }
'''
section=section.replace(needle,needle+'\n'+patch,1)
path.write_text(text[:start]+section+text[end:])
print('Applied guarded OpenGL view lookup compatibility patch')

