# ============================================================
# setup_local.ps1 - Cai dat moi truong Local Ultimate Download Manager v3.0
# Danh cho: May ca nhan co NVIDIA GPU (GTX 950 / compute 5.2+)
# Chay: powershell -ExecutionPolicy Bypass -File .\setup_local.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Ultimate Download Manager v3.0 - Local Setup Script" -ForegroundColor Cyan
Write-Host "   Tich hop: Whisper AI + PyTorch CUDA + ffmpeg" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---- 1. Kiem tra Python ----
Write-Host "[1/6] Kiem tra Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      LOI: Khong tim thay Python! Cai Python 3.10+ tu python.org" -ForegroundColor Red
    exit 1
}

# ---- 2. Kiem tra GPU NVIDIA ----
Write-Host ""
Write-Host "[2/6] Phat hien GPU NVIDIA..." -ForegroundColor Yellow
$gpuInfo = Get-CimInstance -ClassName Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" } | Select-Object -First 1

if ($gpuInfo) {
    $gpuName = $gpuInfo.Name
    $vramMB = [math]::Round($gpuInfo.AdapterRAM / 1MB, 0)
    Write-Host "      OK - GPU: $gpuName ($vramMB MB VRAM)" -ForegroundColor Green
    $hasNvidia = $true

    if ($vramMB -le 2048) {
        Write-Host "      CANH BAO: VRAM <= 2GB" -ForegroundColor Yellow
        Write-Host "      -> Khuyen nghi dung model 'medium' tren CUDA" -ForegroundColor Yellow
        Write-Host "      -> Hoac 'large-v3' tren CPU (can 16GB+ RAM)" -ForegroundColor Yellow
    }
} else {
    Write-Host "      CANH BAO: Khong phat hien GPU NVIDIA. Se cai PyTorch CPU-only." -ForegroundColor Yellow
    $hasNvidia = $false
}

# ---- 3. Cai PyTorch ----
Write-Host ""
Write-Host "[3/6] Cai dat PyTorch..." -ForegroundColor Yellow

if ($hasNvidia) {
    Write-Host "      Cai PyTorch 2.2.2 + CUDA 11.8 (tuong thich GTX 950 / compute 5.2+)"
    Write-Host "      Qua trinh tai co the mat 10-15 phut (~2.5GB)..." -ForegroundColor Gray
    pip install torch==2.2.2+cu118 torchvision==0.17.2+cu118 torchaudio==2.2.2+cu118 --index-url https://download.pytorch.org/whl/cu118
} else {
    Write-Host "      Cai PyTorch CPU-only..."
    pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu
}

$cudaCheck = python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| Version:', torch.__version__)" 2>&1
Write-Host "      Ket qua: $cudaCheck" -ForegroundColor Green

# ---- 4. Cai openai-whisper + imageio-ffmpeg ----
Write-Host ""
Write-Host "[4/6] Cai openai-whisper + imageio-ffmpeg..." -ForegroundColor Yellow
pip install openai-whisper imageio-ffmpeg
Write-Host "      OK!" -ForegroundColor Green

# ---- 5. Cai cac dependency cua Tool ----
Write-Host ""
Write-Host "[5/6] Cai dependencies Tool (yt-dlp, customtkinter, webvtt-py)..." -ForegroundColor Yellow
pip install yt-dlp customtkinter webvtt-py
Write-Host "      OK!" -ForegroundColor Green

# ---- 6. Tai Whisper Model ----
Write-Host ""
Write-Host "[6/6] Tai Whisper Model..." -ForegroundColor Yellow
Write-Host ""
Write-Host "      Cac model co san:" -ForegroundColor Cyan
Write-Host "        [1] tiny     -  75MB  | Nhanh nhat, it chinh xac" -ForegroundColor White
Write-Host "        [2] base     - 145MB  | Can bang co ban" -ForegroundColor White
Write-Host "        [3] small    - 480MB  | Can bang tot" -ForegroundColor White
Write-Host "        [4] medium   - 1.5GB  | Chat luong cao (KHUYEN NGHI CUDA GTX 950)" -ForegroundColor Green
Write-Host "        [5] large-v3 - 2.9GB  | Tot nhat (danh cho CPU, can 16GB+ RAM)" -ForegroundColor Yellow
Write-Host "        [6] Bo qua   | Tai sau trong Tab Cai dat cua App" -ForegroundColor Gray
Write-Host ""
$choice = Read-Host "      Nhap so lua chon (1-6)"

$modelName = switch ($choice) {
    "1" { "tiny" }
    "2" { "base" }
    "3" { "small" }
    "4" { "medium" }
    "5" { "large-v3" }
    "6" { $null }
    default { "medium" }
}

if ($modelName) {
    Write-Host ""
    Write-Host "      Dang tai model '$modelName' vao thu muc 'models/whisper'..." -ForegroundColor Cyan
    Write-Host "      Vui long cho..." -ForegroundColor Gray
    New-Item -ItemType Directory -Force -Path "models\whisper" | Out-Null
    $pyScript = @"
import whisper, os
os.makedirs('models/whisper', exist_ok=True)
print('Dang load model (se tai neu chua co)...')
whisper.load_model('$modelName', download_root='models/whisper')
print('Tai model hoan thanh!')
"@
    $pyScript | python
    Write-Host "      Model '$modelName' da san sang!" -ForegroundColor Green
} else {
    Write-Host "      Bo qua tai model. Co the tai sau trong tab Cai dat." -ForegroundColor Gray
}

# ---- Hoan thanh ----
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   CAI DAT HOAN TAT!" -ForegroundColor Green
Write-Host ""
Write-Host "   Chay ung dung: python app.py" -ForegroundColor White
Write-Host "   Vao tab Cai dat de xem trang thai GPU va model" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
