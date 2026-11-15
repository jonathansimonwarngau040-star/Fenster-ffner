#!/usr/bin/env python3
"""
Fensteröffner – Flasher für Arduino Nano 33 BLE  (wird zu Fensteroeffner.exe gebaut)

Solange dieses Programm läuft:
  1. holt es alle 30 s das GitHub-Repo,
  2. kompiliert & flasht neuen Code aus sketches/current/ auf den Nano,
  3. schreibt das Ergebnis nach status/last_flash.txt,
  4. speichert die Serial-Ausgabe in logs/serial_YYYY-MM-DD.csv,
  5. pusht alles zurück, damit Claude es lesen kann.
Fenster schließen = Claude hat keinen Zugriff mehr.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial  # pyserial

# ---------------- Einstellungen ----------------
REPO_URL = "https://github.com/jonathansimonwarngau040-star/Fenster-ffner.git"
FQBN = "arduino:mbed_nano:nano33ble"   # Nano 33 BLE / Nano 33 BLE Sense
CORE = "arduino:mbed_nano"
BAUD = 115200
POLL_SEC = 30
PUSH_LOG_SEC = 300
# -----------------------------------------------

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    REPO = Path(os.environ["USERPROFILE"]) / "Fenster-ffner"
    ARDUINO_CLI = str(Path(sys._MEIPASS) / "arduino-cli.exe")
else:
    REPO = Path(__file__).resolve().parent.parent
    ARDUINO_CLI = shutil.which("arduino-cli") or "arduino-cli"

SKETCH_DIR = REPO / "sketches" / "current"
LOG_DIR = REPO / "logs"
STATUS_DIR = REPO / "status"
GIT = "git"

serial_lock = threading.Lock()
pause_serial = threading.Event()
git_lock = threading.Lock()
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ---------------- Einrichtung beim Start ----------------
def ensure_git():
    global GIT
    found = shutil.which("git")
    default = r"C:\Program Files\Git\cmd\git.exe"
    if not found and os.path.exists(default):
        found = default
    if not found:
        log("Git fehlt – wird installiert (evtl. Windows-Abfrage bestätigen) …")
        subprocess.run(["winget", "install", "--id", "Git.Git", "-e", "--silent",
                        "--accept-package-agreements", "--accept-source-agreements"])
        found = default if os.path.exists(default) else None
    if not found:
        sys.exit("Git konnte nicht installiert werden. Bitte https://git-scm.com installieren.")
    GIT = found


def ensure_repo():
    if (REPO / ".git").exists():
        return
    log(f"Lade Repo nach {REPO} – beim ersten Mal öffnet sich ein GitHub-Login …")
    # bewusst ohne capture, damit der Login-Dialog funktioniert
    r = subprocess.run([GIT, "clone", REPO_URL, str(REPO)])
    if r.returncode != 0:
        sys.exit("Repo konnte nicht geladen werden.")
    run([GIT, "config", "user.name", "Fensteroeffner-PC"])
    run([GIT, "config", "user.email", "flasher@localhost"])


def ensure_core():
    code, out = run([ARDUINO_CLI, "core", "list"], cwd=Path.home())
    if CORE in out:
        return
    log("Installiere Board-Paket für Nano 33 BLE (einmalig, dauert ein paar Minuten) …")
    subprocess.run([ARDUINO_CLI, "core", "update-index"])
    subprocess.run([ARDUINO_CLI, "core", "install", CORE])


# ---------------- Git ----------------
def git_pull():
    with git_lock:
        code, out = run([GIT, "pull", "--rebase", "--autostash"])
        if code != 0:
            log("git pull fehlgeschlagen:\n" + out)


def git_push(paths, message):
    with git_lock:
        run([GIT, "add", *paths])
        code, _ = run([GIT, "diff", "--cached", "--quiet"])
        if code == 0:
            return
        run([GIT, "commit", "-m", message])
        code, _ = run([GIT, "push"])
        if code != 0:
            run([GIT, "pull", "--rebase", "--autostash"])
            run([GIT, "push"])


def write_heartbeat():
    STATUS_DIR.mkdir(exist_ok=True)
    (STATUS_DIR / "heartbeat.txt").write_text(
        f"online {datetime.now().isoformat(timespec='seconds')}\n"
        f"board: {find_port() or 'nicht gefunden'}\n", encoding="utf-8")


# ---------------- Arduino ----------------
def sketch_hash():
    h = hashlib.sha256()
    for f in sorted(SKETCH_DIR.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(SKETCH_DIR)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def find_port():
    code, out = run([ARDUINO_CLI, "board", "list", "--format", "json"])
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    ports = data.get("detected_ports", []) if isinstance(data, dict) else data
    for p in ports:
        for b in p.get("matching_boards", []) or []:
            if "nano33ble" in b.get("fqbn", ""):
                return p["port"]["address"]
    return None


def install_libraries():
    req = SKETCH_DIR / "libraries.txt"
    if not req.exists():
        return ""
    out_all = ""
    for line in req.read_text(encoding="utf-8").splitlines():
        lib = line.strip()
        if lib and not lib.startswith("#"):
            _, out = run([ARDUINO_CLI, "lib", "install", lib])
            out_all += f"lib install {lib}:\n{out}\n"
    return out_all


def flash():
    report = [f"Zeit: {datetime.now().isoformat(timespec='seconds')}",
              f"Commit: {run([GIT, 'rev-parse', '--short', 'HEAD'])[1].strip()}",
              install_libraries()]

    code, out = run([ARDUINO_CLI, "compile", "--fqbn", FQBN, str(SKETCH_DIR)])
    report.append("=== COMPILE ===\n" + out)
    if code != 0:
        report.insert(0, "ERGEBNIS: COMPILE_FEHLER")
        return "\n".join(report)

    pause_serial.set()
    with serial_lock:
        port = find_port()
        if not port:
            pause_serial.clear()
            report.insert(0, "ERGEBNIS: KEIN_BOARD_GEFUNDEN")
            return "\n".join(report)
        code, out = run([ARDUINO_CLI, "upload", "-p", port, "--fqbn", FQBN, str(SKETCH_DIR)])
        report.append(f"=== UPLOAD ({port}) ===\n" + out)
    time.sleep(3)
    pause_serial.clear()

    report.insert(0, "ERGEBNIS: OK" if code == 0 else "ERGEBNIS: UPLOAD_FEHLER")
    return "\n".join(report)


def serial_reader():
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
                log(f"Nano verbunden an {port}")
                while not pause_serial.is_set():
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    now = datetime.now()
                    with (LOG_DIR / f"serial_{now:%Y-%m-%d}.csv").open("a", encoding="utf-8") as fh:
                        fh.write(f"{now.isoformat(timespec='milliseconds')};{line}\n")
        except (serial.SerialException, OSError) as e:
            log(f"Serial getrennt ({e}) – neuer Versuch …")
            time.sleep(3)


def log_pusher():
    while True:
        time.sleep(PUSH_LOG_SEC)
        write_heartbeat()
        git_push(["logs", "status"], "Messdaten-Update")


def main():
    print("=" * 60)
    print("  Fensteröffner-Flasher  –  Fenster offen lassen!")
    print("  Solange es läuft, kann Claude Sketches auf den Nano flashen.")
    print("=" * 60)
    ensure_git()
    ensure_repo()
    ensure_core()

    git_pull()
    write_heartbeat()
    git_push(["status"], "Flasher online")
    log("Bereit. Warte auf neuen Code …")

    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=log_pusher, daemon=True).start()

    last = None
    while True:
        git_pull()
        current = sketch_hash()
        if current != last:
            log("Neuer Sketch – kompiliere und flashe …")
            result = flash()
            STATUS_DIR.mkdir(exist_ok=True)
            (STATUS_DIR / "last_flash.txt").write_text(result, encoding="utf-8")
            log(result.splitlines()[0])
            git_push(["status", "logs"], "Flash-Status: " + result.splitlines()[0])
            last = current
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        print(e)
        input("Enter zum Schließen …")
