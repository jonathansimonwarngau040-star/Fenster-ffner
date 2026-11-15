// Test 2 (von Claude geflasht): LED blinkt schnell, Board scannt seine
// eingebauten Sensoren am internen I2C-Bus (Wire1) und meldet sie per Serial.
#include <Wire.h>

struct Chip { uint8_t addr; const char* name; };
const Chip known[] = {
  {0x6B, "LSM9DS1 IMU (Rev1)"}, {0x1E, "LSM9DS1 Magnetometer (Rev1)"},
  {0x68, "BMI270 IMU (Rev2)"},  {0x10, "BMM150 Magnetometer (Rev2)"},
  {0x5F, "HTS221 Temp/Feuchte (Sense Rev1)"}, {0x44, "HS3003 Temp/Feuchte (Sense Rev2)"},
  {0x5C, "LPS22HB Luftdruck (Sense)"}, {0x39, "APDS9960 Licht/Naeherung/Gesten (Sense)"},
};

void scan() {
  Serial.println("scan;start");
  for (uint8_t a = 1; a < 127; a++) {
    Wire1.beginTransmission(a);
    if (Wire1.endTransmission() == 0) {
      const char* n = "unbekannt";
      for (auto& c : known) if (c.addr == a) n = c.name;
      Serial.print("scan;0x"); Serial.print(a, HEX); Serial.print(";"); Serial.println(n);
    }
  }
  Serial.println("scan;ende");
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  Wire1.begin();
  delay(2000);
}

unsigned long lastScan = 0;
void loop() {
  digitalWrite(LED_BUILTIN, (millis() / 150) % 2);
  if (millis() - lastScan > 10000) {  // alle 10 s, damit es sicher im Log landet
    lastScan = millis();
    scan();
  }
}
