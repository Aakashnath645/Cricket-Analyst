# CricAnalyst Desktop (React + Electron + Python)

You now have a hybrid desktop architecture:

- **Frontend/UI:** React (Vite) inside Electron
- **Desktop shell/exe:** Electron + electron-builder
- **Prediction/data engine:** Python API (FastAPI) using your existing ML + feed services

## Architecture

- Python backend API: [server.py](/D:/cricanalyst/backend/server.py)
- React app: [App.jsx](/D:/cricanalyst/desktop/src/App.jsx)
- Electron main process: [main.js](/D:/cricanalyst/desktop/electron/main.js)
- Backend runner: [run_backend.py](/D:/cricanalyst/run_backend.py)

## 1) Setup Python

```powershell
cd D:\cricanalyst
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.train_model --force-generate
```

## 2) Setup React/Electron

```powershell
cd D:\cricanalyst\desktop
npm install
```

## 3) Run as desktop app in development

From project root:

```powershell
cd D:\cricanalyst
.\run_electron_dev.ps1
```

This starts:

- Vite dev server (React UI)
- Electron window
- Python backend (spawned by Electron)

## 4) Build installer/exe with Electron

From project root:

```powershell
cd D:\cricanalyst
.\build_electron_exe.ps1
```

Build flow:

1. Builds backend executable (`dist\CricAnalystApi.exe`)
2. Builds React frontend
3. Packages Electron app installer in `desktop\release\`
4. Signs executable artifacts when signing env vars are configured
5. Runs integrity and security checks (SHA256, signature status, Defender scan, pip check, npm audit)

## 5) Optional code signing (production)

Set these environment variables before running the build script:

```powershell
$env:CRIC_SIGN_CERT_PFX = "C:\path\to\your-certificate.pfx"
$env:CRIC_SIGN_CERT_PASSWORD = "your-password"
$env:CRIC_SIGN_TIMESTAMP_URL = "http://timestamp.digicert.com"
```

To enforce signature validity during checks:

```powershell
$env:CRIC_REQUIRE_SIGNATURE = "1"
```

Then build normally:

```powershell
.\build_electron_exe.ps1
```

## 6) CI security pipeline

A GitHub Actions workflow is provided at `.github/workflows/release-security.yml`.
It runs:

- Python tests (`pytest`)
- Python CVE scan (`pip-audit --strict`)
- Node production audit (`npm audit --omit=dev`)
- Full installer build + security/integrity checks

## 7) Publish installer via GitHub Releases

This repository includes `.github/workflows/release-publish.yml`.
When you push a version tag (for example `v0.1.1`), GitHub Actions will:

- Build the installer on Windows
- Run the same release security checks
- Publish the following files to a GitHub Release:
	- `CricAnalyst-Setup-<version>.exe`
	- `CricAnalyst-Setup-<version>.exe.blockmap`
	- `SHA256SUMS.txt`

### First-time GitHub setup

```powershell
cd D:\cricanalyst
git init -b main
git add .
git commit -m "Initial CricAnalyst release pipeline"
git remote add origin https://github.com/<your-org-or-user>/<your-repo>.git
git push -u origin main
```

### Create a release

```powershell
cd D:\cricanalyst
git tag v0.1.1
git push origin v0.1.1
```

After the workflow completes, download the installer from the GitHub Releases page.

### Optional: signed builds in GitHub Actions

If you want code-signed release assets from CI, add repository secrets:

- `CRIC_SIGN_CERT_PFX_BASE64` (base64-encoded `.pfx` file)
- `CRIC_SIGN_CERT_PASSWORD`

Then update the workflow to decode the certificate and set these environment variables for the build step:

- `CRIC_SIGN_CERT_PFX`
- `CRIC_SIGN_CERT_PASSWORD`
- `CRIC_REQUIRE_SIGNATURE=1`

## API endpoints used by React

- `GET /health`
- `POST /predict/prematch`
- `POST /predict/live`
- `GET /feeds/live`
- `GET /signals/weather?location=...`
- `POST /signals/news`
- `POST /historical/sync`
- `POST /historical/suggest`

## Notes

- The old PySide desktop UI can still exist, but the primary path is now React + Electron.
- Live overs are still handled as cricket notation (`overs + balls`).
- You can continue improving model quality by retraining with richer real datasets.

