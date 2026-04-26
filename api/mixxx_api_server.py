
"""
Unified Mixxx MIDI API Server
All endpoints, in-memory state, MIDI frame assembly, and control logic.
"""
import os
import sys
import time
import glob 
import json
import select
import datetime
import threading
from collections import deque
from typing import List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- In-memory state and control queue ---
_latest_status: dict = {}
_last_received: str = None
_control_queue: deque = deque()

# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: str):
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                self.active.remove(ws)

manager = ConnectionManager()


# --- Event loop reference for cross-thread scheduling ---
import asyncio
main_event_loop = None

# --- FastAPI app setup ---
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_event_loop
    try:
        main_event_loop = asyncio.get_running_loop()
    except Exception:
        pass
    yield

_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
app = FastAPI(title="Mixxx Status API", version="1.0.0", lifespan=lifespan)
app.mount("/web", StaticFiles(directory=_WEB_DIR), name="web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# --- Pydantic models for control endpoints ---
class AutoDJPayload(BaseModel):
    enabled: bool
class EnabledPayload(BaseModel):
    enabled: bool
class PlayPayload(BaseModel):
    play: bool
class FloatPayload(BaseModel):
    value: float
class TalkoverDuckingPayload(BaseModel):
    mode: int

# --- API Endpoints (all from status_server_v1.py) ---

# --- Status Endpoints ---
@app.post("/api/status", status_code=204)
async def receive_status(payload: dict):
    """
    Called by MIDI logic on every completed heartbeat frame.
    Stores the payload as the current status.
    """
    global _latest_status, _last_received
    _latest_status = payload
    _last_received = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    await manager.broadcast(json.dumps({"last_received": _last_received, **_latest_status}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if _latest_status:
            await websocket.send_text(json.dumps({"last_received": _last_received, **_latest_status}))
        while True:
            await websocket.receive_text()   # keep connection alive; we only push
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/status")
async def get_status():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return {
        "last_received": _last_received,
        **_latest_status,
    }

@app.get("/api/status/channels/{channel}")
async def get_channel(channel: str):
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    channels = _latest_status.get("channels", {})
    if channel not in channels:
        raise HTTPException(status_code=404, detail=f"Channel {channel!r} not found")
    return channels[channel]

@app.get("/api/status/internal_clock")
async def get_internal_clock():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return _latest_status.get("internal_clock", {})

@app.get("/api/status/auto_dj")
async def get_auto_dj():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return _latest_status.get("auto_dj", {})

@app.get("/api/status/crossfader")
async def get_crossfader():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return {"crossfader": _latest_status.get("crossfader")}

@app.get("/api/status/master")
async def get_master():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return _latest_status.get("master", {})

@app.get("/api/status/microphone")
async def get_microphone():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return _latest_status.get("microphone", {})

@app.get("/api/status/shoutcast")
async def get_shoutcast():
    if not _latest_status:
        raise HTTPException(status_code=503, detail="No heartbeat received yet")
    return _latest_status.get("shoutcast", {})

@app.get("/health")
async def health():
    return {"status": "ok", "last_received": _last_received}

# --- Control Endpoints ---
@app.post("/api/control/auto_dj/enabled", status_code=202)
async def control_auto_dj_enabled(payload: AutoDJPayload):
    _control_queue.append({"action": "auto_dj_enabled", "value": payload.enabled})
    return {"queued": True, "action": "auto_dj_enabled", "value": payload.enabled}

@app.post("/api/control/auto_dj/fade_now", status_code=202)
async def control_auto_dj_fade_now():
    _control_queue.append({"action": "auto_dj_fade_now", "value": 1})
    return {"queued": True, "action": "auto_dj_fade_now"}

@app.post("/api/control/auto_dj/shuffle_playlist", status_code=202)
async def control_auto_dj_shuffle():
    _control_queue.append({"action": "auto_dj_shuffle", "value": 1})
    return {"queued": True, "action": "auto_dj_shuffle"}

@app.post("/api/control/auto_dj/add_random_track", status_code=202)
async def control_auto_dj_add_random():
    _control_queue.append({"action": "auto_dj_add_random", "value": 1})
    return {"queued": True, "action": "auto_dj_add_random"}

@app.post("/api/control/shoutcast/enabled", status_code=202)
async def control_shoutcast_enabled(payload: EnabledPayload):
    _control_queue.append({"action": "shoutcast_enabled", "value": payload.enabled})
    return {"queued": True, "action": "shoutcast_enabled", "value": payload.enabled}

@app.post("/api/control/channel/1/sync_enabled", status_code=202)
async def control_ch1_sync_enabled(payload: EnabledPayload):
    _control_queue.append({"action": "ch1_sync_enabled", "value": payload.enabled})
    return {"queued": True, "action": "ch1_sync_enabled", "value": payload.enabled}

@app.post("/api/control/channel/2/sync_enabled", status_code=202)
async def control_ch2_sync_enabled(payload: EnabledPayload):
    _control_queue.append({"action": "ch2_sync_enabled", "value": payload.enabled})
    return {"queued": True, "action": "ch2_sync_enabled", "value": payload.enabled}

@app.post("/api/control/channel/1/sync_leader", status_code=202)
async def control_ch1_sync_leader(payload: EnabledPayload):
    _control_queue.append({"action": "ch1_sync_leader", "value": payload.enabled})
    return {"queued": True, "action": "ch1_sync_leader", "value": payload.enabled}

@app.post("/api/control/channel/2/sync_leader", status_code=202)
async def control_ch2_sync_leader(payload: EnabledPayload):
    _control_queue.append({"action": "ch2_sync_leader", "value": payload.enabled})
    return {"queued": True, "action": "ch2_sync_leader", "value": payload.enabled}

@app.post("/api/control/channel/1/play", status_code=202)
async def control_ch1_play(payload: PlayPayload):
    _control_queue.append({"action": "ch1_play", "value": payload.play})
    return {"queued": True, "action": "ch1_play", "value": payload.play}

@app.post("/api/control/channel/2/play", status_code=202)
async def control_ch2_play(payload: PlayPayload):
    _control_queue.append({"action": "ch2_play", "value": payload.play})
    return {"queued": True, "action": "ch2_play", "value": payload.play}

@app.post("/api/control/channel/1/eject", status_code=202)
async def control_ch1_eject():
    _control_queue.append({"action": "ch1_eject", "value": 1})
    return {"queued": True, "action": "ch1_eject"}

@app.post("/api/control/channel/2/eject", status_code=202)
async def control_ch2_eject():
    _control_queue.append({"action": "ch2_eject", "value": 1})
    return {"queued": True, "action": "ch2_eject"}

@app.post("/api/control/internal_clock/sync_leader", status_code=202)
async def control_intclk_sync_leader(payload: EnabledPayload):
    _control_queue.append({"action": "intclk_sync_leader", "value": payload.enabled})
    return {"queued": True, "action": "intclk_sync_leader", "value": payload.enabled}

@app.post("/api/control/channel/1/quantize", status_code=202)
async def control_ch1_quantize(payload: EnabledPayload):
    _control_queue.append({"action": "ch1_quantize", "value": payload.enabled})
    return {"queued": True, "action": "ch1_quantize", "value": payload.enabled}

@app.post("/api/control/channel/2/quantize", status_code=202)
async def control_ch2_quantize(payload: EnabledPayload):
    _control_queue.append({"action": "ch2_quantize", "value": payload.enabled})
    return {"queued": True, "action": "ch2_quantize", "value": payload.enabled}

@app.post("/api/control/channel/1/bpm", status_code=202)
async def control_ch1_bpm(payload: FloatPayload):
    _control_queue.append({"action": "ch1_bpm", "value": payload.value})
    return {"queued": True, "action": "ch1_bpm", "value": payload.value}

@app.post("/api/control/channel/2/bpm", status_code=202)
async def control_ch2_bpm(payload: FloatPayload):
    _control_queue.append({"action": "ch2_bpm", "value": payload.value})
    return {"queued": True, "action": "ch2_bpm", "value": payload.value}

@app.post("/api/control/channel/1/rate", status_code=202)
async def control_ch1_rate(payload: FloatPayload):
    _control_queue.append({"action": "ch1_rate", "value": payload.value})
    return {"queued": True, "action": "ch1_rate", "value": payload.value}

@app.post("/api/control/channel/2/rate", status_code=202)
async def control_ch2_rate(payload: FloatPayload):
    _control_queue.append({"action": "ch2_rate", "value": payload.value})
    return {"queued": True, "action": "ch2_rate", "value": payload.value}

@app.post("/api/control/channel/1/pitch", status_code=202)
async def control_ch1_pitch(payload: FloatPayload):
    _control_queue.append({"action": "ch1_pitch", "value": payload.value})
    return {"queued": True, "action": "ch1_pitch", "value": payload.value}

@app.post("/api/control/channel/2/pitch", status_code=202)
async def control_ch2_pitch(payload: FloatPayload):
    _control_queue.append({"action": "ch2_pitch", "value": payload.value})
    return {"queued": True, "action": "ch2_pitch", "value": payload.value}

@app.post("/api/control/internal_clock/bpm", status_code=202)
async def control_intclk_bpm(payload: FloatPayload):
    _control_queue.append({"action": "intclk_bpm", "value": payload.value})
    return {"queued": True, "action": "intclk_bpm", "value": payload.value}

@app.post("/api/control/crossfader", status_code=202)
async def control_crossfader(payload: FloatPayload):
    if not -1.0 <= payload.value <= 1.0:
        raise HTTPException(status_code=422, detail="Crossfader value must be between -1.0 and 1.0")
    _control_queue.append({"action": "crossfader", "value": payload.value})
    return {"queued": True, "action": "crossfader", "value": payload.value}

@app.post("/api/control/master/talkover_ducking", status_code=202)
async def control_talkover_ducking(payload: TalkoverDuckingPayload):
    if payload.mode not in (0, 1, 2):
        raise HTTPException(status_code=422, detail="mode must be 0 (disabled), 1 (auto), or 2 (manual)")
    _control_queue.append({"action": "talkover_ducking", "value": payload.mode})
    return {"queued": True, "action": "talkover_ducking", "value": payload.mode}

@app.post("/api/control/master/duck_strength", status_code=202)
async def control_duck_strength(payload: FloatPayload):
    if not 0.0 <= payload.value <= 1.0:
        raise HTTPException(status_code=422, detail="duck_strength value must be between 0.0 and 1.0")
    _control_queue.append({"action": "duck_strength", "value": payload.value})
    return {"queued": True, "action": "duck_strength", "value": payload.value}

@app.post("/api/control/microphone/talkover", status_code=202)
async def control_mic_talkover(payload: EnabledPayload):
    _control_queue.append({"action": "mic_talkover", "value": payload.enabled})
    return {"queued": True, "action": "mic_talkover", "value": payload.enabled}

@app.post("/api/control/channel/1/volume", status_code=202)
async def control_ch1_volume(payload: FloatPayload):
    if not 0.0 <= payload.value <= 1.0:
        raise HTTPException(status_code=422, detail="volume must be between 0.0 and 1.0")
    _control_queue.append({"action": "ch1_volume", "value": payload.value})
    return {"queued": True, "action": "ch1_volume", "value": payload.value}

@app.post("/api/control/channel/2/volume", status_code=202)
async def control_ch2_volume(payload: FloatPayload):
    if not 0.0 <= payload.value <= 1.0:
        raise HTTPException(status_code=422, detail="volume must be between 0.0 and 1.0")
    _control_queue.append({"action": "ch2_volume", "value": payload.value})
    return {"queued": True, "action": "ch2_volume", "value": payload.value}

_PREGAIN_MAX = 3.981071705534973
_MASTER_GAIN_MAX = 5.011872336272724



ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    from backend.mixxx_config import MIDI_PORT, midi_port_to_device
except ImportError:
    MIDI_PORT = 0
    def midi_port_to_device(port):
        return f"/dev/snd/midiC1D0"

# MIDI control constants (copy from midi_json_translator.py)
CTRL_CHANNEL = 1
CTRL_AUTO_DJ_EN = 0x19
CTRL_AUTO_DJ_FADE_NOW = 0x1A
CTRL_AUTO_DJ_SHUFFLE = 0x1B
CTRL_AUTO_DJ_ADD_RANDOM = 0x1C
CTRL_SHOUTCAST_EN = 0x1D
CTRL_CH1_SYNC_EN = 0x1E
CTRL_CH2_SYNC_EN = 0x1F
CTRL_CH1_SYNC_LEADER = 0x20
CTRL_CH2_SYNC_LEADER = 0x21
CTRL_CH1_PLAY = 0x22
CTRL_CH2_PLAY = 0x23
CTRL_CH1_EJECT = 0x24
CTRL_CH2_EJECT = 0x25
CTRL_INTCLK_SYNC_LEADER = 0x26
CTRL_CH1_BPM_HIGH = 0x27
CTRL_CH1_BPM_LOW = 0x28
CTRL_CH1_BPM_FRAC = 0x29
CTRL_CH2_BPM_HIGH = 0x2A
CTRL_CH2_BPM_LOW = 0x2B
CTRL_CH2_BPM_FRAC = 0x2C
CTRL_CH1_RATE_SIGN = 0x2D
CTRL_CH1_RATE_INT = 0x2E
CTRL_CH1_RATE_FRAC = 0x2F
CTRL_CH2_RATE_SIGN = 0x30
CTRL_CH2_RATE_INT = 0x31
CTRL_CH2_RATE_FRAC = 0x32
CTRL_CH1_PITCH_SIGN = 0x33
CTRL_CH1_PITCH_INT = 0x34
CTRL_CH1_PITCH_FRAC = 0x35
CTRL_CH2_PITCH_SIGN = 0x36
CTRL_CH2_PITCH_INT = 0x37
CTRL_CH2_PITCH_FRAC = 0x38
CTRL_INTCLK_BPM_HIGH = 0x39
CTRL_INTCLK_BPM_LOW = 0x3A
CTRL_INTCLK_BPM_FRAC = 0x3B
CTRL_CH1_QUANTIZE = 0x3C
CTRL_CH2_QUANTIZE = 0x3D
CTRL_CROSSFADER_SIGN = 0x3E
CTRL_CROSSFADER_INT = 0x3F
CTRL_CROSSFADER_FRAC = 0x40
CTRL_TALKOVER_DUCKING = 0x41
CTRL_DUCK_STRENGTH_INT = 0x42
CTRL_DUCK_STRENGTH_FRAC = 0x43
CTRL_MIC_TALKOVER = 0x44
CTRL_CH1_VOLUME_INT = 0x45
CTRL_CH1_VOLUME_FRAC = 0x46
CTRL_CH2_VOLUME_INT = 0x47
CTRL_CH2_VOLUME_FRAC = 0x48
CTRL_CH1_PREGAIN_INT = 0x49
CTRL_CH1_PREGAIN_FRAC = 0x4A
CTRL_CH2_PREGAIN_INT = 0x4B
CTRL_CH2_PREGAIN_FRAC = 0x4C
CTRL_MASTER_GAIN_INT = 0x4D
CTRL_MASTER_GAIN_FRAC = 0x4E

# Frame notes (copy from midi_json_translator.py)
FRAME_START = 0x63
FRAME_END = 0x64
AUTO_DJ_STATUS = 0x65
SHOUTCAST_STATUS = 0x66
SHOUTCAST_STATE = 0x67
CH1_SYNC_ENABLED = 0x68
CH2_SYNC_ENABLED = 0x69
CH1_PLAY = 0x6A
CH2_PLAY = 0x6B
CH1_END_OF_TRACK = 0x6C
CH2_END_OF_TRACK = 0x6D
CH1_BPM_HIGH = 0x6E
CH1_BPM_LOW = 0x6F
CH1_BPM_FRAC = 0x70
CH2_BPM_HIGH = 0x71
CH2_BPM_LOW = 0x72
CH2_BPM_FRAC = 0x73
CH1_DUR_HIGH = 0x74
CH1_DUR_LOW = 0x75
CH1_DUR_FRAC = 0x76
CH2_DUR_HIGH = 0x77
CH2_DUR_LOW = 0x78
CH2_DUR_FRAC = 0x79
CH1_REM_HIGH = 0x7A
CH1_REM_LOW = 0x7B
CH1_REM_FRAC = 0x7C
CH2_REM_HIGH = 0x7D
CH2_REM_LOW = 0x7E
CH2_REM_FRAC = 0x7F
CH1_RATE_SIGN = 0x00
CH1_RATE_INT = 0x01
CH1_RATE_FRAC = 0x02
CH2_RATE_SIGN = 0x03
CH2_RATE_INT = 0x04
CH2_RATE_FRAC = 0x05
CH1_PITCH_SIGN = 0x06
CH1_PITCH_INT = 0x07
CH1_PITCH_FRAC = 0x08
CH2_PITCH_SIGN = 0x09
CH2_PITCH_INT = 0x0A
CH2_PITCH_FRAC = 0x0B
CH1_RANGE_INT = 0x0C
CH1_RANGE_FRAC = 0x0D
CH2_RANGE_INT = 0x0F
CH2_RANGE_FRAC = 0x10
CH1_RATE_DIR = 0x11
CH2_RATE_DIR = 0x12
INT_CLK_SYNC_LEADER = 0x13
INT_CLK_BPM_HIGH = 0x14
INT_CLK_BPM_LOW = 0x15
INT_CLK_BPM_FRAC = 0x16
CH1_SYNC_LEADER = 0x17
CH2_SYNC_LEADER = 0x18
CH1_TRACK_LOADED = 0x19
CH2_TRACK_LOADED = 0x1A
CH1_QUANTIZE = 0x1B
CH2_QUANTIZE = 0x1C
CROSSFADER_SIGN = 0x1D
CROSSFADER_INT = 0x1E
CROSSFADER_FRAC = 0x1F
TALKOVER_DUCKING = 0x20
DUCK_STRENGTH_INT = 0x21
DUCK_STRENGTH_FRAC = 0x22
MIC_TALKOVER = 0x23
CH1_VOLUME_INT = 0x24
CH1_VOLUME_FRAC = 0x25
CH2_VOLUME_INT = 0x26
CH2_VOLUME_FRAC = 0x27
CH1_PREGAIN_INT = 0x28
CH1_PREGAIN_FRAC = 0x29
CH2_PREGAIN_INT = 0x2A
CH2_PREGAIN_FRAC = 0x2B
MASTER_GAIN_INT = 0x2C
MASTER_GAIN_FRAC = 0x2D

# --- MIDI Frame State ---
_last_frame_counter = -1
_pending = {}

def _build_empty_frame(frame_num):
    return {
        'timestamp':      None,
        'frame':          frame_num,
        'auto_dj':        {'enabled': None},
        'shoutcast':      {'enabled': None, 'status': None},
        'crossfader':     None,
        'master':         {'talkover_ducking': None, 'duck_strength': None, 'gain': None},
        'microphone':     {'talkover': None},
        'internal_clock': {'bpm': None, 'sync_leader': None},
        'channels': {
            '1': {
                'play': None, 'sync_enabled': None, 'sync_leader': None,
                'end_of_track': None, 'track_loaded': None, 'quantize': None,
                'bpm': None, 'duration': None,
                'time_remaining': None, 'rate_pct': None,
                'rate_range_pct': None, 'rate_dir': None, 'pitch_semitones': None,
                'volume': None, 'pregain': None,
            },
            '2': {
                'play': None, 'sync_enabled': None, 'sync_leader': None,
                'end_of_track': None, 'track_loaded': None, 'quantize': None,
                'bpm': None, 'duration': None,
                'time_remaining': None, 'rate_pct': None,
                'rate_range_pct': None, 'rate_dir': None, 'pitch_semitones': None,
                'volume': None, 'pregain': None,
            },
        },
    }

_frame = _build_empty_frame(0)

# --- MIDI Device Discovery ---
def find_virmidi_device():
    default = midi_port_to_device(MIDI_PORT)
    if os.path.exists(default):
        return default
    for id_file in glob.glob('/proc/asound/card*/id'):
        try:
            with open(id_file) as f:
                if 'VirMIDI' in f.read():
                    card_num = id_file.split('/')[3].replace('card', '')
                    dev = f'/dev/snd/midiC{card_num}D0'
                    if os.path.exists(dev):
                        return dev
        except OSError:
            pass
    return None

# --- MIDI Control Writers (helpers) ---
def _write_ctrl(dev_w, note, vel, label):
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, note, vel]))
    dev_w.flush()
    print(f'[{time.strftime("%H:%M:%S")}]  → CTRL {label}: {vel}')

