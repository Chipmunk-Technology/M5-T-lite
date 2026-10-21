#include "sentry.h"

#include <math.h>
#include <string.h>

static float background[PIXEL_COUNT];
static uint8_t hot_run[PIXEL_COUNT];
static uint8_t fast[PIXEL_COUNT];
static uint8_t mask[MASK_BYTES];
static bool have_bg = false;
static bool armed = false;
static uint8_t sensitivity = SENS_MID;
static uint32_t last_ms = 0;
static uint32_t quiet_until = 0;
static uint32_t last_event_ms = 0;

static int threshold_cdeg() {
    if (sensitivity == SENS_HIGH) {
        return 200;
    }
    if (sensitivity == SENS_LOW) {
        return 500;
    }
    return 300;
}

static int need_frames() {
    if (sensitivity == SENS_HIGH) {
        return 2;
    }
    return 3;
}

static bool ignored(int index) {
    return (mask[index >> 3] & (1u << (index & 7))) != 0;
}

void sentry_configure(uint8_t sens, const uint8_t* next_mask, bool next_armed) {
    if (sens > SENS_LOW) {
        sens = SENS_MID;
    }
    sensitivity = sens;
    if (next_mask) {
        memcpy(mask, next_mask, MASK_BYTES);
    }
    armed = next_armed;
}

void sentry_note_time(uint32_t now_ms) { last_ms = now_ms; }

bool sentry_armed() { return armed; }
uint8_t sentry_sensitivity() { return sensitivity; }
const uint8_t* sentry_mask() { return mask; }
uint32_t sentry_last_event_ms() { return last_event_ms; }
uint32_t sentry_quiet_until() { return quiet_until; }

SentryHit sentry_update(const float* temp_c, uint32_t now_ms) {
    SentryHit hit = {false, 0, 0};
    float dt = 0.25f;
    if (last_ms != 0 && now_ms > last_ms) {
        dt = (now_ms - last_ms) / 1000.0f;
        if (dt > 2.0f) {
            dt = 2.0f;
        }
    }
    last_ms = now_ms;
    if (!have_bg) {
        for (int i = 0; i < PIXEL_COUNT; ++i) {
            background[i] = temp_c[i];
            hot_run[i] = 0;
            fast[i] = 0;
        }
        have_bg = true;
        return hit;
    }

    const int gate = threshold_cdeg();
    const int need = need_frames();
    const bool quiet = now_ms < quiet_until;
    int peak = 0;
    int cells = 0;

    for (int i = 0; i < PIXEL_COUNT; ++i) {
        int delta = (int)lroundf((temp_c[i] - background[i]) * 100.0f);
        float tau = fast[i] ? SENTRY_FAST_TAU_S : SENTRY_TAU_S;
        float alpha = 1.0f - expf(-dt / tau);
        if (alpha < 0.0f) {
            alpha = 0.0f;
        }
        if (alpha > 0.5f) {
            alpha = 0.5f;
        }
        background[i] += alpha * (temp_c[i] - background[i]);
        if (!ignored(i) && delta >= gate) {
            if (hot_run[i] < 250) {
                hot_run[i]++;
            }
        } else {
            hot_run[i] = 0;
        }
        if (hot_run[i] >= need) {
            cells++;
            if (delta > peak) {
                peak = delta;
            }
        }
        if (fast[i] && !quiet) {
            fast[i] = 0;
        }
    }

    if (armed && !quiet && cells > 0) {
        hit.fired = true;
        hit.peak_cdeg = (int16_t)peak;
        hit.cells = (uint16_t)cells;
        quiet_until = now_ms + SENTRY_QUIET_MS;
        last_event_ms = now_ms;
        for (int i = 0; i < PIXEL_COUNT; ++i) {
            if (hot_run[i] >= need) {
                fast[i] = 1;
                hot_run[i] = 0;
            }
        }
    }
    return hit;
}
