/*
 * M5Stack Connect — ATOM Matrix v1.1
 *
 * BLE (phone app "WS Connect"):
 *   Legacy: write Wi-Fi SSID + password, then "connect".
 *   Profiles: write {"profiles":[{"ssid","pass","order"}]} (read returns ssid and order only).
 *   Scan: write "scan", then read/notify {"networks":[{"ssid","rssi","secure"}]}.
 *   Info: read {"id","brand","model","fw","name"}.
 *   Status notify stays a short line: "connected <ip>" | "ap <ip>" | "failed" | "connecting".
 *
 * Pakpak CLT13 (BT Spec V2.04):
 *   Advertises as CLT13_XXXX (name only, service UUID not in the advert).
 *   Same GATT service as a real 1-to-3 module.
 *   Also accepts frames over Wi-Fi:  http://<ip>/raw?hex=55...AA
 *
 * Matrix, facing the LEDs, library column 0 on the left:
 *   columns 1–2 (index 0,1) = left ring
 *   column 3    (index 2)   = middle ring
 *   columns 4–5 (index 3,4) = right ring
 *   all 5 rows
 *
 * Board: esp32:esp32:m5stack_atom    Upload speed: 115200
 * Brightness stays low (protocol 0–255 scaled to at most 40/255).
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "esp32-hal-rmt.h"
#include "esp_mac.h"

#define PIN_MATRIX 27
#define PIN_BUTTON 39

static const char *WIFI_SVC = "a5c10000-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_SSID  = "a5c10001-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_PASS  = "a5c10002-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_CTRL  = "a5c10003-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_STAT  = "a5c10004-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_INFO  = "a5c10005-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_PROFILES = "a5c10006-7c3a-4b2e-9f10-6d0a4d13a001";
static const char *CH_SCAN  = "a5c10007-7c3a-4b2e-9f10-6d0a4d13a001";

static const char *PAKPAK_SVC = "E20A39F4-73F5-4BC4-A12F-17D1AD07A961";
static const char *PAKPAK_TX  = "08590F7E-DB05-467E-8757-72F6FAEB13D4";
static const char *PAKPAK_RX  = "08590F7F-DB05-467E-8757-72F6FAEB13D4";

enum : uint8_t {
  CMD_SET_RGB = 0x01, CMD_QUERY_RGB = 0x02, CMD_SET_LEDS = 0x04,
  CMD_QUERY_VERSION = 0x05, CMD_SET_ALL = 0x06, CMD_SET_MODE = 0x07,
  CMD_SET_RGB_SCREEN = 0x08, CMD_QUERY_STATUS = 0x09, CMD_REPORT_STATUS = 0x0A,
  CMD_SET_BRIGHTNESS = 0x0B, CMD_QUERY_BRIGHTNESS = 0x0C,
  CMD_REPORT_CARD = 0x0D, CMD_BUZZER = 0x0E,
};

static const uint8_t VERSION_INFO[10] = {0x02, 0x00, 0x03, 0x10, 0x00, 0x00, 0x02, 0x04, 0x03, 0x00};
static const int RINGS = 3;
static const int LEDS_PER_RING = 16;

struct Ring {
  uint8_t r = 0, g = 0, b = 0;
  uint8_t status = 0x00;
  uint8_t pattern = 0x00;
  bool lit() const { return pattern != 0 || (status != 0x00 && status != 0xFF && (r | g | b)); }
};

static Ring rings[RINGS];
static uint8_t brightness = 100;
static Preferences prefs;
static WebServer http(80);
static String bleName;
static String pendingSsid, pendingPass;
static String ipString;
static String wifiStatus = "idle";
static String lastTxHex;
static const int MAX_PROFILES = 4;
struct WifiProfile { String ssid; String pass; };
static WifiProfile profiles[MAX_PROFILES];
static int profileCount = 0;
static volatile int wifiAction = 0;  // 1 = join stored profiles
static volatile int replacePending = 0;
static volatile int profileAction = 0;
static volatile int scanAction = 0;
static String pendingProfilesJson;
static volatile bool restartAdv = false;
static uint32_t buzzerUntil = 0;
static bool httpStarted = false;

static BLECharacteristic *chSsid = nullptr;
static BLECharacteristic *chPass = nullptr;
static BLECharacteristic *chCtrl = nullptr;
static BLECharacteristic *chStat = nullptr;
static BLECharacteristic *chInfo = nullptr;
static BLECharacteristic *chProfiles = nullptr;
static BLECharacteristic *chScan = nullptr;
static BLECharacteristic *txChar = nullptr;

struct Chunk { uint8_t len; uint8_t data[180]; };
static QueueHandle_t rxQueue;
static uint8_t rxBuf[256];
static size_t rxLen = 0;

static uint8_t pix[25][3];
static rmt_data_t rmtBuf[25 * 24 + 1];
static bool faceDriven = false;
static bool matrixWriteLogged = false;

// ── Matrix ──────────────────────────────────────────────────────────────
static uint8_t scale(uint8_t v) {
  if (brightness == 0 || v == 0) return 0;
  int level = brightness * 40 / 255;
  if (level < 1) level = 1;
  return (uint16_t)v * level / 255;
}

static void putPixel(int row, int col, uint8_t r, uint8_t g, uint8_t b) {
  if (row < 0 || row > 4 || col < 0 || col > 4) return;
  int i = row * 5 + col;
  pix[i][0] = scale(g);
  pix[i][1] = scale(r);
  pix[i][2] = scale(b);
}

static void showMatrix() {
  int n = 0;
  for (int i = 0; i < 25; i++) {
    for (int c = 0; c < 3; c++) {
      uint8_t v = pix[i][c];
      for (int b = 7; b >= 0; --b) {
        bool one = v & (1 << b);
        rmtBuf[n].level0 = 1;
        rmtBuf[n].duration0 = one ? 8 : 4;
        rmtBuf[n].level1 = 0;
        rmtBuf[n].duration1 = one ? 5 : 8;
        n++;
      }
    }
  }
  rmtBuf[n].level0 = 0;
  rmtBuf[n].duration0 = 3000;
  rmtBuf[n].level1 = 0;
  rmtBuf[n].duration1 = 3000;
  n++;
  bool ok = rmtWrite(PIN_MATRIX, rmtBuf, n, 100);
  if (!matrixWriteLogged) {
    matrixWriteLogged = true;
    Serial.printf("matrix write %s (%d symbols)\n", ok ? "ok" : "failed", n);
  }
}

static void fillRing(int ring, uint8_t r, uint8_t g, uint8_t b) {
  const int cols[3][2] = {{0, 1}, {2, -1}, {3, 4}};
  int n = (ring == 1) ? 1 : 2;
  for (int k = 0; k < n; k++)
    for (int row = 0; row < 5; row++)
      putPixel(row, cols[ring][k], r, g, b);
}

static void hue(uint8_t h, uint8_t &r, uint8_t &g, uint8_t &b) {
  uint8_t region = h / 43;
  uint8_t rem = (h - region * 43) * 6;
  uint8_t q = 255 - rem;
  switch (region) {
    case 0: r = 255; g = rem; b = 0; break;
    case 1: r = q; g = 255; b = 0; break;
    case 2: r = 0; g = 255; b = rem; break;
    case 3: r = 0; g = q; b = 255; break;
    case 4: r = rem; g = 0; b = 255; break;
    default: r = 255; g = 0; b = q; break;
  }
}

static void patternColor(const Ring &ring, int row, uint32_t now, uint8_t &r, uint8_t &g, uint8_t &b) {
  static const uint8_t PAL[7][3] = {{255, 0, 0}, {255, 128, 0}, {255, 255, 0}, {0, 255, 0}, {0, 255, 255}, {0, 0, 255}, {160, 0, 255}};
  uint8_t pat = ring.pattern;
  int step = (now / 150) % 5;
  if (pat >= 1 && pat <= 7) {
    const uint8_t *c = PAL[pat - 1];
    uint8_t dim = (row == step) ? 1 : 8;
    r = c[0] / dim; g = c[1] / dim; b = c[2] / dim;
    return;
  }
  hue((uint8_t)((now / 12 + row * 40) & 0xFF), r, g, b);
  if ((pat == 0x0A || pat == 0x0C) && row != step) { r /= 6; g /= 6; b /= 6; }
}

static void render() {
  memset(pix, 0, sizeof pix);
  uint32_t now = millis();
  bool buzz = now < buzzerUntil && ((now / 60) % 2);
  for (int i = 0; i < RINGS; i++) {
    uint8_t r = 0, g = 0, b = 0;
    if (buzz) { r = g = b = 255; }
    else if (rings[i].pattern) patternColor(rings[i], 0, now, r, g, b);
    else if (rings[i].lit()) { r = rings[i].r; g = rings[i].g; b = rings[i].b; }
    if (rings[i].pattern && !buzz) {
      const int cols[3][2] = {{0, 1}, {2, -1}, {3, 4}};
      int n = (i == 1) ? 1 : 2;
      for (int row = 0; row < 5; row++) {
        patternColor(rings[i], row, now, r, g, b);
        for (int k = 0; k < n; k++) putPixel(row, cols[i][k], r, g, b);
      }
    } else {
      fillRing(i, r, g, b);
    }
  }
  showMatrix();
}

static void columnTest() {
  memset(pix, 0, sizeof pix);
  for (int row = 0; row < 5; row++) {
    putPixel(row, 0, 255, 0, 0);
    putPixel(row, 1, 255, 0, 0);
    putPixel(row, 2, 0, 255, 0);
    putPixel(row, 3, 0, 0, 255);
    putPixel(row, 4, 0, 0, 255);
  }
  showMatrix();
}

// ── Pakpak frames ───────────────────────────────────────────────────────
static String toHex(const uint8_t *d, size_t n) {
  String s;
  char t[4];
  for (size_t i = 0; i < n; i++) {
    snprintf(t, sizeof t, i ? " %02X" : "%02X", d[i]);
    s += t;
  }
  return s;
}

static size_t fromHex(const String &in, uint8_t *out, size_t max) {
  size_t n = 0;
  int hi = -1;
  for (unsigned i = 0; i < in.length(); i++) {
    char c = in[i];
    int v = isdigit(c) ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
    if (v < 0) continue;
    if (hi < 0) hi = v;
    else {
      if (n < max) out[n++] = (hi << 4) | v;
      hi = -1;
    }
  }
  return n;
}

static void sendFrame(uint8_t cmd, const uint8_t *params, size_t n) {
  uint8_t f[64];
  size_t total = n + 6;
  if (total > sizeof f) return;
  f[0] = 0x55;
  f[1] = total;
  f[2] = 0x02;
  f[3] = cmd;
  memcpy(f + 4, params, n);
  uint8_t cs = 0;
  for (size_t i = 1; i < total - 2; i++) cs += f[i];
  f[total - 2] = cs;
  f[total - 1] = 0xAA;
  lastTxHex = toHex(f, total);
  if (txChar) {
    txChar->setValue(f, total);
    txChar->notify();
  }
  Serial.printf("TX %s\n", lastTxHex.c_str());
}

static void echo(const uint8_t *f, size_t n) { sendFrame(f[3], f + 4, n - 6); }

static void appendRing(uint8_t *p, const Ring &r) {
  p[0] = r.r; p[1] = r.g; p[2] = r.b; p[3] = r.status;
}

static void sendStatus(int idx, uint8_t cmd, bool pressReport) {
  uint8_t p[6];
  p[0] = idx + 1;
  appendRing(p + 1, rings[idx]);
  if (pressReport && !rings[idx].lit()) p[4] = 0xFF;
  p[5] = rings[idx].pattern;
  sendFrame(cmd, p, sizeof p);
}

static void setRingFromGroup(int i, const uint8_t *g) {
  if (g[3] == 0xFF) return;
  rings[i].r = g[0];
  rings[i].g = g[1];
  rings[i].b = g[2];
  rings[i].status = g[3];
  rings[i].pattern = 0;
}

static void handleFrame(const uint8_t *f, size_t n) {
  if (n < 6 || f[0] != 0x55 || f[n - 1] != 0xAA) return;
  uint8_t cmd = f[3];
  const uint8_t *p = f + 4;
  size_t pn = n - 6;
  Serial.printf("RX %s\n", toHex(f, n).c_str());
  if (f[2] != 0x01) return;

  switch (cmd) {
    case CMD_SET_RGB:
      if (pn >= 4) setRingFromGroup(0, p);
      faceDriven = true;
      echo(f, n);
      break;
    case CMD_QUERY_RGB: {
      uint8_t out[RINGS * 4];
      for (int i = 0; i < RINGS; i++) appendRing(out + i * 4, rings[i]);
      sendFrame(CMD_QUERY_RGB, out, sizeof out);
      break;
    }
    case CMD_SET_LEDS:
      if (pn >= 6) {
        int start = p[0], count = p[1];
        for (int i = 0; i < RINGS; i++) {
          int first = i * LEDS_PER_RING + 1, last = first + LEDS_PER_RING - 1;
          if (start <= last && start + count - 1 >= first) setRingFromGroup(i, p + 2);
        }
      }
      faceDriven = true;
      echo(f, n);
      break;
    case CMD_QUERY_VERSION:
      sendFrame(CMD_QUERY_VERSION, VERSION_INFO, sizeof VERSION_INFO);
      break;
    case CMD_SET_ALL:
      for (int i = 0; i < RINGS && (size_t)(i * 4 + 4) <= pn; i++) setRingFromGroup(i, p + i * 4);
      faceDriven = true;
      echo(f, n);
      break;
    case CMD_SET_MODE:
      if (pn >= 2) {
        for (int i = 0; i < RINGS; i++) {
          if (p[0] != 0 && p[0] != i + 1) continue;
          uint8_t pat = p[1];
          if (pat == 0xFF) pat = (rings[i].pattern % 0x0C) + 1;
          rings[i].pattern = pat;
        }
      }
      faceDriven = true;
      echo(f, n);
      break;
    case CMD_SET_RGB_SCREEN:
      // The round lights one ring with this command: [BtnID] [R G B Status] [Screen 8B].
      // This cube has no digit screen, so the screen bytes are ignored and there is
      // no reply. The ring colour is still applied, or the face stays dark all round.
      if (pn >= 5 && p[0] >= 1 && p[0] <= RINGS) {
        setRingFromGroup(p[0] - 1, p + 1);
        faceDriven = true;
      }
      break;
    case CMD_QUERY_STATUS:
      if (pn >= 1) {
        if (p[0] == 0)
          for (int i = 0; i < RINGS; i++) sendStatus(i, CMD_QUERY_STATUS, false);
        else if (p[0] <= RINGS)
          sendStatus(p[0] - 1, CMD_QUERY_STATUS, false);
      }
      break;
    case CMD_SET_BRIGHTNESS:
      if (pn >= 1) brightness = p[0];
      faceDriven = true;
      echo(f, n);
      break;
    case CMD_QUERY_BRIGHTNESS: {
      uint8_t out[1 + RINGS * 4];
      out[0] = brightness;
      for (int i = 0; i < RINGS; i++) appendRing(out + 1 + i * 4, rings[i]);
      sendFrame(CMD_QUERY_BRIGHTNESS, out, sizeof out);
      break;
    }
    case CMD_BUZZER: {
      int beeps = pn >= 1 ? p[0] : 1;
      buzzerUntil = millis() + 120 * beeps;
      faceDriven = true;
      echo(f, n);
      break;
    }
    default:
      break;
  }
}

static void feedBytes(const uint8_t *d, size_t n) {
  if (rxLen + n > sizeof rxBuf) rxLen = 0;
  memcpy(rxBuf + rxLen, d, n);
  rxLen += n;
  while (rxLen > 0) {
    if (rxBuf[0] != 0x55) {
      memmove(rxBuf, rxBuf + 1, --rxLen);
      continue;
    }
    if (rxLen < 2) return;
    size_t len = rxBuf[1];
    if (len < 6 || len > sizeof rxBuf) {
      memmove(rxBuf, rxBuf + 1, --rxLen);
      continue;
    }
    if (rxLen < len) return;
    if (rxBuf[len - 1] == 0xAA) handleFrame(rxBuf, len);
    memmove(rxBuf, rxBuf + len, rxLen - len);
    rxLen -= len;
  }
}

static bool pressButton(int btn) {
  if (btn < 1 || btn > RINGS) return false;
  int i = btn - 1;
  sendStatus(i, CMD_REPORT_STATUS, true);
  rings[i].status = 0x00;
  rings[i].pattern = 0x00;
  return true;
}

static bool scanCard(const String &uidHex) {
  uint8_t uid[8];
  size_t n = fromHex(uidHex, uid, 8);
  if (n == 0) return false;
  uint8_t p[8] = {0};
  memcpy(p + (8 - n), uid, n);
  sendFrame(CMD_REPORT_CARD, p, 8);
  buzzerUntil = millis() + 150;
  return true;
}

// ── BLE ─────────────────────────────────────────────────────────────────
static void publishStatus(const String &s) {
  wifiStatus = s;
  if (chStat) {
    chStat->setValue(s);
    chStat->notify();
  }
  Serial.println(s);
}

static String jsonEscape(const String &in) {
  String out;
  for (unsigned i = 0; i < in.length(); i++) {
    char c = in[i];
    if (c == '"' || c == '\\') out += '\\';
    if (c >= 32) out += c;
  }
  return out;
}

static String jsonStringValue(const String &src, const char *key) {
  String pat = String("\"") + key + "\":\"";
  int i = src.indexOf(pat);
  if (i < 0) return "";
  i += pat.length();
  String out;
  while (i < (int)src.length()) {
    char c = src[i++];
    if (c == '\\' && i < (int)src.length()) { out += src[i++]; continue; }
    if (c == '"') break;
    out += c;
  }
  return out;
}

static void saveProfiles() {
  prefs.putInt("n", profileCount);
  for (int i = 0; i < MAX_PROFILES; i++) {
    String sk = "s" + String(i);
    String pk = "p" + String(i);
    prefs.putString(sk.c_str(), i < profileCount ? profiles[i].ssid : "");
    prefs.putString(pk.c_str(), i < profileCount ? profiles[i].pass : "");
  }
  if (profileCount > 0) {
    pendingSsid = profiles[0].ssid;
    pendingPass = profiles[0].pass;
    prefs.putString("ssid", profiles[0].ssid);
    prefs.putString("pass", profiles[0].pass);
    if (chSsid) chSsid->setValue(profiles[0].ssid);
  }
}

static void loadProfiles() {
  profileCount = prefs.getInt("n", 0);
  if (profileCount < 0) profileCount = 0;
  if (profileCount > MAX_PROFILES) profileCount = MAX_PROFILES;
  for (int i = 0; i < profileCount; i++) {
    profiles[i].ssid = prefs.getString(("s" + String(i)).c_str(), "");
    profiles[i].pass = prefs.getString(("p" + String(i)).c_str(), "");
  }
  if (profileCount == 0) {
    String saved = prefs.getString("ssid", "");
    if (saved.length()) {
      profiles[0].ssid = saved;
      profiles[0].pass = prefs.getString("pass", "");
      profileCount = 1;
    }
  }
}

static void publishProfiles() {
  String json = "{\"profiles\":[";
  for (int i = 0; i < profileCount; i++) {
    if (i) json += ",";
    json += "{\"ssid\":\"" + jsonEscape(profiles[i].ssid) + "\",\"order\":" + String(i) + "}";
  }
  json += "]}";
  if (chProfiles) chProfiles->setValue(json);
}

static void parseProfilesWrite(const String &body) {
  profileCount = 0;
  int from = 0;
  while (profileCount < MAX_PROFILES) {
    int at = body.indexOf("\"ssid\"", from);
    if (at < 0) break;
    int next = body.indexOf("\"ssid\"", at + 6);
    String window = body.substring(at, next < 0 ? body.length() : next);
    String ssid = jsonStringValue(window, "ssid");
    String pass = jsonStringValue(window, "pass");
    if (ssid.length()) {
      profiles[profileCount].ssid = ssid;
      profiles[profileCount].pass = pass;
      profileCount++;
    }
    from = at + 6;
  }
  saveProfiles();
  publishProfiles();
}

static String deviceInfoJson() {
  return String("{\"id\":\"") + bleName + "\",\"brand\":\"M5Stack\",\"model\":\"ATOM Matrix\",\"fw\":\"1.0\",\"name\":\"" + bleName + "\"}";
}

static void runWifiScan() {
  wifi_mode_t mode = WiFi.getMode();
  int found = WiFi.scanNetworks();
  String json = "{\"networks\":[";
  int kept = 0;
  for (int i = 0; i < found && kept < 6; i++) {
    String ssid = WiFi.SSID(i);
    if (!ssid.length()) continue;
    if (json.length() > 140) break;
    if (kept) json += ",";
    json += "{\"ssid\":\"" + jsonEscape(ssid) + "\",\"rssi\":" + String(WiFi.RSSI(i)) + ",\"secure\":";
    json += (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "false" : "true";
    json += "}";
    kept++;
  }
  json += "]}";
  WiFi.scanDelete();
  if (mode == WIFI_OFF) WiFi.mode(WIFI_OFF);
  if (chScan) {
    chScan->setValue(json);
    chScan->notify();
  }
  Serial.printf("scan %d\n", kept);
}

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { restartAdv = true; }
  void onDisconnect(BLEServer *) override { restartAdv = true; }
};

class WifiCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String v = c->getValue();
    if (c == chSsid) pendingSsid = v;
    else if (c == chPass) pendingPass = v;
    else if (c == chCtrl && v == "connect") {
      replacePending = 1;
      wifiAction = 1;
    }
    else if (c == chProfiles) {
      pendingProfilesJson = v;
      profileAction = 1;
    } else if (c == chScan) {
      scanAction = 1;
    }
  }
};

class PakpakCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    uint8_t *data = c->getData();
    size_t n = c->getLength();
    Chunk chunk;
    chunk.len = min(sizeof chunk.data, n);
    memcpy(chunk.data, data, chunk.len);
    xQueueSend(rxQueue, &chunk, 0);
  }
};

static void setupBle() {
  uint8_t mac[6] = {};
  // WiFi.macAddress() is still all zeros here, before the radio starts.
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  char suffix[8];
  snprintf(suffix, sizeof suffix, "%02X%02X", mac[4], mac[5]);
  bleName = String("CLT13_") + suffix;

  BLEDevice::init(bleName.c_str());
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());

  // Default service size is 15 handles. This service needs 17
  // (7 characteristics, two of them with a notify descriptor), so the
  // scan characteristic was dropped and the phone hid the scan button.
  BLEService *wifi = server->createService(BLEUUID(WIFI_SVC), 32);
  chSsid = wifi->createCharacteristic(CH_SSID, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE);
  chPass = wifi->createCharacteristic(CH_PASS, BLECharacteristic::PROPERTY_WRITE);
  chCtrl = wifi->createCharacteristic(CH_CTRL, BLECharacteristic::PROPERTY_WRITE);
  chStat = wifi->createCharacteristic(CH_STAT, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chStat->addDescriptor(new BLE2902());
  chInfo = wifi->createCharacteristic(CH_INFO, BLECharacteristic::PROPERTY_READ);
  chProfiles = wifi->createCharacteristic(CH_PROFILES, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE);
  chScan = wifi->createCharacteristic(CH_SCAN, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_NOTIFY);
  chScan->addDescriptor(new BLE2902());
  WifiCB *wifiCb = new WifiCB();
  chSsid->setCallbacks(wifiCb);
  chPass->setCallbacks(wifiCb);
  chCtrl->setCallbacks(wifiCb);
  chProfiles->setCallbacks(wifiCb);
  chScan->setCallbacks(wifiCb);
  chInfo->setValue(deviceInfoJson());
  publishProfiles();
  chSsid->setValue(pendingSsid);
  chStat->setValue(wifiStatus);
  chScan->setValue("{\"networks\":[]}");
  wifi->start();

  BLEService *pak = server->createService(PAKPAK_SVC);
  txChar = pak->createCharacteristic(PAKPAK_TX, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic *rx = pak->createCharacteristic(PAKPAK_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new PakpakCB());
  pak->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  BLEAdvertisementData ad;
  ad.setFlags(0x06);
  ad.setName(bleName.c_str());
  adv->setAdvertisementData(ad);
  adv->start();
  Serial.printf("BLE %s\n", bleName.c_str());
}

// ── Wi-Fi and HTTP ──────────────────────────────────────────────────────
static void startHttp() {
  if (httpStarted) return;
  httpStarted = true;
  http.on("/", [] {
    String page =
      "<!doctype html><meta name=viewport content=\"width=device-width,initial-scale=1\">"
      "<title>M5Stack</title><body style=\"font-family:system-ui;background:#111;color:#eee;margin:16px\">"
      "<h2>";
    page += bleName;
    page += "</h2><p>IP ";
    page += ipString;
    page += "</p><p>Columns 1–2 left, column 3 middle, columns 4–5 right.</p>"
            "<input id=hex style=\"width:70%\" placeholder=\"55 ... AA\">"
            "<button onclick=\"fetch('/raw?hex='+encodeURIComponent(hex.value)).then(r=>r.text()).then(t=>log.textContent=t)\">Send</button>"
            "<pre id=log></pre></body>";
    http.send(200, "text/html", page);
  });
  http.on("/state", [] {
    String s = "{\"name\":\"" + bleName + "\",\"ip\":\"" + ipString + "\",\"status\":\"" + wifiStatus + "\",\"brightness\":" + String(brightness) + ",\"rings\":[";
    for (int i = 0; i < RINGS; i++) {
      if (i) s += ",";
      s += "{\"btn\":" + String(i + 1) + ",\"r\":" + rings[i].r + ",\"g\":" + rings[i].g + ",\"b\":" + rings[i].b + ",\"pattern\":" + rings[i].pattern + "}";
    }
    s += "]}";
    http.send(200, "application/json", s);
  });
  http.on("/raw", [] {
    uint8_t f[64];
    size_t n = fromHex(http.arg("hex"), f, sizeof f);
    lastTxHex = "";
    if (n) feedBytes(f, n);
    http.send(n ? 200 : 400, "text/plain", n ? lastTxHex : "hex required");
  });
  http.on("/press", [] {
    bool ok = pressButton(http.arg("btn").toInt());
    http.send(ok ? 200 : 400, "text/plain", ok ? lastTxHex : "btn 1..3");
  });
  http.on("/card", [] {
    bool ok = scanCard(http.arg("uid"));
    http.send(ok ? 200 : 400, "text/plain", ok ? lastTxHex : "uid hex required");
  });
  http.begin();
}

static bool tryOne(const String &ssid, const String &pass) {
  publishStatus("connecting");
  WiFi.disconnect(false, false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid.c_str(), pass.c_str());
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 12000) delay(200);
  return WiFi.status() == WL_CONNECTED;
}

static void joinWifi() {
  if (replacePending && pendingSsid.length()) {
    profiles[0].ssid = pendingSsid;
    profiles[0].pass = pendingPass;
    profileCount = 1;
    saveProfiles();
  }
  replacePending = 0;
  pendingSsid = "";
  pendingPass = "";
  if (profileCount == 0) {
    publishStatus("failed");
    return;
  }
  for (int i = 0; i < profileCount; i++) {
    if (!profiles[i].ssid.length()) continue;
    if (!tryOne(profiles[i].ssid, profiles[i].pass)) continue;
    ipString = WiFi.localIP().toString();
    prefs.putString("ssid", profiles[i].ssid);
    prefs.putString("pass", profiles[i].pass);
    if (chSsid) chSsid->setValue(profiles[i].ssid);
    publishStatus("connected " + ipString);
    startHttp();
    restartAdv = true;
    return;
  }
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  String ap = String("M5Stack-") + bleName.substring(6);
  WiFi.softAP(ap.c_str(), "m5stack");
  ipString = WiFi.softAPIP().toString();
  publishStatus("ap " + ipString);
  startHttp();
  restartAdv = true;
}

static void pollButton() {
  static bool down = false;
  static uint32_t downAt = 0, lastUp = 0;
  static int clicks = 0;
  static bool longDone = false;
  bool pressed = digitalRead(PIN_BUTTON) == LOW;
  uint32_t now = millis();
  if (pressed && !down) { down = true; downAt = now; longDone = false; }
  if (pressed && down && !longDone && now - downAt > 800) {
    longDone = true;
    clicks = 0;
    scanCard("04A1B2C3");
  }
  if (!pressed && down) {
    down = false;
    if (!longDone && now - downAt > 30) { clicks++; lastUp = now; }
  }
  if (!down && clicks && now - lastUp > 350) {
    pressButton(min(clicks, RINGS));
    clicks = 0;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUTTON, INPUT);
  bool rmtOk = rmtInit(PIN_MATRIX, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_2, 10000000);
  rmtSetEOT(PIN_MATRIX, LOW);
  Serial.printf("rmt init %d\n", rmtOk);
  prefs.begin("m5conn", false);
  loadProfiles();
  rxQueue = xQueueCreate(16, sizeof(Chunk));
  // Stay off Wi-Fi until the phone sends a network, or a name is already saved.
  // Starting the radio here drops the Bluetooth advert on a cube with no network.
  setupBle();
  columnTest();
  Serial.println("column test: red=left (cols 1-2), green=middle, blue=right (cols 4-5)");
  delay(1500);
  if (profileCount > 0) wifiAction = 1;
}

void loop() {
  Chunk chunk;
  while (xQueueReceive(rxQueue, &chunk, 0) == pdTRUE) feedBytes(chunk.data, chunk.len);
  if (restartAdv) {
    restartAdv = false;
    BLEDevice::startAdvertising();
  }
  if (profileAction) {
    profileAction = 0;
    parseProfilesWrite(pendingProfilesJson);
    pendingProfilesJson = "";
    pendingSsid = "";
    pendingPass = "";
    wifiAction = 1;
  }
  if (wifiAction) {
    wifiAction = 0;
    joinWifi();
  }
  if (scanAction) {
    scanAction = 0;
    runWifiScan();
  }
  if (httpStarted) http.handleClient();
  pollButton();
  static uint32_t lastDraw = 0;
  if (millis() - lastDraw > 30) {
    lastDraw = millis();
    if (faceDriven) render();
    else columnTest();
  }
}
