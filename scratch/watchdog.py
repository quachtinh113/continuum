import os
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Setup paths
cwd = Path(__file__).parent.parent
logs_dir = cwd / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
log_file = logs_dir / "watchdog.log"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}\n"
    if sys.stdout is not None:
        try:
            print(msg)
        except Exception:
            pass
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Failed to write to watchdog.log: {e}")

log("=======================================================")
log("V9 CONTINUUM - PYTHON WATCHDOG STARTED")
log("=======================================================")

bot_process = None

def get_heartbeat_file():
    # Resolve magic number from settings to get exact filename prefix
    try:
        sys.path.append(str(cwd))
        from config import settings
        magic = getattr(settings, "MAGIC_NUMBER", 202500)
        prefix = f"bot_{magic}_" if magic != 202500 else ""
    except Exception as e:
        log(f"Warning: Could not import settings: {e}. Using default prefix.")
        prefix = ""
    return logs_dir / f"{prefix}heartbeat.txt"

def get_bot_pid():
    pid_file = logs_dir / "bot.pid"
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except Exception:
            return None
    return None

def kill_bot(pid):
    if pid:
        log(f"☠️ Killing bot process with PID {pid}...")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True)
        except Exception as e:
            log(f"Error killing PID {pid}: {e}")
    else:
        log("☠️ PID not found. Fallback: Killing python processes running main...")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "python.exe"], capture_output=True)
            else:
                subprocess.run(["pkill", "-9", "-f", "v9_continuum.main"], capture_output=True)
        except Exception as e:
            log(f"Error in fallback kill: {e}")

def start_bot():
    global bot_process
    log("🔄 Starting V9 Continuum Bot process...")
    try:
        bot_process = subprocess.Popen(
            [sys.executable, "-m", "v9_continuum.main"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log(f"✅ Bot process spawned with Popen PID: {bot_process.pid}")
    except Exception as e:
        log(f"❌ Failed to start bot: {e}")

# Clean up old heartbeat files before start
try:
    import traceback
    
    hb_file = get_heartbeat_file()
    if hb_file.exists():
        try:
            hb_file.unlink()
        except Exception:
            pass

    start_bot()
    last_heartbeat_check = time.time()
    wait_for_init_timer = time.time()

    while True:
        time.sleep(15)
        
        # 1. Check if subprocess has exited
        if bot_process:
            poll = bot_process.poll()
            if poll is not None:
                log(f"🚨 Bot process exited with code {poll}. Restarting...")
                start_bot()
                wait_for_init_timer = time.time()
                continue
                
        # 2. Check heartbeat age
        hb_file = get_heartbeat_file()
        if hb_file.exists():
            try:
                hb_content = hb_file.read_text().strip()
                if hb_content:
                    hb_time = int(hb_content)
                    now = int(time.time())
                    diff = now - hb_time
                    if diff > 60:
                        log(f"🚨 ALARM! Bot is frozen! Heartbeat age: {diff} seconds. Restarting...")
                        # Kill both by pid file and Popen handle to be safe
                        pid = get_bot_pid() or (bot_process.pid if bot_process else None)
                        kill_bot(pid)
                        if bot_process:
                            try:
                                bot_process.kill()
                            except Exception:
                                pass
                        start_bot()
                        wait_for_init_timer = time.time()
                    else:
                        # Healthy
                        pass
            except Exception as e:
                log(f"Warning: Error reading heartbeat: {e}")
        else:
            # Heartbeat file doesn't exist yet (bot is initializing)
            age_since_start = time.time() - wait_for_init_timer
            if age_since_start > 60:
                log(f"🚨 Bot failed to create heartbeat file after {int(age_since_start)}s. Force restarting...")
                pid = get_bot_pid() or (bot_process.pid if bot_process else None)
                kill_bot(pid)
                start_bot()
                wait_for_init_timer = time.time()
            else:
                log(f"⏳ Waiting for bot to initialize... ({int(age_since_start)}s elapsed)")
except Exception as e:
    crash_file = logs_dir / "watchdog_crash.log"
    with open(crash_file, "w", encoding="utf-8") as f:
        f.write(f"Crash at {datetime.now()}\n")
        f.write(str(e) + "\n")
        traceback.print_exc(file=f)
    raise
