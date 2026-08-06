import os
import time

def main():
    hb_path = "logs/heartbeat.txt"
    if not os.path.exists(hb_path):
        print(f"{hb_path} not found")
        return
        
    mtime = os.path.getmtime(hb_path)
    now = time.time()
    diff = now - mtime
    print(f"Heartbeat path: {hb_path}")
    print(f"Last modified: {time.ctime(mtime)}")
    print(f"Current time:  {time.ctime(now)}")
    print(f"Seconds since update: {diff:.2f} seconds")
    
    with open(hb_path, "r") as f:
        print(f"Content: {f.read().strip()}")

if __name__ == '__main__':
    main()
