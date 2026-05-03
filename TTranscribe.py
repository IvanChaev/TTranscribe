import os
import sys
import tempfile
import pyaudio
import wave
import threading
import tkinter as tk
from tkinter import filedialog
import pyperclip
from faster_whisper import WhisperModel
from tkinterdnd2 import DND_FILES, TkinterDnD

# ---------- Настройки ----------
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
# Временный WAV будет создаваться в системной папке Temp
WAVE_FILENAME = os.path.join(tempfile.gettempdir(), "transcriber_temp.wav")

# ---------- Глобальные переменные ----------
recording = False
frames = []
stop_event = threading.Event()
audio_thread = None
p = None
stream = None

# ---------- Управление записью ----------
def start_audio_stream():
    global p, stream
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)

def stop_audio_stream():
    global stream, p
    if stream is not None:
        stream.stop_stream()
        stream.close()
    if p is not None:
        p.terminate()

def record_loop():
    global frames
    while not stop_event.is_set():
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception as e:
            print(f"Ошибка записи: {e}")
            break

def save_wav(filename):
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# ---------- Расшифровка с микрофона ----------
def transcribe_mic():
    status_label.config(text="Идёт расшифровка (GPU)...")
    root.update_idletasks()
    try:
        model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
        segments, info = model.transcribe(WAVE_FILENAME, beam_size=10, language="ru")
        full_text = ""
        for seg in segments:
            full_text += seg.text + " "
        pyperclip.copy(full_text.strip())
        if os.path.exists(WAVE_FILENAME):
            os.remove(WAVE_FILENAME)
        status_label.config(text="Готово! Текст скопирован в буфер обмена.")
    except Exception as e:
        status_label.config(text=f"Ошибка: {e}")
        if "cublas" in str(e).lower() or "cuda" in str(e).lower():
            status_label.config(text="Ошибка GPU. Проверьте установку CUDA (см. README).")

# ---------- Расшифровка загруженного файла ----------
def transcribe_file(file_path):
    status_label.config(text="Идёт расшифровка файла (GPU)...")
    root.update_idletasks()
    try:
        model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
        segments, info = model.transcribe(file_path, beam_size=10, language="ru")
        full_text = ""
        for seg in segments:
            full_text += seg.text + " "
        pyperclip.copy(full_text.strip())
        status_label.config(text="Готово! Текст скопирован в буфер обмена.")
    except Exception as e:
        status_label.config(text=f"Ошибка при расшифровке: {e}")

# ---------- Обработчик перетаскивания ----------
def on_drop(event):
    file_path = event.data.strip('{}')
    if file_path:
        threading.Thread(target=transcribe_file, args=(file_path,), daemon=True).start()

# ---------- Выбор файла через диалог ----------
def load_file():
    file_path = filedialog.askopenfilename(
        title="Выберите аудиофайл",
        filetypes=[("Аудиофайлы", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac"),
                   ("Все файлы", "*.*")]
    )
    if file_path:
        threading.Thread(target=transcribe_file, args=(file_path,), daemon=True).start()

# ---------- Кнопка записи ----------
def toggle_recording():
    global recording, audio_thread, frames, stop_event

    if not recording:
        frames = []
        stop_event.clear()
        recording = True
        record_btn.config(text="⏹ Остановить запись", bg="#ff6666")
        status_label.config(text="● Идёт запись...")

        start_audio_stream()
        audio_thread = threading.Thread(target=record_loop, daemon=True)
        audio_thread.start()
    else:
        recording = False
        stop_event.set()
        audio_thread.join(timeout=1.0)
        stop_audio_stream()
        save_wav(WAVE_FILENAME)

        record_btn.config(text="🎤 Начать запись", bg="#aaffaa")
        status_label.config(text="Запись остановлена, обработка...")
        root.update_idletasks()

        threading.Thread(target=transcribe_mic, daemon=True).start()

# ---------- Закрытие ----------
def on_closing():
    global recording
    if recording:
        stop_event.set()
        if audio_thread and audio_thread.is_alive():
            audio_thread.join(0.5)
        stop_audio_stream()
    if os.path.exists(WAVE_FILENAME):
        os.remove(WAVE_FILENAME)
    root.destroy()

# ---------- GUI ----------
root = TkinterDnD.Tk()
root.title("Голосовой транскрайбер (large-v3-turbo) [GPU]")
root.geometry("450x330")
root.protocol("WM_DELETE_WINDOW", on_closing)

title_label = tk.Label(root, text="Запись и расшифровка голоса", font=("Arial", 14))
title_label.pack(pady=15)

# Зона для перетаскивания
drop_label = tk.Label(root, text="Перетащите аудиофайл сюда", font=("Arial", 11),
                      bg="#f0f0f0", relief="groove", padx=20, pady=10)
drop_label.pack(pady=10)
drop_label.drop_target_register(DND_FILES)
drop_label.dnd_bind('<<Drop>>', on_drop)

record_btn = tk.Button(root, text="🎤 Начать запись", font=("Arial", 12),
                       bg="#aaffaa", activebackground="#88dd88",
                       width=20, height=2, command=toggle_recording)
record_btn.pack(pady=5)

load_btn = tk.Button(root, text="📁 Загрузить аудио", font=("Arial", 12),
                     bg="#cce5ff", activebackground="#99ccff",
                     width=20, height=2, command=load_file)
load_btn.pack(pady=5)

status_label = tk.Label(root, text="Ожидание действий", font=("Arial", 10), fg="gray")
status_label.pack(pady=10)

exit_btn = tk.Button(root, text="Выход", font=("Arial", 10),
                     command=on_closing, width=10)
exit_btn.pack(pady=5)

root.mainloop()