# Building the Thoth Windows Installer

This guide explains how to build a distributable Windows installer for Thoth.

## Architecture

The installer bundles:

| Component | Purpose |
|-----------|---------|
| **Python 3.13 (embeddable)** | Self-contained Python runtime (no system Python needed) |
| **Ollama** | Local LLM inference engine (installed silently) |
| **Thoth source + dependencies** | The Streamlit app and all pip packages |

At install time, the installer:
1. Extracts the embedded Python and app files
2. Installs Ollama silently
3. Runs `get-pip.py` and `pip install -r requirements.txt` to set up packages
4. Creates Start Menu and (optionally) Desktop shortcuts

The launcher script starts Ollama (if not already running) and launches the Streamlit app.

## Prerequisites

1. **Inno Setup 6** – free installer compiler  
   Download: https://jrsoftware.org/isdl.php  
   Make sure `ISCC.exe` is installed (default: `C:\Program Files (x86)\Inno Setup 6\`)

2. **Internet connection** – the build script downloads:
   - Python embeddable package (~25 MB)
   - `get-pip.py` (~2.5 MB)
   - Ollama installer (~100 MB)

3. **(Optional)** An icon file at `thoth.ico` in the project root.  
   If you don't have one, remove or comment out the `SetupIconFile` and `IconFilename` lines in `thoth_setup.iss`.

## Build Steps

```powershell
# From the project root:
.\installer\build_installer.ps1
```

This will:
1. Download Python 3.13 embeddable package
2. Download `get-pip.py`
3. Download the Ollama installer
4. Compile everything into a single installer EXE

The output is placed in `dist\ThothSetup_1.0.0.exe`.

### Options

```powershell
# Use a different Python version:
.\installer\build_installer.ps1 -PythonVersion "3.12.8"

# Skip downloads if build/ already has the files:
.\installer\build_installer.ps1 -SkipDownloads
```

## What the Installer Installs

On the end user's machine:

```
C:\Program Files\Thoth\
├── launch_thoth.bat        # Main launcher (Start Menu shortcut points here)
├── get-pip.py              # Deleted after install
├── install_deps.bat        # Deleted after install
├── python\                 # Embedded Python runtime
│   ├── python.exe
│   ├── python313.dll
│   ├── Lib\site-packages\  # All pip packages installed here
│   └── ...
└── app\                    # Your application code
    ├── app.py
    ├── models.py
    ├── rag.py
    ├── documents.py
    ├── threads.py
    ├── api_keys.py
    ├── requirements.txt
    └── vector_store\
```

Ollama is installed system-wide via its official installer.

## End-User Experience

1. Run `ThothSetup_1.0.0.exe`
2. Follow the wizard (installs Ollama + Python packages automatically)
3. Launch Thoth from Start Menu or Desktop shortcut
4. The app opens in the default browser at `http://localhost:8501`

## Notes

- **CPU-only PyTorch**: The `requirements.txt` uses CPU-only torch to keep the installer smaller. Users with NVIDIA GPUs can manually upgrade to CUDA torch after installation.
- **First launch**: The first run may take longer as the default LLM model (`qwen3:8b`) is downloaded by Ollama (~5 GB).
- **API Keys**: Users configure API keys (e.g. Tavily) from the in-app **⚙️ Settings** panel. Keys are saved to `api_keys.json` in the app directory. No keys are hardcoded or bundled in the installer.
- **Uninstall**: The installer registers with Windows Add/Remove Programs for clean uninstallation.
