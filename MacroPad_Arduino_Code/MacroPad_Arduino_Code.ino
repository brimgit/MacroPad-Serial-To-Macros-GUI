#include "FastInterruptEncoder.h"
#include <Keypad.h>
#include <FastLED.h>
#include <EEPROM.h>

// ─── LED config ───────────────────────────────────────────────────────────────
#define NUMPIXELS      10
#define MAX_BRIGHTNESS 50

#define PIN1 5
#define PIN2 4
#define PIN3 0
#define PIN4 2

CRGB strip1[NUMPIXELS];
CRGB strip2[NUMPIXELS];
CRGB strip3[NUMPIXELS];
CRGB strip4[NUMPIXELS];
CRGB* strips[4] = { strip1, strip2, strip3, strip4 };

struct Color {
  uint8_t r, g, b;
};

struct StripData {
  Color   color;
  Color   fadeColor;
  Color   volumeColor;
  bool    useFade;
  bool    useVolume;
  int     percentage;
  uint8_t blendStart;   // 0-90: LED position (%) where fade gradient begins
};

StripData stripsData[4];

// ─── EEPROM ───────────────────────────────────────────────────────────────────
#define EEPROM_SIZE          2000
#define EEPROM_MAGIC_ADDR    0      // version byte — bump to force reinit on layout change
#define EEPROM_MAGIC_VAL     0xB1
#define EEPROM_DATA_START    4

// ─── Encoders (0-indexed, matches Python E:0..E:3) ────────────────────────────
#define ENCODER_READ_DELAY 50

Encoder enc0(22, 21, SINGLE, 250);
Encoder enc1(33, 32, SINGLE, 250);
Encoder enc2(26, 25, SINGLE, 250);
Encoder enc3(13, 12, SINGLE, 250);
unsigned long encoderTimer = 0;
int lastTicks[4] = { 0, 0, 0, 0 };
unsigned long encoderActivityTime[4] = { 0, 0, 0, 0 };
unsigned long encoderLedTimeoutMs = 2000UL;
uint8_t stripEffect[4]  = { 0, 0, 0, 0 };  // 0=off 1=breathe 2=wave 3=rainbow 4=chase 5=colorcycle 6=sparkle
float   effectPhase[4]  = { 0.0f, 0.0f, 0.0f, 0.0f };
unsigned long effectTimer = 0;
unsigned long effectInterval = 10;

// ─── Keypad ───────────────────────────────────────────────────────────────────
const byte ROWS = 3;
const byte COLS = 4;
byte rowPins[ROWS] = { 14, 27, 23 };
byte colPins[COLS] = { 16, 17, 18, 19 };
char keys[ROWS][COLS] = {
  { '5','6','7','8' },
  { '1','2','3','4' },
  { 'A','B','C','D' }
};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);
unsigned long keyPressTimes[LIST_MAX];


