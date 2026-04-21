import cv2
import numpy as np

# Detect skin tone directly from RGB without complex filtering
def _analyze_skin_tone(img_rgb):
    """
    Analyze skin tone by sampling multiple face regions.
    Uses LAB color space for accurate skin tone detection across all skin types.
    """
    try:
        # Get face region
        face = get_face_region(img_rgb)
        
        if face is None or face.size == 0:
            return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}
        
        # Sample cheek region (most reliable for skin tone)
        # Cheeks are typically center of face, below eyes
        h, w, _ = face.shape
        cheek_top = int(h * 0.35)
        cheek_bottom = int(h * 0.65)
        cheek_left = int(w * 0.15)
        cheek_right = int(w * 0.85)
        
        cheek_region = face[cheek_top:cheek_bottom, cheek_left:cheek_right]
        
        if cheek_region.size == 0:
            cheek_region = face
        
        # Convert to LAB color space for accurate tone analysis
        lab = cv2.cvtColor(cheek_region, cv2.COLOR_RGB2LAB)
        
        # Sample the center pixels (most likely to be skin)
        lab_h, lab_w, _ = lab.shape
        center_region = lab[lab_h//4:3*lab_h//4, lab_w//4:3*lab_w//4]
        
        # Extract LAB channels
        L = center_region[:, :, 0].flatten()
        A = center_region[:, :, 1].flatten()
        B = center_region[:, :, 2].flatten()
        
        # Use percentiles to ignore outliers
        avg_L = np.percentile(L, 50)  # median
        avg_A = np.percentile(A, 50)
        avg_B = np.percentile(B, 50)
        
        print(f"[SKIN TONE DEBUG] L={avg_L:.1f}, A={avg_A:.1f}, B={avg_B:.1f}")
        
        # Skin tone classification based on LAB L channel
        # Calibrated for actual skin tone data:
        if avg_L < 100:
            tone = "deep"       # Very dark skin
        elif avg_L < 140:
            tone = "medium"     # Medium/tan skin
        else:
            tone = "fair"       # Light/fair skin
        
        # Undertone classification
        a_diff = avg_A - 128
        b_diff = avg_B - 128
        
        if a_diff > 5 and b_diff > 5:
            undertone = "warm"
        elif a_diff < -8:
            undertone = "cool"
        else:
            undertone = "neutral"
        
        print(f"[SKIN TONE DEBUG] Detected: {tone}, undertone: {undertone}")
        
        return {
            "tone": tone,
            "undertone": undertone,
            "brightness": float(avg_L)
        }
        
    except Exception as e:
        print(f"[SKIN TONE ERROR] {e}")
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}


# Face Detection - Robust across all image types
def get_face_region(image):
    """Extract face region from image using multiple detection strategies."""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Try face detection with Haar cascades
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.05,
            minNeighbors=4,
            minSize=(50, 50)
        )
        
        if len(faces) > 0:
            x, y, w, h = faces[0]
            # Extract face region, adjust to get cheeks/face area
            y_start = max(0, y)
            y_end = min(image.shape[0], y + h)
            x_start = max(0, x)
            x_end = min(image.shape[1], x + w)
            return image[y_start:y_end, x_start:x_end]
        
        # Fallback: sample face from upper-center area (likely face location)
        h, w, _ = image.shape
        # Sample upper-middle portion where face typically is
        face_top = max(0, int(h * 0.1))
        face_bottom = min(h, int(h * 0.7))
        face_left = max(0, int(w * 0.2))
        face_right = min(w, int(w * 0.8))
        
        return image[face_top:face_bottom, face_left:face_right]
        
    except Exception as e:
        print(f"[FACE DETECT ERROR] {e}")
        h, w, _ = image.shape
        return image[int(h*0.1):int(h*0.7), int(w*0.2):int(w*0.8)]


# Robust Skin Tone Detection
def detect_skin_properties(image_path):
    """Detect skin tone from image file path."""
    img = cv2.imread(image_path)
    if img is None:
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return _analyze_skin_tone(img_rgb)


# Color Recommendation
def recommend_colors(tone, undertone):
    """Recommend colors based on skin tone and undertone."""
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
        return _analyze_skin_tone(image_array)
    except Exception as e:
        print(f"Error detecting skin properties: {e}")
        return {"tone": "medium", "undertone": "neutral", "brightness": 120.0}