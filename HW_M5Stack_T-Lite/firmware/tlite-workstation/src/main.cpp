#include <M5Unified.h>
#include <Preferences.h>
#include <math.h>
#include <string.h>

#include "link.h"
#include "panel.h"
#include "proto.h"
#include "sensor.h"
#include "sentry.h"

static Preferences prefs;
static uint8_t work_mode = WORK_MEMORY;
static uint16_t emissivity_milli = 950;
static bool use_ta = true;
static uint8_t mask_bytes[MASK_BYTES];
static char host_text[160];
static bool host_emphasis = false;
static uint32_t host_text_ms = 0;
static uint32_t host_cmd_ms = 0;
static bool button_latched = false;
static bool hello_pending = true;
static uint32_t seq_no = 0;
static int16_t live_pixels[PIXEL_COUNT];
static int battery_pct = -1;
static uint32_t battery_ms = 0;
static volatile bool m5_ready = false;

static uint8_t beep_phase = 0;
static uint32_t beep_ms = 0;

struct StoredEvent {
    bool used;
    bool sent;
    uint32_t time_ms;
    uint32_t seq;
    int16_t peak;
    uint16_t cells;
    int16_t pixels[PIXEL_COUNT];
};
static StoredEvent stored[4];

static int16_t to_cdeg(float celsius) {
    if (isnan(celsius)) {
        return 0;
    }
    int v = (int)lroundf(celsius * 100.0f);
    if (v > 32767) {
        v = 32767;
    }
    if (v < -32768) {
        v = -32768;
    }
    return (int16_t)v;
}

static void save_prefs() {
    prefs.putUChar("armed", sentry_armed() ? 1 : 0);
    prefs.putUChar("sens", sentry_sensitivity());
    prefs.putUChar("work", work_mode);
    prefs.putUShort("emis", emissivity_milli);
    prefs.putUChar("useta", use_ta ? 1 : 0);
    prefs.putBytes("mask", mask_bytes, MASK_BYTES);
}

static void load_prefs() {
    memset(mask_bytes, 0, sizeof(mask_bytes));
    uint8_t armed = prefs.getUChar("armed", 0);
    uint8_t sens = prefs.getUChar("sens", SENS_MID);
    work_mode = prefs.getUChar("work", WORK_MEMORY);
    if (work_mode > WORK_SENTRY) {
        work_mode = WORK_MEMORY;
    }
    emissivity_milli = prefs.getUShort("emis", 950);
    use_ta = prefs.getUChar("useta", 1) != 0;
    prefs.getBytes("mask", mask_bytes, MASK_BYTES);
    sentry_configure(sens, mask_bytes, armed != 0);
}

static void remember_event(uint32_t now, int16_t peak, uint16_t cells) {
    int slot = -1;
    for (int i = 0; i < 4; ++i) {
        if (!stored[i].used) {
            slot = i;
            break;
        }
    }
    if (slot < 0) {
        slot = 0;
        uint32_t oldest = stored[0].time_ms;
        for (int i = 1; i < 4; ++i) {
            if (stored[i].time_ms < oldest) {
                oldest = stored[i].time_ms;
                slot = i;
            }
        }
    }
    stored[slot].used = true;
    stored[slot].sent = host_cmd_ms != 0 && (now - host_cmd_ms) < 3000;
    stored[slot].time_ms = now;
    stored[slot].seq = seq_no;
    stored[slot].peak = peak;
    stored[slot].cells = cells;
    memcpy(stored[slot].pixels, live_pixels, sizeof(live_pixels));
}

static void send_stored(const StoredEvent& ev) {
    LiveFrame frame = {};
    frame.flags = FLAG_COMPLETE | FLAG_EVENT | FLAG_STORED;
    if (sentry_armed()) {
        frame.flags |= FLAG_ARMED;
    }
    frame.seq = ev.seq;
    frame.time_ms = ev.time_ms;
    frame.emissivity_milli = emissivity_milli;
    frame.sentry_peak_cdeg = ev.peak;
    frame.sentry_cells = ev.cells;
    frame.sensitivity = sentry_sensitivity();
    frame.battery_pct = (battery_pct < 0) ? 255 : (uint8_t)battery_pct;
    frame.work = work_mode;
    frame.quiet_minutes = 0;
    frame.event_age_s = 0;
    frame.pixels = ev.pixels;
    link_send_frame(frame);
}

static void flush_stored() {
    for (int i = 0; i < 4; ++i) {
        if (stored[i].used && !stored[i].sent) {
            send_stored(stored[i]);
            stored[i].sent = true;
        }
    }
}

