#pragma once

#include "proto.h"

#include <stdint.h>

struct SentryHit {
    bool fired;
    int16_t peak_cdeg;
    uint16_t cells;
};

void sentry_configure(uint8_t sensitivity, const uint8_t mask[MASK_BYTES], bool armed);
void sentry_note_time(uint32_t now_ms);
SentryHit sentry_update(const float* temp_c, uint32_t now_ms);

bool sentry_armed();
uint8_t sentry_sensitivity();
const uint8_t* sentry_mask();
uint32_t sentry_last_event_ms();
uint32_t sentry_quiet_until();
