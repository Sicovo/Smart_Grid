# Smart Grid

Dashboard and control software for the five-module DC smart grid.

## Requirements

- Python 3.10+
- Node.js 22+
- npm

## Setup

### Linux

Run setup once, then start the three services in separate terminals:

```bash
./setup.sh
```

```bash
./run_backend.sh
./run_poller.sh
./run_frontend.sh
```

### Windows

Install dependencies:

```powershell
python -m pip install -r requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

Start the backend, poller and frontend:

```powershell
.\run_windows_all.ps1
```

Use `.\run_windows.ps1` to start only the backend and frontend.

## Addresses

| Service | Address |
| --- | --- |
| Frontend | `http://localhost:5173` |
| Backend | `http://localhost:8000` |
| Pico command server | `http://<pico-ip>:80/cmd` |

Both the frontend and backend listen on the PC's LAN address. Other devices on
the same network can open `http://<pc-ip>:5173`.

## Pico Network

The default firmware configuration uses:

| Module | IP address |
| --- | --- |
| Supercapacitor | `192.168.137.21` |
| Export | `192.168.137.22` |
| Grid import | `192.168.137.23` |
| PV | `192.168.137.24` |
| LED load | `192.168.137.25` |

Each Pico listens for commands on port `80`. Telemetry is pushed by the Pico to
the backend on port `8000`:

```text
POST http://192.168.137.1:8000/modules/tlm/<role>
```

Valid telemetry roles are `pv`, `grid`, `export`, `cap` and `led`. The poller
only collects grid simulation data; it does not poll Pico `/tlm` endpoints.

To create the Windows hotspot, run PowerShell as administrator:

```powershell
netsh wlan set hostednetwork mode=disallow
net stop WlanSvc
net start WlanSvc
netsh wlan set hostednetwork mode=allow ssid=PICO_AP key=12345688
netsh wlan start hostednetwork
```

If the network addresses change, update each module's `wifi_config.py`, the
`BACKEND_PUSH_HOST` in its `common.py`, and the backend `PICO_<ROLE>_URL`
environment variables.
end.

```bash
VITE_API_BASE_URL=http://192.168.1.50:8000 npm run dev
```