static void handle_command(const HostCommand& cmd) {
    host_cmd_ms = millis();
    switch (cmd.cmd) {
        case CMD_SET_SENTRY:
            if (cmd.len >= 2) {
                sentry_configure(cmd.payload[1], mask_bytes, cmd.payload[0] != 0);
                save_prefs();
                link_send_settings(sentry_armed(), sentry_sensitivity(), work_mode, mask_bytes);
            }
            break;
        case CMD_SET_MASK:
            if (cmd.len == MASK_BYTES) {
                memcpy(mask_bytes, cmd.payload, MASK_BYTES);
                sentry_configure(sentry_sensitivity(), mask_bytes, sentry_armed());
                save_prefs();
                link_send_settings(sentry_armed(), sentry_sensitivity(), work_mode, mask_bytes);
            }
            break;
        case CMD_SET_COND:
            if (cmd.len >= 3) {
                uint16_t emis;
                memcpy(&emis, cmd.payload, 2);
                if (emis < 50) {
                    emis = 50;
                }
                if (emis > 1000) {
                    emis = 1000;
                }
                emissivity_milli = emis;
                use_ta = cmd.payload[2] != 0;
                save_prefs();
            }
            break;
        case CMD_SET_TEXT:
            if (cmd.len >= 2) {
                host_emphasis = cmd.payload[0] != 0;
                size_t n = cmd.len - 1;
                if (n > sizeof(host_text) - 1) {
                    n = sizeof(host_text) - 1;
                }
                memcpy(host_text, cmd.payload + 1, n);
                host_text[n] = 0;
                host_text_ms = millis();
            }
            break;
        case CMD_SET_WORK:
            if (cmd.len >= 1 && cmd.payload[0] <= WORK_SENTRY) {
                work_mode = cmd.payload[0];
                save_prefs();
            }
            break;
        case CMD_PING:
            if (hello_pending) {
                const SensorView* view = sensor_latest();
                if (view->ready) {
                    uint64_t mac = ESP.getEfuseMac();
                    uint8_t bytes[6];
                    for (int i = 0; i < 6; ++i) {
                        bytes[i] = (uint8_t)((mac >> (8 * i)) & 0xFF);
                    }
                    link_send_hello(bytes, view->ee);
                    hello_pending = false;
                }
            }
            flush_stored();
            link_send_settings(sentry_armed(), sentry_sensitivity(), work_mode, mask_bytes);
            break;
        default:
            break;
    }
}

static void service_commands() {
    if (host_cmd_ms != 0 && millis() - host_cmd_ms > 3000) {
        hello_pending = true;
    }
    HostCommand cmd;
    while (link_next_command(&cmd)) {
        handle_command(cmd);
    }
}

static void start_beep(uint32_t now) {
    if (!m5_ready || beep_phase != 0) {
        return;
    }
    beep_phase = 1;
    beep_ms = now;
    M5.Speaker.tone(2700, 70);
}

static void service_beep(uint32_t now) {
    if (beep_phase == 1 && now - beep_ms >= 150) {
        beep_phase = 2;
        M5.Speaker.tone(2700, 70);
    } else if (beep_phase == 2 && now - beep_ms >= 320) {
        beep_phase = 0;
    }
}

static void refresh_panel(uint32_t now, bool event_now) {
    const bool host_fresh = host_text_ms != 0 && (now - host_text_ms) < 2000 && host_text[0];
    if (host_cmd_ms != 0 && now - host_cmd_ms < 2000) {
        panel_set_status("連線");
    } else if (sentry_armed()) {
        panel_set_status("守候");
    } else {
        panel_set_status("未連線");
    }
    if (host_fresh) {
        panel_set_sentence(host_text, host_emphasis || event_now);
    } else if (!sensor_latest()->ready) {
        panel_set_sentence("感測器未找到", false);
    } else if (event_now || (sentry_last_event_ms() != 0 && now - sentry_last_event_ms() < 60000)) {
        panel_set_sentence("剛剛有暖物經過", true);
    } else if (sentry_armed()) {
        panel_set_sentence("守候中", false);
    } else {
        panel_set_sentence("未連線", false);
    }
    panel_render();
}

