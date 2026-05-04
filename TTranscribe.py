import os
import pyaudio
import wave
import threading
import tempfile
import tkinter as tk
from tkinter import filedialog
import pyperclip
import asyncio
import edge_tts
import pygame
from faster_whisper import WhisperModel
from tkinterdnd2 import DND_FILES, TkinterDnD

# ---------- Настройки аудио ----------
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
WAVE_FILENAME = "temp_record.wav"

# ---------- Глобальные переменные ----------
recording = False
frames = []
stop_event = threading.Event()
audio_thread = None
p = None
stream = None

# ---------- Цветовая схема (тёмная тема) ----------
DARK_BG        = "#2e2e2e"
BUTTON_BG      = "#555555"
TEXT_BG        = "#4f4f4f"
HIGHLIGHT_BG   = "#777777"
TEXT_FG        = "red"
DROP_BG        = "#3a3a3a"

# ---------- Безопасное обновление GUI из потоков ----------
def safe_gui_call(func):
    """Выполнить функцию в главном потоке Tkinter."""
    root.after(0, func)

# ---------- Аудио функции ----------
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

# ---------- Расшифровка (по умолчанию CPU, легко переключить на GPU) ----------
def transcribe_mic():
    def task():
        try:
            safe_gui_call(lambda: status_label.config(text="Идёт расшифровка (CPU)..."))
            # По умолчанию используется CPU. Чтобы включить GPU NVIDIA, замените:
            # device="cpu" -> device="cuda", compute_type="int8" -> compute_type="float16"
            model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
            segments, info = model.transcribe(WAVE_FILENAME, beam_size=10, language="ru")
            full_text = " ".join(seg.text for seg in segments)
            pyperclip.copy(full_text.strip())
            if os.path.exists(WAVE_FILENAME):
                os.remove(WAVE_FILENAME)
            safe_gui_call(lambda: status_label.config(text="Готово! Текст скопирован в буфер обмена."))
        except Exception as e:
            safe_gui_call(lambda: status_label.config(text=f"Ошибка: {e}"))
    threading.Thread(target=task, daemon=True).start()

def transcribe_file(file_path):
    def task():
        try:
            safe_gui_call(lambda: status_label.config(text="Идёт расшифровка файла (CPU)..."))
            # Аналогично, для GPU замените параметры на device="cuda", compute_type="float16"
            model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
            segments, info = model.transcribe(file_path, beam_size=10, language="ru")
            full_text = " ".join(seg.text for seg in segments)
            pyperclip.copy(full_text.strip())
            safe_gui_call(lambda: status_label.config(text="Готово! Текст скопирован в буфер обмена."))
        except Exception as e:
            safe_gui_call(lambda: status_label.config(text=f"Ошибка при расшифровке: {e}"))
    threading.Thread(target=task, daemon=True).start()

def on_drop(event):
    file_path = event.data.strip('{}')
    if file_path:
        threading.Thread(target=transcribe_file, args=(file_path,), daemon=True).start()

