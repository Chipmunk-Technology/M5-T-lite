#pragma once

#include <stdint.h>

static const int SENSOR_EE_WORDS = 832;

struct SensorView {
    bool ready;
    bool complete;
    uint8_t subpage;
    float ta_c;
    float vdd_v;
    float temp_c[768];
    uint16_t ee[SENSOR_EE_WORDS];
};

// Scans the internal I2C bus once. Uses address 0x33 only.
// Chess mode, 8 Hz subpages (about 4 complete frames per second).
bool sensor_begin();
const SensorView* sensor_latest();
bool sensor_poll(float emissivity, float reflected_c, bool use_ta);
