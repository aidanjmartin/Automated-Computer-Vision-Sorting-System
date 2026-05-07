// sorter_arduino.ino
// USB Serial from Jetson -> Arduino Mega -> MOSFET DC Motor + Servo Arm

#include <Servo.h>

// --- PINS ---
const int MOSFET_PIN = 9;   // PWM -> AOD609A gate (conveyor DC motor)
const int SERVO_PIN  = 10;  // Servo arm (sorts to 3 bins)

// --- TUNING ---
const int CONVEYOR_SPEED = 200;    // 0-255 PWM duty
const int SORT_RUN_MS    = 1200;   // Conveyor on time per object
const int SERVO_SETTLE_MS = 400;   // Wait for arm to swing

// Servo positions (degrees) -- one per bin
const int POS_CIRCLE   = 30;
const int POS_SQUARE   = 90;
const int POS_TRIANGLE = 150;
const int POS_HOME     = 90;

Servo armServo;

void setup() {
  Serial.begin(9600);
  pinMode(MOSFET_PIN, OUTPUT);
  analogWrite(MOSFET_PIN, 0); // Motor off

  armServo.attach(SERVO_PIN);
  armServo.write(POS_HOME);

  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    int target = -1;

    // Match shape codes from final_sorter_usb.py
    if      (cmd == 'O') target = POS_CIRCLE;
    else if (cmd == 'S') target = POS_SQUARE;
    else if (cmd == 'T') target = POS_TRIANGLE;
    else return; // Ignore newlines / unknown chars

    sortObject(target);

    // Tell Python we're done so it stops blocking
    Serial.println("DONE");
  }
}

void sortObject(int angle) {
  // 1. Swing arm to bin
  armServo.write(angle);
  delay(SERVO_SETTLE_MS);

  // 2. Run conveyor to push object off
  analogWrite(MOSFET_PIN, CONVEYOR_SPEED);
  delay(SORT_RUN_MS);
  analogWrite(MOSFET_PIN, 0);

  // 3. Return arm to center
  armServo.write(POS_HOME);
  delay(SERVO_SETTLE_MS);
}
