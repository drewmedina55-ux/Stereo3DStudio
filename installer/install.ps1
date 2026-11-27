# Stereo3D Studio installer - sets up the GPU runtime next to Stereo3DStudio.exe
# Safe to re-run: it repairs or rebuilds the runtime.
# The setup wizard runs it with -Unattended -ProgressFile <file>; the models folder is never touched.
param([switch]$Cpu, [switch]$NoModels, [switch]$NoShortcuts, [switch]$Unattended,
      [ValidateSet("ask", "yes", "no")][string]$LargeModel = "ask", [string]$ProgressFile = "")

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = Split-Path -Parent $PSScriptRoot
$Version = "1.4.1"
$Runtime = Join-Path $Root "runtime"
$Tools = Join-Path $PSScriptRoot "tools"
$LogFile = Join-Path $Root "install_log.txt"
$TorchVer = "2.14.1"
$VisionVer = "0.29.1"

Start-Transcript -Path $LogFile -Force | Out-Null

function Report($pct, $msg) {
    # progress for the setup wizard: "percent|text" (or DONE|... / FAIL|...)
    if ($ProgressFile) { try { Set-Content -Path $ProgressFile -Value "$pct|$msg" -Encoding UTF8 -ErrorAction Stop } catch {} }
}
function Step($msg, $pct = -1) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan; if ($pct -ge 0) { Report $pct $msg } }
function Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Run-Logged($File, [string[]]$Arguments) {
    # Runs a program and copies all of its output into the console + install log.
    $o = [IO.Path]::GetTempFileName(); $e = [IO.Path]::GetTempFileName()
    $quoted = $Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }
    $p = Start-Process -FilePath $File -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $o -RedirectStandardError $e
    Get-Content $o, $e -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    Remove-Item $o, $e -ErrorAction SilentlyContinue
    return $p.ExitCode
}
function Fail($msg) {
    Write-Host ""; Write-Host "INSTALL FAILED: $msg" -ForegroundColor Red
    Write-Host "Details were saved to: $LogFile" -ForegroundColor Red
    Report "FAIL" $msg
    Stop-Transcript | Out-Null
    exit 1
}

Write-Host ""
Write-Host "  Stereo3D Studio $Version setup" -ForegroundColor White
Write-Host "  2D -> 3D converter - by Drew Medina (drewmedina.com)" -ForegroundColor DarkGray
Write-Host "  Install folder: $Root" -ForegroundColor DarkGray

