"""
core/tts_engine.py
------------------
Two-thread pre-buffered TTS pipeline for ARIA.

Architecture
------------

  enqueue_text()
       │
       ▼
  TEXT_QUEUE  ──── Thread 1: _tts_generator ────►  AUDIO_QUEUE
                   (Piper synthesis,                     │
                    runs while prev chunk plays)         │
                                                 Thread 2: _audio_player
                                                 (pygame playback +
                                                  word-sync printing)

Pre-buffering guarantee
-----------------------
Because synthesis (Thread 1) and playback (Thread 2) run concurrently,
chunk N+1 is fully synthesised on disk *while* chunk N is playing.
When the player finishes chunk N it immediately finds chunk N+1 ready
in AUDIO_QUEUE — zero inter-chunk gap.

Hybrid playback modes (is_first flag)
--------------------------------------
First chunk  →  text printed instantly before audio, no per-word delay.
                Gives the user immediate visual + audio feedback.
Later chunks →  words printed one-by-one timed to audio duration.
                Maintains tight A/V synchronisation.

Interrupt safety
-----------------
INTERRUPT_EVENT is checked at the top of every loop iteration in both
workers.  stop_speaking() drains both queues atomically and deletes
any pending temp WAV files before clearing the event flag.
"""

import os
import json
import queue
import threading
import tempfile
import time
import uuid
import subprocess
import urllib.request
import zipfile
import warnings

from core.state_manager import state_manager
from core.event_manager import events

warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# ── Module-level queues and control primitives ─────────────────────────────────

# TEXT_QUEUE carries (text, print_text, is_first) tuples from callers → generator
TEXT_QUEUE: queue.Queue = queue.Queue()

# AUDIO_QUEUE carries (wav_path, text, print_text, is_first) tuples from
# generator → player.  The generator fills this while the player is busy so
# the next chunk is always ready before it is needed.
AUDIO_QUEUE: queue.Queue = queue.Queue()

# Set to interrupt both workers immediately; cleared by stop_speaking()
INTERRUPT_EVENT = threading.Event()

TTS_THREAD = None
PLAYER_THREAD = None

# Persistent Piper process — started once, reused for every chunk.
# Access is serialised through _PIPER_LOCK (generator thread is the only writer).
_PIPER_PROC: subprocess.Popen | None = None
_PIPER_LOCK = threading.Lock()

# ── Piper configuration ────────────────────────────────────────────────────────

pygame.mixer.init()

PIPER_DIR    = os.path.join(os.path.dirname(__file__), "piper_tts")
PIPER_EXE    = os.path.join(PIPER_DIR, "piper", "piper.exe")
MODEL_DIR    = os.path.join(PIPER_DIR, "models")
MODEL_ONNX   = os.path.join(MODEL_DIR, "en_US-lessac-medium.onnx")
MODEL_JSON   = os.path.join(MODEL_DIR, "en_US-lessac-medium.onnx.json")

PIPER_RELEASE_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
VOICE_ONNX_URL    = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
VOICE_JSON_URL    = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Piper voice parameters — slow/calm/flirty character
_PIPER_LENGTH_SCALE    = 1.35   # >1.0 = slower speech
_PIPER_NOISE_SCALE     = 0.8    # 0–1; higher = breathier/huskier
_PIPER_SENTENCE_SIL    = 0.4    # seconds of silence after each sentence


# ── Setup ──────────────────────────────────────────────────────────────────────

