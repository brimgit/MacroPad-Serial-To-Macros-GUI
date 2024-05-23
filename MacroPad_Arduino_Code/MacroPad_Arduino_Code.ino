#include "FastInterruptEncoder.h"
#include <Keypad.h>
#include <Adafruit_NeoPixel.h>
#include <EEPROM.h> // Include the EEPROM library

//-------------------------------------------------------Neopixel setup-------------------------------------------------------
#define PIN1        5 // The pin your first strip is connected to
#define PIN2        4 // Adjust for your second strip
#define PIN3        0 // Adjust for your third strip
#define PIN4        2 // Adjust for your fourth strip
#define NUMPIXELS  10 // Number of LEDs in each strip
#define MAX_BRIGHTNESS 50 // Max brightness for an LED

Adafruit_NeoPixel strips[4] = 
{
  Adafruit_NeoPixel(NUMPIXELS, PIN1, NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(NUMPIXELS, PIN2, NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(NUMPIXELS, PIN3, NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(NUMPIXELS, PIN4, NEO_GRB + NEO_KHZ800)
};

int colors[4][3]; // Store color values for each strip
int fadeColors[4][3]; // Store fade color values for each strip
int volumeColors[4][3]; // Store volume color values for each strip (complementary colors)
bool useFade[4] = {false, false, false, false}; // Store whether to use fade for each strip
bool useVolume[4] = {false, false, false, false}; // Store whether to use volume for each strip
int percentages[4] = {0, 0, 0, 0}; // Store percentage values for each strip

//-------------------------------------------------------EEPROM Addresses-------------------------------------------------------
#define EEPROM_SIZE 128 // Define the size of the EEPROM (increased size to store additional colors)
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

  // Initialize all Neopixel strips
  for(int i = 0; i < 4; i++) 
  {
    strips[i].begin();
    strips[i].show(); // Initialize all pixels to 'off'
  }

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
            strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(MAX_BRIGHTNESS, 0, 0));
            break;
          case 1: // Green
            strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(0, MAX_BRIGHTNESS, 0));
            break;
          case 2: // Blue
            strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(0, 0, MAX_BRIGHTNESS));
            break;
        }
        strips[stripIndex].show();
        delay(delayTime);
      }
    }
    // Turn off all LEDs
    for(int i = 0; i < NUMPIXELS; i++) {
      strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(0, 0, 0));
    }
    strips[stripIndex].show();
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

//-------------------------------------------------------Handle Neopixels-------------------------------------------------------
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
        percentages[stripIndex] = percentage;
        lightUpPercentage(stripIndex, percentage);
      } else {
        Serial.println("Invalid input. Please format as stripIndex:percentage (e.g., 1:50).");
      }
    }
  }
//-------------------------------------------------------End Handle Neopixels-------------------------------------------------------
}

//-------------------------------------------------------Handle LED-Brightness-------------------------------------------------------
void lightUpPercentage(int stripIndex, int percentage) 
{
  int fullLeds = percentage / 10; // Calculate the number of fully lit LEDs
  int partialLedBrightness = (percentage % 10) * (MAX_BRIGHTNESS / 10); // Calculate the brightness for the partially lit LED

  for(int i = 0; i < NUMPIXELS; i++) 
  {
    int red, green, blue;

    if (useFade[stripIndex]) {
      float factor = (float)percentage / 100.0;
      red = colors[stripIndex][0] * (1 - factor) + fadeColors[stripIndex][0] * factor;
      green = colors[stripIndex][1] * (1 - factor) + fadeColors[stripIndex][1] * factor;
      blue = colors[stripIndex][2] * (1 - factor) + fadeColors[stripIndex][2] * factor;
    } else if (useVolume[stripIndex]) {
      if (i < 7) {
        // LEDs 0-6 use the original color
        red = colors[stripIndex][0];
        green = colors[stripIndex][1];
        blue = colors[stripIndex][2];
      } else if (i == 7 || i == 8) {
        // LEDs 7-8 transition from the original color to the complementary color
        float factor = (float)(percentage - 70) / 30.0; // Transition from 70% to 100%
        red = colors[stripIndex][0] * (1 - factor) + volumeColors[stripIndex][0] * factor;
        green = colors[stripIndex][1] * (1 - factor) + volumeColors[stripIndex][1] * factor;
        blue = colors[stripIndex][2] * (1 - factor) + volumeColors[stripIndex][2] * factor;
      } else if (i == 9) {
        // LED 9 is the complementary color
        red = volumeColors[stripIndex][0];
        green = volumeColors[stripIndex][1];
        blue = volumeColors[stripIndex][2];
      } else {
        // Default to the original color for safety
        red = colors[stripIndex][0];
        green = colors[stripIndex][1];
        blue = colors[stripIndex][2];
      }
    } else {
      red = colors[stripIndex][0];
      green = colors[stripIndex][1];
      blue = colors[stripIndex][2];
    }

    if (i < fullLeds) 
    {
      // This LED is fully lit
      strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(red, green, blue));
    } else if (i == fullLeds) 
    {
      // This LED is partially lit according to the percentage
      strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(
        (red * partialLedBrightness) / MAX_BRIGHTNESS,
        (green * partialLedBrightness) / MAX_BRIGHTNESS,
        (blue * partialLedBrightness) / MAX_BRIGHTNESS
      ));
    } else 
    {
      // LEDs that should be off
      strips[stripIndex].setPixelColor(i, strips[stripIndex].Color(0, 0, 0)); // Turn off
    }
  }
  strips[stripIndex].show(); // Update the strip to show the new colors
}

