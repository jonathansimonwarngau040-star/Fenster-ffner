// Ruhezustand: LED blinkt langsam (1 s an, 1 s aus), wartet auf neuen Sketch.
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
  static unsigned long last = 0;
  if (millis() - last > 60000) { last = millis(); Serial.println("bereit"); }
}
