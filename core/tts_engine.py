import os
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
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

TEXT_QUEUE = queue.Queue()
AUDIO_QUEUE = queue.Queue()
INTERRUPT_EVENT = threading.Event()

TTS_THREAD = None
PLAYER_THREAD = None

# Initialize PyGame Mixer
pygame.mixer.init()

# --- PIPER CONFIGURATION ---
PIPER_DIR = os.path.join(os.path.dirname(__file__), "piper_tts")
PIPER_EXE = os.path.join(PIPER_DIR, "piper", "piper.exe")
MODEL_DIR = os.path.join(PIPER_DIR, "models")
MODEL_ONNX = os.path.join(MODEL_DIR, "en_US-lessac-medium.onnx")
MODEL_JSON = os.path.join(MODEL_DIR, "en_US-lessac-medium.onnx.json")

PIPER_RELEASE_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
VOICE_ONNX_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
VOICE_JSON_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

def ensure_piper_setup():
    if not os.path.exists(PIPER_EXE):
        print("\nARIA > Downloading Piper TTS Engine (this only happens once)...")
        os.makedirs(PIPER_DIR, exist_ok=True)
        zip_path = os.path.join(PIPER_DIR, "piper.zip")
        urllib.request.urlretrieve(PIPER_RELEASE_URL, zip_path)
        print("ARIA > Extracting Piper...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(path=PIPER_DIR)
        os.remove(zip_path)
    
    if not os.path.exists(MODEL_ONNX):
        print("ARIA > Downloading high-quality voice model (~50MB)...")
        os.makedirs(MODEL_DIR, exist_ok=True)
        urllib.request.urlretrieve(VOICE_ONNX_URL, MODEL_ONNX)
        urllib.request.urlretrieve(VOICE_JSON_URL, MODEL_JSON)
        print("ARIA > Voice model ready!")


def start_tts_engine():
    global TTS_THREAD, PLAYER_THREAD
    
    TTS_THREAD = threading.Thread(target=_tts_generator, daemon=True)
    TTS_THREAD.start()
    
    PLAYER_THREAD = threading.Thread(target=_audio_player, daemon=True)
    PLAYER_THREAD.start()

def stop_speaking():
    """Immediately stops playback and clears the queues."""
    INTERRUPT_EVENT.set()
    
    # Stop pygame playback
    channel = pygame.mixer.Channel(0)
    if channel.get_busy():
        channel.stop()
        
    # Drain queues
    while not TEXT_QUEUE.empty():
        try:
            TEXT_QUEUE.get_nowait()
            TEXT_QUEUE.task_done()
        except queue.Empty:
            break
            
    while not AUDIO_QUEUE.empty():
        try:
            audio_file = AUDIO_QUEUE.get_nowait()
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
            AUDIO_QUEUE.task_done()
        except queue.Empty:
            break
            
    # Reset interrupt event so new speech can start
    time.sleep(0.05) # Give workers a tiny window to notice the interrupt
    INTERRUPT_EVENT.clear()
    state_manager.set_state("idle")

def enqueue_text(text, print_text=False):
    if text and text.strip():
        TEXT_QUEUE.put((text.strip(), print_text))

def is_speaking():
    channel = pygame.mixer.Channel(0)
    return channel.get_busy() or TEXT_QUEUE.unfinished_tasks > 0 or AUDIO_QUEUE.unfinished_tasks > 0

# To be compatible with old speak_chunk
def speak_chunk(text):
    enqueue_text(text)


def _tts_generator():
    ensure_piper_setup()
    
    while True:
        try:
            # Check queue periodically to remain responsive to interrupts
            try:
                item = TEXT_QUEUE.get(timeout=0.1)
                if isinstance(item, tuple):
                    text, print_text = item
                else:
                    text = item
                    print_text = False
            except queue.Empty:
                continue

            if text is None:
                break
                
            if INTERRUPT_EVENT.is_set():
                TEXT_QUEUE.task_done()
                continue

            temp_path = os.path.join(tempfile.gettempdir(), f"aria_tts_{uuid.uuid4().hex}.wav")
            
            try:
                # Call piper via subprocess with fine-tuned parameters for a flirty, exhausted, lazy voice
                cmd = f'"{PIPER_EXE}" --model "{MODEL_ONNX}" --length_scale 1.35 --noise_scale 0.8 --sentence_silence 0.4 --output_file "{temp_path}"'
                # Pipe text to stdin
                process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                process.communicate(input=text.encode('utf-8'))
            except Exception as e:
                print(f"[Piper Error] {e}")
                TEXT_QUEUE.task_done()
                continue

            # Add to audio playback queue
            if not INTERRUPT_EVENT.is_set() and os.path.exists(temp_path):
                AUDIO_QUEUE.put((temp_path, text, print_text))
            else:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass

            TEXT_QUEUE.task_done()

        except Exception as e:
            print(f"[TTS Generator Error] {e}")


def _audio_player():
    while True:
        try:
            item = AUDIO_QUEUE.get()
            
            if item is None:
                break
                
            if isinstance(item, tuple) and len(item) == 3:
                audio_file, text, print_text = item
            else:
                audio_file = item
                text = ""
                print_text = False
                
            if INTERRUPT_EVENT.is_set():
                try:
                    os.remove(audio_file)
                except:
                    pass
                AUDIO_QUEUE.task_done()
                continue
                
            try:
                # Load directly into memory as a Sound object
                sound = pygame.mixer.Sound(audio_file)
                channel = pygame.mixer.Channel(0)
                
                # Wait until channel is completely free
                while channel.get_busy():
                    if INTERRUPT_EVENT.is_set():
                        break
                    time.sleep(0.01)
                    
                if INTERRUPT_EVENT.is_set():
                    channel.stop()
                    continue

                state_manager.set_state("speaking")
                channel.play(sound)

                if print_text and text:
                    duration = sound.get_length()
                    words = text.split()
                    if words:
                        # Slightly faster than actual duration to prevent text lagging behind audio
                        delay = (duration / len(words)) * 0.95 
                        for word in words:
                            if INTERRUPT_EVENT.is_set():
                                break
                            print(word + " ", end="", flush=True)
                            time.sleep(delay)
                    
            finally:
                # We can instantly delete the file because Sound loaded it to memory
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
                        
            AUDIO_QUEUE.task_done()
            
            if not is_speaking():
                state_manager.set_state("idle")

        except Exception as e:
            print(f"[Audio Player Error] {e}")
