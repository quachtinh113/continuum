import subprocess
import sys

proc = subprocess.Popen(
    [sys.executable, "-m", "v9_continuum.main"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace"
)

try:
    stdout, stderr = proc.communicate(timeout=15)
    print("STDOUT:")
    print(stdout)
    print("STDERR:")
    print(stderr)
    print(f"EXIT CODE: {proc.returncode}")
except subprocess.TimeoutExpired:
    print("PROCESS RUNNING STABLY PAST 15 SECONDS!")
    proc.terminate()
