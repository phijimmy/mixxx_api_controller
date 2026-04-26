// mixxx_controller.js — for use with Mixxx Api Browser Controller
// Mixxx QtScript (ES5) — uses engine/midi globals provided by Mixxx

var mabc = {}; 

// ── Config ────────────────────────────────────────────────────────────────────
var heartbeatInterval = 500; // ms
var channel           = 0;    // MIDI channel 1 (0-indexed)
var frameCounter      = 0;    // 0-127 wrapping

// ── Frame notes ───────────────────────────────────────────────────────────────
var frameStartNote = 99;   // frame start: velocity = frame counter
var frameEndNote   = 100;  // frame end:   velocity = same frame counter
var autoDJStatusNote = 101; // [AutoDJ]enabled status: velocity = 0 (off) or 1 (on)
var shoutcastStatusNote = 102; // [Shoutcast]enabled status: velocity = 0 (off) or 1 (on)
var shoutcastStateNote = 103; // [Shoutcast]status: velocity = 0 (disconnected), 1 (pending), 2 (connected)
var ch1SyncEnabledNote = 104; // [Channel1]sync_enabled: velocity = 0 (off) or 1 (on)
var ch2SyncEnabledNote = 105; // [Channel2]sync_enabled: velocity = 0 (off) or 1 (on)
var ch1PlayNote = 106; // [Channel1]play: velocity = 0 (stopped) or 1 (playing)
var ch2PlayNote = 107; // [Channel2]play: velocity = 0 (stopped) or 1 (playing)
var ch1EndOfTrackNote = 108; // [Channel1]end_of_track: velocity = 0 (not end) or 1 (end)
var ch2EndOfTrackNote = 109; // [Channel2]end_of_track: velocity = 0 (not end) or 1 (end)
var ch1BpmHighNote = 110; // [Channel1]bpm integer high byte: floor(bpm) >> 7
var ch1BpmLowNote  = 111; // [Channel1]bpm integer low byte:  floor(bpm) & 0x7F
var ch1BpmFracNote = 112; // [Channel1]bpm fractional hundredths: round((bpm - floor(bpm)) * 100)
var ch2BpmHighNote = 113; // [Channel2]bpm integer high byte
var ch2BpmLowNote  = 114; // [Channel2]bpm integer low byte
var ch2BpmFracNote = 115; // [Channel2]bpm fractional hundredths
var ch1DurHighNote = 116; // [Channel1]duration integer high byte
var ch1DurLowNote  = 117; // [Channel1]duration integer low byte
var ch1DurFracNote = 118; // [Channel1]duration fractional hundredths
var ch2DurHighNote = 119; // [Channel2]duration integer high byte
var ch2DurLowNote  = 120; // [Channel2]duration integer low byte
var ch2DurFracNote = 121; // [Channel2]duration fractional hundredths
var ch1RemHighNote = 122; // [Channel1]time_remaining integer high byte
var ch1RemLowNote  = 123; // [Channel1]time_remaining integer low byte
var ch1RemFracNote = 124; // [Channel1]time_remaining fractional hundredths
var ch2RemHighNote = 125; // [Channel2]time_remaining integer high byte
var ch2RemLowNote  = 126; // [Channel2]time_remaining integer low byte
var ch2RemFracNote = 127; // [Channel2]time_remaining fractional hundredths
// Notes 0-11: signed float values (sign=0/1, integer part, fractional hundredths)
var ch1RateSignNote  = 0;  // [Channel1]rate% sign: 0=positive, 1=negative
var ch1RateIntNote   = 1;  // [Channel1]rate% integer part (abs)
var ch1RateFracNote  = 2;  // [Channel1]rate% fractional hundredths
var ch2RateSignNote  = 3;  // [Channel2]rate% sign
var ch2RateIntNote   = 4;  // [Channel2]rate% integer part
var ch2RateFracNote  = 5;  // [Channel2]rate% fractional hundredths
var ch1PitchSignNote = 6;  // [Channel1]pitch sign
var ch1PitchIntNote  = 7;  // [Channel1]pitch integer part (semitones)
var ch1PitchFracNote = 8;  // [Channel1]pitch fractional hundredths
var ch2PitchSignNote = 9;  // [Channel2]pitch sign
var ch2PitchIntNote  = 10; // [Channel2]pitch integer part (semitones)
var ch2PitchFracNote = 11; // [Channel2]pitch fractional hundredths
var ch1RangeIntNote  = 12; // [Channel1]rateRange integer (always 0, but for consistency)
var ch1RangeFracNote = 13; // [Channel1]rateRange fractional hundredths (e.g. 8 -> vel=8)
var ch2RangeIntNote  = 15; // [Channel2]rateRange integer
var ch2RangeFracNote = 16; // [Channel2]rateRange fractional hundredths
var ch1RateDirNote   = 17; // [Channel1]rate_dir: 0=normal(+1), 1=inverted(-1)
var ch2RateDirNote   = 18; // [Channel2]rate_dir: 0=normal(+1), 1=inverted(-1)
var intClkSyncLeaderNote = 19; // [InternalClock]sync_leader: 0=off, 1=on
var intClkBpmHighNote    = 20; // [InternalClock]bpm integer high byte: floor(bpm) >> 7
var intClkBpmLowNote     = 21; // [InternalClock]bpm integer low byte:  floor(bpm) & 0x7F
var intClkBpmFracNote    = 22; // [InternalClock]bpm fractional hundredths
var ch1SyncLeaderNote    = 23; // [Channel1]sync_leader: 0=off, 1=on
var ch2SyncLeaderNote    = 24; // [Channel2]sync_leader: 0=off, 1=on
var ch1TrackLoadedNote   = 25; // [Channel1]track_loaded: 0=empty, 1=loaded
var ch2TrackLoadedNote   = 26; // [Channel2]track_loaded: 0=empty, 1=loaded
var ch1QuantizeNote      = 27; // [Channel1]quantize: 0=off, 1=on
var ch2QuantizeNote      = 28; // [Channel2]quantize: 0=off, 1=on
var crossfaderSignNote   = 29; // [Master]crossfader sign: 0=positive/zero, 1=negative
var crossfaderIntNote    = 30; // [Master]crossfader integer part (0 or 1)
var crossfaderFracNote   = 31; // [Master]crossfader fractional hundredths
var talkoverDuckingNote  = 32; // [Master]talkoverDucking: 0=disabled, 1=auto, 2=manual
var duckStrengthIntNote  = 33; // [Master]duckStrength integer part (always 0)
var duckStrengthFracNote = 34; // [Master]duckStrength fractional hundredths (triggers assembly)
var micTalkoverNote      = 35; // [Microphone]talkover: 0=off, 1=on
var ch1VolumeIntNote     = 36; // [Channel1]volume integer part (0 or 1)
var ch1VolumeFracNote    = 37; // [Channel1]volume fractional hundredths (triggers assembly)
var ch2VolumeIntNote     = 38; // [Channel2]volume integer part (0 or 1)
var ch2VolumeFracNote    = 39; // [Channel2]volume fractional hundredths (triggers assembly)
var ch1PregainIntNote    = 40; // [Channel1]pregain integer part (0-3)
var ch1PregainFracNote   = 41; // [Channel1]pregain fractional hundredths (triggers assembly)
var ch2PregainIntNote    = 42; // [Channel2]pregain integer part (0-3)
var ch2PregainFracNote   = 43; // [Channel2]pregain fractional hundredths (triggers assembly)
var masterGainIntNote    = 44; // [Master]gain integer part (0-5)
var masterGainFracNote   = 45; // [Master]gain fractional hundredths (triggers assembly)

