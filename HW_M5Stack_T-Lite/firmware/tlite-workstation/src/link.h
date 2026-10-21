#pragma once

#include "proto.h"
#include "sensor.h"

#include <stdint.h>

struct LiveFrame {
    uint8_t flags;
    uint32_t seq;
    uint32_t time_ms;
    int16_t ta_cdeg;
    int16_t vdd_cv;
    uint16_t emissivity_milli;
    int16_t reflected_cdeg;
    int16_t sentry_peak_cdeg;
    uint16_t sentry_cells;
    uint8_t sensitivity;
    uint8_t battery_pct;
    uint8_t work;
    uint8_t quiet_minutes;
    uint16_t event_age_s;
    const int16_t* pixels;
};

struct HostCommand {
    uint8_t cmd;
    const uint8_t* payload;
    uint16_t len;
};

void link_begin();
void link_send_hello(const uint8_t mac[6], const uint16_t* ee);
void link_send_settings(uint8_t armed, uint8_t sens, uint8_t work, const uint8_t* mask);
void link_send_frame(const LiveFrame& frame);
bool link_next_command(HostCommand* out);
