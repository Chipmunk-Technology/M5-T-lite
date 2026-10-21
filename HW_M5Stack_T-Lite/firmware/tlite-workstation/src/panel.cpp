#include "panel.h"

#include <M5Unified.h>
#include <string.h>

static M5Canvas canvas(&M5.Display);
static char status_line[32] = "未連線";
static char sentence[160] = "";
static int battery = -1;
static bool emphasis = false;
static bool dirty = true;

void panel_begin() {
    if (M5.Display.width() > M5.Display.height()) {
        M5.Display.setRotation((M5.Display.getRotation() + 1) & 3);
    }
    canvas.setColorDepth(16);
    canvas.createSprite(M5.Display.width(), M5.Display.height());
    canvas.setFont(&fonts::efontCN_14);
    canvas.setTextWrap(true);
    dirty = true;
    panel_render();
}

void panel_set_status(const char* text) {
    if (!text) {
        text = "";
    }
    if (strncmp(status_line, text, sizeof(status_line)) != 0) {
        strncpy(status_line, text, sizeof(status_line) - 1);
        status_line[sizeof(status_line) - 1] = 0;
        dirty = true;
    }
}

void panel_set_sentence(const char* utf8, bool emph) {
    if (!utf8) {
        utf8 = "";
    }
    if (emphasis != emph || strncmp(sentence, utf8, sizeof(sentence)) != 0) {
        strncpy(sentence, utf8, sizeof(sentence) - 1);
        sentence[sizeof(sentence) - 1] = 0;
        emphasis = emph;
        dirty = true;
    }
}

void panel_set_battery(int percent) {
    if (percent != battery) {
        battery = percent;
        dirty = true;
    }
}

void panel_render() {
    if (!dirty) {
        return;
    }
    dirty = false;
    const int w = canvas.width();
    const int h = canvas.height();
    canvas.fillSprite(canvas.color565(246, 241, 232));
    canvas.setTextColor(canvas.color565(28, 25, 21));
    canvas.setCursor(6, 8);
    canvas.print(status_line);

    canvas.setTextColor(emphasis ? canvas.color565(154, 52, 18) : canvas.color565(28, 25, 21));
    canvas.setCursor(6, 48);
    canvas.setClipRect(4, 40, w - 8, h - 88);
    canvas.print(sentence);
    canvas.clearClipRect();

    canvas.setTextColor(canvas.color565(28, 25, 21));
    canvas.setCursor(6, h - 28);
    if (battery >= 0 && battery <= 100) {
        canvas.printf("電量 %d%%", battery);
    } else {
        canvas.print("電量 —");
    }
    canvas.pushSprite(0, 0);
}
