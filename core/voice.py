import os
import queue
import threading
import pyttsx3
import wave
import tempfile
import pyaudio
import numpy as np
from core.state_manager import state_manager

TTS_QUEUE = queue.Queue()
TTS_THREAD = None
TTS_ENGINE = None

def init_tts():
    global TTS_ENGINE, TTS_THREAD
    
    # Initialize pyttsx3
    TTS_ENGINE = pyttsx3.init()
    
    # Find and set female voice
    voices = TTS_ENGINE.getProperty('voices')
    for voice in voices:
        # Zira is the default female voice on Windows
        if "Zira" in voice.name or "female" in voice.name.lower():
            TTS_ENGINE.setProperty('voice', voice.id)
            break
            
    # Start TTS worker thread
    TTS_THREAD = threading.Thread(target=_tts_worker, daemon=True)
    TTS_THREAD.start()

def _tts_worker():
    while True:
        text = TTS_QUEUE.get()
        if text is None:
            break
        try:
            TTS_ENGINE.say(text)
            TTS_ENGINE.runAndWait()
        except Exception as e:
            print(f"[TTS Error] {e}")
        TTS_QUEUE.task_done()

def speak(text):
    if text.strip():
        TTS_QUEUE.put(text)


# --- FASTER-WHISPER STT LOGIC ---

WHISPER_MODEL = None

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        # Use CPU with int8 to ensure it runs on any system without requiring CUDA
        WHISPER_MODEL = WhisperModel("base.en", device="cpu", compute_type="int8")
    return WHISPER_MODEL

def listen_offline():
    model = get_whisper_model()
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    SILENCE_THRESHOLD = 500  # RMS threshold for silence
    SILENCE_DURATION = 1.5   # Seconds of silence before stopping
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    state_manager.set_state("listening")
    print("\nARIA > Listening... (speak now)")
    
    frames = []
    silent_chunks = 0
    started_speaking = False
    
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            # Calculate RMS audio volume
            audio_data = np.frombuffer(data, dtype=np.int16)
            # Avoid division by zero warnings if array is empty
            if len(audio_data) > 0:
                rms = np.sqrt(np.mean(np.square(audio_data.astype(np.float32))))
            else:
                rms = 0
            
            if rms > SILENCE_THRESHOLD:
                started_speaking = True
                silent_chunks = 0
            elif started_speaking:
                silent_chunks += 1
                
            # Stop recording if silent for SILENCE_DURATION seconds
            if started_speaking and silent_chunks > int((RATE / CHUNK) * SILENCE_DURATION):
                break
                
            # Safety timeout (e.g. max 30 seconds of recording if continuous speech)
            if len(frames) > int((RATE / CHUNK) * 30):
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    if not started_speaking:
        return ""
        
    state_manager.set_state("thinking")
    print("\rARIA > Transcribing...  ", end="", flush=True)
    
    # Save to temp WAV file
    temp_wav = os.path.join(tempfile.gettempdir(), "aria_stt_temp.wav")
    try:
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            
        # Transcribe
        segments, info = model.transcribe(temp_wav, beam_size=5)
        text = " ".join([segment.text.strip() for segment in segments])
        
        return text.strip()
    except Exception as e:
        print(f"\n[STT Error] {e}")
        return ""
    finally:
        try:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
        except:
            pass
