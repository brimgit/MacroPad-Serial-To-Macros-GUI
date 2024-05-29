#include "FastInterruptEncoder.h"
#include <Keypad.h>
#include <FastLED.h>
#include <EEPROM.h> // Include the EEPROM library

//-------------------------------------------------------FastLED setup-------------------------------------------------------
#define NUMPIXELS  10 // Number of LEDs in each strip
#define MAX_BRIGHTNESS 50 // Max brightness for an LED

// Define the pins for each strip
#define PIN1        5 
#define PIN2        4 
#define PIN3        0 
#define PIN4        2 

CRGB strip1[NUMPIXELS]; // Define LED arrays for each strip
CRGB strip2[NUMPIXELS];
CRGB strip3[NUMPIXELS];
CRGB strip4[NUMPIXELS];

CRGB* strips[4] = {strip1, strip2, strip3, strip4}; // Array of strip arrays

struct Color {
  uint8_t r, g, b;
};

struct StripData {
  Color color;
  Color fadeColor;
  Color volumeColor;
  bool useFade;
  bool useVolume;
  int percentage;
};

StripData stripsData[4]; // Store data for each strip

//-------------------------------------------------------EEPROM Addresses-------------------------------------------------------
#define EEPROM_SIZE 2000 // Define the size of the EEPROM
#define EEPROM_START_ADDRESS 0

//-------------------------------------------------------End setup-------------------------------------------------------
//-------------------------------------------------------Begin Encoders----------------------------------------------------
#define ENCODER_READ_DELAY    50

Encoder enc1(22, 21, SINGLE, 250);
Encoder enc2(33, 32, SINGLE, 250);
Encoder enc3(26, 25, SINGLE, 250);
Encoder enc4(13, 12, SINGLE, 250);
unsigned long encodertimer = 0;

int lastTicks1 = 0;
int lastTicks2 = 0;
int lastTicks3 = 0;
int lastTicks4 = 0;
//-------------------------------------------------------End Encoders----------------------------------------------------

//-------------------------------------------------------Begin Keypad----------------------------------------------------
const byte ROWS = 3;
const byte COLS = 4;
byte rowPins[ROWS] = {14, 27, 23};
byte colPins[COLS] = {16, 17, 18, 19};
char keys[ROWS][COLS] = {
  {'5','6','7','8'},
  {'1','2','3','4'},
  {'A','B','C','D'}
};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);
//-------------------------------------------------------End Keypad----------------------------------------------------

