import datetime
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import serial
from serial.tools import list_ports
from PIL import Image, ImageOps, ImageTk

BAUD = 115200
IMG_W, IMG_H = 256, 288
RAW_BYTES = IMG_W * IMG_H // 2
SCALE = 1.5
CAPTURE_TIMEOUT = 40

ERR_MESSAGES = {
    "ERR_TIMEOUT": "Jari tidak terdeteksi, silakan coba lagi.",
    "ERR_CANCEL": "Pengambilan dibatalkan.",
    "ERR_SENSOR": "Sensor tidak merespons, silakan coba lagi.",
    "ERR_UPLOAD": "Sensor gagal mengirim gambar, silakan coba lagi.",
}

HI_TABLE = bytes((i >> 4) * 17 for i in range(256))
LO_TABLE = bytes((i & 0x0F) * 17 for i in range(256))


def raw_to_image(raw: bytes, enhance: bool = True) -> Image.Image:
    pix = bytearray(IMG_W * IMG_H)
    pix[0::2] = raw.translate(HI_TABLE)
    pix[1::2] = raw.translate(LO_TABLE)
    img = Image.frombytes("L", (IMG_W, IMG_H), bytes(pix))
    if enhance:
        img = ImageOps.autocontrast(img, cutoff=1)
    return img

def base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SAVE_DIR = os.path.join(base_dir(), "hasil_fingerprint")

class FingerprintApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Penangkap Sidik Jari")
        self.resizable(False, False)

        self.ser = None
        self.busy = False
        self.raw = None
        self.photo = None
        self.port_map = {}
        self.events = queue.Queue()

        self._build_ui()
        self.refresh_ports()
        self._show_placeholder()
        self._update_buttons()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self._poll)

    def _build_ui(self):
        pad = dict(padx=8, pady=4)

        conn = ttk.LabelFrame(self, text="Koneksi Arduino")
        conn.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(conn, text="Port:").grid(row=0, column=0, padx=6, pady=6)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(conn, textvariable=self.port_var, width=42, state="readonly")
        self.port_box.grid(row=0, column=1, padx=4)
        ttk.Button(conn, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=4)
        self.btn_connect = ttk.Button(conn, text="Hubungkan", command=self.toggle_connect)
        self.btn_connect.grid(row=0, column=3, padx=4)
        self.lbl_conn = ttk.Label(conn, text="● Belum terhubung", foreground="#b00020")
        self.lbl_conn.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))

        self.canvas = tk.Canvas(
            self, width=int(IMG_W * SCALE), height=int(IMG_H * SCALE),
            bg="#222222", highlightthickness=0,
        )
        self.canvas.grid(row=1, column=0, rowspan=2, **pad)

        right = ttk.LabelFrame(self, text="Penangkapan Sidik Jari")
        right.grid(row=1, column=1, sticky="nsew", **pad)
        self.lbl_status = ttk.Label(right, text="Hubungkan Arduino terlebih dahulu.",
                                    wraplength=300, justify="left", font=("Segoe UI", 10, "bold"))
        self.lbl_status.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        self.progress = ttk.Progressbar(right, length=300, maximum=100)
        self.progress.grid(row=1, column=0, columnspan=2, padx=8, pady=4)

        self.btn_capture = ttk.Button(right, text="Simpan Sidik Jari", command=self.start_capture)
        self.btn_capture.grid(row=2, column=0, sticky="ew", padx=8, pady=6, ipady=6)
        self.btn_cancel = ttk.Button(right, text="Batal", command=self.cancel_capture)
        self.btn_cancel.grid(row=2, column=1, sticky="ew", padx=8, pady=6, ipady=6)

        self.autosave_var = tk.BooleanVar(value=True)
        self.enhance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Simpan otomatis (PNG)", variable=self.autosave_var).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8)
        ttk.Checkbutton(right, text="Tingkatkan kontras", variable=self.enhance_var,
                        command=self._render).grid(row=4, column=0, columnspan=2, sticky="w", padx=8)

        self.btn_save = ttk.Button(right, text="Simpan Sebagai...", command=self.save_as)
        self.btn_save.grid(row=5, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(right, text="Buka Folder Hasil", command=self.open_folder).grid(
            row=5, column=1, sticky="ew", padx=8, pady=6)

        logf = ttk.LabelFrame(self, text="Catatan")
        logf.grid(row=2, column=1, sticky="nsew", **pad)
        self.log = tk.Text(logf, width=42, height=8, state="disabled", wrap="word")
        self.log.grid(row=0, column=0, padx=6, pady=6)

    def _show_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            int(IMG_W * SCALE) // 2, int(IMG_H * SCALE) // 2,
            text="Gambar sidik jari\nakan tampil di sini", fill="#888888",
            font=("Segoe UI", 12), justify="center",
        )

    def _update_buttons(self):
        connected = self.ser is not None
        self.btn_capture.config(state="normal" if connected and not self.busy else "disabled")
        self.btn_cancel.config(state="normal" if self.busy else "disabled")
        self.btn_connect.config(state="disabled" if self.busy else "normal",
                                text="Matikan" if connected else "Hubungkan")
        self.btn_save.config(state="normal" if self.raw else "disabled")

    def set_status(self, text):
        self.lbl_status.config(text=text)

    def add_log(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"[{stamp}] {text}\n")
        self.log.see("end")
        self.log.config(state="disabled")


    def refresh_ports(self):
        self.port_map = {}
        names = []
        best = None
        for p in list_ports.comports():
            label = f"{p.device} - {p.description}"
            self.port_map[label] = p.device
            names.append(label)
            desc = (p.description or "").lower() + (p.manufacturer or "").lower()
            if best is None and any(k in desc for k in ("arduino", "ch340", "usb serial", "usb-serial", "cp210")):
                best = label
        self.port_box["values"] = names
        if names:
            self.port_var.set(best or names[0])
        else:
            self.port_var.set("")

    def toggle_connect(self):
        if self.ser:
            self._disconnect("Koneksi diputuskan.")
            return
        label = self.port_var.get()
        if not label:
            messagebox.showwarning("Port kosong", "Sambungkan Arduino lalu klik 'Refresh'.")
            return
        self.busy = True
        self._update_buttons()
        self.set_status("Menghubungkan")
        threading.Thread(target=self._connect_worker, args=(self.port_map[label],), daemon=True).start()

    def _connect_worker(self, port):
        try:
            ser = serial.Serial(port, BAUD, timeout=0.5)
        except serial.SerialException as e:
            self.events.put(("connected", False, f"Tidak bisa membuka {port}: {e}\n"
                             "Pastikan Serial Monitor Arduino IDE sudah ditutup."))
            return
        try:
            time.sleep(2.2)
            ser.reset_input_buffer()
            ser.write(b"P")
            result, deadline = None, time.time() + 4
            while time.time() < deadline:
                line = ser.readline().decode(errors="ignore").strip()
                if line in ("SENSOR_OK", "SENSOR_ERR"):
                    result = line
                    break
            if result == "SENSOR_OK":
                self.events.put(("connected", True, ser))
                return
            ser.close()
            if result == "SENSOR_ERR":
                msg = "Sensor AS608 tidak merespons. Periksa kabel TX/RX dan daya."
            else:
                msg = "Arduino tidak menjawab. Pastikan sketch sudah di-upload dan port benar."
            self.events.put(("connected", False, msg))
        except Exception as e:
            try:
                ser.close()
            except Exception:
                pass
            self.events.put(("connected", False, str(e)))

    def _disconnect(self, msg):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.busy = False
        self.lbl_conn.config(text="● Belum terhubung", foreground="#b00020")
        self.set_status(msg)
        self.add_log(msg)
        self._update_buttons()

    def start_capture(self):
        if not self.ser or self.busy:
            return
        self.busy = True
        self.progress["value"] = 0
        self.set_status("Menghubungi sensor...")
        self._update_buttons()
        threading.Thread(target=self._capture_worker, args=(self.ser,), daemon=True).start()

    def cancel_capture(self):
        if self.ser and self.busy:
            try:
                self.ser.write(b"X")
            except Exception:
                pass

        def _capture_worker(self, ser):
            MAX_ATTEMPTS = 5
            try:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    try:
                        if attempt > 1:
                            msg = f"Percobaan ulang {attempt}/{MAX_ATTEMPTS}..."
                            self.events.put(("log", msg))
                            self.events.put(("status", msg + " Tempelkan jari lagi."))
                            time.sleep(1.2)
                        self._do_capture_once(ser)
                        return
                    except RuntimeError as e:
                        msg = str(e)
                        if ("tidak lengkap/rusak" in msg or
                            "Data gambar terputus" in msg) and attempt < MAX_ATTEMPTS:
                            self.events.put(("log", f"Percobaan {attempt} gagal: {msg}"))
                            continue
                        raise
            except serial.SerialException as e:
                self.events.put(("lost", f"Koneksi serial terputus: {e}"))
            except Exception as e:
                self.events.put(("error", str(e)))
            finally:
                self.events.put(("done",))

    def _do_capture_once(self, ser):
        try:
            ser.timeout = 0.5
            ser.reset_input_buffer()
            ser.write(b"C")
            t0 = time.time()
            while True:
                if time.time() - t0 > CAPTURE_TIMEOUT:
                    raise RuntimeError("Tidak ada respons dari Arduino (timeout).")
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if line == "WAIT_FINGER":
                    self.events.put(("status", "Tempelkan jari Anda pada sensor..."))
                elif line == "FINGER_OK":
                    self.events.put(("status", "Jari terdeteksi, mengambil gambar..."))
                elif line == "IMG_START":
                    break
                elif line.startswith("ERR_"):
                    raise RuntimeError(ERR_MESSAGES.get(line, line))

            raw = bytearray()
            ser.timeout = 3
            while len(raw) < RAW_BYTES:
                chunk = ser.read(min(2048, RAW_BYTES - len(raw)))
                if not chunk:
                    raise RuntimeError("Data gambar terputus, Silakan coba lagi.")
                raw += chunk
                self.events.put(("progress", len(raw) * 100 / RAW_BYTES))
            ser.timeout = 1.0
            tail = ""
            deadline = time.time() + 6
            while time.time() < deadline:
                line = ser.readline().decode(errors="ignore").strip()
                if line.startswith("IMG_END"):
                    tail = line
                    break
                if line:
                    self.events.put(("log", line))
            if tail != "IMG_END_OK":
                raise RuntimeError("Gambar tidak lengkap/rusak. Coba lagi "
                                   "(lihat baris DBG_FAIL di Catatan).")
            self.events.put(("image", bytes(raw)))
        except serial.SerialException as e:
            self.events.put(("lost", f"Koneksi serial terputus: {e}"))
        except Exception as e:
            self.events.put(("error", str(e)))
        finally:
            self.events.put(("done",))

    def _render(self):
        if not self.raw:
            return
        img = raw_to_image(self.raw, self.enhance_var.get())
        big = img.resize((int(IMG_W * SCALE), int(IMG_H * SCALE)), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(big)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    def _autosave(self):
        os.makedirs(SAVE_DIR, exist_ok=True)
        name = datetime.datetime.now().strftime("sidikjari_%Y%m%d_%H%M%S.png")
        path = os.path.join(SAVE_DIR, name)
        raw_to_image(self.raw, self.enhance_var.get()).save(path)
        return path

    def save_as(self):
        if not self.raw:
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=SAVE_DIR, defaultextension=".png",
            initialfile=datetime.datetime.now().strftime("sidikjari_%Y%m%d_%H%M%S"),
            filetypes=[("PNG", "*.png"), ("BMP", "*.bmp"), ("JPEG", "*.jpg")],
        )
        if path:
            raw_to_image(self.raw, self.enhance_var.get()).save(path)
            self.add_log(f"Disimpan: {path}")
            self.set_status("Gambar disimpan.")

    def open_folder(self):
        os.makedirs(SAVE_DIR, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(SAVE_DIR)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", SAVE_DIR])
            else:
                subprocess.Popen(["xdg-open", SAVE_DIR])
        except Exception as e:
            messagebox.showerror("Gagal membuka folder", str(e))

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "status":
                    self.set_status(ev[1])
                    self.add_log(ev[1])
                elif kind == "log":
                    self.add_log(ev[1])
                elif kind == "progress":
                    self.progress["value"] = ev[1]
                elif kind == "connected":
                    self.busy = False
                    if ev[1]:
                        self.ser = ev[2]
                        self.lbl_conn.config(text="Sensor Terhubung", foreground="#1b7f3b")
                        self.set_status("Klik 'Simpan Sidik Jari'.")
                        self.add_log("Terhubung ke Arduino dan sensor.")
                    else:
                        self.set_status("Gagal terhubung.")
                        self.add_log(ev[2])
                        messagebox.showerror("Gagal terhubung", ev[2])
                    self._update_buttons()
                elif kind == "image":
                    self.raw = ev[1]
                    self._render()
                    msg = "Sidik jari berhasil ditangkap."
                    if self.autosave_var.get():
                        try:
                            path = self._autosave()
                            msg += f" Tersimpan: {path}"
                        except Exception as e:
                            msg += f" (gagal menyimpan otomatis: {e})"
                    self.set_status("Berhasil! Gambar ditampilkan.")
                    self.add_log(msg)
                elif kind == "error":
                    self.set_status(ev[1])
                    self.add_log(ev[1])
                    self.progress["value"] = 0
                elif kind == "lost":
                    self._disconnect(ev[1])
                    messagebox.showerror("Koneksi terputus", ev[1])
                elif kind == "done":
                    self.busy = False
                    self._update_buttons()
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def on_close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    FingerprintApp().mainloop()