// ─── setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  EEPROM.begin(EEPROM_SIZE);

  if (!enc0.init(0)) while (1);
  if (!enc1.init(1)) while (1);
  if (!enc2.init(2)) while (1);
  if (!enc3.init(3)) while (1);

  FastLED.addLeds<NEOPIXEL, PIN1>(strip1, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN2>(strip2, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN3>(strip3, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN4>(strip4, NUMPIXELS).setCorrection(TypicalLEDStrip);

  FastLED.setBrightness(25);  // default 10% — overridden by Python on connect
  loadColorsFromEEPROM();
  startupSequence();

  // Start with all strips off; each lights up when its encoder is turned
  for (int i = 0; i < 4; i++)
    fill_solid(strips[i], NUMPIXELS, CRGB::Black);
  FastLED.show();
}

// ─── Startup: all strips flash red×3, green×3, blue×3 ────────────────────────
void startupSequence() {
  uint8_t cr[3] = { MAX_BRIGHTNESS, 0,              0              };
  uint8_t cg[3] = { 0,             MAX_BRIGHTNESS,  0              };
  uint8_t cb[3] = { 0,             0,               MAX_BRIGHTNESS };

  uint8_t* cols[3][3] = { {cr, cg, cb} };  // unused, just iterate manually

  for (int c = 0; c < 3; c++) {
    uint8_t r = (c == 0) ? MAX_BRIGHTNESS : 0;
    uint8_t g = (c == 1) ? MAX_BRIGHTNESS : 0;
    uint8_t bv = (c == 2) ? MAX_BRIGHTNESS : 0;

    for (int flash = 0; flash < 3; flash++) {
      for (int s = 0; s < 4; s++)
        for (int i = 0; i < NUMPIXELS; i++)
          strips[s][i] = CRGB(r, g, bv);
      FastLED.show();
      delay(150);

      for (int s = 0; s < 4; s++)
        for (int i = 0; i < NUMPIXELS; i++)
          strips[s][i] = CRGB(0, 0, 0);
      FastLED.show();
      delay(100);
    }
  }
}

// ─── loop ─────────────────────────────────────────────────────────────────────
void loop() {
  handleKeypad();

  enc0.loop();
  enc1.loop();
  enc2.loop();
  enc3.loop();

  if ((unsigned long)(millis() - encoderTimer) >= ENCODER_READ_DELAY) {
    checkEncoder(enc0, lastTicks[0], 0);
    checkEncoder(enc1, lastTicks[1], 1);
    checkEncoder(enc2, lastTicks[2], 2);
    checkEncoder(enc3, lastTicks[3], 3);
    encoderTimer = millis();
  }

  // Turn off (or start breathing) each strip after encoder inactivity
  for (int i = 0; i < 4; i++) {
    if (encoderActivityTime[i] > 0 &&
        (millis() - encoderActivityTime[i] > encoderLedTimeoutMs)) {
      encoderActivityTime[i] = 0;
      if (stripEffect[i] == 0) {
        fill_solid(strips[i], NUMPIXELS, CRGB::Black);
        FastLED.show();
      }
      // If an effect is active, updateEffects() will animate from here
    }
  }

  updateEffects();

  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;
    handleLEDCommand(input);
  }
}

// ─── Idle LED effects (runs at ~60 fps) ──────────────────────────────────────
void updateEffects() {
  if ((millis() - effectTimer) < effectInterval) return;
  effectTimer = millis();

  bool changed = false;
  for (int i = 0; i < 4; i++) {
    if (stripEffect[i] == 0 || encoderActivityTime[i] > 0) continue;
    Color c = stripsData[i].color;
    float &ph = effectPhase[i];

    switch (stripEffect[i]) {

      case 1: { // Breathe — smootherstep curve, stays bright longer, no dark snap
        float t = (sinf(ph) + 1.0f) * 0.5f;
        t = t * t * t * (t * (6.0f * t - 15.0f) + 10.0f);  // smootherstep
        float br = 0.13f + t * 0.70f;                        // 13-83%, avoids quantisation at dark end
        for (int j = 0; j < NUMPIXELS; j++)
          strips[i][j] = CRGB((uint8_t)(c.r*br),(uint8_t)(c.g*br),(uint8_t)(c.b*br));
        ph += 0.012f;
        break;
      }
      case 2: { // Wave — ripple across strip
        for (int j = 0; j < NUMPIXELS; j++) {
          float angle = ph + (float)j * (6.2832f / NUMPIXELS);
          float br = (sinf(angle) + 1.0f) * 0.5f;
          br = 0.04f + br * 0.78f;
          strips[i][j] = CRGB((uint8_t)(c.r*br),(uint8_t)(c.g*br),(uint8_t)(c.b*br));
        }
        ph += 0.034f;
        break;
      }
      case 3: { // Rainbow — hue band scrolls
        uint8_t hue = (uint8_t)ph;
        for (int j = 0; j < NUMPIXELS; j++) {
          CRGB rgb;
          hsv2rgb_rainbow(CHSV(hue + (j * 256 / NUMPIXELS), 240, 200), rgb);
          strips[i][j] = rgb;
        }
        ph += 0.22f;
        if (ph >= 256.0f) ph -= 256.0f;
        break;
      }
      case 4: { // Chase — glowing dot with fade trail
        for (int j = 0; j < NUMPIXELS; j++)
          strips[i][j].fadeToBlackBy(55);
        int pos = (int)ph % NUMPIXELS;
        strips[i][pos]              = CRGB(c.r, c.g, c.b);
        strips[i][(pos+1)%NUMPIXELS] = CRGB(c.r*0.5f, c.g*0.5f, c.b*0.5f);
        ph += 0.11f;
        if (ph >= NUMPIXELS) ph -= NUMPIXELS;
        break;
      }
      case 5: { // Color Cycle — all LEDs same interpolated color, glassy smooth
        uint8_t h0 = (uint8_t)ph;
        float   t  = ph - (float)h0;
        CRGB c0, c1;
        hsv2rgb_rainbow(CHSV(h0,     255, 210), c0);
        hsv2rgb_rainbow(CHSV(h0 + 1, 255, 210), c1);
        CRGB blended;
        blended.r = (uint8_t)(c0.r + (c1.r - c0.r) * t);
        blended.g = (uint8_t)(c0.g + (c1.g - c0.g) * t);
        blended.b = (uint8_t)(c0.b + (c1.b - c0.b) * t);
        fill_solid(strips[i], NUMPIXELS, blended);
        ph += 0.063f;
        if (ph >= 256.0f) ph -= 256.0f;
        break;
      }
      case 6: { // Sparkle — random twinkles in strip color
        for (int j = 0; j < NUMPIXELS; j++)
          strips[i][j].fadeToBlackBy(35);
        if (random8() < 70) {
          uint8_t pos = random8(NUMPIXELS);
          uint8_t br  = random8(160, 255);
          strips[i][pos] = CRGB((uint8_t)(c.r*br/255),(uint8_t)(c.g*br/255),(uint8_t)(c.b*br/255));
        }
        break;
      }
    }

    if (ph > 6.2832f && stripEffect[i] <= 2) ph -= 6.2832f;
    changed = true;
  }
  if (changed) FastLED.show();
}

// ─── Encoder output: E:N:+  or  E:N:-  (N = 0-3) ────────────────────────────
void checkEncoder(Encoder &enc, int &last, int idx) {
  int cur = enc.getTicks();
  if (cur != last) {
    Serial.print("E:");
    Serial.print(idx);
    Serial.print(":");
    Serial.println(cur > last ? "+" : "-");
    last = cur;
    encoderActivityTime[idx] = millis();
    lightUpPercentage(idx, stripsData[idx].percentage);
  }
}

// ─── Keypad output: KP:<key>:DOWN  /  KP:<key>:UP:<ms> ───────────────────────
void handleKeypad() {
  if (keypad.getKeys()) {
    for (int i = 0; i < LIST_MAX; i++) {
      if (!keypad.key[i].stateChanged) continue;
      char k = keypad.key[i].kchar;
      switch (keypad.key[i].kstate) {
        case PRESSED:
          keyPressTimes[i] = millis();
          Serial.print("KP:");
          Serial.print(k);
          Serial.println(":DOWN");
          break;
        case RELEASED: {
          unsigned long holdMs = millis() - keyPressTimes[i];
          Serial.print("KP:");
          Serial.print(k);
          Serial.print(":UP:");
          Serial.println(holdMs);
          break;
        }
        default:
          break;
      }
    }
  }
}

// ─── LED serial command parser ────────────────────────────────────────────────
// Commands (strip index N is 1-based):
//   BRIGHT:V               global brightness 0-255
//   N:colorvolume(R,G,B)   volume bar mode
//   N:colorfade(R,G,B)     fade mode
//   N:color(R,G,B)         solid colour
//   N:P                    set percentage 0-100
void handleLEDCommand(String &input) {
  if (input.startsWith("BRIGHT:")) {
    int val = constrain(input.substring(7).toInt(), 0, 255);
    FastLED.setBrightness(val);
    FastLED.show();
    return;
  }

  if (input.startsWith("ENC_TIMEOUT:")) {
    unsigned long secs = (unsigned long)input.substring(12).toInt();
    encoderLedTimeoutMs = secs * 1000UL;
    return;
  }

  if (input.startsWith("EFFECT_SPEED:")) {
    unsigned long ms = (unsigned long)input.substring(13).toInt();
    if (ms >= 1 && ms <= 200) effectInterval = ms;
    return;
  }

  if (input.startsWith("EFFECT:")) {
    int n, val;
    if (sscanf(input.c_str(), "EFFECT:%d:%d", &n, &val) == 2) {
      int idx = n - 1;
      if (idx >= 0 && idx < 4) {
        stripEffect[idx] = (uint8_t)constrain(val, 0, 6);
        effectPhase[idx] = 0.0f;
        if (stripEffect[idx] == 0 && encoderActivityTime[idx] == 0) {
          fill_solid(strips[idx], NUMPIXELS, CRGB::Black);
          FastLED.show();
        }
      }
    }
    return;
  }

  if (input.indexOf("colorfade") != -1) {
    int n, r1, g1, b1, r2, g2, b2, bs;
    // Format: N:colorfade(R1,G1,B1,R2,G2,B2,BLEND_START)
    if (sscanf(input.c_str(), "%d:colorfade(%d,%d,%d,%d,%d,%d,%d)",
               &n, &r1, &g1, &b1, &r2, &g2, &b2, &bs) == 8) {
      int idx = n - 1;
      if (idx >= 0 && idx < 4)
        changeStripColorFade(idx, r1, g1, b1, r2, g2, b2, (uint8_t)constrain(bs, 0, 90));
    }

  } else if (input.indexOf("colorvolume") != -1) {
    int n, r, g, b;
    if (sscanf(input.c_str(), "%d:colorvolume(%d,%d,%d)", &n, &r, &g, &b) == 4) {
      int idx = n - 1;
      if (idx >= 0 && idx < 4 && r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255)
        changeStripColorVolume(idx, r, g, b);
    }

  } else if (input.indexOf("color") != -1) {
    int n, r, g, b;
    if (sscanf(input.c_str(), "%d:color(%d,%d,%d)", &n, &r, &g, &b) == 4) {
      int idx = n - 1;
      if (idx >= 0 && idx < 4 && r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255)
        changeStripColor(idx, r, g, b);
    }

  } else {
    int colonPos = input.indexOf(':');
    if (colonPos > 0) {
      int idx = input.substring(0, colonPos).toInt() - 1;
      int pct = input.substring(colonPos + 1).toInt();
      if (idx >= 0 && idx < 4 && pct >= 0 && pct <= 100) {
        stripsData[idx].percentage = pct;
        lightUpPercentage(idx, pct);
      }
    }
  }
}

// ─── LED rendering ────────────────────────────────────────────────────────────
void lightUpPercentage(int idx, int pct) {
  encoderActivityTime[idx] = millis();  // reset timeout whenever a strip is lit
  int fullLeds          = pct / 10;
  int partialBrightness = (pct % 10) * (MAX_BRIGHTNESS / 10);

  for (int i = 0; i < NUMPIXELS; i++) {
    uint8_t r, g, b;

    if (stripsData[idx].useFade) {
      // Gradient is across LED positions, not volume percentage.
      // blendStart (0-90%) = the LED position where colour begins to transition.
      float ledPos = (NUMPIXELS > 1) ? (float)i / (float)(NUMPIXELS - 1) : 0.0f;
      float blendS = stripsData[idx].blendStart / 100.0f;
      float t = 0.0f;
      if (ledPos > blendS && blendS < 1.0f)
        t = (ledPos - blendS) / (1.0f - blendS);
      t = max(0.0f, min(1.0f, t));
      r = (uint8_t)(stripsData[idx].color.r   * (1.0f - t) + stripsData[idx].fadeColor.r * t);
      g = (uint8_t)(stripsData[idx].color.g   * (1.0f - t) + stripsData[idx].fadeColor.g * t);
      b = (uint8_t)(stripsData[idx].color.b   * (1.0f - t) + stripsData[idx].fadeColor.b * t);

    } else if (stripsData[idx].useVolume) {
      if (i < 7) {
        r = stripsData[idx].color.r;
        g = stripsData[idx].color.g;
        b = stripsData[idx].color.b;
      } else if (i <= 8) {
        float t = (float)(i - 6) / 3.0f;
        r = (uint8_t)(stripsData[idx].color.r    * (1.0f - t) + stripsData[idx].volumeColor.r * t);
        g = (uint8_t)(stripsData[idx].color.g    * (1.0f - t) + stripsData[idx].volumeColor.g * t);
        b = (uint8_t)(stripsData[idx].color.b    * (1.0f - t) + stripsData[idx].volumeColor.b * t);
      } else {
        r = stripsData[idx].volumeColor.r;
        g = stripsData[idx].volumeColor.g;
        b = stripsData[idx].volumeColor.b;
      }

    } else {
      r = stripsData[idx].color.r;
      g = stripsData[idx].color.g;
      b = stripsData[idx].color.b;
    }

    if (i < fullLeds) {
      strips[idx][i] = CRGB(r, g, b);
    } else if (i == fullLeds) {
      strips[idx][i] = CRGB(
        (uint8_t)((r * partialBrightness) / MAX_BRIGHTNESS),
        (uint8_t)((g * partialBrightness) / MAX_BRIGHTNESS),
        (uint8_t)((b * partialBrightness) / MAX_BRIGHTNESS)
      );
    } else {
      strips[idx][i] = CRGB(0, 0, 0);
    }
  }
  FastLED.show();
}

void changeStripColor(int idx, int r, int g, int b) {
  stripsData[idx].color.r   = (uint8_t)r;
  stripsData[idx].color.g   = (uint8_t)g;
  stripsData[idx].color.b   = (uint8_t)b;
  stripsData[idx].useFade   = false;
  stripsData[idx].useVolume = false;
  lightUpPercentage(idx, stripsData[idx].percentage);
  saveColorsToEEPROM();
}

void changeStripColorFade(int idx, int r1, int g1, int b1,
                          int r2, int g2, int b2, uint8_t blendStart) {
  stripsData[idx].color.r     = (uint8_t)r1;
  stripsData[idx].color.g     = (uint8_t)g1;
  stripsData[idx].color.b     = (uint8_t)b1;
  stripsData[idx].fadeColor.r = (uint8_t)r2;
  stripsData[idx].fadeColor.g = (uint8_t)g2;
  stripsData[idx].fadeColor.b = (uint8_t)b2;
  stripsData[idx].blendStart  = blendStart;
  stripsData[idx].useFade     = true;
  stripsData[idx].useVolume   = false;
  lightUpPercentage(idx, stripsData[idx].percentage);
  saveColorsToEEPROM();
}

void changeStripColorVolume(int idx, int r, int g, int b) {
  stripsData[idx].color.r       = (uint8_t)r;
  stripsData[idx].color.g       = (uint8_t)g;
  stripsData[idx].color.b       = (uint8_t)b;
  stripsData[idx].volumeColor.r = (uint8_t)(255 - r);
  stripsData[idx].volumeColor.g = (uint8_t)(255 - g);
  stripsData[idx].volumeColor.b = (uint8_t)(255 - b);
  stripsData[idx].useFade       = false;
  stripsData[idx].useVolume     = true;
  lightUpPercentage(idx, stripsData[idx].percentage);
  saveColorsToEEPROM();
}

// ─── EEPROM ───────────────────────────────────────────────────────────────────
void initDefaultStrips() {
  for (int i = 0; i < 4; i++) {
    stripsData[i].color.r       = MAX_BRIGHTNESS;
    stripsData[i].color.g       = MAX_BRIGHTNESS;
    stripsData[i].color.b       = MAX_BRIGHTNESS;
    stripsData[i].fadeColor.r   = 255;
    stripsData[i].fadeColor.g   = 100;
    stripsData[i].fadeColor.b   = 0;
    stripsData[i].volumeColor.r = (uint8_t)(255 - MAX_BRIGHTNESS);
    stripsData[i].volumeColor.g = (uint8_t)(255 - MAX_BRIGHTNESS);
    stripsData[i].volumeColor.b = (uint8_t)(255 - MAX_BRIGHTNESS);
    stripsData[i].useFade       = false;
    stripsData[i].useVolume     = false;
    stripsData[i].percentage    = 50;
    stripsData[i].blendStart    = 0;
  }
}

void saveColorsToEEPROM() {
  EEPROM.put(EEPROM_MAGIC_ADDR, (uint8_t)EEPROM_MAGIC_VAL);
  int addr = EEPROM_DATA_START;
  for (int i = 0; i < 4; i++) {
    EEPROM.put(addr, stripsData[i]);
    addr += sizeof(StripData);
  }
  EEPROM.commit();
}

void loadColorsFromEEPROM() {
  uint8_t magic;
  EEPROM.get(EEPROM_MAGIC_ADDR, magic);
  if (magic != EEPROM_MAGIC_VAL) {
    // Struct layout changed — reinitialise with safe defaults
    initDefaultStrips();
    saveColorsToEEPROM();
    return;
  }
  int addr = EEPROM_DATA_START;
  for (int i = 0; i < 4; i++) {
    EEPROM.get(addr, stripsData[i]);
    addr += sizeof(StripData);
  }
  for (int i = 0; i < 4; i++) {
    if (stripsData[i].percentage < 0 || stripsData[i].percentage > 100)
      stripsData[i].percentage = 50;
    if (stripsData[i].blendStart > 90)
      stripsData[i].blendStart = 0;
  }
}
