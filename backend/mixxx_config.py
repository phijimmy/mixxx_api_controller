#!/usr/bin/env python3
"""
mixxx_config.py — Shared configuration for Mixxx Api Browser Controller components.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── MIDI ──────────────────────────────────────────────────────────────────────
MIDI_PORT = 'hw:1,0'  # amidi port — also used to derive /dev/snd path


AUTODJ_ID        = 1                                                   # Mixxx AutoDJ playlist id

def midi_port_to_device(port=None):
    """Derive the raw ALSA MIDI device path from an amidi port string."""
    if port is None:
        port = MIDI_PORT
    try:
        _, addr = port.split(':', 1)
        card, dev = addr.split(',')
        return f'/dev/snd/midiC{int(card)}D{int(dev)}'
    except (ValueError, IndexError):
        return '/dev/snd/midiC1D0'

 