def load_file():
    file_path = filedialog.askopenfilename(
        title="Выберите аудиофайл",
        filetypes=[("Аудиофайлы", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac"),
                   ("Все файлы", "*.*")]
    )
    if file_path:
        threading.Thread(target=transcribe_file, args=(file_path,), daemon=True).start()

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
        record_btn.config(text="🎤 Начать запись", bg=BUTTON_BG)
        status_label.config(text="Запись остановлена, обработка...")
        transcribe_mic()

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

# ---------- TTS (Edge) ----------
def _tts_job(text):
    tmp_path = None
    try:
        safe_gui_call(lambda: tts_status.config(text="Генерация речи..."))
        communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural", rate="+50%")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        asyncio.run(communicate.save(tmp_path))

        safe_gui_call(lambda: tts_status.config(text="Воспроизведение..."))
        pygame.mixer.quit()
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        safe_gui_call(lambda: tts_status.config(text="Озвучено"))
    except Exception as e:
        safe_gui_call(lambda: tts_status.config(text=f"Ошибка TTS: {e}"))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        pygame.mixer.quit()

def speak():
    text = tts_text.get("1.0", tk.END).strip()
    if not text:
        tts_status.config(text="Нечего озвучивать")
        return
    tts_status.config(text="Запуск...")
    threading.Thread(target=_tts_job, args=(text,), daemon=True).start()

def paste_tts():
    try:
        clipboard_text = pyperclip.paste()
        if clipboard_text:
            tts_text.delete("1.0", tk.END)
            tts_text.insert("1.0", clipboard_text)
            tts_status.config(text="Текст вставлен из буфера")
        else:
            tts_status.config(text="Буфер обмена пуст")
    except Exception as e:
        tts_status.config(text=f"Ошибка вставки: {e}")

def clear_tts():
    tts_text.delete("1.0", tk.END)
    tts_status.config(text="Очищено")

# ========== GUI ==========
root = TkinterDnD.Tk()
root.title("Голосовой ассистент: Транскрибация и TTS (large-v3-turbo) [CPU]")
root.configure(bg=DARK_BG)
root.protocol("WM_DELETE_WINDOW", on_closing)

main_frame = tk.Frame(root, bg=DARK_BG)
main_frame.pack(fill="both", expand=True, padx=0, pady=0)

# ====== TTS ======
tts_section = tk.Frame(main_frame, bg=DARK_BG)
tts_section.pack(fill="x", padx=10)

tts_title = tk.Label(tts_section, text="Синтез речи (TTS) — Edge TTS (Dmitry)",
                     font=("Arial", 12, "bold"), bg=DARK_BG, fg=TEXT_FG, anchor="center")
tts_title.pack(fill="x", pady=(5, 3))

tts_frame = tk.Frame(tts_section, bg=DARK_BG)
tts_frame.pack(fill="x")

tts_text = tk.Text(tts_frame, height=5, font=("Arial", 11), wrap="word",
                   bg=TEXT_BG, fg=TEXT_FG, insertbackground=TEXT_FG)
tts_text.pack(pady=(0, 3))

tts_button_frame = tk.Frame(tts_frame, bg=DARK_BG)
tts_button_frame.pack(pady=(0, 3))

btn_tts_font = ("Arial", 13, "bold")
paste_btn = tk.Button(tts_button_frame, text="📋 Вставить", font=btn_tts_font,
                      bg=BUTTON_BG, fg=TEXT_FG, activebackground=HIGHLIGHT_BG, activeforeground=TEXT_FG,
                      width=12, height=1, command=paste_tts)
paste_btn.pack(side=tk.LEFT, padx=4)

speak_btn = tk.Button(tts_button_frame, text="🔊 Озвучить", font=btn_tts_font,
                      bg=BUTTON_BG, fg=TEXT_FG, activebackground=HIGHLIGHT_BG, activeforeground=TEXT_FG,
                      width=12, height=1, command=speak)
speak_btn.pack(side=tk.LEFT, padx=4)

clear_btn = tk.Button(tts_button_frame, text="🗑 Очистить", font=btn_tts_font,
                      bg=BUTTON_BG, fg=TEXT_FG, activebackground=HIGHLIGHT_BG, activeforeground=TEXT_FG,
                      width=12, height=1, command=clear_tts)
clear_btn.pack(side=tk.LEFT, padx=4)

tts_status = tk.Label(tts_frame, text="", font=("Arial", 10), bg=DARK_BG, fg=TEXT_FG)
tts_status.pack(pady=(3, 0))

# ====== Транскрибация ======
trans_section = tk.Frame(main_frame, bg=DARK_BG)
trans_section.pack(fill="both", expand=True, padx=10, pady=(6, 10))

trans_frame = tk.Frame(trans_section, bg=DARK_BG, highlightthickness=4,
                       highlightbackground="black", highlightcolor="black")
trans_frame.pack(fill="both", expand=True)

title_label = tk.Label(trans_frame, text="Запись и расшифровка", font=("Arial", 15, "bold"),
                       bg=DARK_BG, fg=TEXT_FG)
title_label.pack(pady=(5, 3))

drop_label = tk.Label(trans_frame, text="Перетащите аудиофайл сюда", font=("Arial", 14, "bold"),
                      bg=DROP_BG, fg=TEXT_FG, relief="groove", padx=20, pady=30)
drop_label.pack(fill="x", pady=3)
drop_label.drop_target_register(DND_FILES)
drop_label.dnd_bind('<<Drop>>', on_drop)

btn_trans_font = ("Arial", 14, "bold")
record_btn = tk.Button(trans_frame, text="🎤 Начать запись", font=btn_trans_font,
                       bg=BUTTON_BG, fg=TEXT_FG, activebackground=HIGHLIGHT_BG, activeforeground=TEXT_FG,
                       width=24, height=2, command=toggle_recording)
record_btn.pack(pady=3)

load_btn = tk.Button(trans_frame, text="📁 Загрузить аудио", font=btn_trans_font,
                     bg=BUTTON_BG, fg=TEXT_FG, activebackground=HIGHLIGHT_BG, activeforeground=TEXT_FG,
                     width=24, height=2, command=load_file)
load_btn.pack(pady=3)

status_label = tk.Label(trans_frame, text="Ожидание действий", font=("Arial", 12, "bold"),
                        bg=DARK_BG, fg=TEXT_FG)
status_label.pack(pady=(3, 5))

# ---------- Минимальные размеры ----------
root.update_idletasks()
req_width_tts = tts_button_frame.winfo_reqwidth()
req_width_trans = max(drop_label.winfo_reqwidth(), record_btn.winfo_reqwidth(), load_btn.winfo_reqwidth())
min_width = max(req_width_tts, req_width_trans) + 20
min_height = 495
root.minsize(min_width, min_height)
root.geometry(f"{min_width}x{min_height}")

root.mainloop()
