# Antigravity Workspace Rules — Token Optimization & Best Practices

To optimize context window token usage and minimize API latency, the agent MUST adhere to the following rules when working in this workspace:

## 1. On-Device Log Analysis (Mandatory)
* **DO NOT** read raw JSONL log files (e.g., `logs/audit_*.jsonl`) into the context window using `view_file` or tail commands.
* **ALWAYS** use the dedicated parser script `scratch/analyze_trading_logs.py` via `run_command` to inspect, filter, or summarize trading logs.
* **Example Usage:**
  ```powershell
  python scratch/analyze_trading_logs.py --file logs/audit_2026-06-29.jsonl --summary
  python scratch/analyze_trading_logs.py --file logs/audit_2026-06-29.jsonl --errors --tail 10
  ```

## 2. On-Device Computation (Compute over Context)
* When asked to analyze large datasets (such as CSVs, JSON exports, or database tables), write a local helper script in the `scratch/` directory to aggregate and summarize the data.
* Execute the script locally and only print the final processed summaries to the context window.

## 3. Targeted File Reading
* When inspecting code, never read whole files if only a specific function or class is relevant.
* First, use `grep_search` to find the exact line numbers of interest.
* Then, call `view_file` specifying the exact `StartLine` and `EndLine` parameters to fetch only the relevant lines of code.
