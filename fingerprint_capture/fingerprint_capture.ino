#include <AltSoftSerial.h>

AltSoftSerial fpSerial;

const uint8_t LED_GREEN = 5;
const uint8_t LED_RED   = 6;

const uint16_t IMG_BYTES         = 36864;
const uint32_t FINGER_TIMEOUT_MS = 20000;
const uint8_t  COMM_ERR          = 0xFE;

uint8_t rxBuf[256];

void ledReady()  { digitalWrite(LED_GREEN, HIGH); digitalWrite(LED_RED, LOW); }
void ledOff()    { digitalWrite(LED_GREEN, LOW);  digitalWrite(LED_RED, LOW); }

void ledError() {
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, HIGH);
  delay(1500);
  ledReady();
}

void ledSuccess() {
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(LED_GREEN, LOW);  delay(120);
    digitalWrite(LED_GREEN, HIGH); delay(120);
  }
  ledReady();
}

void sendPacket(uint8_t pid, const uint8_t* data, uint16_t len) {
  uint16_t plen = len + 2;
  uint16_t sum  = pid + (plen >> 8) + (plen & 0xFF);
  fpSerial.write((uint8_t)0xEF);
  fpSerial.write((uint8_t)0x01);
  for (uint8_t i = 0; i < 4; i++) fpSerial.write((uint8_t)0xFF);
  fpSerial.write(pid);
  fpSerial.write((uint8_t)(plen >> 8));
  fpSerial.write((uint8_t)(plen & 0xFF));
  for (uint16_t i = 0; i < len; i++) {
    fpSerial.write(data[i]);
    sum += data[i];
  }
  fpSerial.write((uint8_t)(sum >> 8));
  fpSerial.write((uint8_t)(sum & 0xFF));
}

int readByte(uint32_t timeoutMs) {
  uint32_t t = millis();
  while (!fpSerial.available()) {
    if (millis() - t > timeoutMs) return -1;
  }
  return fpSerial.read();
}

bool readPacket(uint8_t &pid, uint8_t *out, uint16_t &len, uint16_t maxLen, uint32_t timeoutMs) {
  int b;
  uint8_t state = 0;
  while (true) {
    b = readByte(timeoutMs);
    if (b < 0) return false;
    if (state == 0) {
      if (b == 0xEF) state = 1;
    } else {
      if (b == 0x01) break;
      state = (b == 0xEF) ? 1 : 0;
    }
  }
  for (uint8_t i = 0; i < 4; i++) {
    if (readByte(timeoutMs) < 0) return false;
  }
  int p  = readByte(timeoutMs);
  int hi = readByte(timeoutMs);
  int lo = readByte(timeoutMs);
  if (p < 0 || hi < 0 || lo < 0) return false;
  pid = (uint8_t)p;

  uint16_t plen = ((uint16_t)hi << 8) | (uint8_t)lo;
  if (plen < 2 || (plen - 2) > maxLen) return false;
  len = plen - 2;

  uint16_t sum = pid + hi + lo;
  for (uint16_t i = 0; i < len; i++) {
    b = readByte(timeoutMs);
    if (b < 0) return false;
    out[i] = (uint8_t)b;
    sum += (uint8_t)b;
  }
  int ch = readByte(timeoutMs);
  int cl = readByte(timeoutMs);
  if (ch < 0 || cl < 0) return false;
  return (uint16_t)(((uint16_t)ch << 8) | (uint8_t)cl) == sum;
}

uint8_t sendCmd(uint8_t instr, const uint8_t* params, uint8_t n) {
  while (fpSerial.available()) fpSerial.read();
  uint8_t content[8];
  content[0] = instr;
  for (uint8_t i = 0; i < n; i++) content[i + 1] = params[i];
  sendPacket(0x01, content, n + 1);

  uint8_t  pid;
  uint16_t len;
  if (!readPacket(pid, rxBuf, len, sizeof(rxBuf), 1000)) return COMM_ERR;
  if (pid != 0x07 || len < 1) return COMM_ERR;
  return rxBuf[0];
}

void pingSensor() {
  const uint8_t pass[4] = {0, 0, 0, 0};
  uint8_t r = sendCmd(0x13, pass, 4);
  if (r == 0x00) {
    Serial.println(F("SENSOR_OK"));
    ledSuccess();
  } else {
    Serial.println(F("SENSOR_ERR"));
    ledError();
  }
}

void captureFingerprint() {
  Serial.println(F("WAIT_FINGER"));
  uint32_t t0 = millis(), lastBlink = 0;
  bool blink = false;
  uint8_t r;

  while (true) {
    if (Serial.available() && Serial.read() == 'X') {
      Serial.println(F("ERR_CANCEL"));
      ledReady();
      return;
    }
    if (millis() - t0 > FINGER_TIMEOUT_MS) {
      Serial.println(F("ERR_TIMEOUT"));
      ledError();
      return;
    }
    if (millis() - lastBlink > 300) {
      blink = !blink;
      digitalWrite(LED_GREEN, blink);
      lastBlink = millis();
    }
    r = sendCmd(0x01, NULL, 0);
    if (r == 0x00) break;
    if (r == COMM_ERR) {
      Serial.println(F("ERR_SENSOR"));
      ledError();
      return;
    }
    delay(50);
  }

  Serial.println(F("FINGER_OK"));
  digitalWrite(LED_GREEN, HIGH);

  r = sendCmd(0x0A, NULL, 0);
  if (r != 0x00) {
    Serial.println(F("ERR_UPLOAD"));
    ledError();
    return;
  }

  Serial.println(F("IMG_START"));
  uint32_t total   = 0;
  uint16_t packets = 0;
  uint8_t  failCode = 0;
  uint8_t  failPid  = 0;
  uint32_t failAt   = 0;
  bool ok = true;

  while (total < IMG_BYTES) {
    uint8_t  pid;
    uint16_t len;
    if (!readPacket(pid, rxBuf, len, sizeof(rxBuf), 1500)) {
      failCode = 1; failAt = total; ok = false; break;
    }
    if (pid != 0x02 && pid != 0x08) {
      failCode = 2; failPid = pid; failAt = total; ok = false; break;
    }
    uint16_t n = len;
    if (n > IMG_BYTES - total) n = (uint16_t)(IMG_BYTES - total);
    Serial.write(rxBuf, n);
    total += n;
    packets++;
    if (pid == 0x08) break;
  }
  if (total != IMG_BYTES) ok = false;
  while (total < IMG_BYTES) { Serial.write((uint8_t)0); total++; }

  if (failCode == 1) {
    Serial.print(F("DBG_FAIL readPacket at ")); Serial.println(failAt);
  } else if (failCode == 2) {
    Serial.print(F("DBG_FAIL pid 0x")); Serial.print(failPid, HEX);
    Serial.print(F(" at "));            Serial.println(failAt);
  }
  Serial.print(F("DBG_TOTAL ")); Serial.print(total);
  Serial.print(F(" pkts "));     Serial.println(packets);

  Serial.println(ok ? F("IMG_END_OK") : F("IMG_END_ERR"));
  if (ok) ledSuccess(); else ledError();
}

void setup() {
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  ledOff();

  Serial.begin(115200);
  fpSerial.begin(57600);
  delay(500);

  Serial.println(F("READY"));
  ledReady();
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'P')      pingSensor();
    else if (c == 'C') captureFingerprint();
  }
}