void setup() {
  Serial.begin(115200);
  
  // Initialize EEPROM
  EEPROM.begin(EEPROM_SIZE);
  
  // Initialize all encoders and check each one
  initEncoder(enc1, 0, "Encoder 1");
  initEncoder(enc2, 1, "Encoder 2");
  initEncoder(enc3, 2, "Encoder 3");
  initEncoder(enc4, 3, "Encoder 4");

  // Initialize all FastLED strips
  FastLED.addLeds<NEOPIXEL, PIN1>(strip1, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN2>(strip2, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN3>(strip3, NUMPIXELS).setCorrection(TypicalLEDStrip);
  FastLED.addLeds<NEOPIXEL, PIN4>(strip4, NUMPIXELS).setCorrection(TypicalLEDStrip);

  // Load colors from EEPROM
  loadColorsFromEEPROM();

  // Run the startup sequence
  startupSequence();
}

void initEncoder(Encoder &encoder, int id, const char *name) {
  if (!encoder.init(id)) {
    while (1); // Halt if initialization fails
  }
}
//-------------------------------------------------------Startup sequence----------------------------------------------------

void startupSequence() 
{
  int delayTime = 10; // Time in milliseconds for each color display

  for(int stripIndex = 0; stripIndex < 4; stripIndex++) {
    for(int colorStep = 0; colorStep < 3; colorStep++) { // Cycle through 3 basic colors
      for(int i = 0; i < NUMPIXELS; i++) {
        switch(colorStep) {
          case 0: // Red
            strips[stripIndex][i] = CRGB(MAX_BRIGHTNESS, 0, 0);
            break;
          case 1: // Green
            strips[stripIndex][i] = CRGB(0, MAX_BRIGHTNESS, 0);
            break;
          case 2: // Blue
            strips[stripIndex][i] = CRGB(0, 0, MAX_BRIGHTNESS);
            break;
        }
        FastLED.show();
        delay(delayTime);
      }
    }
    // Turn off all LEDs
    for(int i = 0; i < NUMPIXELS; i++) {
      strips[stripIndex][i] = CRGB(0, 0, 0);
    }
    FastLED.show();
  }
}
//-------------------------------------------------------End Startup Sequence----------------------------------------------------

void loop() 
{
  handleKeypad();
  
  enc1.loop();
  enc2.loop();
  enc3.loop();
  enc4.loop();
   
  if ((unsigned long)(millis() - encodertimer) >= ENCODER_READ_DELAY) 
  {
    // Check for changes and print the corresponding sign with encoder label
    checkAndPrintChange(enc1, lastTicks1, "Enc1");
    checkAndPrintChange(enc2, lastTicks2, "Enc2");
    checkAndPrintChange(enc3, lastTicks3, "Enc3");
    checkAndPrintChange(enc4, lastTicks4, "Enc4");
    
    encodertimer = millis();
  } 

//-------------------------------------------------------Handle FastLED-------------------------------------------------------
  if (Serial.available() > 0) 
  {
    String input = Serial.readStringUntil('\n'); // Read the input string until newline
    if (input.indexOf("colorfade") != -1) {
      int stripIndex;
      int red, green, blue;
      sscanf(input.c_str(), "%d:colorfade(%d,%d,%d)", &stripIndex, &red, &green, &blue);
      stripIndex -= 1; // Convert to 0-based index
      if(stripIndex >= 0 && stripIndex < 4 && red >= 0 && red <= 255 && green >= 0 && green <= 255 && blue >= 0 && blue <= 255) {
        changeStripColorFade(stripIndex, red, green, blue);
      } else {
        Serial.println("Invalid input. Please format as stripIndex:colorfade(R,G,B) (e.g., 1:colorfade(0,255,0)).");
      }
    } else if (input.indexOf("colorvolume") != -1) {
      int stripIndex;
      int red, green, blue;
      sscanf(input.c_str(), "%d:colorvolume(%d,%d,%d)", &stripIndex, &red, &green, &blue);
      stripIndex -= 1; // Convert to 0-based index
      if(stripIndex >= 0 && stripIndex < 4 && red >= 0 && red <= 255 && green >= 0 && green <= 255 && blue >= 0 && blue <= 255) {
        changeStripColorVolume(stripIndex, red, green, blue);
      } else {
        Serial.println("Invalid input. Please format as stripIndex:colorvolume(R,G,B) (e.g., 1:colorvolume(0,255,0)).");
      }
    } else if (input.indexOf("color") != -1) {
      int stripIndex;
      int red, green, blue;
      sscanf(input.c_str(), "%d:color(%d,%d,%d)", &stripIndex, &red, &green, &blue);
      stripIndex -= 1; // Convert to 0-based index
      if(stripIndex >= 0 && stripIndex < 4 && red >= 0 && red <= 255 && green >= 0 && green <= 255 && blue >= 0 && blue <= 255) {
        changeStripColor(stripIndex, red, green, blue);
      } else {
        Serial.println("Invalid input. Please format as stripIndex:color(R,G,B) (e.g., 1:color(255,0,0)).");
      }
    } else {
      int stripIndex = input.charAt(0) - '1'; // Convert the first character to strip index (0-3)
      int percentage = input.substring(2).toInt(); // Extract percentage from the input
      if(stripIndex >= 0 && stripIndex < 4 && percentage >= 0 && percentage <= 100) {
        stripsData[stripIndex].percentage = percentage;
        lightUpPercentage(stripIndex, percentage);
      } else {
        Serial.println("Invalid input. Please format as stripIndex:percentage (e.g., 1:50).");
      }
    }
  }
//-------------------------------------------------------End Handle FastLED-------------------------------------------------------
}

//-------------------------------------------------------Handle LED-Brightness-------------------------------------------------------
void lightUpPercentage(int stripIndex, int percentage) 
{
  int fullLeds = percentage / 10; // Calculate the number of fully lit LEDs
  int partialLedBrightness = (percentage % 10) * (MAX_BRIGHTNESS / 10); // Calculate the brightness for the partially lit LED

  for(int i = 0; i < NUMPIXELS; i++) 
  {
    int red, green, blue;

    if (stripsData[stripIndex].useFade) {
      float factor = (float)percentage / 100.0;
      red = stripsData[stripIndex].color.r * (1 - factor) + stripsData[stripIndex].fadeColor.r * factor;
      green = stripsData[stripIndex].color.g * (1 - factor) + stripsData[stripIndex].fadeColor.g * factor;
      blue = stripsData[stripIndex].color.b * (1 - factor) + stripsData[stripIndex].fadeColor.b * factor;
    } else if (stripsData[stripIndex].useVolume) {
      if (i < 7) {
        // LEDs 0-6 use the original color
        red = stripsData[stripIndex].color.r;
        green = stripsData[stripIndex].color.g;
        blue = stripsData[stripIndex].color.b;
      } else if (i == 7 || i == 8) {
        // LEDs 7-8 transition from the original color to the complementary color
        float factor = (float)(i - 6) / 3.0; // Transition from LED 7 to LED 9
        red = stripsData[stripIndex].color.r * (1 - factor) + stripsData[stripIndex].volumeColor.r * factor;
        green = stripsData[stripIndex].color.g * (1 - factor) + stripsData[stripIndex].volumeColor.g * factor;
        blue = stripsData[stripIndex].color.b * (1 - factor) + stripsData[stripIndex].volumeColor.b * factor;
      } else if (i == 9) {
        // LED 9 is the complementary color
        red = stripsData[stripIndex].volumeColor.r;
        green = stripsData[stripIndex].volumeColor.g;
        blue = stripsData[stripIndex].volumeColor.b;
      } else {
        // Default to the original color for safety
        red = stripsData[stripIndex].color.r;
        green = stripsData[stripIndex].color.g;
        blue = stripsData[stripIndex].color.b;
      }
    } else {
      red = stripsData[stripIndex].color.r;
      green = stripsData[stripIndex].color.g;
      blue = stripsData[stripIndex].color.b;
    }

    if (i < fullLeds) 
    {
      // This LED is fully lit
      strips[stripIndex][i] = CRGB(red, green, blue);
    } else if (i == fullLeds) 
    {
      // This LED is partially lit according to the percentage
      strips[stripIndex][i] = CRGB(
        (red * partialLedBrightness) / MAX_BRIGHTNESS,
        (green * partialLedBrightness) / MAX_BRIGHTNESS,
        (blue * partialLedBrightness) / MAX_BRIGHTNESS
      );
    } else 
    {
      // LEDs that should be off
      strips[stripIndex][i] = CRGB(0, 0, 0); // Turn off
    }
  }
  FastLED.show(); // Update the strip to show the new colors
}

void changeStripColor(int stripIndex, int red, int green, int blue) 
{
  stripsData[stripIndex].color.r = red;
  stripsData[stripIndex].color.g = green;
  stripsData[stripIndex].color.b = blue;
  stripsData[stripIndex].useFade = false;
  stripsData[stripIndex].useVolume = false;
  lightUpPercentage(stripIndex, stripsData[stripIndex].percentage);
  saveColorsToEEPROM();
}

void changeStripColorFade(int stripIndex, int red, int green, int blue) 
{
  stripsData[stripIndex].fadeColor.r = red;
  stripsData[stripIndex].fadeColor.g = green;
  stripsData[stripIndex].fadeColor.b = blue;
  stripsData[stripIndex].useFade = true;
  stripsData[stripIndex].useVolume = false;
  lightUpPercentage(stripIndex, stripsData[stripIndex].percentage);
  saveColorsToEEPROM();
}

void changeStripColorVolume(int stripIndex, int red, int green, int blue) 
{
  stripsData[stripIndex].color.r = red;
  stripsData[stripIndex].color.g = green;
  stripsData[stripIndex].color.b = blue;
  int compRgb[3];
  complementaryRgb(red, green, blue, compRgb);
  stripsData[stripIndex].volumeColor.r = compRgb[0];
  stripsData[stripIndex].volumeColor.g = compRgb[1];
  stripsData[stripIndex].volumeColor.b = compRgb[2];
  stripsData[stripIndex].useFade = false;
  stripsData[stripIndex].useVolume = true;
  lightUpPercentage(stripIndex, stripsData[stripIndex].percentage);
  saveColorsToEEPROM();
}

void complementaryRgb(int r, int g, int b, int compRgb[3]) {
  compRgb[0] = 255 - r;
  compRgb[1] = 255 - g;
  compRgb[2] = 255 - b;
}

//-------------------------------------------------------End Handle LED-Brightness-------------------------------------------------------

void checkAndPrintChange(Encoder &enc, int &lastTicks, const char* label) 
{
  int currentTicks = enc.getTicks();
  if (currentTicks != lastTicks) {
    Serial.print(label);
    Serial.print(": ");
    if (currentTicks > lastTicks) {
      Serial.println("+");
    } else {
      Serial.println("-");
    }
    lastTicks = currentTicks; // Update last ticks to current
  }
}

//-------------------------------------------------------Begin Keypad Function----------------------------------------------------
void handleKeypad() 
{
  if (keypad.getKeys()) {
    for (int i = 0; i < LIST_MAX; i++) {
      if (keypad.key[i].stateChanged) {
        switch (keypad.key[i].kstate) {
          case PRESSED:
          case HOLD:
            Serial.print(keypad.key[i].kchar);
            Serial.print(":");
            Serial.println((keypad.key[i].kstate == PRESSED) ? " Pressed" : " Held");
            break;
            default:
            break;
        }
      }
    }
  }
}
//-------------------------------------------------------End Keypad Function----------------------------------------------------

//-------------------------------------------------------EEPROM Functions-------------------------------------------------------
void saveColorsToEEPROM() 
{
  int address = EEPROM_START_ADDRESS;
  for (int i = 0; i < 4; i++) {
    EEPROM.put(address, stripsData[i]);
    address += sizeof(StripData);
  }
  EEPROM.commit(); // Ensure data is written to EEPROM
}

void loadColorsFromEEPROM() 
{
  int address = EEPROM_START_ADDRESS;
  for (int i = 0; i < 4; i++) {
    EEPROM.get(address, stripsData[i]);
    address += sizeof(StripData);
  }

  // Initialize colors if EEPROM contains no valid data
  for (int i = 0; i < 4; i++) {
    if (stripsData[i].color.r == 255 && stripsData[i].color.g == 255 && stripsData[i].color.b == 255) {
      stripsData[i].color.r = MAX_BRIGHTNESS;
      stripsData[i].color.g = MAX_BRIGHTNESS;
      stripsData[i].color.b = MAX_BRIGHTNESS;
      stripsData[i].fadeColor.r = MAX_BRIGHTNESS;
      stripsData[i].fadeColor.g = MAX_BRIGHTNESS;
      stripsData[i].fadeColor.b = MAX_BRIGHTNESS;
      stripsData[i].volumeColor.r = 255 - MAX_BRIGHTNESS;
      stripsData[i].volumeColor.g = 255 - MAX_BRIGHTNESS;
      stripsData[i].volumeColor.b = 255 - MAX_BRIGHTNESS;
    }
  }
}
//-------------------------------------------------------End EEPROM Functions---------------------------------------------------