// ── Heartbeat ─────────────────────────────────────────────────────────────────
mabc._sendHeartbeat = function() {
    // Send frame start
    midi.sendShortMsg(0x90 + channel, frameStartNote, frameCounter);

    // Query [Shoutcast]enabled status (0 or 1)
    var shoutcastEnabled = engine.getValue('[Shoutcast]', 'enabled') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, shoutcastStatusNote, shoutcastEnabled);

    // Query [Shoutcast]status (0=disconnected, 1=pending, 2=connected)
    var shoutcastState = engine.getValue('[Shoutcast]', 'status');
    midi.sendShortMsg(0x90 + channel, shoutcastStateNote, shoutcastState);

    // Query [AutoDJ]enabled status (0 or 1)
    var autoDJEnabled = engine.getValue('[AutoDJ]', 'enabled') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, autoDJStatusNote, autoDJEnabled);


    // Query [Channel1]sync_enabled status (0 or 1)
    var ch1SyncEnabled = engine.getValue('[Channel1]', 'sync_enabled') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1SyncEnabledNote, ch1SyncEnabled);


    // Query [Channel2]sync_enabled status (0 or 1)
    var ch2SyncEnabled = engine.getValue('[Channel2]', 'sync_enabled') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2SyncEnabledNote, ch2SyncEnabled);

    // Query [Channel1]play status (0=stopped, 1=playing)
    var ch1Play = engine.getValue('[Channel1]', 'play') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1PlayNote, ch1Play);


    // Query [Channel2]play status (0=stopped, 1=playing)
    var ch2Play = engine.getValue('[Channel2]', 'play') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2PlayNote, ch2Play);


    // Query [Channel1]end_of_track status (0=not end, 1=end)
    var ch1EndOfTrack = engine.getValue('[Channel1]', 'end_of_track') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1EndOfTrackNote, ch1EndOfTrack);

    // Query [Channel2]end_of_track status (0=not end, 1=end)
    var ch2EndOfTrack = engine.getValue('[Channel2]', 'end_of_track') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2EndOfTrackNote, ch2EndOfTrack);

    // Query [Channel1]bpm (integer high + integer low + fractional hundredths)
    var ch1Bpm     = engine.getValue('[Channel1]', 'bpm');
    var ch1BpmInt  = Math.floor(ch1Bpm);
    var ch1BpmFrac = Math.round((ch1Bpm - ch1BpmInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1BpmHighNote, (ch1BpmInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1BpmLowNote,  ch1BpmInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1BpmFracNote, ch1BpmFrac & 0x7F);

    // Query [Channel2]bpm (integer high + integer low + fractional hundredths)
    var ch2Bpm     = engine.getValue('[Channel2]', 'bpm');
    var ch2BpmInt  = Math.floor(ch2Bpm);
    var ch2BpmFrac = Math.round((ch2Bpm - ch2BpmInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2BpmHighNote, (ch2BpmInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2BpmLowNote,  ch2BpmInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2BpmFracNote, ch2BpmFrac & 0x7F);

    // Query [Channel1]duration (integer high + integer low + fractional hundredths)
    var ch1Dur     = engine.getValue('[Channel1]', 'duration');
    var ch1DurInt  = Math.floor(ch1Dur);
    var ch1DurFrac = Math.round((ch1Dur - ch1DurInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1DurHighNote, (ch1DurInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1DurLowNote,  ch1DurInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1DurFracNote, ch1DurFrac & 0x7F);

    // Query [Channel2]duration (integer high + integer low + fractional hundredths)
    var ch2Dur     = engine.getValue('[Channel2]', 'duration');
    var ch2DurInt  = Math.floor(ch2Dur);
    var ch2DurFrac = Math.round((ch2Dur - ch2DurInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2DurHighNote, (ch2DurInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2DurLowNote,  ch2DurInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2DurFracNote, ch2DurFrac & 0x7F);

    // Query [Channel1]time_remaining (integer high + integer low + fractional hundredths)
    var ch1Rem     = engine.getValue('[Channel1]', 'time_remaining');
    var ch1RemInt  = Math.floor(ch1Rem);
    var ch1RemFrac = Math.round((ch1Rem - ch1RemInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1RemHighNote, (ch1RemInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1RemLowNote,  ch1RemInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1RemFracNote, ch1RemFrac & 0x7F);

    // Query [Channel2]time_remaining (integer high + integer low + fractional hundredths)
    var ch2Rem     = engine.getValue('[Channel2]', 'time_remaining');
    var ch2RemInt  = Math.floor(ch2Rem);
    var ch2RemFrac = Math.round((ch2Rem - ch2RemInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2RemHighNote, (ch2RemInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2RemLowNote,  ch2RemInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2RemFracNote, ch2RemFrac & 0x7F);

    // Query [Channel1]rate% = rate * rate_dir * rateRange * 100 (matches Mixxx display)
    var ch1RateRange = engine.getValue('[Channel1]', 'rateRange');
    var ch1RateDir   = engine.getValue('[Channel1]', 'rate_dir');
    var ch1RatePct   = engine.getValue('[Channel1]', 'rate') * ch1RateDir * ch1RateRange * 100;
    var ch1RateAbs   = Math.abs(ch1RatePct);
    var ch1RateInt   = Math.floor(ch1RateAbs);
    var ch1RateFrac  = Math.round((ch1RateAbs - ch1RateInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1RateSignNote,  ch1RatePct < 0 ? 1 : 0);
    midi.sendShortMsg(0x90 + channel, ch1RateIntNote,   ch1RateInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1RateFracNote,  ch1RateFrac & 0x7F);

    // Query [Channel1]rateRange (e.g. 0.08 -> sent as int=0, frac=8)
    var ch1RangeVal  = ch1RateRange * 100;
    midi.sendShortMsg(0x90 + channel, ch1RangeIntNote,  Math.floor(ch1RangeVal) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1RangeFracNote, Math.round((ch1RangeVal - Math.floor(ch1RangeVal)) * 100) & 0x7F);

    // Query [Channel2]rate% = rate * rate_dir * rateRange * 100
    var ch2RateRange = engine.getValue('[Channel2]', 'rateRange');
    var ch2RateDir   = engine.getValue('[Channel2]', 'rate_dir');
    var ch2RatePct   = engine.getValue('[Channel2]', 'rate') * ch2RateDir * ch2RateRange * 100;
    var ch2RateAbs   = Math.abs(ch2RatePct);
    var ch2RateInt   = Math.floor(ch2RateAbs);
    var ch2RateFrac  = Math.round((ch2RateAbs - ch2RateInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2RateSignNote,  ch2RatePct < 0 ? 1 : 0);
    midi.sendShortMsg(0x90 + channel, ch2RateIntNote,   ch2RateInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2RateFracNote,  ch2RateFrac & 0x7F);

    // Query [Channel2]rateRange
    var ch2RangeVal  = ch2RateRange * 100;
    midi.sendShortMsg(0x90 + channel, ch2RangeIntNote,  Math.floor(ch2RangeVal) & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2RangeFracNote, Math.round((ch2RangeVal - Math.floor(ch2RangeVal)) * 100) & 0x7F);

    // Query [Channel1]rate_dir (already read above, send as MIDI)
    midi.sendShortMsg(0x90 + channel, ch1RateDirNote, ch1RateDir < 0 ? 1 : 0);

    // Query [Channel2]rate_dir (already read above, send as MIDI)
    midi.sendShortMsg(0x90 + channel, ch2RateDirNote, ch2RateDir < 0 ? 1 : 0);

    // Query [Channel1]pitch (in semitones)
    var ch1Pitch     = engine.getValue('[Channel1]', 'pitch');
    var ch1PitchAbs  = Math.abs(ch1Pitch);
    var ch1PitchInt  = Math.floor(ch1PitchAbs);
    var ch1PitchFrac = Math.round((ch1PitchAbs - ch1PitchInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1PitchSignNote,  ch1Pitch < 0 ? 1 : 0);
    midi.sendShortMsg(0x90 + channel, ch1PitchIntNote,   ch1PitchInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1PitchFracNote,  ch1PitchFrac & 0x7F);

    // Query [Channel2]pitch
    var ch2Pitch     = engine.getValue('[Channel2]', 'pitch');
    var ch2PitchAbs  = Math.abs(ch2Pitch);
    var ch2PitchInt  = Math.floor(ch2PitchAbs);
    var ch2PitchFrac = Math.round((ch2PitchAbs - ch2PitchInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2PitchSignNote,  ch2Pitch < 0 ? 1 : 0);
    midi.sendShortMsg(0x90 + channel, ch2PitchIntNote,   ch2PitchInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2PitchFracNote,  ch2PitchFrac & 0x7F);

    // Query [Channel1]sync_leader (0=off, 1=on)
    var ch1SyncLeader = engine.getValue('[Channel1]', 'sync_leader') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1SyncLeaderNote, ch1SyncLeader);

    // Query [Channel2]sync_leader (0=off, 1=on)
    var ch2SyncLeader = engine.getValue('[Channel2]', 'sync_leader') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2SyncLeaderNote, ch2SyncLeader);

    // Query [InternalClock]sync_leader (0=off, 1=on)
    var intClkSyncLeader = engine.getValue('[InternalClock]', 'sync_leader') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, intClkSyncLeaderNote, intClkSyncLeader);

    // Query [Channel1]track_loaded (0=empty, 1=loaded)
    var ch1TrackLoaded = engine.getValue('[Channel1]', 'track_loaded') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1TrackLoadedNote, ch1TrackLoaded);

    // Query [Channel2]track_loaded (0=empty, 1=loaded)
    var ch2TrackLoaded = engine.getValue('[Channel2]', 'track_loaded') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2TrackLoadedNote, ch2TrackLoaded);

    // Query [Channel1]quantize (0=off, 1=on)
    var ch1Quantize = engine.getValue('[Channel1]', 'quantize') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch1QuantizeNote, ch1Quantize);

    // Query [Channel2]quantize (0=off, 1=on)
    var ch2Quantize = engine.getValue('[Channel2]', 'quantize') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, ch2QuantizeNote, ch2Quantize);

    // Query [Master]crossfader (-1.0 to +1.0, sign + integer + fractional hundredths)
    var crossfader     = engine.getValue('[Master]', 'crossfader');
    var crossfaderAbs  = Math.abs(crossfader);
    var crossfaderInt  = Math.floor(crossfaderAbs);
    var crossfaderFrac = Math.round((crossfaderAbs - crossfaderInt) * 100);
    midi.sendShortMsg(0x90 + channel, crossfaderSignNote,  crossfader < 0 ? 1 : 0);
    midi.sendShortMsg(0x90 + channel, crossfaderIntNote,   crossfaderInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, crossfaderFracNote,  crossfaderFrac & 0x7F);

    // Query [Master]talkoverDucking (0=disabled, 1=auto, 2=manual)
    var talkoverDucking = engine.getValue('[Master]', 'talkoverDucking');
    midi.sendShortMsg(0x90 + channel, talkoverDuckingNote, talkoverDucking & 0x7F);

    // Query [Master]duckStrength (0.0 to 1.0)
    var duckStrength     = engine.getValue('[Master]', 'duckStrength');
    var duckStrengthInt  = Math.floor(duckStrength);
    var duckStrengthFrac = Math.round((duckStrength - duckStrengthInt) * 100);
    midi.sendShortMsg(0x90 + channel, duckStrengthIntNote,  duckStrengthInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, duckStrengthFracNote, duckStrengthFrac & 0x7F);

    // Query [Microphone]talkover (0=off, 1=on)
    var micTalkover = engine.getValue('[Microphone]', 'talkover') ? 1 : 0;
    midi.sendShortMsg(0x90 + channel, micTalkoverNote, micTalkover);

    // Query [Channel1]volume (0.0 to 1.0)
    var ch1Volume     = engine.getValue('[Channel1]', 'volume');
    var ch1VolumeInt  = Math.floor(ch1Volume);
    var ch1VolumeFrac = Math.round((ch1Volume - ch1VolumeInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1VolumeIntNote,  ch1VolumeInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1VolumeFracNote, ch1VolumeFrac & 0x7F);

    // Query [Channel2]volume (0.0 to 1.0)
    var ch2Volume     = engine.getValue('[Channel2]', 'volume');
    var ch2VolumeInt  = Math.floor(ch2Volume);
    var ch2VolumeFrac = Math.round((ch2Volume - ch2VolumeInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2VolumeIntNote,  ch2VolumeInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2VolumeFracNote, ch2VolumeFrac & 0x7F);

    // Query [Channel1]pregain (0.0 to 3.981071705534973)
    var ch1Pregain     = engine.getValue('[Channel1]', 'pregain');
    var ch1PregainInt  = Math.floor(ch1Pregain);
    var ch1PregainFrac = Math.round((ch1Pregain - ch1PregainInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch1PregainIntNote,  ch1PregainInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch1PregainFracNote, ch1PregainFrac & 0x7F);

    // Query [Channel2]pregain (0.0 to 3.981071705534973)
    var ch2Pregain     = engine.getValue('[Channel2]', 'pregain');
    var ch2PregainInt  = Math.floor(ch2Pregain);
    var ch2PregainFrac = Math.round((ch2Pregain - ch2PregainInt) * 100);
    midi.sendShortMsg(0x90 + channel, ch2PregainIntNote,  ch2PregainInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, ch2PregainFracNote, ch2PregainFrac & 0x7F);

    // Query [Master]gain (0.0 to 5.011872336272724)
    var masterGain     = engine.getValue('[Master]', 'gain');
    var masterGainInt  = Math.floor(masterGain);
    var masterGainFrac = Math.round((masterGain - masterGainInt) * 100);
    midi.sendShortMsg(0x90 + channel, masterGainIntNote,  masterGainInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, masterGainFracNote, masterGainFrac & 0x7F);

    // Query [InternalClock]bpm (integer high + integer low + fractional hundredths)
    var intClkBpm     = engine.getValue('[InternalClock]', 'bpm');
    var intClkBpmInt  = Math.floor(intClkBpm);
    var intClkBpmFrac = Math.round((intClkBpm - intClkBpmInt) * 100);
    midi.sendShortMsg(0x90 + channel, intClkBpmHighNote, (intClkBpmInt >> 7) & 0x7F);
    midi.sendShortMsg(0x90 + channel, intClkBpmLowNote,  intClkBpmInt & 0x7F);
    midi.sendShortMsg(0x90 + channel, intClkBpmFracNote, intClkBpmFrac & 0x7F);

    // Send frame end
    midi.sendShortMsg(0x90 + channel, frameEndNote, frameCounter);
    frameCounter = (frameCounter + 1) & 0x7F;
};

// ── Lifecycle ─────────────────────────────────────────────────────────────────
mabc._heartbeatTimer = null;

// ── Inbound float control buffer ──────────────────────────────────────────────
// Stores partial high/sign bytes until the final (frac) byte arrives and
// triggers engine.setValue().
var _ctrlBuf = {};

// ── Inbound control handler ───────────────────────────────────────────────────
// Called by Mixxx for any MIDI message bound with <script-binding/> in the XML.
// Uses engine.setValue() directly so boolean controls set the exact value
// regardless of whether they are toggle-mode ControlPushButtons.
mabc.incomingMidi = function(channel, control, value, status, group) {
    if (status === 0x91) {  // control channel
        if (control === 0x19) {          // CTRL_AUTO_DJ_EN
            engine.setValue('[AutoDJ]', 'enabled', value > 0 ? 1 : 0);
        } else if (control === 0x1A) {   // CTRL_AUTO_DJ_FADE_NOW (momentary)
            engine.setValue('[AutoDJ]', 'fade_now', 1);
            engine.setValue('[AutoDJ]', 'fade_now', 0);
        } else if (control === 0x1B) {   // CTRL_AUTO_DJ_SHUFFLE (momentary)
            engine.setValue('[AutoDJ]', 'shuffle_playlist', 1);
            engine.setValue('[AutoDJ]', 'shuffle_playlist', 0);
        } else if (control === 0x1C) {   // CTRL_AUTO_DJ_ADD_RANDOM (momentary)
            engine.setValue('[AutoDJ]', 'add_random_track', 1);
            engine.setValue('[AutoDJ]', 'add_random_track', 0);
        } else if (control === 0x1D) {   // CTRL_SHOUTCAST_EN
            engine.setValue('[Shoutcast]', 'enabled', value > 0 ? 1 : 0);
        } else if (control === 0x1E) {   // CTRL_CH1_SYNC_EN
            engine.setValue('[Channel1]', 'sync_enabled', value > 0 ? 1 : 0);
        } else if (control === 0x1F) {   // CTRL_CH2_SYNC_EN
            engine.setValue('[Channel2]', 'sync_enabled', value > 0 ? 1 : 0);
        } else if (control === 0x20) {   // CTRL_CH1_SYNC_LEADER
            engine.setValue('[Channel1]', 'sync_leader', value > 0 ? 1 : 0);
        } else if (control === 0x21) {   // CTRL_CH2_SYNC_LEADER
            engine.setValue('[Channel2]', 'sync_leader', value > 0 ? 1 : 0);
        } else if (control === 0x22) {   // CTRL_CH1_PLAY
            engine.setValue('[Channel1]', 'play', value > 0 ? 1 : 0);
        } else if (control === 0x23) {   // CTRL_CH2_PLAY
            engine.setValue('[Channel2]', 'play', value > 0 ? 1 : 0);
        } else if (control === 0x24) {   // CTRL_CH1_EJECT (momentary)
            engine.setValue('[Channel1]', 'eject', 1);
            engine.setValue('[Channel1]', 'eject', 0);
        } else if (control === 0x25) {   // CTRL_CH2_EJECT (momentary)
            engine.setValue('[Channel2]', 'eject', 1);
            engine.setValue('[Channel2]', 'eject', 0);
        } else if (control === 0x26) {   // CTRL_INTCLK_SYNC_LEADER
            engine.setValue('[InternalClock]', 'sync_leader', value > 0 ? 1 : 0);

        // ── Float controls: Channel BPM (high + low + frac) ──────────────────
        } else if (control === 0x27) {
            _ctrlBuf.ch1BpmHigh = value;
        } else if (control === 0x28) {
            _ctrlBuf.ch1BpmLow  = value;
        } else if (control === 0x29) {
            var ch1BpmVal = ((_ctrlBuf.ch1BpmHigh || 0) << 7 | (_ctrlBuf.ch1BpmLow || 0)) + value / 100;
            engine.setValue('[Channel1]', 'bpm', ch1BpmVal);
        } else if (control === 0x2A) {
            _ctrlBuf.ch2BpmHigh = value;
        } else if (control === 0x2B) {
            _ctrlBuf.ch2BpmLow  = value;
        } else if (control === 0x2C) {
            var ch2BpmVal = ((_ctrlBuf.ch2BpmHigh || 0) << 7 | (_ctrlBuf.ch2BpmLow || 0)) + value / 100;
            engine.setValue('[Channel2]', 'bpm', ch2BpmVal);

        // ── Float controls: Channel Rate% (sign + int + frac) ────────────────
        // Rate% = rate * rate_dir * rateRange * 100 (matches heartbeat status)
        // To set: rate = pct / (rate_dir * rateRange * 100)
        } else if (control === 0x2D) {
            _ctrlBuf.ch1RateSign = value;
        } else if (control === 0x2E) {
            _ctrlBuf.ch1RateInt  = value;
        } else if (control === 0x2F) {
            var ch1RatePct  = ((_ctrlBuf.ch1RateInt || 0) + value / 100) * (_ctrlBuf.ch1RateSign ? -1 : 1);
            var ch1RateRange = engine.getValue('[Channel1]', 'rateRange');
            var ch1RateDir   = engine.getValue('[Channel1]', 'rate_dir');
            engine.setValue('[Channel1]', 'rate', ch1RatePct / (ch1RateDir * ch1RateRange * 100));
        } else if (control === 0x30) {
            _ctrlBuf.ch2RateSign = value;
        } else if (control === 0x31) {
            _ctrlBuf.ch2RateInt  = value;
        } else if (control === 0x32) {
            var ch2RatePct  = ((_ctrlBuf.ch2RateInt || 0) + value / 100) * (_ctrlBuf.ch2RateSign ? -1 : 1);
            var ch2RateRange = engine.getValue('[Channel2]', 'rateRange');
            var ch2RateDir   = engine.getValue('[Channel2]', 'rate_dir');
            engine.setValue('[Channel2]', 'rate', ch2RatePct / (ch2RateDir * ch2RateRange * 100));

        // ── Float controls: Channel Pitch in semitones (sign + int + frac) ───
        } else if (control === 0x33) {
            _ctrlBuf.ch1PitchSign = value;
        } else if (control === 0x34) {
            _ctrlBuf.ch1PitchInt  = value;
        } else if (control === 0x35) {
            var ch1PitchVal = ((_ctrlBuf.ch1PitchInt || 0) + value / 100) * (_ctrlBuf.ch1PitchSign ? -1 : 1);
            engine.setValue('[Channel1]', 'pitch', ch1PitchVal);
        } else if (control === 0x36) {
            _ctrlBuf.ch2PitchSign = value;
        } else if (control === 0x37) {
            _ctrlBuf.ch2PitchInt  = value;
        } else if (control === 0x38) {
            var ch2PitchVal = ((_ctrlBuf.ch2PitchInt || 0) + value / 100) * (_ctrlBuf.ch2PitchSign ? -1 : 1);
            engine.setValue('[Channel2]', 'pitch', ch2PitchVal);

        // ── Float controls: InternalClock BPM (high + low + frac) ────────────
        } else if (control === 0x39) {
            _ctrlBuf.intClkBpmHigh = value;
        } else if (control === 0x3A) {
            _ctrlBuf.intClkBpmLow  = value;
        } else if (control === 0x3B) {
            var intBpmVal = ((_ctrlBuf.intClkBpmHigh || 0) << 7 | (_ctrlBuf.intClkBpmLow || 0)) + value / 100;
            engine.setValue('[InternalClock]', 'bpm', intBpmVal);
        } else if (control === 0x3C) {   // CTRL_CH1_QUANTIZE
            engine.setValue('[Channel1]', 'quantize', value > 0 ? 1 : 0);
        } else if (control === 0x3D) {   // CTRL_CH2_QUANTIZE
            engine.setValue('[Channel2]', 'quantize', value > 0 ? 1 : 0);

        // ── Float control: Master Crossfader (sign + int + frac) ─────────────
        } else if (control === 0x3E) {   // CTRL_CROSSFADER_SIGN
            _ctrlBuf.crossfaderSign = value;
        } else if (control === 0x3F) {   // CTRL_CROSSFADER_INT
            _ctrlBuf.crossfaderInt  = value;
        } else if (control === 0x40) {   // CTRL_CROSSFADER_FRAC (triggers apply)
            var cfVal = ((_ctrlBuf.crossfaderInt || 0) + value / 100) * (_ctrlBuf.crossfaderSign ? -1 : 1);
            engine.setValue('[Master]', 'crossfader', cfVal);

        // ── Talkover ducking mode (single byte 0/1/2) ─────────────────────────
        } else if (control === 0x41) {   // CTRL_TALKOVER_DUCKING
            engine.setValue('[Master]', 'talkoverDucking', value & 3);

        // ── Float control: Master duckStrength (int + frac) ───────────────────
        } else if (control === 0x42) {   // CTRL_DUCK_STRENGTH_INT
            _ctrlBuf.duckStrengthInt = value;
        } else if (control === 0x43) {   // CTRL_DUCK_STRENGTH_FRAC (triggers apply)
            var dsVal = (_ctrlBuf.duckStrengthInt || 0) + value / 100;
            engine.setValue('[Master]', 'duckStrength', dsVal);

        // ── Microphone talkover (single byte 0/1) ─────────────────────────────
        } else if (control === 0x44) {   // CTRL_MIC_TALKOVER
            engine.setValue('[Microphone]', 'talkover', value > 0 ? 1 : 0);

        // ── Float controls: Channel volumes (int + frac) ──────────────────────
        } else if (control === 0x45) {   // CTRL_CH1_VOLUME_INT
            _ctrlBuf.ch1VolumeInt = value;
        } else if (control === 0x46) {   // CTRL_CH1_VOLUME_FRAC (triggers apply)
            var ch1VolVal = (_ctrlBuf.ch1VolumeInt || 0) + value / 100;
            engine.setValue('[Channel1]', 'volume', ch1VolVal);
        } else if (control === 0x47) {   // CTRL_CH2_VOLUME_INT
            _ctrlBuf.ch2VolumeInt = value;
        } else if (control === 0x48) {   // CTRL_CH2_VOLUME_FRAC (triggers apply)
            var ch2VolVal = (_ctrlBuf.ch2VolumeInt || 0) + value / 100;
            engine.setValue('[Channel2]', 'volume', ch2VolVal);

        // ── Float controls: Channel pregain (int + frac, range 0.0–3.981) ──────
        } else if (control === 0x49) {   // CTRL_CH1_PREGAIN_INT
            _ctrlBuf.ch1PregainInt = value;
        } else if (control === 0x4A) {   // CTRL_CH1_PREGAIN_FRAC (triggers apply)
            var ch1PregainVal = (_ctrlBuf.ch1PregainInt || 0) + value / 100;
            engine.setValue('[Channel1]', 'pregain', ch1PregainVal);
        } else if (control === 0x4B) {   // CTRL_CH2_PREGAIN_INT
            _ctrlBuf.ch2PregainInt = value;
        } else if (control === 0x4C) {   // CTRL_CH2_PREGAIN_FRAC (triggers apply)
            var ch2PregainVal = (_ctrlBuf.ch2PregainInt || 0) + value / 100;
            engine.setValue('[Channel2]', 'pregain', ch2PregainVal);

        // ── Float control: Master gain (int + frac, range 0.0–5.012) ─────────
        } else if (control === 0x4D) {   // CTRL_MASTER_GAIN_INT
            _ctrlBuf.masterGainInt = value;
        } else if (control === 0x4E) {   // CTRL_MASTER_GAIN_FRAC (triggers apply)
            var masterGainVal = (_ctrlBuf.masterGainInt || 0) + value / 100;
            engine.setValue('[Master]', 'gain', masterGainVal);
        }
    }
};
mabc.init = function(id) {
    mabc._heartbeatTimer = engine.beginTimer(heartbeatInterval, mabc._sendHeartbeat, false);
};

mabc.shutdown = function() {
    if (mabc._heartbeatTimer !== null) {
        engine.stopTimer(mabc._heartbeatTimer);
        mabc._heartbeatTimer = null;
    }
};
