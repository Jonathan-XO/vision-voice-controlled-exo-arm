#include <ESP32Servo.h>

// Servo objects
Servo elbowLR;
Servo elbowUD;
Servo wristUD;
Servo gripper;

// Define servo pins
const int PIN_ELBOW_LR = 18;
const int PIN_ELBOW_UD = 19;
const int PIN_WRIST_UD = 21;
const int PIN_GRIPPER = 22;

void setup() {
  Serial.begin(115200);

  // Attach servos
  elbowLR.attach(PIN_ELBOW_LR, 500, 2400);
  elbowUD.attach(PIN_ELBOW_UD, 500, 2400);
  wristUD.attach(PIN_WRIST_UD, 500, 2400);
  gripper.attach(PIN_GRIPPER, 500, 2400);

  // Move all servos to starting position
  elbowLR.write(90);
  elbowUD.write(90);
  wristUD.write(90);
  gripper.write(0); // open
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    int values[4] = {90, 90, 90, 0}; // default values

    int index = 0;
    int lastComma = -1;

    // Parse CSV line
    for (int i = 0; i < line.length(); i++) {
      if (line[i] == ',' || i == line.length() - 1) {
        int end = (i == line.length() - 1) ? i + 1 : i;
        String valStr = line.substring(lastComma + 1, end);
        values[index] = valStr.toInt();
        index++;
        lastComma = i;
        if (index >= 4) break;
      }
    }

    // Write to servos
    elbowLR.write(constrain(values[0], 0, 180));
    elbowUD.write(constrain(values[1], 0, 180));
    wristUD.write(constrain(values[2], 0, 180));
    gripper.write(constrain(values[3], 0, 180));
  }
}
