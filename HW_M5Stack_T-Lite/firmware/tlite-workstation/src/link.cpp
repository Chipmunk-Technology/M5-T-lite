#include "link.h"

#include <string.h>

static uint8_t rx[512];
static size_t rx_len = 0;
static uint8_t tx[1800];
static uint8_t cmd_payload[180];

static void write_u16(uint8_t* p, uint16_t v) { memcpy(p, &v, 2); }
static void write_u32(uint8_t* p, uint32_t v) { memcpy(p, &v, 4); }

static uint16_t read_u16(const uint8_t* p) {
    uint16_t v;
    memcpy(&v, p, 2);
    return v;
}

static void send_buf(size_t len) {
    uint16_t crc = proto_crc16(tx, len);
    write_u16(tx + len, crc);
    Serial.write(tx, len + 2);
}

void link_begin() {
    // Must run before M5.begin(), which opens Serial at 460800.
    Serial.setRxBufferSize(2048);
}

void link_send_hello(const uint8_t mac[6], const uint16_t* ee) {
    tx[0] = 'T';
    tx[1] = 'L';
    tx[2] = '0';
    tx[3] = 'H';
    tx[4] = PROTO_VERSION;
    memcpy(tx + 5, mac, 6);
    write_u16(tx + 11, SENSOR_EE_WORDS);
    memcpy(tx + 13, ee, SENSOR_EE_WORDS * 2);
    send_buf(13 + SENSOR_EE_WORDS * 2);
}

void link_send_settings(uint8_t armed, uint8_t sens, uint8_t work, const uint8_t* mask) {
    tx[0] = 'T';
    tx[1] = 'L';
    tx[2] = '0';
    tx[3] = 'M';
    tx[4] = PROTO_VERSION;
    tx[5] = armed ? 1 : 0;
    tx[6] = sens;
    tx[7] = work;
    memcpy(tx + 8, mask, MASK_BYTES);
    send_buf(8 + MASK_BYTES);
}

void link_send_frame(const LiveFrame& frame) {
    tx[0] = 'T';
    tx[1] = 'L';
    tx[2] = '0';
    tx[3] = '1';
    tx[4] = PROTO_VERSION;
    tx[5] = frame.flags;
    write_u16(tx + 6, 36);
    write_u32(tx + 8, frame.seq);
    write_u32(tx + 12, frame.time_ms);
    write_u16(tx + 16, (uint16_t)frame.ta_cdeg);
    write_u16(tx + 18, (uint16_t)frame.vdd_cv);
    write_u16(tx + 20, frame.emissivity_milli);
    write_u16(tx + 22, (uint16_t)frame.reflected_cdeg);
    write_u16(tx + 24, (uint16_t)frame.sentry_peak_cdeg);
    write_u16(tx + 26, frame.sentry_cells);
    tx[28] = frame.sensitivity;
    tx[29] = frame.battery_pct;
    tx[30] = frame.work;
    tx[31] = frame.quiet_minutes;
    write_u16(tx + 32, frame.event_age_s);
    write_u16(tx + 34, 0);
    memcpy(tx + 36, frame.pixels, PIXEL_COUNT * 2);
    send_buf(36 + PIXEL_COUNT * 2);
}

bool link_next_command(HostCommand* out) {
    while (Serial.available() && rx_len < sizeof(rx)) {
        rx[rx_len++] = (uint8_t)Serial.read();
    }
    while (rx_len >= 8) {
        size_t start = 0;
        bool found = false;
        for (size_t i = 0; i + 4 <= rx_len; ++i) {
            if (rx[i] == 'T' && rx[i + 1] == 'L' && rx[i + 2] == '0' && rx[i + 3] == 'C') {
                start = i;
                found = true;
                break;
            }
        }
        if (!found) {
            rx_len = 0;
            return false;
        }
        if (start > 0) {
            memmove(rx, rx + start, rx_len - start);
            rx_len -= start;
        }
        if (rx_len < 8) {
            return false;
        }
        if (rx[4] != PROTO_VERSION) {
            memmove(rx, rx + 1, rx_len - 1);
            rx_len--;
            continue;
        }
        uint16_t len = read_u16(rx + 6);
        if (len > sizeof(cmd_payload)) {
            memmove(rx, rx + 1, rx_len - 1);
            rx_len--;
            continue;
        }
        size_t total = 8 + len + 2;
        if (rx_len < total) {
            return false;
        }
        uint16_t expect = proto_crc16(rx, 8 + len);
        uint16_t got = read_u16(rx + 8 + len);
        if (expect != got) {
            memmove(rx, rx + 1, rx_len - 1);
            rx_len--;
            continue;
        }
        memcpy(cmd_payload, rx + 8, len);
        out->cmd = rx[5];
        out->payload = cmd_payload;
        out->len = len;
        memmove(rx, rx + total, rx_len - total);
        rx_len -= total;
        return true;
    }
    return false;
}