static void publish_frame(const SensorView* view, const SentryHit& hit, uint32_t now) {
    for (int i = 0; i < PIXEL_COUNT; ++i) {
        live_pixels[i] = to_cdeg(view->temp_c[i]);
    }
    seq_no++;
    if (hit.fired) {
        remember_event(now, hit.peak_cdeg, hit.cells);
        start_beep(now);
    }
    float reflected = use_ta ? view->ta_c : view->ta_c;
    LiveFrame frame = {};
    frame.flags = FLAG_COMPLETE;
    if (view->subpage) {
        frame.flags |= FLAG_SUBPAGE;
    }
    if (hit.fired) {
        frame.flags |= FLAG_EVENT;
    }
    if (button_latched) {
        frame.flags |= FLAG_BUTTON;
        button_latched = false;
    }
    if (sentry_armed()) {
        frame.flags |= FLAG_ARMED;
    }
    frame.seq = seq_no;
    frame.time_ms = now;
    frame.ta_cdeg = to_cdeg(view->ta_c);
    frame.vdd_cv = to_cdeg(view->vdd_v);
    frame.emissivity_milli = emissivity_milli;
    frame.reflected_cdeg = to_cdeg(reflected);
    frame.sentry_peak_cdeg = hit.peak_cdeg;
    frame.sentry_cells = hit.cells;
    frame.sensitivity = sentry_sensitivity();
    frame.battery_pct = (battery_pct < 0) ? 255 : (uint8_t)battery_pct;
    frame.work = work_mode;
    if (sentry_armed()) {
        uint32_t origin = sentry_last_event_ms();
        uint32_t minutes = (now - origin) / 60000u;
        if (origin == 0) {
            minutes = now / 60000u;
        }
        frame.quiet_minutes = minutes > 254 ? 254 : (uint8_t)minutes;
        if (origin == 0) {
            frame.event_age_s = 0xFFFF;
        } else {
            uint32_t age = (now - origin) / 1000u;
            frame.event_age_s = age > 65534 ? 65534 : (uint16_t)age;
        }
    } else {
        frame.quiet_minutes = 255;
        frame.event_age_s = 0xFFFF;
    }
    frame.pixels = live_pixels;
    link_send_frame(frame);
}

static void start_m5(void*) {
    auto cfg = M5.config();
    cfg.serial_baudrate = 0;
    cfg.fallback_board = m5::board_t::board_M5StickCPlus;
    cfg.clear_display = true;
    cfg.internal_imu = false;
    cfg.internal_rtc = false;
    cfg.internal_mic = false;
    M5.begin(cfg);
    M5.Speaker.begin();
    M5.Speaker.setVolume(180);
    // Keep the battery path and the hat supply after USB data is unplugged.
    M5.Power.setExtOutput(true);
    M5.Power.setBatteryCharge(true);
    panel_begin();
    panel_set_status("未連線");
    panel_set_sentence("未連線", false);
    panel_render();
    m5_ready = true;
    vTaskDelete(nullptr);
}

static void axp_exten_on() {
    Wire.beginTransmission(0x34);
    Wire.write(0x12);
    if (Wire.endTransmission(false) != 0) {
        return;
    }
    if (Wire.requestFrom((uint8_t)0x34, (uint8_t)1) != 1) {
        return;
    }
    uint8_t value = Wire.read() | 0x40;
    Wire.beginTransmission(0x34);
    Wire.write(0x12);
    Wire.write(value);
    Wire.endTransmission();
}

void setup() {
    link_begin();
    Serial.begin(115200);
    prefs.begin("tlite", false);
    load_prefs();
    link_send_settings(sentry_armed(), sentry_sensitivity(), work_mode, mask_bytes);
    Wire.begin(21, 22);
    axp_exten_on();
    delay(200);
    sensor_begin();
    link_send_settings(sentry_armed(), sentry_sensitivity(), work_mode, mask_bytes);
}

void loop() {
    const uint32_t now = millis();
    service_commands();
    service_beep(now);
    if (m5_ready) {
        M5.update();
        if (work_mode == WORK_MEMORY && M5.BtnA.wasPressed()) {
            button_latched = true;
        }
        if (battery_ms == 0 || now - battery_ms > 1000) {
            battery_ms = now;
            int level = M5.Power.getBatteryLevel();
            battery_pct = level;
            panel_set_battery(level);
        }
    }

    SentryHit hit = {};
    const SensorView* view = sensor_latest();
    if (view->ready) {
        float emis = emissivity_milli / 1000.0f;
        if (sensor_poll(emis, view->ta_c, use_ta)) {
            view = sensor_latest();
            if (view->complete) {
                hit = sentry_update(view->temp_c, now);
                publish_frame(view, hit, now);
            }
        }
    }
    if (m5_ready) {
        refresh_panel(now, hit.fired);
    }
}
