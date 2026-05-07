# final_sorter_usb.py
# Computer Vision on Jetson -> USB Serial -> Arduino -> Motors

import cv2
import numpy as np
import serial
import time
from collections import deque, Counter

# --- USB CONFIGURATION ---
# We found earlier that your port is ttyACM0
ARDUINO_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

# --- VISION CONFIGURATION ---
BUFFER_MAX_LEN = 30       # How many frames to keep for voting
MIN_VOTES = 15            # Minimum frames needed to vote
CONFIDENCE_THRESHOLD = 0.75
NOISE_FILTER_AREA = 200   # Ignore tiny specks
BOX_SCALE = 0.55          # Size of the Decision Box (0.55 = ~30% area)

# --- CONNECT TO ARDUINO ---
print(f"Connecting to Arduino on {ARDUINO_PORT}...")
try:
    arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # IMPORTANT: Wait for Arduino to reboot
    print("Connection Established!")
except Exception as e:
    print(f"FATAL ERROR: Could not connect to Arduino: {e}")
    print("Check USB cable or permissions (sudo usermod -a -G dialout $USER)")
    exit()

# --- VISION FUNCTIONS ---
def detect_shape(contour):
    """ Analyzes contour to find Shape Name """
    shape_name = "unidentified"
    perimeter = cv2.arcLength(contour, True)
    # 0.03 is the "Strictness" (Epsilon). Lower = Stricter.
    approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
    num_vertices = len(approx)

    if num_vertices == 3:
        shape_name = "Triangle"
    elif num_vertices == 4:
        (x, y, w, h) = cv2.boundingRect(approx)
        aspect_ratio = w / float(h)
        # Allow slightly imperfect squares (0.90 - 1.10)
        if 0.90 <= aspect_ratio <= 1.10: shape_name = "Square"
        else: shape_name = "Rectangle"
    elif num_vertices == 5:
        shape_name = "Pentagon"
    else:
        area = cv2.contourArea(contour)
        if perimeter > 0:
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            # Allow imperfect circles (0.80 - 1.20)
            if 0.80 < circularity < 1.20: shape_name = "Circle"
    return shape_name

def send_command_to_arduino(shape):
    print(f"--- SENDING COMMAND FOR {shape} ---")
    
    # Send the single letter code
    if shape == "Circle":
        arduino.write(b'O') # 'O' for Circle (Orb)
    elif shape == "Square":
        arduino.write(b'S') # 'S' for Square
    elif shape == "Triangle":
        arduino.write(b'T') # 'T' for Triangle
    else:
        print("Unknown shape, skipping sort.")
        return

    print("Waiting for Arduino to finish sorting...")
    
    # Block until the Arduino replies (it sends a line when done)
    # This prevents the camera from sending 50 commands while the motor is moving
    while True:
        if arduino.in_waiting > 0:
            response = arduino.readline().decode().strip()
            print(f"Arduino Says: {response}")
            break
        time.sleep(0.1)
    
    print("Ready for next object.")


def main():
    cap = cv2.VideoCapture(0)
    # Force low resolution for high FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("Error: Camera not found.")
        return

    # Get dimensions for the Decision Box
    ret, frame = cap.read()
    if not ret: return
    h, w = frame.shape[:2]
    
    box_w = int(w * BOX_SCALE)
    box_h = int(h * BOX_SCALE)
    box_x1 = int((w - box_w) / 2)
    box_y1 = int((h - box_h) / 2)
    box_x2 = box_x1 + box_w
    box_y2 = box_y1 + box_h
    
    detection_buffer = deque(maxlen=BUFFER_MAX_LEN)
    current_decision = "None"

    print("System Ready. Place object in Blue Box.")
    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # --- IMAGE PROCESSING ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        
        # Adaptive Threshold (Block Size 71, Constant 2)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 71, 5)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found_shape_in_box = False
        
        for cnt in contours:
            if cv2.contourArea(cnt) > NOISE_FILTER_AREA: 
                # Calculate Center
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                else: continue

                # Check if Center is inside Decision Box
                in_box = (box_x1 < cX < box_x2) and (box_y1 < cY < box_y2)
                shape = detect_shape(cnt)
                
                color = (200, 200, 200) # Grey (Ignore)
                if in_box:
                    color = (0, 255, 0) # Green (Scan)
                    if shape != "unidentified":
                        detection_buffer.append(shape)
                        found_shape_in_box = True
                
                # Draw Outline
                cv2.drawContours(frame, [cnt], -1, color, 2)
                cv2.putText(frame, shape, (cX - 20, cY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # --- VOTING LOGIC ---
        if len(detection_buffer) >= MIN_VOTES:
            vote_counts = Counter(detection_buffer)
            most_common_shape, count = vote_counts.most_common(1)[0]
            confidence = count / len(detection_buffer)
            
            if confidence >= CONFIDENCE_THRESHOLD:
                current_decision = most_common_shape
                print(f"DECISION: {current_decision} ({confidence*100:.0f}%)")
                
                # SEND TO ARDUINO
                send_command_to_arduino(current_decision)
                
                # Clear buffer so we don't sort the same object twice immediately
                detection_buffer.clear()
                
        if not found_shape_in_box and len(detection_buffer) == 0:
             current_decision = "None"

        # --- GUI OVERLAYS ---
        # Draw Decision Box
        cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (255, 0, 0), 2)
        cv2.putText(frame, "DECISION ZONE", (box_x1, box_y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Draw Status
        cv2.putText(frame, f"Decision: {current_decision}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Show Windows (Comment out 'Threshold' if not needed)
        cv2.imshow("Sorter Vision", frame)
        cv2.imshow("Computer Vision (Threshold)", thresh)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    arduino.close()
    print("Program Terminated.")

if __name__ == "__main__":
    main()