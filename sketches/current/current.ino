// Test-Sketch: blinkt und meldet sich jede Sekunde per Serial.
// Wird von Claude ersetzt, sobald die Pipeline läuft.

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  Serial.print("alive;");
  Serial.println(millis());
  delay(1000);
}
