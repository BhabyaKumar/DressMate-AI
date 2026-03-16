import cv2
import numpy as np


def detect_skin_tone(image_path):

    img = cv2.imread(image_path)

    if img is None:
        print("Image not found")
        return None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        print("No face detected")
        return None

    x, y, w, h = faces[0]

    face = img_rgb[y:y+h, x:x+w]

    avg_color = np.mean(face.reshape(-1, 3), axis=0)

    brightness = np.mean(avg_color)

    if brightness > 200:
        tone = "Fair"
    elif brightness > 140:
        tone = "Medium"
    else:
        tone = "Dark"

    return tone