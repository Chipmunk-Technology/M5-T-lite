#pragma once

#include <stdint.h>

void panel_begin();
void panel_set_status(const char* text);
void panel_set_sentence(const char* utf8, bool emphasis);
void panel_set_battery(int percent);
void panel_render();
