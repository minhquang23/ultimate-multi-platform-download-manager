import os
import platform
import ctypes

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

def get_system_ram():
    """Lấy tổng dung lượng RAM vật lý của hệ thống (GB)."""
    try:
        if platform.system() == "Windows":
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024**3), 1)
    except Exception:
        pass
    
    # Fallback dự phòng
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        return 8.0  # Cấu hình giả định an toàn

def get_cpu_info():
    """Lấy thông tin tên CPU và số luồng xử lý."""
    cpu_name = "Unknown CPU"
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            cpu_name = name.strip()
        else:
            cpu_name = platform.processor() or "Unknown CPU"
    except Exception:
        cpu_name = platform.processor() or "Unknown CPU"
    
    cores = os.cpu_count() or 1
    return f"{cpu_name} ({cores} nhân/luồng)"

def get_gpu_info():
    """Lấy thông tin GPU hỗ trợ CUDA và dung lượng VRAM (GB)."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = round(vram_bytes / (1024**3), 1)
            return {
                "available": True,
                "name": name,
                "vram_gb": vram_gb
            }
    except Exception:
        pass
    
    return {
        "available": False,
        "name": None,
        "vram_gb": 0.0
    }

# Các ngưỡng cấu hình tối thiểu và khuyến nghị cho từng model Whisper
WHISPER_REQUIREMENTS = {
    "tiny": {
        "ram": 2.0,
        "vram": 1.0,
        "name_vi": "Tiny"
    },
    "base": {
        "ram": 4.0,
        "vram": 1.5,
        "name_vi": "Base"
    },
    "small": {
        "ram": 8.0,
        "vram": 2.0,
        "name_vi": "Small"
    },
    "medium": {
        "ram": 8.0,
        "vram": 5.0,
        "name_vi": "Medium"
    },
    "large-v3": {
        "ram": 16.0,
        "vram": 10.0,
        "name_vi": "Large-v3"
    },
    "large": {
        "ram": 16.0,
        "vram": 10.0,
        "name_vi": "Large-v3"
    },
    "large-v2": {
        "ram": 16.0,
        "vram": 10.0,
        "name_vi": "Large-v3"
    }
}

def get_recommendation(ram_gb, gpu_info):
    """
    Trả về cấu hình model và device khuyến khích dựa trên cấu hình phần cứng hiện tại.
    """
    if gpu_info["available"]:
        vram = gpu_info["vram_gb"]
        if vram >= 10.0:
            return {"model": "large-v3", "device": "cuda"}
        elif vram >= 5.0:
            return {"model": "medium", "device": "cuda"}
        elif vram >= 2.0:
            return {"model": "small", "device": "cuda"}  # GTX 950 (2GB VRAM) khuyến nghị Small CUDA
        else:
            return {"model": "base", "device": "cuda"}
    else:
        # CPU Mode
        if ram_gb >= 16.0:
            return {"model": "small", "device": "cpu"}  # CPU chỉ khuyến nghị tối đa Small vì Medium/Large rất chậm
        elif ram_gb >= 8.0:
            return {"model": "small", "device": "cpu"}
        else:
            return {"model": "base", "device": "cpu"}

def check_compatibility(model_id, device_id, ram_gb, gpu_info):
    """
    Kiểm tra cấu hình hiện tại có đáp ứng được model & device đã chọn hay không.
    Trả về: (ram_ok, vram_ok, overall_ok, ram_req, vram_req)
    """
    model_clean = model_id.lower().strip()
    # Tìm thông tin model yêu cầu
    req = WHISPER_REQUIREMENTS.get("small") # Mặc định
    for k, v in WHISPER_REQUIREMENTS.items():
        if k in model_clean:
            req = v
            break

    ram_req = req["ram"]
    vram_req = req["vram"]

    ram_ok = ram_gb >= ram_req

    if "cuda" in device_id.lower() or (device_id.lower() == "auto" and gpu_info["available"]):
        # Cần kiểm tra VRAM GPU
        if gpu_info["available"]:
            vram_ok = gpu_info["vram_gb"] >= vram_req
        else:
            vram_ok = False # Chọn CUDA nhưng không phát hiện GPU CUDA
    else:
        # CPU Mode -> Không cần kiểm tra VRAM GPU
        vram_ok = True

    overall_ok = ram_ok and vram_ok
    return ram_ok, vram_ok, overall_ok, ram_req, vram_req
