import os
import sys
import datetime
import json

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def check_log_times():
    hb_path = "logs/heartbeat.txt"
    if os.path.exists(hb_path):
        hb_mtime = os.path.getmtime(hb_path)
        hb_local = datetime.datetime.fromtimestamp(hb_mtime)
        hb_utc = datetime.datetime.fromtimestamp(hb_mtime, datetime.timezone.utc)
        print("=== 1. HEARTBEAT LOG (Chu kỳ giám sát thực tế) ===")
        print(f"  - Local Time (GMT+7) : {hb_local.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - UTC Time           : {hb_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  - Độ trễ so với hiện tại: {round((datetime.datetime.now() - hb_local).total_seconds(), 1)}s")

    audit_path = "logs/audit_2026-08-17.jsonl"
    if os.path.exists(audit_path):
        audit_mtime = os.path.getmtime(audit_path)
        audit_file_local = datetime.datetime.fromtimestamp(audit_mtime)
        print("\n=== 2. AUDIT LOG (Sự kiện giao dịch & rủi ro) ===")
        print(f"  - Lần ghi file gần nhất (Local): {audit_file_local.strftime('%Y-%m-%d %H:%M:%S')}")
        
        with open(audit_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        
        if lines:
            print(f"  - Tổng số bản ghi hôm nay: {len(lines)}")
            print("  - 3 bản ghi sự kiện mới nhất:")
            for line in lines[-3:]:
                try:
                    data = json.loads(line)
                    ts = data.get("timestamp") or data.get("time") or "N/A"
                    evt = data.get("event") or data.get("action") or data.get("message") or str(data)
                    sym = data.get("symbol", "")
                    print(f"    * [{ts}] {sym} | {evt}")
                except Exception:
                    print(f"    * {line[:100]}")

if __name__ == "__main__":
    check_log_times()
