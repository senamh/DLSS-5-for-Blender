// File input adapter for pinned upstream DLSS5-Feeder host. No neural/color implementation.
#include <cmath>
static const char *g_frame_dir = nullptr;
static UINT g_frame_w = 0, g_frame_h = 0;
static bool g_validate_frame = false;

static bool FrameRead(const char *name, size_t size, std::vector<unsigned char> &data)
{
    std::string path = std::string(g_frame_dir) + "/" + name;
    FILE *f = nullptr;
    if (fopen_s(&f, path.c_str(), "rb") || !f) return false;
    data.resize(size);
    bool ok = fread(data.data(), 1, size, f) == size && fgetc(f) == EOF;
    fclose(f); return ok;
}
static bool FrameLoad(std::vector<unsigned char> &color, std::vector<unsigned char> &depth,
                      std::vector<unsigned char> &motion)
{
    if (!g_frame_dir || g_frame_w < 96 || g_frame_h < 96 || g_frame_w > 4096 || g_frame_h > 4096)
    { Log("[frame] supported dimensions: 96..4096 on each side"); return false; }
    const size_t pixels = size_t(g_frame_w) * g_frame_h;
    if (!FrameRead("color.rgba8", pixels*4, color) || !FrameRead("depth.f32", pixels*4, depth) ||
        !FrameRead("motion.f16", pixels*4, motion))
    { Log("[frame] missing file or incorrect byte count"); return false; }
    for (size_t i=0; i<pixels; ++i)
    {
        float z; memcpy(&z, depth.data()+4*i, 4);
        if (!std::isfinite(z) || z<0 || z>1) { Log("[frame] invalid device depth"); return false; }
    }
    // First version is deliberately a still-frame adapter. Animated guides need a
    // separate timing/direction validation, not an assumed four-to-two channel cast.
    for (unsigned char b : motion) if (b != 0)
    { Log("[frame] temporal/animated input is not supported by this still adapter"); return false; }
    Log("[frame] validated %ux%u: Blender display RGBA8, normal device depth R32F, static RG16F",
        g_frame_w, g_frame_h);
    return true;
}
static ID3D12Resource *FrameBuffer(UINT64 size, D3D12_HEAP_TYPE type)
{
    D3D12_HEAP_PROPERTIES hp={}; hp.Type=type;
    D3D12_RESOURCE_DESC rd={}; rd.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; rd.Width=size;
    rd.Height=1; rd.DepthOrArraySize=1; rd.MipLevels=1; rd.SampleDesc.Count=1;
    rd.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    ID3D12Resource *r=nullptr;
    const auto state=type==D3D12_HEAP_TYPE_UPLOAD?D3D12_RESOURCE_STATE_GENERIC_READ:D3D12_RESOURCE_STATE_COPY_DEST;
    if (FAILED(h.dev->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&rd,state,nullptr,
        __uuidof(ID3D12Resource),reinterpret_cast<void **>(&r)))) return nullptr;
    return r;
}
static void FrameBarrier(ID3D12Resource *r,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after)
{
    D3D12_RESOURCE_BARRIER b={}; b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    b.Transition.pResource=r; b.Transition.StateBefore=before; b.Transition.StateAfter=after;
    b.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    h.list->ResourceBarrier(1,&b);
}
static bool FrameUpload(ID3D12Resource *texture,const std::vector<unsigned char> &bytes)
{
    auto desc=texture->GetDesc(); D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp={}; UINT64 size=0;
    h.dev->GetCopyableFootprints(&desc,0,1,0,&fp,nullptr,nullptr,&size);
    ID3D12Resource *upload=FrameBuffer(size,D3D12_HEAP_TYPE_UPLOAD);
    if (!upload) return false;
    void *mapped=nullptr; D3D12_RANGE none={0,0};
    if (FAILED(upload->Map(0,&none,&mapped))) { upload->Release(); return false; }
    memset(mapped,0,size_t(size));
    for (UINT y=0;y<g_frame_h;++y)
        memcpy(static_cast<unsigned char *>(mapped)+size_t(y)*fp.Footprint.RowPitch,
               bytes.data()+size_t(y)*g_frame_w*4,size_t(g_frame_w)*4);
    upload->Unmap(0,nullptr);
    if (!BeginCommands()) { upload->Release(); return false; }
    FrameBarrier(texture,D3D12_RESOURCE_STATE_COMMON,D3D12_RESOURCE_STATE_COPY_DEST);
    D3D12_TEXTURE_COPY_LOCATION src={}; src.pResource=upload;
    src.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; src.PlacedFootprint=fp;
    D3D12_TEXTURE_COPY_LOCATION dst={}; dst.pResource=texture; dst.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    h.list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);
    FrameBarrier(texture,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    bool ok=WaitFenceValue(h.fence,EndCommands(),5000);
    if (ok) upload->Release(); // On timeout keep in-flight memory alive until process exit.
    return ok;
}
static bool FrameSave(ID3D12Resource *texture)
{
    auto desc=texture->GetDesc(); D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp={}; UINT64 size=0;
    h.dev->GetCopyableFootprints(&desc,0,1,0,&fp,nullptr,nullptr,&size);
    ID3D12Resource *readback=FrameBuffer(size,D3D12_HEAP_TYPE_READBACK);
    if (!readback) return false;
    if (!BeginCommands()) { readback->Release(); return false; }
    FrameBarrier(texture,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);
    D3D12_TEXTURE_COPY_LOCATION src={}; src.pResource=texture; src.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    D3D12_TEXTURE_COPY_LOCATION dst={}; dst.pResource=readback;
    dst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; dst.PlacedFootprint=fp;
    h.list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);
    if (!WaitFenceValue(h.fence,EndCommands(),5000)) return false;
    void *mapped=nullptr;
    if (FAILED(readback->Map(0,nullptr,&mapped))) { readback->Release(); return false; }
    std::string path=std::string(g_frame_dir)+"/ngx_output.rgba8";
    FILE *f=nullptr; bool ok=fopen_s(&f,path.c_str(),"wb")==0 && f;
    if (f) {
        for (UINT y=0;y<g_frame_h;++y)
            if (fwrite(static_cast<unsigned char *>(mapped)+size_t(y)*fp.Footprint.RowPitch,4,g_frame_w,f)!=g_frame_w) ok=false;
        if (fclose(f)) ok=false;
    }
    D3D12_RANGE none={0,0}; readback->Unmap(0,&none); readback->Release(); return ok;
}
static int RunFrame()
{
    std::vector<unsigned char> color_bytes,depth_bytes,motion_bytes;
    if (!FrameLoad(color_bytes,depth_bytes,motion_bytes)) return 1;
    if (g_validate_frame) return 0; // Does not create a device or claim NVIDIA execution.
    if (!g_renodx_present) { Log("[frame] RenoDX required; refusing silent SR-only fallback"); return 1; }
    ID3D12Resource *color=MakeTex(g_frame_w,g_frame_h,DXGI_FORMAT_R8G8B8A8_UNORM,false);
    ID3D12Resource *depth=MakeTex(g_frame_w,g_frame_h,DXGI_FORMAT_R32_FLOAT,false);
    ID3D12Resource *motion=MakeTex(g_frame_w,g_frame_h,DXGI_FORMAT_R16G16_FLOAT,false);
    ID3D12Resource *output=MakeTex(g_frame_w,g_frame_h,DXGI_FORMAT_R8G8B8A8_UNORM,true);
    if (!color || !depth || !motion || !output) return 1;
    if (!FrameUpload(color,color_bytes) || !FrameUpload(depth,depth_bytes) || !FrameUpload(motion,motion_bytes)) return 1;
    for (int i=0;i<120;++i) { PumpPresent(true); Sleep(8); }
    NVSDK_NGX_Result result=NVSDK_NGX_Result_Fail;
    int flags=NVSDK_NGX_DLSS_Feature_Flags_MVLowRes | NVSDK_NGX_DLSS_Feature_Flags_AutoExposure;
    if (!CreateFeature(g_frame_w,g_frame_h,flags,&result) || !BeginCommands()) return 1;
    FrameBarrier(output,D3D12_RESOURCE_STATE_COMMON,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    if (!WaitFenceValue(h.fence,EndCommands(),5000)) return 1;
    if (!Evaluate(color,output,depth,motion,g_frame_w,g_frame_h,1,1.0f,1.0f) ||
        !WaitFenceValue(h.fence,h.fence_value,5000) || !FrameSave(output)) return 1;
    Log("[frame] NGX output written. Feature 18 success in RenoDX log MUST independently confirm DLSS 5.");
    return 0;
}

