"""Experiment 0 - records installed software versions and hardware. Read-only. Run: python research\\exp0\\record_environment.py"""
import json, os, platform, subprocess, sys, ctypes
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
info = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "machine": platform.machine(),
        "processor_string": platform.processor(), "logical_cpus": os.cpu_count()}
def ver(m):
    try: return __import__(m).__version__
    except Exception as e: return f"not importable ({e.__class__.__name__})"
for m in ("torch", "torchvision", "PIL", "numpy", "pandas", "sklearn", "fastapi", "uvicorn"): info[m] = ver(m)
try:
    import torch
    info["cuda_available"] = bool(torch.cuda.is_available()); info["torch_cuda_build"] = torch.version.cuda
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0); info["gpu"] = {"name": p.name, "vram_gb": round(p.total_memory / 2**30, 2)}
    info["torch_threads"] = torch.get_num_threads()
except Exception as e: info["torch_error"] = str(e)
try:
    class MS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "ae")]
    s = MS(); s.l = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)); info["ram_gb"] = round(s.tp / 2**30, 1)
except Exception: info["ram_gb"] = "not available"
for key, cmd in (("cpu_name", "wmic cpu get name /value"), ("gpu_names", "wmic path win32_VideoController get name /value")):
    try: info[key] = [l.split("=", 1)[1].strip() for l in subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).splitlines() if "=" in l and l.split("=", 1)[1].strip()]
    except Exception: info[key] = "not available"
json.dump(info, open(os.path.join(ROOT, "research", "exp0", "environment.json"), "w"), indent=2); print(json.dumps(info, indent=2))
