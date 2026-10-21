#pragma once

#include <Arduino.h>
#include <stdint.h>

// USB link for 熱記憶. Little-endian. CRC-16/CCITT-FALSE over the bytes before the CRC.
// Baud 460800 is the workstation link. Flash backup stays at 115200.

static const uint8_t PROTO_VERSION = 1;
static const int PIXEL_COUNT = 768;
static const int MASK_BYTES = 96;

static const uint8_t FLAG_COMPLETE = 0x01;
static const uint8_t FLAG_SUBPAGE = 0x02;
static const uint8_t FLAG_EVENT = 0x04;
static const uint8_t FLAG_BUTTON = 0x08;
static const uint8_t FLAG_ARMED = 0x10;
static const uint8_t FLAG_STEADY = 0x20;
static const uint8_t FLAG_STORED = 0x40;

static const uint8_t CMD_SET_SENTRY = 1;
static const uint8_t CMD_SET_MASK = 2;
static const uint8_t CMD_SET_COND = 3;
static const uint8_t CMD_SET_TEXT = 4;
static const uint8_t CMD_SET_WORK = 5;
static const uint8_t CMD_PING = 6;

static const uint8_t WORK_MEMORY = 0;
static const uint8_t WORK_LEAK = 1;
static const uint8_t WORK_SENTRY = 2;

static const uint8_t SENS_HIGH = 0;
static const uint8_t SENS_MID = 1;
static const uint8_t SENS_LOW = 2;

// Sentry design contract (not yet measured on this unit).
static const float SENTRY_TAU_S = 30.0f;
static const float SENTRY_FAST_TAU_S = 3.0f;
static const uint32_t SENTRY_QUIET_MS = 10000;

uint16_t proto_crc16(const uint8_t* data, size_t len);
