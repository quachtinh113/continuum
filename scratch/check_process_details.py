import psutil
import datetime

def main():
    pids = [3044, 6136]
    for pid in pids:
        try:
            p = psutil.Process(pid)
            print(f"==========================================")
            print(f"PID: {pid}")
            print(f"Name: {p.name()}")
            print(f"Cmdline: {p.cmdline()}")
            print(f"Status: {p.status()}")
            print(f"Created: {datetime.datetime.fromtimestamp(p.create_time())}")
            print(f"CPU Percent: {p.cpu_percent(interval=0.1)}")
            print(f"Parent: {p.parent()}")
        except Exception as e:
            print(f"Failed to get details for PID {pid}: {e}")
            
if __name__ == '__main__':
    main()
