#!/usr/bin/env python3
"""
Fensteröffner – Auto-Flasher für Arduino Nano 33 BLE

Läuft dauerhaft auf dem PC, an dem der Nano per USB hängt:
  1. Holt alle 30 s das GitHub-Repo (git pull).
  2. Hat sich sketches/current/ geändert -> kompiliert & flasht mit arduino-cli.
     Ergebnis (Erfolg/Fehlermeldung) landet in status/last_flash.txt.
  3. Liest dauerhaft den Serial-Port mit und speichert jede Zeile mit
     Zeitstempel in logs/serial_YYYY-MM-DD.csv.
  4. Pusht Status + Logs regelmäßig zurück ins Repo.

So kann Claude Sketches pushen, Compilerfehler lesen und Messdaten auswerten.
"""

import hashlib
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial  # pip install pyserial

# ---------------- Einstellungen ----------------
REPO = Path(__file__).resolve().parent.parent
SKETCH_DIR = REPO / "sketches" / "current"
LOG_DIR = REPO / "logs"
STATUS_FILE = REPO / "status" / "last_flash.txt"
FQBN = "arduino:mbed_nano:nano33ble"   # Nano 33 BLE und Nano 33 BLE Sense
BAUD = 115200
POLL_SEC = 30          # wie oft nach neuem Code geschaut wird
PUSH_LOG_SEC = 300     # wie oft Logs hochgeladen werden
# -----------------------------------------------

serial_lock = threading.Lock()
pause_serial = threading.Event()
git_lock = threading.Lock()


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run(cmd, cwd=REPO):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def sketch_hash():
    h = hashlib.sha256()
    for f in sorted(SKETCH_DIR.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(SKETCH_DIR)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def find_port():
    code, out = run(["arduino-cli", "board", "list", "--format", "json"])
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    ports = data.get("detected_ports", data) if isinstance(data, dict) else data
    for p in ports:
        for b in p.get("matching_boards", []) or []:
            if "nano33ble" in b.get("fqbn", ""):
                return p["port"]["address"]
    return None


def git_pull():
    with git_lock:
        code, out = run(["git", "pull", "--rebase", "--autostash"])
        if code != 0:
            log("git pull fehlgeschlagen:\n" + out)


def git_push(paths, message):
    with git_lock:
        run(["git", "add", *paths])
        code, _ = run(["git", "diff", "--cached", "--quiet"])
        if code == 0:
            return  # nichts zu committen
        run(["git", "commit", "-m", message])
        code, out = run(["git", "push"])
        if code != 0:
            run(["git", "pull", "--rebase", "--autostash"])
            run(["git", "push"])


def install_libraries():
    req = SKETCH_DIR / "libraries.txt"
    if not req.exists():
        return ""
    out_all = ""
    for line in req.read_text(encoding="utf-8").splitlines():
        lib = line.strip()
        if lib and not lib.startswith("#"):
            _, out = run(["arduino-cli", "lib", "install", lib])
            out_all += f"lib install {lib}:\n{out}\n"
    return out_all


def flash():
    report = [f"Zeit: {datetime.now().isoformat(timespec='seconds')}",
              f"Commit: {run(['git', 'rev-parse', '--short', 'HEAD'])[1].strip()}"]
    report.append(install_libraries())

    code, out = run(["arduino-cli", "compile", "--fqbn", FQBN, str(SKETCH_DIR)])
    report.append("=== COMPILE ===\n" + out)
    if code != 0:
        report.insert(0, "ERGEBNIS: COMPILE_FEHLER")
        return "\n".join(report)

    pause_serial.set()           # Serial-Port freigeben
    with serial_lock:
        port = find_port()
        if not port:
            report.insert(0, "ERGEBNIS: KEIN_BOARD_GEFUNDEN")
            pause_serial.clear()
            return "\n".join(report)
        code, out = run(["arduino-cli", "upload", "-p", port,
                         "--fqbn", FQBN, str(SKETCH_DIR)])
        report.append(f"=== UPLOAD ({port}) ===\n" + out)
    time.sleep(3)                # Board bootet neu
    pause_serial.clear()

    report.insert(0, "ERGEBNIS: OK" if code == 0 else "ERGEBNIS: UPLOAD_FEHLER")
    return "\n".join(report)


def serial_reader():
    """Liest dauerhaft vom Nano und schreibt in Tages-CSV."""
    LOG_DIR.mkdir(exist_ok=True)
    while True:
        if pause_serial.is_set():
            time.sleep(0.5)
            continue
        port = find_port()
        if not port:
            time.sleep(5)
            continue
        try:
            with serial_lock, serial.Serial(port, BAUD, timeout=1) as ser:
                log(f"Serial verbunden: {port}")
                while not pause_serial.is_set():
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    now = datetime.now()
                    f = LOG_DIR / f"serial_{now:%Y-%m-%d}.csv"
                    with f.open("a", encoding="utf-8") as fh:
                        fh.write(f"{now.isoformat(timespec='milliseconds')};{line}\n")
        except (serial.SerialException, OSError) as e:
            log(f"Serial getrennt ({e}), neuer Versuch …")
            time.sleep(3)


def log_pusher():
    while True:
        time.sleep(PUSH_LOG_SEC)
        git_push(["logs"], "Messdaten-Update")


def main():
    log(f"Repo: {REPO}")
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=log_pusher, daemon=True).start()

    last = None
    while True:
        git_pull()
        current = sketch_hash()
        if current != last:
            log("Neuer Sketch erkannt – flashe …")
            result = flash()
            STATUS_FILE.parent.mkdir(exist_ok=True)
            STATUS_FILE.write_text(result, encoding="utf-8")
            log(result.splitlines()[0])
            git_push(["status", "logs"], "Flash-Status: " + result.splitlines()[0])
            last = current
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
