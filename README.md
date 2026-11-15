# Fensteröffner – Datensammlung mit Arduino Nano 33 BLE

## Benutzung
1. **Fensteroeffner.exe** herunterladen (bei GitHub eingeloggt sein):
   https://github.com/jonathansimonwarngau040-star/Fenster-ffner/releases/latest/download/Fensteroeffner.exe
2. Nano per USB anschließen, exe starten. Beim ersten Start installiert sie Git,
   lädt dieses Repo nach `%USERPROFILE%\Fenster-ffner` (GitHub-Login im Browser)
   und installiert das Board-Paket.
3. Fenster offen lassen. Solange es läuft, flasht es neuen Code automatisch.
   Fenster schließen = kein Zugriff mehr.

## Aufbau
```
sketches/current/       aktueller Sketch (+ optional libraries.txt)
status/last_flash.txt   Compile/Upload-Ergebnis
status/heartbeat.txt    Lebenszeichen des Flashers (alle 5 min)
status/build.txt        Ergebnis des letzten exe-Builds
logs/serial_*.csv       Messdaten: Zeitstempel;Zeile vom Arduino
tools/flasher.py        Quellcode der exe (wird per GitHub Actions gebaut)
```
