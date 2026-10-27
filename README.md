# Penangkap Sidik Jari - Arduino UNO + AS608

## Isi paket
- `fingerprint_capture/fingerprint_capture.ino` : sketch utama (capture + kirim gambar ke PC)
- `setsyspara/setsyspara.ino`                  : sketch konfigurasi — ubah baudrate sensor (jalankan sekali)
- `probe_baud/probe_baud.ino`                  : sketch diagnostik — deteksi baud sensor saat ini
- `fingerprint_app.py`                         : aplikasi jendela (GUI) untuk menangkap dan menyimpan gambar
- `run.bat`                                    : klik dua kali untuk menjalankan (Windows)
- `requirements.txt`                           : daftar library Python (pyserial, Pillow)

Setiap folder sketch **harus terpisah** (aturan Arduino: 1 folder = 1 sketch, nama folder = nama `.ino`).

## Komponen
Arduino UNO, sensor AS608, 2 LED (hijau & merah), 2 resistor (330 Ω – 1 kΩ), 1 kapasitor elektrolit 100 µF (10 V atau 16 V), breadboard, kabel jumper, kabel USB.

## Koneksi pin
| Dari | Ke Arduino UNO |
|---|---|
| AS608 VCC | 5V |
| AS608 GND | GND |
| AS608 TX | D8 (RX AltSoftSerial) |
| AS608 RX | D9 (TX AltSoftSerial) |
| LED hijau (+) | D6 lewat resistor |
| LED merah (+) | D7 lewat resistor |
| Kaki (−) kedua LED | GND |
| Kapasitor 100 µF Kaki (+) | VCC Sensor |
| Kapasitor 100 µF Kaki (-) | GND Sensor |

Kapasitor menjadi buffer lonjakan arus AS608 (~95 mA saat upload gambar). Tanpa ini, tegangan 5V drop sesaat → bit error → gambar korup.

Catatan:
- Warna kabel bisa berbeda antar produsen. Ikuti label/pinout modul, terutama VCC dan GND.
- Jika kabel sensor ada 6 (WAKEUP dan 3.3V-touch), dua kabel itu dibiarkan tidak terhubung.
- TX sensor harus ke D8, RX sensor ke D9.
- Pin D8/D9 adalah pin tetap `AltSoftSerial` di UNO — tidak bisa diganti.

## Library yang diperlukan

### 1. AltSoftSerial (WAJIB)
Install via Arduino IDE: **Sketch → Include Library → Manage Libraries** → cari **"AltSoftSerial"** by *Paul Stoffregen* → **Install**.

### 2. Perbesar buffer RX AltSoftSerial (WAJIB untuk AS608)
Buffer default hanya 80 byte — paket AS608 = 128 byte, sehingga sering overflow. Ubah ke 240:

1. Buka `%USERPROFILE%\Documents\Arduino\libraries\AltSoftSerial\src\AltSoftSerial.cpp`
2. Cari baris: `#define RX_BUFFER_SIZE 80`
3. Ubah menjadi: `#define RX_BUFFER_SIZE 240`
4. Simpan, **restart Arduino IDE**, lalu compile ulang sketch.

(Jangan 256 — tipe `uint8_t` head/tail hanya muat 0–255.)

## Baudrate sensor

Sensor AS608 mendukung beberapa baud. **Default pabrik = 57600**, tapi pada Arduino UNO dengan SoftwareSerial bit-banged, baud tinggi menyebabkan kegagalan sesekali (~30% success rate pada 57600; ~73% pada 19200).

**Rekomendasi untuk keandalan maksimum: 19200.**

Untuk mengubah baud:
1. Cek posisi sensor saat ini dengan `probe_baud.ino` (upload, buka Serial Monitor @115200, tekan Reset board).
2. Jika ingin pindah ke 19200 (dari 57600):
   - Edit `setsyspara.ino`:
     ```cpp
     fp.begin(57600);                        // baud sensor SEKARANG
     const uint8_t para[2] = {0x04, 0x02};   // 0x02 = N=2 → 19200 (TARGET)
     ```
   - Upload, buka Serial Monitor @115200, Reset → tunggu `BERHASIL`.