if (-not [Environment]::Is64BitOperatingSystem) { Fail "64-bit Windows is required." }
Get-ChildItem -Path $Root -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# Keep everything self-contained inside the install folder
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root "runtime_python"
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
$env:UV_LINK_MODE = "copy"
$env:UV_HTTP_TIMEOUT = "600"
$env:PYTHONNOUSERSITE = "1"
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 1. GPU
Step "Checking your NVIDIA GPU" 3
$Flavor = "cpu"
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $smi) {
    $cand = Join-Path $env:SystemRoot "System32\nvidia-smi.exe"
    if (Test-Path $cand) { $smi = $cand }
}
if ($Cpu) {
    Warn "CPU-only install requested."
} elseif ($smi) {
    $name = (& $smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
    if ($name) { Ok "Found: $name" }
    # Decide from the driver version number (reliable across nvidia-smi versions).
    $drvText = (& $smi --query-gpu=driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
    $driver = 0.0
    if ("$drvText" -match "([0-9]+)\.([0-9]+)") {
        $driver = [double]::Parse(("{0}.{1}" -f $Matches[1], $Matches[2]), [Globalization.CultureInfo]::InvariantCulture)
    }
    # Fallback: CUDA version from the header text (format varies, so match loosely)
    $cudaMax = 0.0
    $out = ((& $smi 2>$null) + (& $smi --version 2>$null)) -join "`n"
    if ($out -match "CUDA\s*Version\s*:?\s*([0-9]+)\.([0-9]+)") {
        $cudaMax = [double]::Parse(("{0}.{1}" -f $Matches[1], $Matches[2]), [Globalization.CultureInfo]::InvariantCulture)
    }
    $cc = (& $smi --query-gpu=compute_cap --format=csv,noheader 2>$null | Select-Object -First 1)
    $isBlackwell = ("$name" -match "RTX\s*50|RTX PRO|B[0-9]{2,3}") -or ("$cc" -match "^1[2-9]\.")
    Ok ("Driver {0}  (CUDA {1})" -f $driver, $(if ($cudaMax -gt 0) { $cudaMax } else { "n/a" }))

    if ($driver -ge 580 -or $cudaMax -ge 13.0) { $Flavor = "cu132" }        # CUDA 13.x driver
    elseif ($driver -ge 528 -or $cudaMax -ge 12.6) { $Flavor = "cu126" }    # CUDA 12.x driver
    if ($isBlackwell -and $Flavor -eq "cu126") {
        Warn "RTX 50-series needs a CUDA 13 driver (580 or newer). Please update the driver."
        $Flavor = "cpu"
    }
    if ($Flavor -eq "cpu") {
        Warn "Could not confirm a CUDA-capable driver (driver '$drvText')."
        Warn "Continuing with a CPU-only install. Send install_log.txt if this looks wrong."
    }
} else {
    Warn "No NVIDIA GPU/driver found. Installing the CPU build (works, but slow)."
}
Ok "Runtime flavor: $Flavor"

# ---------------------------------------------------------------- 2. uv (python + package manager)
Step "Getting the Python package manager (uv)" 8
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
$uv = Join-Path $Tools "uv.exe"
if (-not (Test-Path $uv)) {
    $zip = Join-Path $Tools "uv.zip"
    try {
        Invoke-WebRequest -ErrorAction Stop -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip
        Expand-Archive -ErrorAction Stop -Path $zip -DestinationPath $Tools -Force
        Remove-Item $zip -Force
    } catch { Fail "Could not download uv: $($_.Exception.Message)" }
}
if (-not (Test-Path $uv)) { Fail "uv.exe missing after download." }
Ok (& $uv --version)

# ---------------------------------------------------------------- 3. runtime
Step "Creating the Python 3.12 runtime" 12
if (Test-Path $Runtime) {
    Warn "Removing previous runtime..."
    Remove-Item -Recurse -Force $Runtime
}
& $uv venv $Runtime --python 3.12 --seed
if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python runtime." }
$py = Join-Path $Runtime "Scripts\python.exe"

Step "Installing PyTorch ($Flavor) - a large download, about 2.5 GB for GPU" 18
if ($Flavor -eq "cpu") {
    & $uv pip install --python $py "torch==$TorchVer" "torchvision==$VisionVer" --index-url "https://download.pytorch.org/whl/cpu"
} else {
    & $uv pip install --python $py "torch==$TorchVer+$Flavor" "torchvision==$VisionVer+$Flavor" --index-url "https://download.pytorch.org/whl/$Flavor"
}
if ($LASTEXITCODE -ne 0) {
    Warn "Pinned PyTorch $TorchVer not available for $Flavor - installing the newest build instead."
    & $uv pip install --python $py torch torchvision --index-url "https://download.pytorch.org/whl/$Flavor"
    if ($LASTEXITCODE -ne 0) { Fail "PyTorch install failed." }
}

Step "Installing the 3D engine and interface packages" 60
$req = Join-Path $Root "engine\requirements.txt"
& $uv pip install --python $py -r $req "PySide6>=6.7,<6.13" "diffusers>=0.32" "peft>=0.14" "transformers>=4.46" "sentencepiece" "protobuf" "bitsandbytes>=0.45"
if ($LASTEXITCODE -ne 0) { Fail "Package install failed." }
# let the runtime find the app + engine without any environment variables
$site = Join-Path $Runtime "Lib\site-packages"
Set-Content -Path (Join-Path $site "stereo3dstudio.pth") -Encoding ASCII -Value @((Join-Path $Root "app"), (Join-Path $Root "engine"))

# ---------------------------------------------------------------- 4. verify GPU
Step "Testing GPU acceleration" 78
$gpuCode = Run-Logged $py @((Join-Path $PSScriptRoot "prefetch.py"), "check")
if ($gpuCode -eq 0) { Ok "CUDA is working." }
elseif ($Flavor -ne "cpu") { Warn "PyTorch installed but CUDA did not start. Update your NVIDIA driver and re-run setup." }

# ---------------------------------------------------------------- 5. models
if (-not $NoModels) {
    $modelArgs = @((Join-Path $PSScriptRoot "prefetch.py"), "models")
    $vitl = Join-Path $Root "models\iw3\pretrained_models\hub\checkpoints\depth_anything_v2_vitl.pth"
    if (Test-Path $vitl) {
        Ok "Depth Anything V2 Large found in the models folder."
    } else {
        Write-Host ""
        Write-Host "  The default depth model, Depth Anything V2 Large (1.3 GB), is licensed" -ForegroundColor White
        Write-Host "  CC BY-NC 4.0: free for personal / non-commercial use only." -ForegroundColor White
        if ($LargeModel -eq "ask" -and -not $Unattended) {
            $ans = Read-Host "  Accept the license and download it now? [Y/n]"
            $LargeModel = $(if ($ans -eq "" -or $ans -match "^[Yy]") { "yes" } else { "no" })
        }
        if ($LargeModel -eq "yes") { $modelArgs += "large" }
        else { Warn "Skipped - you can download it later from the Models button." }
    }
    Step "Downloading the default depth models (a few minutes for the 1.3 GB model)" 82
    $mc = Run-Logged $py $modelArgs
    if ($mc -ne 0) { Warn "Model pre-download failed - Stereo3D Studio will download them on first use." }
}

# ---------------------------------------------------------------- 6. launcher + shortcuts
Step "Finishing up" 93
$exe = Join-Path $Root "Stereo3DStudio.exe"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (Test-Path $csc) {
    $built = Join-Path $PSScriptRoot "Stereo3DStudio.local.exe"
    $cc = Run-Logged $csc @("/nologo", "/target:winexe", "/optimize+", "/win32icon:$(Join-Path $Root 'assets\stereo3dstudio.ico')", "/r:System.Windows.Forms.dll", "/out:$built", (Join-Path $PSScriptRoot "Launcher.cs"))
    if ($cc -eq 0 -and (Test-Path $built)) { Move-Item -Force $built $exe; Ok "Launcher compiled on this PC" }
}

Step "Test-starting Stereo3D Studio" 96
$st = Run-Logged $py @("-X", "utf8", "-m", "stereo3dstudio", "--selftest")
if ($st -eq 0) { Ok "Stereo3D Studio starts correctly." }
else { Warn "The start test failed (details above). Please send install_log.txt." }
if (Test-Path $exe) { Ok "Stereo3DStudio.exe ready" } else { Warn "Launcher EXE missing - use 'Stereo3D Studio (console).bat' instead." }

if (-not $NoShortcuts -and (Test-Path $exe)) {
    $shell = New-Object -ComObject WScript.Shell
    $targets = @(
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "Stereo3D Studio.lnk"),
        (Join-Path ([Environment]::GetFolderPath("Programs")) "Stereo3D Studio.lnk")
    )
    # remove shortcuts from the app's old name
    $olds = foreach ($n in @("StereoForge.lnk", "Convert3D.lnk", "Stereo Studio.lnk")) {
        (Join-Path ([Environment]::GetFolderPath("Desktop")) $n)
        (Join-Path ([Environment]::GetFolderPath("Programs")) $n)
    }
    foreach ($old in $olds) {
        Remove-Item $old -ErrorAction SilentlyContinue
    }
    foreach ($t in $targets) {
        $lnk = $shell.CreateShortcut($t)
        $lnk.TargetPath = $exe
        $lnk.WorkingDirectory = $Root
        $lnk.IconLocation = "$exe,0"
        $lnk.Description = "Stereo3D Studio - 2D to 3D converter"
        $lnk.Save()
    }
    Ok "Shortcuts added to Desktop and Start menu"
}

# free the download cache (several GB)
$null = Run-Logged $uv @("cache", "clean")
Remove-Item -Recurse -Force $env:UV_CACHE_DIR -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Stereo3D Studio $Version is installed." -ForegroundColor Green
if ($gpuCode -ne 0) { Write-Host "  Note: running without GPU acceleration (see messages above)." -ForegroundColor Yellow }
Write-Host "  Launch it from the Desktop shortcut or Stereo3DStudio.exe." -ForegroundColor White
Report "DONE" $(if ($gpuCode -ne 0) { "Installed without GPU acceleration - see install_log.txt" } else { "Installed" })
Stop-Transcript | Out-Null
exit 0