void changeStripColor(int stripIndex, int red, int green, int blue) 
{
  colors[stripIndex][0] = red;
  colors[stripIndex][1] = green;
  colors[stripIndex][2] = blue;
  useFade[stripIndex] = false;
  useVolume[stripIndex] = false;
  lightUpPercentage(stripIndex, percentages[stripIndex]);
  saveColorsToEEPROM();
}

void changeStripColorFade(int stripIndex, int red, int green, int blue) 
{
  fadeColors[stripIndex][0] = red;
  fadeColors[stripIndex][1] = green;
  fadeColors[stripIndex][2] = blue;
  useFade[stripIndex] = true;
  useVolume[stripIndex] = false;
  lightUpPercentage(stripIndex, percentages[stripIndex]);
  saveColorsToEEPROM();
}

void changeStripColorVolume(int stripIndex, int red, int green, int blue) 
{
  colors[stripIndex][0] = red;
  colors[stripIndex][1] = green;
  colors[stripIndex][2] = blue;
  int ryb[3];
  int compRyb[3];
  int compRgb[3];
  rgbToRyb(red, green, blue, ryb);
  complementaryRyb(ryb, compRyb);
  rybToRgb(compRyb[0], compRyb[1], compRyb[2], compRgb);
  volumeColors[stripIndex][0] = compRgb[0];
  volumeColors[stripIndex][1] = compRgb[1];
  volumeColors[stripIndex][2] = compRgb[2];
  useFade[stripIndex] = false;
  useVolume[stripIndex] = true;
  lightUpPercentage(stripIndex, percentages[stripIndex]);
  saveColorsToEEPROM();
}

void rgbToRyb(int r, int g, int b, int ryb[3]) {
  float w = fmin(r, fmin(g, b));
  float y = fmin(r, g) - w;
  float m = fmin(g, b) - w;
  float c = fmin(r, b) - w;

  ryb[0] = r - y - c;
  ryb[1] = g - m - c;
  ryb[2] = b - m - c;

  ryb[0] += m;
  ryb[1] += y;
  ryb[2] += c;
}

void rybToRgb(int ry, int y, int b, int rgb[3]) {
  float w = fmin(ry, fmin(y, b));
  float r = ry + w;
  float g = y + w;
  float c = b + w;

  rgb[0] = r;
  rgb[1] = g - r;
  rgb[2] = c - r;
}

void complementaryRyb(int ryb[3], int compRyb[3]) {
  compRyb[0] = 255 - ryb[0];
  compRyb[1] = 255 - ryb[1];
  compRyb[2] = 255 - ryb[2];
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
  for (int i = 0; i < 4; i++) {
    EEPROM.write(EEPROM_START_ADDRESS + i * 3, colors[i][0]);
    EEPROM.write(EEPROM_START_ADDRESS + i * 3 + 1, colors[i][1]);
    EEPROM.write(EEPROM_START_ADDRESS + i * 3 + 2, colors[i][2]);
    EEPROM.write(EEPROM_START_ADDRESS + 12 + i * 3, fadeColors[i][0]);
    EEPROM.write(EEPROM_START_ADDRESS + 12 + i * 3 + 1, fadeColors[i][1]);
    EEPROM.write(EEPROM_START_ADDRESS + 12 + i * 3 + 2, fadeColors[i][2]);
    EEPROM.write(EEPROM_START_ADDRESS + 24 + i * 3, volumeColors[i][0]);
    EEPROM.write(EEPROM_START_ADDRESS + 24 + i * 3 + 1, volumeColors[i][1]);
    EEPROM.write(EEPROM_START_ADDRESS + 24 + i * 3 + 2, volumeColors[i][2]);
  }
  EEPROM.commit(); // Ensure data is written to EEPROM
}

void loadColorsFromEEPROM() 
{
  bool validData = false;
  for (int i = 0; i < 4; i++) {
    int red = EEPROM.read(EEPROM_START_ADDRESS + i * 3);
    int green = EEPROM.read(EEPROM_START_ADDRESS + i * 3 + 1);
    int blue = EEPROM.read(EEPROM_START_ADDRESS + i * 3 + 2);

    if (red != 255 || green != 255 || blue != 255) {
      validData = true;
    }
    
    colors[i][0] = red;
    colors[i][1] = green;
    colors[i][2] = blue;
    // Initialize fade colors to default color
    fadeColors[i][0] = EEPROM.read(EEPROM_START_ADDRESS + 12 + i * 3);
    fadeColors[i][1] = EEPROM.read(EEPROM_START_ADDRESS + 12 + i * 3 + 1);
    fadeColors[i][2] = EEPROM.read(EEPROM_START_ADDRESS + 12 + i * 3 + 2);
    volumeColors[i][0] = EEPROM.read(EEPROM_START_ADDRESS + 24 + i * 3);
    volumeColors[i][1] = EEPROM.read(EEPROM_START_ADDRESS + 24 + i * 3 + 1);
    volumeColors[i][2] = EEPROM.read(EEPROM_START_ADDRESS + 24 + i * 3 + 2);
  }

  if (!validData) {
    // Initialize colors to white if EEPROM contains no valid data
    for (int i = 0; i < 4; i++) {
      colors[i][0] = MAX_BRIGHTNESS;
      colors[i][1] = MAX_BRIGHTNESS;
      colors[i][2] = MAX_BRIGHTNESS;
      fadeColors[i][0] = MAX_BRIGHTNESS;
      fadeColors[i][1] = MAX_BRIGHTNESS;
      fadeColors[i][2] = MAX_BRIGHTNESS;
      volumeColors[i][0] = 255 - MAX_BRIGHTNESS;
      volumeColors[i][1] = 255 - MAX_BRIGHTNESS;
      volumeColors[i][2] = 255 - MAX_BRIGHTNESS;
    }
  }
}
//-------------------------------------------------------End EEPROM Functions---------------------------------------------------
