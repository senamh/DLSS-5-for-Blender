// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <cmath>

namespace stock_color {
inline float luminance(const float* c) {
    return c[0]*0.2126f + c[1]*0.7152f + c[2]*0.0722f;
}
// Preserve chromatic ratios while making a bounded inference proxy.
inline void proxy(const float* original, float* result) {
    const float peak = std::max({0.0f, original[0], original[1], original[2]});
    for (int c=0; c<3; ++c) result[c] = std::max(0.0f, original[c])/(1.0f+peak);
}
// Experimental luminance transfer, independently implemented. This is not
// an exact RenoDX codec (in particular, it does not include OkLab hue correction).
inline void compose(const float* original, const float* input, const float* neural, float* out) {
    const float oy = luminance(original), py = luminance(input), ny = luminance(neural);
    if (ny <= 1e-5f) {
        for (int c=0; c<3; ++c) out[c] = original[c];
        return;
    }
    const float scale = oy < py ? std::max(0.0f, oy)/std::max(py, 1e-6f)
                               : 1.0f + std::max(0.0f, oy-py)/ny;
    for (int c=0; c<3; ++c) out[c] = neural[c]*scale;
}
}

