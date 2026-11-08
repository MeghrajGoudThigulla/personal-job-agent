"""System monitoring utilities."""


def get_process_memory_mb() -> float:
    """
    Returns current process Resident Set Size (RSS) in MB using /proc/self/status.
    Falls back to 0.0 if not on Linux or if /proc is inaccessible.
    """
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return round(int(parts[1]) / 1024.0, 2)
    except Exception:
        pass
    return 0.0