def _write_bpm_ctrl(dev_w, high_note, value, label):
    int_part  = int(value)
    frac_part = round((value - int_part) * 100) & 0x7F
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, high_note,     (int_part >> 7) & 0x7F]))
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, high_note + 1, int_part & 0x7F]))
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, high_note + 2, frac_part]))
    dev_w.flush()
    print(f'[{time.strftime("%H:%M:%S")}]  → CTRL {label}: {value:.2f} BPM')

def _write_signed_ctrl(dev_w, sign_note, value, label):
    sign      = 1 if value < 0 else 0
    abs_val   = abs(value)
    int_part  = int(abs_val)
    frac_part = round((abs_val - int_part) * 100) & 0x7F
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, sign_note,     sign]))
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, sign_note + 1, int_part & 0x7F]))
    dev_w.write(bytes([0x90 + CTRL_CHANNEL, sign_note + 2, frac_part]))
    dev_w.flush()
    print(f'[{time.strftime("%H:%M:%S")}]  → CTRL {label}: {value:+.2f}')

# --- MIDI Control Polling and Sending ---
def poll_and_send_controls(dev_w):
    # Directly use the in-memory _control_queue
    commands = list(_control_queue)
    _control_queue.clear()
    for cmd in commands:
        action = cmd.get('action')
        value  = cmd.get('value')
        if action == 'auto_dj_enabled':
            _write_ctrl(dev_w, CTRL_AUTO_DJ_EN,         1 if value else 0, 'AutoDJ.enabled')
        elif action == 'auto_dj_fade_now':
            _write_ctrl(dev_w, CTRL_AUTO_DJ_FADE_NOW,   1,                 'AutoDJ.fade_now')
        elif action == 'auto_dj_shuffle':
            _write_ctrl(dev_w, CTRL_AUTO_DJ_SHUFFLE,    1,                 'AutoDJ.shuffle_playlist')
        elif action == 'auto_dj_add_random':
            _write_ctrl(dev_w, CTRL_AUTO_DJ_ADD_RANDOM, 1,                 'AutoDJ.add_random_track')
        elif action == 'shoutcast_enabled':
            _write_ctrl(dev_w, CTRL_SHOUTCAST_EN,       1 if value else 0, 'Shoutcast.enabled')
        elif action == 'ch1_sync_enabled':
            _write_ctrl(dev_w, CTRL_CH1_SYNC_EN,        1 if value else 0, 'Ch1.sync_enabled')
        elif action == 'ch2_sync_enabled':
            _write_ctrl(dev_w, CTRL_CH2_SYNC_EN,        1 if value else 0, 'Ch2.sync_enabled')
        elif action == 'ch1_sync_leader':
            _write_ctrl(dev_w, CTRL_CH1_SYNC_LEADER,    1 if value else 0, 'Ch1.sync_leader')
        elif action == 'ch2_sync_leader':
            _write_ctrl(dev_w, CTRL_CH2_SYNC_LEADER,    1 if value else 0, 'Ch2.sync_leader')
        elif action == 'ch1_play':
            _write_ctrl(dev_w, CTRL_CH1_PLAY,           1 if value else 0, 'Ch1.play')
        elif action == 'ch2_play':
            _write_ctrl(dev_w, CTRL_CH2_PLAY,           1 if value else 0, 'Ch2.play')
        elif action == 'ch1_eject':
            _write_ctrl(dev_w, CTRL_CH1_EJECT,          1,                 'Ch1.eject')
        elif action == 'ch2_eject':
            _write_ctrl(dev_w, CTRL_CH2_EJECT,          1,                 'Ch2.eject')
        elif action == 'intclk_sync_leader':
            _write_ctrl(dev_w, CTRL_INTCLK_SYNC_LEADER, 1 if value else 0, 'InternalClock.sync_leader')
        elif action == 'ch1_bpm':
            _write_bpm_ctrl(dev_w, CTRL_CH1_BPM_HIGH,    float(value), 'Ch1.bpm')
        elif action == 'ch2_bpm':
            _write_bpm_ctrl(dev_w, CTRL_CH2_BPM_HIGH,    float(value), 'Ch2.bpm')
        elif action == 'ch1_rate':
            _write_signed_ctrl(dev_w, CTRL_CH1_RATE_SIGN, float(value), 'Ch1.rate%')
        elif action == 'ch2_rate':
            _write_signed_ctrl(dev_w, CTRL_CH2_RATE_SIGN, float(value), 'Ch2.rate%')
        elif action == 'ch1_pitch':
            _write_signed_ctrl(dev_w, CTRL_CH1_PITCH_SIGN, float(value), 'Ch1.pitch')
        elif action == 'ch2_pitch':
            _write_signed_ctrl(dev_w, CTRL_CH2_PITCH_SIGN, float(value), 'Ch2.pitch')
        elif action == 'intclk_bpm':
            _write_bpm_ctrl(dev_w, CTRL_INTCLK_BPM_HIGH,  float(value), 'InternalClock.bpm')
        elif action == 'ch1_quantize':
            _write_ctrl(dev_w, CTRL_CH1_QUANTIZE, 1 if value else 0, 'Ch1.quantize')
        elif action == 'ch2_quantize':
            _write_ctrl(dev_w, CTRL_CH2_QUANTIZE, 1 if value else 0, 'Ch2.quantize')
        elif action == 'crossfader':
            _write_signed_ctrl(dev_w, CTRL_CROSSFADER_SIGN, float(value), 'Master.crossfader')
        elif action == 'talkover_ducking':
            _write_ctrl(dev_w, CTRL_TALKOVER_DUCKING, int(value) & 3, 'Master.talkoverDucking')
        elif action == 'duck_strength':
            duck_int  = int(float(value))
            duck_frac = round((float(value) - duck_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_DUCK_STRENGTH_INT,  duck_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_DUCK_STRENGTH_FRAC, duck_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Master.duckStrength: {float(value):.2f}')
        elif action == 'mic_talkover':
            _write_ctrl(dev_w, CTRL_MIC_TALKOVER, 1 if value else 0, 'Microphone.talkover')
        elif action == 'ch1_volume':
            vol_int  = int(float(value))
            vol_frac = round((float(value) - vol_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH1_VOLUME_INT,  vol_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH1_VOLUME_FRAC, vol_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Ch1.volume: {float(value):.2f}')
        elif action == 'ch2_volume':
            vol_int  = int(float(value))
            vol_frac = round((float(value) - vol_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH2_VOLUME_INT,  vol_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH2_VOLUME_FRAC, vol_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Ch2.volume: {float(value):.2f}')
        elif action == 'ch1_pregain':
            pg_int  = int(float(value))
            pg_frac = round((float(value) - pg_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH1_PREGAIN_INT,  pg_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH1_PREGAIN_FRAC, pg_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Ch1.pregain: {float(value):.4f}')
        elif action == 'ch2_pregain':
            pg_int  = int(float(value))
            pg_frac = round((float(value) - pg_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH2_PREGAIN_INT,  pg_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_CH2_PREGAIN_FRAC, pg_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Ch2.pregain: {float(value):.4f}')
        elif action == 'master_gain':
            gain_int  = int(float(value))
            gain_frac = round((float(value) - gain_int) * 100) & 0x7F
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_MASTER_GAIN_INT,  gain_int & 0x7F]))
            dev_w.write(bytes([0x90 + CTRL_CHANNEL, CTRL_MASTER_GAIN_FRAC, gain_frac]))
            dev_w.flush()
            print(f'[{time.strftime("%H:%M:%S")}]  → CTRL Master.gain: {float(value):.4f}')

# --- MIDI Note Processing and Frame Assembly ---
def process_note(note, vel):
    ch = _frame['channels']
    if note == FRAME_START:
        expected = (_last_frame_counter + 1) & 0x7F
        skip = f'  *** SKIPPED {(vel - expected) & 0x7F} frame(s) ***' if _last_frame_counter >= 0 and vel != expected else ''
        return f'Frame.start #{vel}{skip}'
    elif note == FRAME_END:
        match = '✓' if vel == ((_last_frame_counter + 1) & 0x7F) or _last_frame_counter < 0 else '✗ MISMATCH'
        return f'Frame.end   #{vel} {match}'
    elif note == AUTO_DJ_STATUS:
        _frame['auto_dj']['enabled'] = bool(vel)
        return f'AutoDJ.enabled: {"ON" if vel else "OFF"}'
    elif note == SHOUTCAST_STATUS:
        _frame['shoutcast']['enabled'] = bool(vel)
        return f'Shoutcast.enabled: {"ON" if vel else "OFF"}'
    elif note == SHOUTCAST_STATE:
        s = {0: 'disconnected', 1: 'pending', 2: 'connected'}.get(vel, f'unknown({vel})')
        _frame['shoutcast']['status'] = s
        return f'Shoutcast.status: {s}'
    elif note == CH1_SYNC_ENABLED:
        ch['1']['sync_enabled'] = bool(vel)
        return f'Channel1.sync_enabled: {"ON" if vel else "OFF"}'
    elif note == CH2_SYNC_ENABLED:
        ch['2']['sync_enabled'] = bool(vel)
        return f'Channel2.sync_enabled: {"ON" if vel else "OFF"}'
    elif note == CH1_PLAY:
        ch['1']['play'] = bool(vel)
        return f'Channel1.play: {"PLAYING" if vel else "STOPPED"}'
    elif note == CH2_PLAY:
        ch['2']['play'] = bool(vel)
        return f'Channel2.play: {"PLAYING" if vel else "STOPPED"}'
    elif note == CH1_END_OF_TRACK:
        ch['1']['end_of_track'] = bool(vel)
        return f'Channel1.end_of_track: {"END" if vel else "NOT END"}'
    elif note == CH2_END_OF_TRACK:
        ch['2']['end_of_track'] = bool(vel)
        return f'Channel2.end_of_track: {"END" if vel else "NOT END"}'
    elif note == CH1_TRACK_LOADED:
        ch['1']['track_loaded'] = bool(vel)
        return f'Channel1.track_loaded: {"LOADED" if vel else "EMPTY"}'
    elif note == CH2_TRACK_LOADED:
        ch['2']['track_loaded'] = bool(vel)
        return f'Channel2.track_loaded: {"LOADED" if vel else "EMPTY"}'
    elif note == CH1_QUANTIZE:
        ch['1']['quantize'] = bool(vel)
        return f'Channel1.quantize: {"ON" if vel else "OFF"}'
    elif note == CH2_QUANTIZE:
        ch['2']['quantize'] = bool(vel)
        return f'Channel2.quantize: {"ON" if vel else "OFF"}'
    elif note == CROSSFADER_SIGN:
        _pending['crossfader_sign'] = vel; return None
    elif note == CROSSFADER_INT:
        _pending['crossfader_int'] = vel; return None
    elif note == CROSSFADER_FRAC:
        sign = _pending.pop('crossfader_sign', 0)
        val  = round((_pending.pop('crossfader_int', 0) + vel / 100.0) * (-1 if sign else 1), 2)
        _frame['crossfader'] = val
        return f'Master.crossfader: {val:+.2f}'
    elif note == TALKOVER_DUCKING:
        label = {0: 'disabled', 1: 'auto', 2: 'manual'}.get(vel, f'unknown({vel})')
        _frame['master']['talkover_ducking'] = vel
        return f'Master.talkoverDucking: {label}'
    elif note == DUCK_STRENGTH_INT:
        _pending['duck_strength_int'] = vel; return None
    elif note == DUCK_STRENGTH_FRAC:
        val = round(_pending.pop('duck_strength_int', 0) + vel / 100.0, 2)
        _frame['master']['duck_strength'] = val
        return f'Master.duckStrength: {val:.2f}'
    elif note == MIC_TALKOVER:
        _frame['microphone']['talkover'] = bool(vel)
        return f'Microphone.talkover: {"ON" if vel else "OFF"}'
    elif note == CH1_VOLUME_INT:
        _pending['ch1_volume_int'] = vel; return None
    elif note == CH1_VOLUME_FRAC:
        val = round(_pending.pop('ch1_volume_int', 0) + vel / 100.0, 2)
        ch['1']['volume'] = val
        return f'Channel1.volume: {val:.2f}'
    elif note == CH2_VOLUME_INT:
        _pending['ch2_volume_int'] = vel; return None
    elif note == CH2_VOLUME_FRAC:
        val = round(_pending.pop('ch2_volume_int', 0) + vel / 100.0, 2)
        ch['2']['volume'] = val
        return f'Channel2.volume: {val:.2f}'
    elif note == CH1_PREGAIN_INT:
        _pending['ch1_pregain_int'] = vel; return None
    elif note == CH1_PREGAIN_FRAC:
        val = round(_pending.pop('ch1_pregain_int', 0) + vel / 100.0, 4)
        ch['1']['pregain'] = val
        return f'Channel1.pregain: {val:.4f}'
    elif note == CH2_PREGAIN_INT:
        _pending['ch2_pregain_int'] = vel; return None
    elif note == CH2_PREGAIN_FRAC:
        val = round(_pending.pop('ch2_pregain_int', 0) + vel / 100.0, 4)
        ch['2']['pregain'] = val
        return f'Channel2.pregain: {val:.4f}'
    elif note == MASTER_GAIN_INT:
        _pending['master_gain_int'] = vel; return None
    elif note == MASTER_GAIN_FRAC:
        val = round(_pending.pop('master_gain_int', 0) + vel / 100.0, 4)
        _frame['master']['gain'] = val
        return f'Master.gain: {val:.4f}'
    elif note == CH1_BPM_HIGH:
        _pending['ch1_bpm_high'] = vel; return None
    elif note == CH1_BPM_LOW:
        _pending['ch1_bpm_low'] = vel; return None
    elif note == CH1_BPM_FRAC:
        high = _pending.pop('ch1_bpm_high', 0); low = _pending.pop('ch1_bpm_low', 0)
        bpm = round((high * 128 + low) + vel / 100.0, 2)
        ch['1']['bpm'] = bpm
        return f'Channel1.bpm: {bpm:.2f} BPM'
    elif note == CH2_BPM_HIGH:
        _pending['ch2_bpm_high'] = vel; return None
    elif note == CH2_BPM_LOW:
        _pending['ch2_bpm_low'] = vel; return None
    elif note == CH2_BPM_FRAC:
        high = _pending.pop('ch2_bpm_high', 0); low = _pending.pop('ch2_bpm_low', 0)
        bpm = round((high * 128 + low) + vel / 100.0, 2)
        ch['2']['bpm'] = bpm
        return f'Channel2.bpm: {bpm:.2f} BPM'
    elif note == CH1_DUR_HIGH:
        _pending['ch1_dur_high'] = vel; return None
    elif note == CH1_DUR_LOW:
        _pending['ch1_dur_low'] = vel; return None
    elif note == CH1_DUR_FRAC:
        high = _pending.pop('ch1_dur_high', 0); low = _pending.pop('ch1_dur_low', 0)
        secs = round((high * 128 + low) + vel / 100.0, 2)
        ch['1']['duration'] = secs
        return f'Channel1.duration: {secs:.2f}s'
    elif note == CH2_DUR_HIGH:
        _pending['ch2_dur_high'] = vel; return None
    elif note == CH2_DUR_LOW:
        _pending['ch2_dur_low'] = vel; return None
    elif note == CH2_DUR_FRAC:
        high = _pending.pop('ch2_dur_high', 0); low = _pending.pop('ch2_dur_low', 0)
        secs = round((high * 128 + low) + vel / 100.0, 2)
        ch['2']['duration'] = secs
        return f'Channel2.duration: {secs:.2f}s'
    elif note == CH1_REM_HIGH:
        _pending['ch1_rem_high'] = vel; return None
    elif note == CH1_REM_LOW:
        _pending['ch1_rem_low'] = vel; return None
    elif note == CH1_REM_FRAC:
        high = _pending.pop('ch1_rem_high', 0); low = _pending.pop('ch1_rem_low', 0)
        secs = round((high * 128 + low) + vel / 100.0, 2)
        ch['1']['time_remaining'] = secs
        return f'Channel1.time_remaining: {secs:.2f}s'
    elif note == CH2_REM_HIGH:
        _pending['ch2_rem_high'] = vel; return None
    elif note == CH2_REM_LOW:
        _pending['ch2_rem_low'] = vel; return None
    elif note == CH2_REM_FRAC:
        high = _pending.pop('ch2_rem_high', 0); low = _pending.pop('ch2_rem_low', 0)
        secs = round((high * 128 + low) + vel / 100.0, 2)
        ch['2']['time_remaining'] = secs
        return f'Channel2.time_remaining: {secs:.2f}s'
    elif note == CH1_RATE_SIGN:
        _pending['ch1_rate_sign'] = vel; return None
    elif note == CH1_RATE_INT:
        _pending['ch1_rate_int'] = vel; return None
    elif note == CH1_RATE_FRAC:
        sign = _pending.pop('ch1_rate_sign', 0)
        val  = round((_pending.pop('ch1_rate_int', 0) + vel / 100.0) * (-1 if sign else 1), 2)
        ch['1']['rate_pct'] = val
        return f'Channel1.rate: {val:+.2f}%'
    elif note == CH2_RATE_SIGN:
        _pending['ch2_rate_sign'] = vel; return None
    elif note == CH2_RATE_INT:
        _pending['ch2_rate_int'] = vel; return None
    elif note == CH2_RATE_FRAC:
        sign = _pending.pop('ch2_rate_sign', 0)
        val  = round((_pending.pop('ch2_rate_int', 0) + vel / 100.0) * (-1 if sign else 1), 2)
        ch['2']['rate_pct'] = val
        return f'Channel2.rate: {val:+.2f}%'
    elif note == CH1_RANGE_INT:
        _pending['ch1_range_int'] = vel; return None
    elif note == CH1_RANGE_FRAC:
        rng = round(_pending.pop('ch1_range_int', 0) + vel / 100.0, 2)
        ch['1']['rate_range_pct'] = rng
        return f'Channel1.rateRange: {rng:.2f}%'
    elif note == CH2_RANGE_INT:
        _pending['ch2_range_int'] = vel; return None
    elif note == CH2_RANGE_FRAC:
        rng = round(_pending.pop('ch2_range_int', 0) + vel / 100.0, 2)
        ch['2']['rate_range_pct'] = rng
        return f'Channel2.rateRange: {rng:.2f}%'
    elif note == CH1_RATE_DIR:
        s = 'inverted' if vel else 'normal'
        ch['1']['rate_dir'] = s
        return f'Channel1.rate_dir: {s}'
    elif note == CH2_RATE_DIR:
        s = 'inverted' if vel else 'normal'
        ch['2']['rate_dir'] = s
        return f'Channel2.rate_dir: {s}'
    elif note == CH1_SYNC_LEADER:
        ch['1']['sync_leader'] = bool(vel)
        return f'Channel1.sync_leader: {"ON" if vel else "OFF"}'
    elif note == CH2_SYNC_LEADER:
        ch['2']['sync_leader'] = bool(vel)
        return f'Channel2.sync_leader: {"ON" if vel else "OFF"}'
    elif note == INT_CLK_SYNC_LEADER:
        _frame['internal_clock']['sync_leader'] = bool(vel)
        return f'InternalClock.sync_leader: {"ON" if vel else "OFF"}'
    elif note == INT_CLK_BPM_HIGH:
        _pending['intclk_bpm_high'] = vel; return None
    elif note == INT_CLK_BPM_LOW:
        _pending['intclk_bpm_low'] = vel; return None
    elif note == INT_CLK_BPM_FRAC:
        high = _pending.pop('intclk_bpm_high', 0); low = _pending.pop('intclk_bpm_low', 0)
        bpm = round((high * 128 + low) + vel / 100.0, 2)
        _frame['internal_clock']['bpm'] = bpm
        return f'InternalClock.bpm: {bpm:.2f} BPM'
    elif note == CH1_PITCH_SIGN:
        _pending['ch1_pitch_sign'] = vel; return None
    elif note == CH1_PITCH_INT:
        _pending['ch1_pitch_int'] = vel; return None
    elif note == CH1_PITCH_FRAC:
        sign = _pending.pop('ch1_pitch_sign', 0)
        val  = round((_pending.pop('ch1_pitch_int', 0) + vel / 100.0) * (-1 if sign else 1), 2)
        ch['1']['pitch_semitones'] = val
        return f'Channel1.pitch: {val:+.2f} semitones'
    elif note == CH2_PITCH_SIGN:
        _pending['ch2_pitch_sign'] = vel; return None
    elif note == CH2_PITCH_INT:
        _pending['ch2_pitch_int'] = vel; return None
    elif note == CH2_PITCH_FRAC:
        sign = _pending.pop('ch2_pitch_sign', 0)
        val  = round((_pending.pop('ch2_pitch_int', 0) + vel / 100.0) * (-1 if sign else 1), 2)
        ch['2']['pitch_semitones'] = val
        return f'Channel2.pitch: {val:+.2f} semitones'
    return f'note=0x{note:02X} vel={vel}  [UNKNOWN]'

# --- Publish Frame to API (now direct call) ---
def publish_frame(frame):
    # Instead of HTTP POST, update in-memory status and broadcast
    global _latest_status, _last_received
    _latest_status = frame
    _last_received = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    # Broadcast to all WebSocket clients
    import asyncio
    global main_event_loop
    loop = None
    try:
        # Try to get the running loop (main thread)
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Not in main thread, use the main_event_loop captured at startup
        if main_event_loop is not None:
            loop = main_event_loop
        else:
            print(f"[publish_frame] ERROR: No event loop available (main_event_loop is None)")
            return
    try:
        coro = manager.broadcast(json.dumps({"last_received": _last_received, **_latest_status}))
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        fut.add_done_callback(lambda f: f.exception() and print(f"[publish_frame] Broadcast error: {f.exception()}"))
    except Exception as e:
        print(f"[publish_frame] ERROR scheduling broadcast: {e}")

# --- MIDI Thread Main Loop ---
def midi_thread_main():
    global _last_frame_counter, _frame
    dev = find_virmidi_device()
    if not dev:
        print('ERROR: VirMIDI raw device not found.')
        print('Searched: ' + midi_port_to_device(MIDI_PORT))
        print('Fix: sudo chmod a+r /dev/snd/midiC*  OR  sudo usermod -aG audio $USER')
        return
    print('--- MIDI JSON Translator (Integrated) ---')
    print(f'Reading from:   {dev}')
    print('Waiting for frames from Mixxx... (Ctrl+C to quit)\n')
    try:
        dev_w = open(dev, 'wb', buffering=0)
        with open(dev, 'rb') as f:
            buf = bytearray()
            while True:
                r, _, _ = select.select([f], [], [], 0.01)  # 10ms timeout for responsiveness
                if r:
                    byte = f.read(1)
                    if not byte:
                        continue
                    b = byte[0]
                    if b & 0x80:
                        buf = bytearray([b])
                    else:
                        buf.append(b)
                        if len(buf) == 3:
                            status, note, vel = buf
                            if status == 0x90:
                                if note == FRAME_START:
                                    _frame = _build_empty_frame(vel)
                                    _frame['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
                                desc = process_note(note, vel)
                                # if desc is not None:
                                #     print(f'[{time.strftime("%H:%M:%S")}]  {desc}')
                                if note == FRAME_END:
                                    _last_frame_counter = vel
                                    publish_frame(_frame)
                                    poll_and_send_controls(dev_w)
                            buf = bytearray([buf[0]])
                else:
                    # No MIDI data, but still process control queue for instant response
                    poll_and_send_controls(dev_w)
    except PermissionError:
        print(f'\nERROR: No permission to read {dev}')
        print(f'Fix: sudo chmod a+r {dev}')
        print(f'Or:  sudo usermod -aG audio $USER && newgrp audio')
    except KeyboardInterrupt:
        print('\nExiting.')

# --- Start MIDI Thread on Startup ---
def start_midi_thread():
    t = threading.Thread(target=midi_thread_main, daemon=True)
    t.start()

start_midi_thread()

@app.post("/api/control/master/gain", status_code=202)
async def control_master_gain(payload: FloatPayload):
    if not 0.0 <= payload.value <= _MASTER_GAIN_MAX:
        raise HTTPException(status_code=422, detail=f"gain must be between 0.0 and {_MASTER_GAIN_MAX}")
    _control_queue.append({"action": "master_gain", "value": payload.value})
    return {"queued": True, "action": "master_gain", "value": payload.value}

@app.post("/api/control/channel/1/pregain", status_code=202)
async def control_ch1_pregain(payload: FloatPayload):
    if not 0.0 <= payload.value <= _PREGAIN_MAX:
        raise HTTPException(status_code=422, detail=f"pregain must be between 0.0 and {_PREGAIN_MAX}")
    _control_queue.append({"action": "ch1_pregain", "value": payload.value})
    return {"queued": True, "action": "ch1_pregain", "value": payload.value}

@app.post("/api/control/channel/2/pregain", status_code=202)
async def control_ch2_pregain(payload: FloatPayload):
    if not 0.0 <= payload.value <= _PREGAIN_MAX:
        raise HTTPException(status_code=422, detail=f"pregain must be between 0.0 and {_PREGAIN_MAX}")
    _control_queue.append({"action": "ch2_pregain", "value": payload.value})
    return {"queued": True, "action": "ch2_pregain", "value": payload.value}

@app.get("/api/control/pending")
async def get_pending_controls():
    commands = list(_control_queue)
    _control_queue.clear()
    return commands
