// Raumluft-Logger: SCD41 (CO2, Temperatur, Feuchte) am Nano 33 BLE
// Anschluss: VCC->3V3, GND->GND, SDA->A4, SCL->A5
// Serial-Ausgabe (alle 30 s, Mittelwert): luft;CO2_ppm;Temp_C;Feuchte_%
// RGB-LED als Ampel: gruen <1000 ppm, gelb 1000-1400, rot >1400
#include <Wire.h>
#include <SensirionI2cScd4x.h>

SensirionI2cScd4x scd;
const unsigned long LOG_MS = 30000;

void led(bool r, bool g, bool b) {          // RGB-LED ist active-low
  digitalWrite(LEDR, !r); digitalWrite(LEDG, !g); digitalWrite(LEDB, !b);
}

bool startSensor() {
  scd.begin(Wire, SCD41_I2C_ADDR_62);
  scd.wakeUp();
  scd.stopPeriodicMeasurement();
  delay(500);
  scd.reinit();
  return scd.startPeriodicMeasurement() == 0;
}

bool sensorOk = false;
unsigned long lastLog = 0, lastRetry = 0;
float sumCo2 = 0, sumT = 0, sumRh = 0; int n = 0;

void setup() {
  pinMode(LEDR, OUTPUT); pinMode(LEDG, OUTPUT); pinMode(LEDB, OUTPUT);
  led(0, 0, 1);
  Serial.begin(115200);
  Wire.begin();
  delay(2000);
  sensorOk = startSensor();
  Serial.println(sensorOk ? "status;SCD41 gestartet" : "fehler;SCD41 nicht gefunden");
}

void loop() {
  if (!sensorOk) {
    led((millis() / 500) % 2, 0, 0);          // rot blinken = kein Sensor
    if (millis() - lastRetry > 10000) {
      lastRetry = millis();
      sensorOk = startSensor();
      Serial.println(sensorOk ? "status;SCD41 gestartet" : "fehler;SCD41 nicht gefunden");
    }
    return;
  }

  bool ready = false;
  if (scd.getDataReadyStatus(ready) == 0 && ready) {
    uint16_t co2; float t, rh;
    if (scd.readMeasurement(co2, t, rh) == 0 && co2 > 0) {
      sumCo2 += co2; sumT += t; sumRh += rh; n++;
      if (co2 < 1000)      led(0, 1, 0);
      else if (co2 < 1400) led(1, 1, 0);
      else                 led(1, 0, 0);
    }
  }

  if (millis() - lastLog >= LOG_MS && n > 0) {
    lastLog = millis();
    Serial.print("luft;");
    Serial.print(sumCo2 / n, 0); Serial.print(";");
    Serial.print(sumT / n, 1);   Serial.print(";");
    Serial.println(sumRh / n, 1);
    sumCo2 = sumT = sumRh = 0; n = 0;
  }
  delay(100);
}
