# Automated Computer Vision Sorting System

Real-time shape sorter: a Jetson runs OpenCV to identify objects on a conveyor, then sends a single-byte command over USB serial to an Arduino Mega that drives a DC conveyor motor (through a MOSFET) and a servo arm to drop the object into the correct bin.

[Demo video](demo.mov)

## How it works

1. **Vision (`sorter_main.py`)** — captures camera frames, adaptive-thresholds them, finds contours, and classifies each one as `Circle`, `Square`, or `Triangle`. A 30-frame voting buffer with a 75% confidence threshold prevents jitter from misfiring the sorter.
2. **Serial protocol** — once the vote passes, Python writes a single byte (`O`, `S`, or `T`) to `/dev/ttyACM0` at 9600 baud, then blocks until the Arduino replies `DONE`.
3. **Actuation (`sorter_arduino/sorter_arduino.ino`)** — Arduino swings the servo arm to the bin angle, runs the conveyor for ~1.2 s via PWM on the MOSFET gate, returns the arm to home, and replies `DONE`.

## Hardware

- Arduino Mega 2560 R3
- AOD609A dual N-channel MOSFET (low-side switch) for the DC motor
- 1N5408 flyback diodes across the DC motor
- Hobby servo for the sorting arm
- 7.4 V battery for motor power, USB from Jetson for logic + comms

See [`wiring.png`](wiring.png) for the schematic.

### Default pins

| Signal              | Pin |
|---------------------|-----|
| MOSFET gate (PWM)   | D9  |
| Servo signal        | D10 |

## Running it

On the Jetson:
```bash
pip install opencv-python pyserial numpy
python3 sorter_main.py
```

Press `q` in the preview window to quit. If the serial port differs, change `ARDUINO_PORT` at the top of `sorter_main.py`.

On the Arduino, open `sorter_arduino/sorter_arduino.ino` in the Arduino IDE, select the Mega 2560, and upload.

## Tuning

- **Servo bin angles** (`POS_CIRCLE`, `POS_SQUARE`, `POS_TRIANGLE`) in the `.ino`.
- **Conveyor speed / run time** (`CONVEYOR_SPEED`, `SORT_RUN_MS`) in the `.ino`.
- **Vision confidence / vote count** (`MIN_VOTES`, `CONFIDENCE_THRESHOLD`) in `sorter_main.py`.
