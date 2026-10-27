# Penangkap Sidik Jari - Arduino UNO + AS608

## Isi paket
- `fingerprint_capture/fingerprint_capture.ino` : sketch Arduino (tanpa library tambahan)
- `fingerprint_app.py` : aplikasi jendela (GUI) untuk menangkap dan menyimpan gambar
- `jalankan.bat` : klik dua kali untuk menjalankan (Windows)
- `requirements.txt` : daftar library Python (pyserial, Pillow)

## Komponen
Arduino UNO, sensor AS608, 2 LED (hijau & merah), 2 resistor 3.3 kΩ, breadboard, kabel jumper, kabel USB.

## Koneksi pin
| Dari | Ke Arduino UNO |
|---|---|
| AS608 VCC (merah) | 5V |
| AS608 GND (hitam) | GND |
| AS608 TX (kuning) | D2 |
| AS608 RX (putih/hijau) | D3 |
| LED hijau (+) | D7 lewat resistor 3.3 kΩ |
| LED merah (+) | D8 lewat resistor 3.3 kΩ |
| Kaki (-) kedua LED | GND |

Catatan:
- Warna kabel bisa berbeda antar produsen. Ikuti label/pinout pada modul Anda, terutama VCC dan GND.
- Jika kabel sensor ada 6 (WAKEUP dan 3.3V-touch), dua kabel itu dibiarkan tidak terhubung.
- TX sensor harus ke RX Arduino (D2), RX sensor ke TX Arduino (D3) - disilang.
- Opsional (lebih aman): pasang pembagi tegangan 1 kΩ + 2 kΩ pada jalur D3 -> RX sensor, karena logika sensor 3.3 V.
- Dengan resistor 3.3 kΩ arus LED sekitar 1 mA, jadi redup. Jika kurang terang, gunakan 330 Ω - 1 kΩ.

## Langkah
1. Rakit sesuai tabel dengan Arduino masih tercabut dari USB.
2. Pasang Arduino IDE, buka `fingerprint_capture.ino` (folder dan nama file harus sama), pilih board Arduino Uno dan port, klik Upload. LED hijau menyala jika siap.
3. Tutup Serial Monitor Arduino IDE (port tidak boleh dipakai dua program).
4. Pasang Python 3.9+ dari python.org (centang "Add Python to PATH").
5. Klik dua kali `jalankan.bat`.
6. Di aplikasi: pilih port, klik **Hubungkan**, lalu **Tangkap Sidik Jari**, tempelkan jari saat diminta.
7. Gambar tampil di jendela dan otomatis tersimpan di folder `hasil_fingerprint` (PNG). Gunakan **Simpan Sebagai...** untuk BMP/JPG.

## Arti LED
- Hijau menyala: siap
- Hijau berkedip: menunggu jari
- Hijau berkedip 3x: berhasil
- Merah 1,5 detik: gagal/waktu habis

## Jadikan satu file .exe (opsional, tanpa Python di PC pengguna)
```
pip install pyinstaller
pyinstaller --onefile --windowed fingerprint_app.py
```
File hasil ada di folder `dist`.

## Pemecahan masalah
- "Sensor tidak merespons": cek TX/RX tidak tertukar, daya 5V, dan baud sensor default 57600.
- "Gambar rusak": pastikan ukuran paket data sensor masih default (128 byte) dan kabel tidak longgar.
- Port tidak muncul: pasang driver CH340 jika memakai Arduino klon.
