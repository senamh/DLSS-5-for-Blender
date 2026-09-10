#include "stock_color.h"
#include <cassert>
#include <cmath>

int main() {
    for (float peak : {0.0f, 0.01f, 0.5f, 1.0f, 16.0f, 10000.0f}) {
        float input[3] = {peak, peak*0.2f, peak*0.05f}, proxy[3], output[3];
        stock_color::proxy(input, proxy);
        stock_color::compose(input, proxy, proxy, output);
        for (int c=0; c<3; ++c) {
            assert(proxy[c] >= 0 && proxy[c] < 1);
            assert(std::abs(output[c]-input[c]) <= 1e-4f*std::max(1.0f, peak));
        }
        float neural[3] = {proxy[0]*0.9f, proxy[1]*0.9f, proxy[2]*0.9f};
        stock_color::compose(input, proxy, neural, output);
        for (float c : output) assert(std::isfinite(c) && c >= 0);
        if (peak >= 16) assert(stock_color::luminance(output) > stock_color::luminance(input)*0.99f);
        float black[3] = {};
        stock_color::compose(input, proxy, black, output);
        for (int c=0; c<3; ++c) assert(output[c] == input[c]);
    }
}

