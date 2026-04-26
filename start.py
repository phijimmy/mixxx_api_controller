#!/usr/bin/env python3
"""
start.py — Radio1 startup script.

Starts the API server and MIDI JSON translator as child processes,
then waits. Ctrl+C shuts everything down cleanly.

Run from the project root:
    python3 start.py
"""
import subprocess
import sys
import os
import time
import signal

ROOT   = os.path.dirname(os.path.abspath(__file__))
VENV   = os.path.join(ROOT, '.venv', 'bin', 'python')
PYTHON = VENV if os.path.exists(VENV) else sys.executable

SERVICES = [
    {
        'name':    'Mixxx API Server',
        # Use uvicorn to run the FastAPI app in api/mixxx_api_server.py
        'cmd':     [PYTHON, '-m', 'uvicorn', 'api.mixxx_api_server:app',
                    '--host', '0.0.0.0', '--port', '5002',
                    '--log-level', 'error', '--no-access-log'],
        'cwd':     ROOT,
        'startup_wait': 1.5,   # seconds to wait before starting next service
    },
]

_procs = []


def shutdown(signum=None, frame=None):
    print('\n\nShutting down Mixxx services...')
    for name, proc in reversed(_procs):
        if proc.poll() is None:
            print(f'  Stopping {name} (pid {proc.pid})...')
            proc.terminate()
    # Give them a moment to exit cleanly, then force-kill
    deadline = time.time() + 4
    for name, proc in _procs:
        remaining = deadline - time.time()
        if remaining > 0:
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                print(f'  Force-killing {name}')
                proc.kill()
    print('All services stopped.')
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Launch Mixxx (detached — survives server restarts) ────────────────────
    try:
        _mixxx_running = subprocess.run(
            ['pgrep', '-x', 'mixxx'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode == 0
        if _mixxx_running:
            print("[startup] Mixxx is already running — skipping launch.")
        else:
            print("[startup] Launching Mixxx (detached)...")
            subprocess.Popen(
                ['mixxx'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,   # detach from this process group/session
            )
            print("[startup] Mixxx started (independent — will not stop with the server).")
    except FileNotFoundError:
        print("[startup] 'mixxx' not found in PATH — skipping Mixxx launch.")
    except Exception as e:
        print(f"[startup] Failed to launch Mixxx: {e}")

    print('═' * 56)
    print('  Mixxx Startup')
    print('═' * 56)

    # Print LAN access URLs — use routing trick to get the real LAN IPv4
    try:
        import socket as _socket
        _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        lan_ip = _s.getsockname()[0]
        _s.close()
        print(f'\n  Controller UI   : http://{lan_ip}:5002/web/controller.html')
        print(f'  API (direct): http://{lan_ip}:5002')
    except Exception:
        pass
    print()

    for svc in SERVICES:
        print(f'\n  ▶  Starting {svc["name"]}...')
        proc = subprocess.Popen(
            svc['cmd'],
            cwd=svc['cwd'],
            stdout=subprocess.DEVNULL,   # silence routine print() output
            stderr=None,                 # inherit parent stderr so real errors show
        )
        _procs.append((svc['name'], proc))
        print(f'     pid {proc.pid}')
        if svc['startup_wait']:
            time.sleep(svc['startup_wait'])
            # Check it didn't die immediately
            if proc.poll() is not None:
                print(f'\n  ✗ {svc["name"]} exited early (code {proc.returncode}). Aborting.')
                shutdown()

    print('\n' + '═' * 56)
    print('  All services running.')
    print('  API docs : http://localhost:5002/docs')
    print('  Status   : http://localhost:5002/api/status')
    print('  Ctrl+C to stop everything.')
    print('═' * 56 + '\n')

    # Wait forever — let the child processes log to stdout/stderr directly
    while True:
        for name, proc in _procs:
            if proc.poll() is not None:
                print(f'\n  ✗ {name} exited unexpectedly (code {proc.returncode}). Shutting down.')
                shutdown()
        time.sleep(2)


if __name__ == '__main__':
    main()
