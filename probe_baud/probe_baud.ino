#include <AltSoftSerial.h>

void probeBaud(uint32_t baud) {
  AltSoftSerial fp;
  fp.begin(baud);
  delay(200);
  uint8_t pkt[] = {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
                   0x01, 0x00, 0x07, 0x13, 0, 0, 0, 0, 0x00, 0x1B};
  while (fp.available()) fp.read();
  for (uint8_t b : pkt) fp.write(b);
  uint32_t t = millis();
  while (millis() - t < 800) {
    if (fp.available()) {
      if (fp.read() == 0xEF) {
        Serial.print(F("  >> Sensor menjawab di "));
        Serial.print(baud); Serial.println(F(" baud"));
        return;
      }
    }
  }
  Serial.print(F("  -- Tidak ada jawaban di "));
  Serial.print(baud); Serial.println(F(" baud"));
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println(F("=== PROBE BAUD SENSOR ==="));
  probeBaud(57600);
  delay(300);
  probeBaud(19200);
  delay(300);
  Serial.println(F("=== selesai ==="));
}

void loop() { }