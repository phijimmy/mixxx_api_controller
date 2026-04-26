# Mixxx API Controller — Documentation

This documentation covers the main components of the Mixxx API Controller system, including the API server, MIDI controller integration, and configuration. It also provides setup instructions and a requirements list for recreating the environment.

## Overview

The Mixxx API Controller is a system for controlling and monitoring Mixxx DJ software via a web-based interface and MIDI. It consists of:
- A FastAPI server for real-time status and control
- A browser-based controller UI
- MIDI device integration for hardware/software control

---

## 1. API Server (`api/mixxx_api_server.py`)

### Purpose
- Acts as the main backend for the controller system
- Receives MIDI data, assembles status frames, and exposes them via a REST API and WebSocket
- Accepts control commands from the web UI and sends them to Mixxx via MIDI

### Key Features
- **Status Endpoints:**
  - `/api/status` (GET/POST): Get/set the current system status (heartbeat)
  - `/api/status/channels/{channel}`: Get status for a specific channel
  - `/api/status/internal_clock`, `/api/status/auto_dj`, `/api/status/crossfader`, `/api/status/master`, `/api/status/microphone`, `/api/status/shoutcast`: Get subsystem statuses
  - `/ws`: WebSocket for live status updates
  - `/health`: Health check endpoint
- **Control Endpoints:**
  - `/api/control/...`: POST endpoints for all major controls (play, sync, quantize, volume, pitch, crossfader, AutoDJ, Shoutcast, etc.)
- **MIDI Integration:**
  - Receives MIDI messages, parses them, and updates in-memory state
  - Sends MIDI commands to Mixxx in response to API calls
- **Threaded MIDI Polling:**
  - Runs a background thread to poll and send MIDI controls
- **Web UI Hosting:**
  - Serves the controller web interface from `/web`

### Usage
- Start the server with the provided `start.py` script (which ensures the correct Python environment)
- The server listens on port 5002 by default
- The web UI connects via WebSocket for live updates and uses REST endpoints for control

---

## 2. MIDI Controller Script (`controllers/mixxx_controller.js`)

### Purpose
- JavaScript for Mixxx's MIDI scripting engine
- Handles sending Mixxx state as MIDI messages (heartbeat)
- Receives MIDI control messages and applies them to Mixxx using `engine.setValue()`

### Key Features
- **Heartbeat:**
  - Periodically sends all relevant Mixxx state (play, bpm, sync, etc.) as MIDI notes
- **Inbound Control:**
  - Receives MIDI messages from the API server and applies them to Mixxx controls
- **Frame Assembly:**
  - Uses a set of MIDI notes to encode all relevant state and control values

### Usage
- Loaded by Mixxx as a controller script (see the XML preset)
- Communicates with the API server via a virtual MIDI device (e.g., VirMIDI)

---

## 3. Controller Preset (`controllers/VirMIDI_1-0.midi.xml`)

### Purpose
- Mixxx controller preset XML
- Binds MIDI notes to the JavaScript handler functions

### Key Features
- **Script Binding:**
  - All relevant MIDI notes are bound to the `mabc.incomingMidi` handler in the JS script
- **No Outputs:**
  - All communication is inbound (from API server to Mixxx)

### Usage
- Load this preset in Mixxx to enable the API controller integration

---

## 4. Configuration (`backend/mixxx_config.py`)

### Purpose
- Central configuration for MIDI port and device mapping

### Key Features
- **MIDI_PORT:** Default ALSA MIDI port string (e.g., 'hw:1,0')
- **midi_port_to_device():** Utility to convert port string to device path (e.g., '/dev/snd/midiC1D0')

### Usage
- Used by the API server to locate the correct MIDI device for communication

---

## 5. Web UI (`web/controller.html`)

### Purpose
- Browser-based interface for controlling and monitoring Mixxx

### Key Features
- **Live Status:**
  - Connects to the API server via WebSocket for real-time updates
- **Controls:**
  - Sends control commands to the API server via REST endpoints
- **UI Elements:**
  - Channel controls, mixer, AutoDJ, Shoutcast, and more

### Usage
- Open in a browser (served from the API server at `/web/controller.html`)
- Requires the API server to be running

---

## 6. Startup Script (`start.py`)

### Purpose
- Ensures the correct Python environment is activated
- Starts the API server using uvicorn

### Usage
- Run from the `mixxx_api_controller` directory:
  ```sh
  ./start.py
  # or
  python3 start.py
  ```
- The script will activate the local `.venv` if present

---

# Environment Setup

## Python Requirements
- Python 3.8+
- See requirements.txt for all Python dependencies

## System Requirements
- **Mixxx DJ Software** (2.4+ recommended)
- **ALSA MIDI** (Linux)
- **Virtual MIDI Device** (e.g., VirMIDI)
- **amidi** (for MIDI device access)

## Setup Steps
1. Install system dependencies:
   - Mixxx
   - ALSA MIDI tools
   - VirMIDI (or equivalent)
2. Set up Python environment:
   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Start the API server:
   ```sh
   ./start.py
   # or
   python3 start.py
   ```
4. Load the controller preset and JS script in Mixxx
5. Open the web UI in your browser

---

# Troubleshooting
- Ensure the correct MIDI device is mapped in `mixxx_config.py`
- Check Mixxx controller log for JS errors
- Use `/health` endpoint to verify API server is running

---

# Author
- J.Phillips (original author)

# License

This project is licensed under the MIT License. See the LICENSE file for details.
