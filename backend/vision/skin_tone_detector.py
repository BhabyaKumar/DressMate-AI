import cv2
import numpy as np

# Lighting Normalization

def normalize_lighting(img):
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)

    l = cv2.equalizeHist(l)

    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)


# Face Detection (OpenCV)
def get_face_region(image):

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) > 0:
        x, y, w, h = faces[0]
        return image[y:y+h, x:x+w]

    # fallback (center crop)
    h, w, _ = image.shape
    return image[h//4:h//2, w//4:w//2]


#  Skin Mask (YCrCb)
def get_skin_mask(image):

    ycrcb = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)

    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)

    mask = cv2.inRange(ycrcb, lower, upper)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    return mask


#  Skin Tone + Undertone Detection
def detect_skin_properties(image_path):

    img = cv2.imread(image_path)

    if img is None:
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Face region
    face = get_face_region(img_rgb)

    # Normalize lighting
    face = normalize_lighting(face)

    # Skin mask
    mask = get_skin_mask(face)
    skin_pixels = face[mask > 0]

    if len(skin_pixels) == 0:
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}

    # LAB conversion
    lab = cv2.cvtColor(skin_pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB)

    L = lab[:, :, 0]
    A = lab[:, :, 1]
    B = lab[:, :, 2]

    avg_L = np.mean(L)
    avg_A = np.mean(A)
    avg_B = np.mean(B)


    # Tone Classification (3-level stable)

    if avg_L < 85:
        tone = "dark"
    elif avg_L < 160:
        tone = "medium"
    else:
        tone = "fair"

    # Undertone Classification

    if avg_A > 150 and avg_B > 150:
        undertone = "warm"
    elif avg_A < 135:
        undertone = "cool"
    else:
        undertone = "neutral"

    return {
        "tone": tone,
        "undertone": undertone,
        "brightness": float(avg_L)
    }


# Color Recommendation

def recommend_colors(tone, undertone):

    if undertone == "warm":
        base = ["gold", "orange", "peach", "coral", "mustard"]
    elif undertone == "cool":
        base = ["blue", "navy", "purple", "pink", "lavender"]
    else:
        base = ["white", "grey", "black", "beige"]

    if tone == "fair":
        extra = ["maroon", "emerald", "crimson"]
    elif tone == "medium":
        extra = ["olive", "teal", "yellow"]
    else:
        extra = ["cream", "bright white", "pastel"]

    return base + extra


# WRAPPER: Detect from numpy array (for app.py integration)
def detect_skin_properties_from_array(image_array: np.ndarray):
    """
    Analyze skin tone from numpy array (RGB format).
    Returns dict with tone, undertone, brightness.
    Falls back gracefully if face not detected.
    """
    if image_array is None or len(image_array) == 0:
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}

    try:
        img_rgb = image_array

        # Face region
        face = get_face_region(img_rgb)

        # Normalize lighting
        face = normalize_lighting(face)

        # Skin mask
        mask = get_skin_mask(face)
        skin_pixels = face[mask > 0]

        if len(skin_pixels) == 0:
            return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}

        # LAB conversion
        lab = cv2.cvtColor(skin_pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB)

        L = lab[:, :, 0]
        A = lab[:, :, 1]
        B = lab[:, :, 2]

        avg_L = np.mean(L)
        avg_A = np.mean(A)
        avg_B = np.mean(B)

        # Tone Classification
        if avg_L < 85:
            tone = "dark"
        elif avg_L < 160:
            tone = "medium"
        else:
            tone = "fair"

        # Undertone Classification
        if avg_A > 150 and avg_B > 150:
            undertone = "warm"
        elif avg_A < 135:
            undertone = "cool"
        else:
            undertone = "neutral"

        return {
            "tone": tone,
            "undertone": undertone,
            "brightness": float(avg_L)
        }

    except Exception as e:
        print(f"Error detecting skin properties: {e}")
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}