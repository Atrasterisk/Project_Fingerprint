/*
  SetSysPara - Ubah baudrate AS608 ke 19200
  JALANKAN SEKALI SAJA. Setelah sukses, upload sketch utama yang sudah diubah.
  Koneksi: AS608 TX -> D8, RX -> D9
*/
#include <AltSoftSerial.h>
AltSoftSerial fp;

void sendPacket(uint8_t pid, const uint8_t* data, uint16_t len) {
  uint16_t plen = len + 2;
  uint16_t sum  = pid + (plen >> 8) + (plen & 0xFF);
  fp.write((uint8_t)0xEF); fp.write((uint8_t)0x01);
  for (uint8_t i = 0; i < 4; i++) fp.write((uint8_t)0xFF);
  fp.write(pid);
  fp.write((uint8_t)(plen >> 8)); fp.write((uint8_t)(plen & 0xFF));
  for (uint16_t i = 0; i < len; i++) { fp.write(data[i]); sum += data[i]; }
  fp.write((uint8_t)(sum >> 8)); fp.write((uint8_t)(sum & 0xFF));
}

bool readPacket(uint8_t &pid, uint8_t *out, uint16_t &len, uint32_t to) {
  uint32_t t = millis(); uint8_t st = 0; int b;
  auto rb = [&]() -> int {
    while (!fp.available()) if (millis() - t > to) return -1;
    return fp.read();
  };
  while (true) {
    b = rb(); if (b < 0) return false;
    if (st == 0) { if (b == 0xEF) st = 1; }
    else { if (b == 0x01) break; st = (b == 0xEF) ? 1 : 0; }
  }
  for (int i = 0; i < 4; i++) if (rb() < 0) return false;
  int p = rb(), hi = rb(), lo = rb();
  if (p < 0 || hi < 0 || lo < 0) return false;
  pid = p;
  uint16_t plen = ((uint16_t)hi << 8) | lo;
  len = plen - 2;
  uint16_t sum = pid + hi + lo;
  for (uint16_t i = 0; i < len; i++) { b = rb(); if (b < 0) return false; out[i] = b; sum += b; }
  int ch = rb(), cl = rb();
  if (ch < 0 || cl < 0) return false;
  return (uint16_t)((ch << 8) | cl) == sum;
}

uint8_t cmd(uint8_t instr, const uint8_t* params, uint8_t n) {
  while (fp.available()) fp.read();
  uint8_t c[8]; c[0] = instr;
  for (uint8_t i = 0; i < n; i++) c[i+1] = params[i];
  sendPacket(0x01, c, n + 1);
  uint8_t pid, buf[64]; uint16_t len;
  if (!readPacket(pid, buf, len, 1000)) return 0xFE;
  if (pid != 0x07 || len < 1) return 0xFE;
  return buf[0];
}

void setup() {
  Serial.begin(115200);
  fp.begin(19200);
  delay(500);

  Serial.println(F("=== SetSysPara: baud 19200 ==="));

  // 1) Verifikasi password default 0,0,0,0
  const uint8_t pwd[4] = {0, 0, 0, 0};
  uint8_t r = cmd(0x13, pwd, 4);
  if (r != 0x00) {
    Serial.print(F("GAGAL VfyPwd. Kode 0x")); Serial.println(r, HEX);
    Serial.println(F("Sensor mungkin pakai password custom. Tidak ada perubahan."));
    return;
  }
  Serial.println(F("Password OK."));

  // 2) SetSysPara - ubah baud multiplier (N) ke 2 => 9600*2 = 19200
  // Format: [param_number=4, value=N]
  const uint8_t para[2] = {0x04, 0x06};
  r = cmd(0x0E, para, 2);
  if (r != 0x00) {
    Serial.print(F("GAGAL SetSysPara. Kode 0x")); Serial.println(r, HEX);
    return;
  }
  Serial.println(F("BERHASIL: baud sensor = 19200."));
  Serial.println(F("Sekarang:"));
  Serial.println(F("  1. Ubah fingerprint.ino: fpSerial.begin(19200);"));
  Serial.println(F("  2. Upload ulang fingerprint.ino."));
  Serial.println(F("  3. JANGAN jalankan sketch ini lagi."));
}

void loop() { }