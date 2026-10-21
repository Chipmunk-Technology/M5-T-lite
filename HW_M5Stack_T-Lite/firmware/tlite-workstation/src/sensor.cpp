#include "sensor.h"

// Adafruit MLX90640 1.1.2 keeps DumpEE / CalculateTo as class methods.
// The access keyword is only a compile-time gate; the calls below are the
// same functions the library uses internally, with our emissivity and Ta.
#pragma push_macro("private")
#define private public
#include <Adafruit_MLX90640.h>
#pragma pop_macro("private")
#include <Wire.h>
#include <math.h>
#include <string.h>

static Adafruit_MLX90640 mlx;
static paramsMLX90640 params;
static uint16_t frame_data[834];
static SensorView view;
static bool begun = false;
static uint8_t seen_pages = 0;

static bool probe_mlx() {
    bool found = false;
    for (uint8_t addr = 1; addr < 127; ++addr) {
        Wire.beginTransmission(addr);
        uint8_t err = Wire.endTransmission();
        if (err == 0 && addr == 0x33) {
            found = true;
        }
    }
    return found;
}

bool sensor_begin() {
    memset(&view, 0, sizeof(view));
    for (int i = 0; i < 768; ++i) {
        view.temp_c[i] = NAN;
    }
    Wire.setClock(400000);
    Wire.setTimeOut(50);
    if (!probe_mlx()) {
        view.ready = false;
        return false;
    }
    if (!mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
        view.ready = false;
        return false;
    }
    mlx.setMode(MLX90640_CHESS);
    mlx.setRefreshRate(MLX90640_8_HZ);
    if (mlx.MLX90640_DumpEE(MLX90640_I2CADDR_DEFAULT, view.ee) != 0) {
        view.ready = false;
        return false;
    }
    if (mlx.MLX90640_ExtractParameters(view.ee, &params) != 0) {
        view.ready = false;
        return false;
    }
    begun = true;
    view.ready = true;
    return true;
}

const SensorView* sensor_latest() { return &view; }

bool sensor_poll(float emissivity, float reflected_c, bool use_ta) {
    if (!begun) {
        return false;
    }
    uint16_t status = 0;
    if (mlx.MLX90640_I2CRead(MLX90640_I2CADDR_DEFAULT, 0x8000, 1, &status) != 0) {
        view.complete = false;
        return false;
    }
    if ((status & 0x0008) == 0) {
        view.complete = false;
        return false;
    }
    int sub = mlx.MLX90640_GetFrameData(MLX90640_I2CADDR_DEFAULT, frame_data);
    if (sub < 0) {
        view.complete = false;
        return false;
    }
    view.subpage = (uint8_t)(sub & 1);
    view.ta_c = mlx.MLX90640_GetTa(frame_data, &params);
    view.vdd_v = mlx.MLX90640_GetVdd(frame_data, &params);
    float tr = use_ta ? view.ta_c : reflected_c;
    if (emissivity < 0.05f) {
        emissivity = 0.05f;
    }
    if (emissivity > 1.0f) {
        emissivity = 1.0f;
    }
    mlx.MLX90640_CalculateTo(frame_data, &params, emissivity, tr, view.temp_c);
    seen_pages = (uint8_t)(seen_pages | (1u << view.subpage));
    view.complete = (seen_pages & 0x03) == 0x03;
    if (view.complete) {
        for (int i = 0; i < 768; ++i) {
            if (isnan(view.temp_c[i])) {
                view.complete = false;
                break;
            }
        }
    }
    if (view.complete) {
        seen_pages = 0;
    }
    return true;
}