3. Jika ingin kembali ke 57600 (dari 19200):
   - Edit `setsyspara.ino`:
     ```cpp
     fp.begin(19200);                        // baud sensor SEKARANG
     const uint8_t para[2] = {0x04, 0x06};   // 0x06 = N=6 → 57600 (TARGET)
     ```
   - Upload, buka Serial Monitor @115200, Reset → tunggu `BERHASIL`.
4. Sesuaikan `fingerprint_capture.ino`: `fpSerial.begin(19200)` atau `fpSerial.begin(57600)` — **harus cocok dengan baud sensor**.
5. Sesuaikan `CAPTURE_TIMEOUT` di `fingerprint_app.py`:
   - 19200 → `CAPTURE_TIMEOUT = 40` (±20 detik transfer)
   - 57600 → `CAPTURE_TIMEOUT = 40` (±7 detik transfer)
   - 9600  → `CAPTURE_TIMEOUT = 90` (±40 detik transfer)

Verifikasi dengan `probe_baud.ino` setelah setiap perubahan.

## Langkah penggunaan

1. Rakit sesuai tabel dengan Arduino masih tercabut dari USB.
2. Pasang Arduino IDE + library **AltSoftSerial**, ubah buffer RX ke 240 (lihat bagian Library).
3. Buka `fingerprint_capture.ino` (folder dan nama file harus sama), pilih board **Arduino Uno** dan port, klik **Upload**. LED hijau menyala jika siap.
4. (Opsional, jika ingin baud 19200 atau perlu reset ke default) Upload `setsyspara.ino` sekali, lihat pesan `BERHASIL` di Serial Monitor @115200.
5. (Opsional) Upload `probe_baud.ino` untuk memastikan baud sensor sesuai ekspektasi.
6. Upload ulang `fingerprint_capture.ino` dengan `fpSerial.begin(...)` yang sesuai baud sensor.
7. **Tutup Serial Monitor Arduino IDE** dan **tutup Arduino IDE sepenuhnya** (port COM tidak boleh dipakai dua program).
8. Pasang Python 3.9+ dari python.org (centang **"Add Python to PATH"**).
9. Klik dua kali `run.bat`.
10. Di aplikasi: pilih port → **Hubungkan** → **Simpan Sidik Jari** → tempelkan jari saat diminta.
11. Gambar tampil di jendela dan otomatis tersimpan di folder `hasil_fingerprint` (PNG). Gunakan **Simpan Sebagai...** untuk BMP/JPG.

## Auto-retry (sangat disarankan)

Karena hardware AS608 + UNO tidak 100% andal, tambahkan auto-retry di `fingerprint_app.py` agar kegagalan transfer tidak terasa oleh user:

```python
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
                m = str(e)
                if ("tidak lengkap/rusak" in m or
                    "Data gambar terputus" in m) and attempt < MAX_ATTEMPTS:
                    self.events.put(("log", f"Percobaan {attempt} gagal: {m}"))
                    continue
                raise
    except serial.SerialException as e:
        self.events.put(("lost", f"Koneksi serial terputus: {e}"))
    except Exception as e:
        self.events.put(("error", str(e)))
    finally:
        self.events.put(("done",))
```

(Rename fungsi `_capture_worker` yang ada menjadi `_do_capture_once`, isinya tidak diubah.)

Dengan success rate 30% (57600) dan 5 percobaan → P(sukses) ≈ 83%.
Dengan success rate 73% (19200) dan 5 percobaan → P(sukses) ≈ 99,9%.

## Arti LED
- Hijau menyala: siap
- Hijau berkedip: menunggu jari
- Hijau berkedip 3×: berhasil
- Merah 1,5 detik: gagal/waktu habis

## Diagnostik di panel Catatan

Setelah capture, Arduino mengirim baris diagnostik setelah 36864 byte gambar. Yang penting:

| Baris | Arti |
|---|---|
| `DBG_TOTAL 36864 pkts 288` | Normal — 288 paket × 128 byte |
| `IMG_END_OK` | Sukses penuh |
| `DBG_FAIL readPacket at <N>` | Transfer putus di byte N — catat angkanya |
| `DBG_FAIL pid 0x.. at <N>` | Paket aneh (desync) |
| `DBG_TOTAL <N> pkts <M>` | Ukuran gambar sensor berbeda; kirim angkanya |

Jika `DBG_FAIL` berubah-ubah antar percobaan → noise elektrik/kabel. Jika konsisten di angka sama → masalah timing CPU. Solusi: turunkan baud ke 19200.

## Jadikan satu file .exe (opsional, tanpa Python di PC pengguna)
```
pip install pyinstaller
pyinstaller --onefile --windowed fingerprint_app.py
```
File hasil ada di folder `dist`.

## Pemecahan masalah

### "Access is denied" saat upload
Port COM5 (atau COM lain) dipakai program lain. Aplikasi Python (`.bat`) atau Serial Monitor Arduino IDE memegang port.
- Tutup `.bat`, tutup Serial Monitor (✕), tutup Arduino IDE sepenuhnya.
- Cek Task Manager: `python.exe`, `cmd.exe`, `javaw.exe` sisa → **End task**.
- Cabut & colok ulang USB, lalu upload.

### "Gambar tidak lengkap/rusak. Coba lagi"
Transfer serial korup. Penyebab berurutan:
1. **Buffer AltSoftSerial belum 240** — ulangi modifikasi `AltSoftSerial.cpp`, restart IDE, upload ulang sketch.
2. **Kapasitor belum terpasang / salah polaritas** — kapasitor harus paralel VCC–GND sensor, kaki + ke VCC.
3. **Baud terlalu tinggi** — turunkan ke 19200 (lihat bagian Baudrate).
4. **Kabel jumper terlalu panjang/jelek** — perpendek TX/RX ≤ 10 cm.
5. **Beban CPU** — UNO harus melayani dua ISR bersamaan; baud 19200 memberi margin 3×.

### "Sensor tidak merespons" / `.bat` tidak terhubung
- Pastikan **baud sketch = baud sensor**. Gunakan `probe_baud.ino` untuk cek.
- Kabel TX sensor **harus** ke D8, RX ke D9.
- Sensor diberi daya 5V stabil + kapasitor 100 µF.
- Port yang dipilih di `.bat` benar (bukan COM lain).

### Karakter acak di Serial Monitor
- Baud Serial Monitor **bukan 115200** → set ke 115200.
- Sketch aktif adalah `fingerprint_capture.ino` dan Anda menekan `C` di kotak input → data biner mengalir. Tutup, reset board.

### Error `redefinition of setup()` di Arduino IDE
Dua file `.ino` di folder yang sama. Pindahkan salah satu ke folder sendiri. **Setiap sketch harus di folder terpisah** dengan nama folder = nama file `.ino`.

### Port tidak muncul di `.bat`
- Pasang driver **CH340** jika memakai Arduino klon.
- Klik **Refresh** di aplikasi setelah colok USB.

### Sensor kembali ke 57600 tanpa sengaja
Jalankan `setsyspara.ino` dengan kombinasi `fp.begin(<baud_sekarang>)` dan `para={0x04, 0x06}`. Untuk ke 19200: `fp.begin(<baud_sekarang>)` + `para={0x04, 0x02}`.

## Rekomendasi konfigurasi final

| Parameter | Nilai disarankan |
|---|---|
| Baud sensor | **19200** (bukan default 57600) |
| Baud Serial USB | 115200 |
| Baud Serial Monitor | 115200 |
| Buffer RX AltSoftSerial | **240** |
| Kapasitor VCC–GND sensor | **100 µF** (opsional 470 µF + 0.1 µF keramik) |
| Pin sensor | TX → D8, RX → D9 |
| Pin LED | Hijau → D6, Merah → D7 |
| `CAPTURE_TIMEOUT` (app.py) | 40 detik (untuk 19200 & 57600) |
| `MAX_ATTEMPTS` (auto-retry) | 5 |