def ensure_piper_setup() -> None:
    """Download Piper binary and voice model on first run (one-time only)."""
    if not os.path.exists(PIPER_EXE):
        print("\nARIA > Downloading Piper TTS Engine (this only happens once)...")
        os.makedirs(PIPER_DIR, exist_ok=True)
        zip_path = os.path.join(PIPER_DIR, "piper.zip")
        urllib.request.urlretrieve(PIPER_RELEASE_URL, zip_path)
        print("ARIA > Extracting Piper...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(path=PIPER_DIR)
        os.remove(zip_path)

    if not os.path.exists(MODEL_ONNX):
        print("ARIA > Downloading high-quality voice model (~50 MB)...")
        os.makedirs(MODEL_DIR, exist_ok=True)
        urllib.request.urlretrieve(VOICE_ONNX_URL, MODEL_ONNX)
        urllib.request.urlretrieve(VOICE_JSON_URL, MODEL_JSON)
        print("ARIA > Voice model ready!")


def _get_piper() -> subprocess.Popen:
    """Return the shared persistent Piper process, restarting it if it has died.

    Must be called with _PIPER_LOCK held.
    """
    global _PIPER_PROC
    if _PIPER_PROC is None or _PIPER_PROC.poll() is not None:
        # Process does not exist or has exited — (re)start it.
        # --json-input: Piper reads one JSON line per synthesis request:
        #   {"text": "...", "output_file": "/path/to/out.wav"}
        # After finishing each request it writes a JSON result to stdout:
        #   {"output_file": "...", "audio_seconds": X.X, ...}
        # We readline() stdout as a zero-sleep completion signal.
        _PIPER_PROC = subprocess.Popen(
            [
                PIPER_EXE,
                "--model",            MODEL_ONNX,
                "--json-input",
                "--length_scale",     str(_PIPER_LENGTH_SCALE),
                "--noise_scale",      str(_PIPER_NOISE_SCALE),
                "--sentence_silence", str(_PIPER_SENTENCE_SIL),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    return _PIPER_PROC


def _synthesise_chunk(text: str, out_path: str) -> bool:
    """Send *text* to the persistent Piper process and wait for synthesis.

    Parameters
    ----------
    text     : The sentence to synthesise.
    out_path : Absolute path where Piper should write the WAV file.

    Returns
    -------
    bool
        True only when ``out_path`` exists, is non-empty, AND its size has
        stopped growing (i.e. Piper has finished writing it).

    Notes
    -----
    On Windows, Piper may signal stdout *before* the OS flushes the output
    file to disk.  A retry/stabilisation loop (max ~500 ms) absorbs this
    race.  If the file never appears the function returns False so the
    generator discards the chunk gracefully.

    If Piper dies mid-request ``poll()`` will be non-None; ``_get_piper()``
    restarts it transparently on the next call.
    """
    global _PIPER_PROC
    with _PIPER_LOCK:
        try:
            proc = _get_piper()
            payload = json.dumps({"text": text, "output_file": out_path}) + "\n"
            proc.stdin.write(payload.encode("utf-8"))
            proc.stdin.flush()
            # readline() blocks until Piper writes its JSON result line.
            proc.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            print(f"[Piper I/O Error] {exc} — process will restart on next chunk")
            _PIPER_PROC = None
            return False

    # ── File-stabilisation loop ────────────────────────────────────────────
    # Piper may signal stdout before the OS fully flushes the output file
    # (common on Windows).  Poll until the file exists AND its size stops
    # growing, with a hard cap of 500 ms.
    deadline = time.monotonic() + 0.5
    prev_size = -1
    while time.monotonic() < deadline:
        if os.path.isfile(out_path):
            cur_size = os.path.getsize(out_path)
            if cur_size > 0 and cur_size == prev_size:
                return True          # size stable → write complete
            prev_size = cur_size
        time.sleep(0.01)

    # Final check after timeout
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 0


# ── Public API ─────────────────────────────────────────────────────────────────

def start_tts_engine() -> None:
    """Spawn the synthesis and playback worker threads (call once at startup)."""
    global TTS_THREAD, PLAYER_THREAD

    TTS_THREAD = threading.Thread(target=_tts_generator, name="aria-tts-gen", daemon=True)
    TTS_THREAD.start()

    PLAYER_THREAD = threading.Thread(target=_audio_player, name="aria-tts-play", daemon=True)
    PLAYER_THREAD.start()


def enqueue_text(text: str, print_text: bool = False, is_first: bool = False) -> None:
    """Push a text chunk onto the synthesis queue.

    If an interrupt was previously issued, it is cleared here — this is the
    correct moment because we know a new TTS cycle is starting and both worker
    threads have had ample time to react to the flag since stop_speaking().

    Args:
        text:       The sentence/chunk to synthesise and speak.
        print_text: If True the text is printed to the terminal in sync with audio.
        is_first:   If True this is the very first chunk of a new response —
                    text is printed instantly (before audio) to eliminate latency.
    """
    from core.config_manager import config
    if not config.get("tts_enabled", True):
        if print_text and text:
            print(text + " ", end="", flush=True)
        return

    if text and text.strip():
        # Clear any stale interrupt so the workers process this new item
        reset_interrupt()
        TEXT_QUEUE.put((text.strip(), print_text, is_first))


def speak_chunk(text: str) -> None:
    """Compatibility shim for callers that pre-date the hybrid system."""
    enqueue_text(text)


def is_speaking() -> bool:
    """Return True while any text or audio is still pending or playing."""
    channel = pygame.mixer.Channel(0)
    return (
        channel.get_busy()
        or TEXT_QUEUE.unfinished_tasks > 0
        or AUDIO_QUEUE.unfinished_tasks > 0
    )


def stop_speaking() -> None:
    """Interrupt all speech immediately and clear pending queues.

    Deliberately does NOT clear INTERRUPT_EVENT.  Both worker threads
    (synthesis + playback) check the flag at the top of every iteration;
    clearing it here — even after a short sleep — risks a race where a
    worker reads the flag as clear before it has had a chance to react.

    INTERRUPT_EVENT is cleared by reset_interrupt(), which is called
    automatically from enqueue_text() at the start of the next TTS cycle.
    It can also be called directly by the CLI after it has drained user
    input and is ready to accept a new response.

    Safe to call from any thread at any time.
    """
    # 1. Signal both workers to abort immediately
    INTERRUPT_EVENT.set()
    events.emit("interrupt")

    # 2. Stop pygame playback without waiting
    channel = pygame.mixer.Channel(0)
    channel.stop()

    # 3. Drain TEXT_QUEUE — items are (text, print_text, is_first) tuples
    while True:
        try:
            TEXT_QUEUE.get_nowait()
            TEXT_QUEUE.task_done()
        except queue.Empty:
            break

    # 4. Drain AUDIO_QUEUE and delete any pre-buffered WAV files
    while True:
        try:
            item = AUDIO_QUEUE.get_nowait()
            if isinstance(item, tuple) and len(item) >= 1:
                _safe_delete(item[0])
            AUDIO_QUEUE.task_done()
        except queue.Empty:
            break

    # 5. Transition to idle — INTERRUPT_EVENT stays SET until reset_interrupt()
    state_manager.set_state("idle")


def reset_interrupt() -> None:
    """Clear the interrupt flag so the TTS pipeline can accept new input.

    Call this when the system is genuinely ready for the next TTS cycle,
    i.e. *after* the user has finished providing new input and ARIA is
    about to start speaking again.  Calling it too early reintroduces the
    race condition that this design is meant to prevent.
    """
    INTERRUPT_EVENT.clear()


# ── Thread 1: Synthesis (Piper) ────────────────────────────────────────────────

def _tts_generator() -> None:
    """Producer thread: converts text chunks → WAV files via Piper.

    Runs continuously as a daemon.  Because this thread operates independently
    of the player thread, it synthesises chunk N+1 while chunk N is playing —
    this is the pre-buffer mechanism that eliminates inter-chunk gaps.
    """
    ensure_piper_setup()

    while True:
        try:
            # ── Fetch next text item ─────────────────────────────────────────
            try:
                item = TEXT_QUEUE.get(timeout=0.1)
            except queue.Empty:
                continue

            # Unpack — support 3-tuple (current) and legacy 2-tuple / bare string
            if isinstance(item, tuple):
                if len(item) == 3:
                    text, print_text, is_first = item
                else:
                    text, print_text = item[0], item[1]
                    is_first = False
            else:
                text, print_text, is_first = str(item), False, False

            # Sentinel value used to gracefully shut down the thread
            if text is None:
                TEXT_QUEUE.task_done()
                break

            try:
                # ── Interrupt check ──────────────────────────────────────────────
                if INTERRUPT_EVENT.is_set():
                    continue

                # ── Synthesise with persistent Piper process ─────────────────────
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"aria_tts_{uuid.uuid4().hex}.wav"
                )

                synthesised = False
                try:
                    synthesised = _synthesise_chunk(text, temp_path)
                except Exception as exc:
                    print(f"[Piper Error] {exc}")

                # ── Forward to player (or discard if interrupted) ─────────────────
                if synthesised and not INTERRUPT_EVENT.is_set():
                    AUDIO_QUEUE.put((temp_path, text, print_text, is_first))
                else:
                    _safe_delete(temp_path)
            finally:
                TEXT_QUEUE.task_done()

        except Exception as exc:
            print(f"[TTS Generator Error] {exc}")


# ── Thread 2: Playback (pygame) ────────────────────────────────────────────────

def _audio_player() -> None:
    """Consumer thread: plays pre-buffered WAV files and synchronises text output.

    Hybrid playback strategy
    ------------------------
    is_first = True  (instant-start path)
        • Print the entire chunk text immediately BEFORE audio starts.
          The user sees words the instant speech begins — feels instantaneous.
        • No per-word delay loop.

    is_first = False  (sync path)
        • Wait for the channel to become free (gap-free chaining).
        • Start audio.
        • Print words one-by-one timed proportionally to audio duration.
          Text stays tightly in-sync with the voice.

    Because the generator thread pre-fills AUDIO_QUEUE while this thread is
    busy, AUDIO_QUEUE.get() at the end of a chunk almost never blocks —
    chunk N+1 is ready before chunk N finishes.
    """
    while True:
        try:
            # Block until an audio item is available
            item = AUDIO_QUEUE.get()

            # Sentinel: graceful shutdown
            if item is None:
                AUDIO_QUEUE.task_done()
                break

            try:
                # ── Unpack ───────────────────────────────────────────────────────
                if isinstance(item, tuple) and len(item) == 4:
                    wav_path, text, print_text, is_first = item
                elif isinstance(item, tuple) and len(item) == 3:
                    wav_path, text, print_text = item
                    is_first = False
                else:
                    # Malformed item — discard safely
                    continue

                # ── Interrupt check (item may have been queued before interrupt) ──
                if INTERRUPT_EVENT.is_set():
                    _safe_delete(wav_path)
                    continue

                # ── Load audio into pygame memory ─────────────────────────────────
                if not os.path.isfile(wav_path):
                    _safe_delete(wav_path)
                    continue

                try:
                    sound = pygame.mixer.Sound(wav_path)
                except Exception as exc:
                    print(f"[Audio Load Error] {exc}")
                    _safe_delete(wav_path)
                    continue
                finally:
                    # Always delete the temp file — Sound already owns the data
                    _safe_delete(wav_path)

                channel = pygame.mixer.Channel(0)

                # ── FIRST CHUNK: instant-start path ──────────────────────────────
                if is_first:
                    # Print text NOW so the user sees it as audio begins
                    if print_text and text:
                        print(text + " ", end="", flush=True)

                    # Wait only for any previous lingering audio (e.g. greeting)
                    _wait_channel_free(channel, poll=0.005)

                    if not INTERRUPT_EVENT.is_set():
                        state_manager.set_state("speaking")
                        events.emit("tts_start")
                        channel.play(sound)

                # ── SUBSEQUENT CHUNKS: gap-free synced path ───────────────────────
                else:
                    # Wait for the previous chunk to finish — this is near-instant
                    _wait_channel_free(channel, poll=0.005)

                    if not INTERRUPT_EVENT.is_set():
                        state_manager.set_state("speaking")
                        events.emit("tts_start")
                        channel.play(sound)

                        if print_text and text:
                            _print_words_synced(text, sound.get_length())

                # True end-of-speech
                if (
                    not INTERRUPT_EVENT.is_set()
                    and TEXT_QUEUE.empty()
                    and AUDIO_QUEUE.empty()
                ):
                    _wait_channel_free(channel, poll=0.005)
                    if not INTERRUPT_EVENT.is_set():
                        state_manager.set_state("idle")
                        events.emit("tts_end")
                        
            finally:
                AUDIO_QUEUE.task_done()

        except Exception as exc:
            print(f"[Audio Player Error] {exc}")


# ── Private helpers ────────────────────────────────────────────────────────────

def _wait_channel_free(channel: pygame.mixer.Channel, poll: float = 0.01) -> None:
    """Spin-wait until *channel* is no longer busy or INTERRUPT_EVENT fires."""
    while channel.get_busy():
        if INTERRUPT_EVENT.is_set():
            channel.stop()
            return
        time.sleep(poll)


def _print_words_synced(text: str, duration: float) -> None:
    """Print words of *text* spread evenly across *duration* seconds.

    Runs 5 % faster than the true audio duration so text never lags behind
    the voice.  Stops immediately if INTERRUPT_EVENT is set.
    """
    words = text.split()
    if not words or duration <= 0:
        return
    delay = (duration / len(words)) * 0.95
    for word in words:
        if INTERRUPT_EVENT.is_set():
            break
        print(word + " ", end="", flush=True)
        time.sleep(delay)


def _safe_delete(path: str) -> None:
    """Delete *path* silently, ignoring errors (file may already be gone)."""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
