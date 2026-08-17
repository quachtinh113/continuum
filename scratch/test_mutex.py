import ctypes
import sys
import time

MUTEX_NAME = "Global\\V9_CONTINUUM_SINGLE_INSTANCE_MUTEX"
ERROR_ALREADY_EXISTS = 183

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def acquire_single_instance_lock(mutex_name=MUTEX_NAME):
    if sys.platform != "win32":
        import fcntl
        lock_file_path = "/tmp/v9_continuum.lock"
        try:
            fp = open(lock_file_path, "w")
            fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fp
        except IOError:
            print(f"🚨 [SINGLE INSTANCE ERROR] Process already running via file lock: {lock_file_path}")
            sys.exit(1)

    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()

    if last_error == ERROR_ALREADY_EXISTS:
        print(f"🚨 [MUTEX LOCK KILLED] Another V9 Continuum instance is already holding {mutex_name}!")
        print(f"🚨 Immediate process exit to prevent dual execution risk.")
        sys.exit(1)
    
    print(f"🔒 [SINGLE INSTANCE LOCK ACQUIRED] Windows Named Mutex: {mutex_name}")
    return mutex

if __name__ == '__main__':
    m = acquire_single_instance_lock()
    print("Holding lock for 3 seconds...")
    time.sleep(3)
    print("Test completed.")
