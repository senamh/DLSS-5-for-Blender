#pragma once

#include <stddef.h>

#if defined(_WIN32)
#  define CDLSS5_API __declspec(dllexport)
#else
#  define CDLSS5_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Actual bridge ABI: packed RGB, depth float/pixel, motion two floats/pixel. */
CDLSS5_API const char *dlss5nr_version(void);
CDLSS5_API const char *dlss5nr_abi_info(void);
CDLSS5_API const char *dlss5nr_gpu_name(void);
CDLSS5_API int dlss5nr_color_codec_version(void);
CDLSS5_API int dlss5nr_init(int gpu_index, const wchar_t *runtime_dir,
                          char *err, int err_cap);
CDLSS5_API int dlss5nr_process(
    const float *rgb_in, float *rgb_out, int width, int height,
    int style, int preset, float intensity, float tone, float structure,
    float skin, int automask, int reset, char *err, int err_cap);
CDLSS5_API int dlss5nr_process_guided(
    const float *rgb_in, float *rgb_out, const float *depth_in,
    const float *motion_in, int width, int height,
    int style, int preset, float intensity, float tone, float structure,
    float skin, int automask, int reset, char *err, int err_cap);
CDLSS5_API void dlss5nr_shutdown(void);

#ifdef __cplusplus
}
#endif

