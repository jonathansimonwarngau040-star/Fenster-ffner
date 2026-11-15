# Fensteröffner – Datensammlung mit Arduino Nano 33 BLE

## Ablauf
Claude pusht Code → PC flasht automatisch → Serial-Daten gehen zurück ins Repo.

```
sketches/current/   aktueller Sketch (+ optional libraries.txt, ein Library-Name pro Zeile)
status/last_flash.txt   Compile/Upload-Ergebnis des letzten Flashvorgangs
logs/serial_*.csv   Messdaten: Zeitstempel;Zeile vom Arduino
tools/flasher.py    läuft dauerhaft auf dem PC
```

## Einrichtung (einmalig, Windows)
1. `tools/setup_windows.bat` ausführen, danach in neuem Terminal:
   ```
   arduino-cli core update-index
   arduino-cli core install arduino:mbed_nano
   pip install pyserial
   ```
2. Auf GitHub ein **privates** Repo `fensteroeffner` anlegen, diesen Ordner hineinpushen.
3. Nano per USB anschließen und starten:
   ```
   python tools/flasher.py
   ```
   Die LED sollte nach kurzer Zeit blinken, `logs/` füllt sich mit `alive;…`-Zeilen.

Das Fenster muss offen bleiben, solange geflasht/gemessen werden soll.
