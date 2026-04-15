import cv2
import numpy as np


# Helper: Get width at specific height
def get_width_at_y(contour, y_line):
    points = [pt[0] for pt in contour if abs(pt[0][1] - y_line) < 5]

    if len(points) < 2:
        return 0

    xs = [p[0] for p in points]
    return max(xs) - min(xs)


# MAIN: Detect Body Shape from file path or numpy array
def detect_body_shape(image_path_or_array):
    """
    Detect body shape from either a file path or numpy array.
    
    Args:
        image_path_or_array: Either a string (file path) or numpy array (BGR or RGB)
    
    Returns:
        str: Body shape classification (hourglass, pear, inverted_triangle, apple, athletic, rectangle, unknown)
    """
    
    # Handle both file paths and numpy arrays
    if isinstance(image_path_or_array, str):
        img = cv2.imread(image_path_or_array)
    else:
        # Assume it's a numpy array
        img = image_path_or_array.copy()
        
        # If it's RGB, convert to BGR for OpenCV
        if img.shape[2] == 3 and img.dtype == np.uint8:
            # Check if it's likely RGB by assuming RGB images come from PIL
            # We'll try to convert it
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    if img is None:
        return "unknown"

    # Resize for consistency
    img = cv2.resize(img, (300, 600))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150)

    # Contours
    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return "unknown"

    # Largest contour = body
    contour = max(contours, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(contour)

    # Body levels
    shoulder_y = int(y + 0.2 * h)
    waist_y = int(y + 0.5 * h)
    hip_y = int(y + 0.75 * h)

    shoulder = get_width_at_y(contour, shoulder_y)
    waist = get_width_at_y(contour, waist_y)
    hip = get_width_at_y(contour, hip_y)

    if hip == 0 or shoulder == 0:
        return "unknown"

    # Ratios
    sh_hip = shoulder / hip
    waist_ratio = waist / hip


    # ADVANCED CLASSIFICATION


    # Hourglass
    if 0.9 <= sh_hip <= 1.1 and waist_ratio < 0.75:
        return "hourglass"

    # Pear (triangle)
    elif sh_hip < 0.85:
        return "pear"

    # Inverted triangle
    elif sh_hip > 1.2:
        return "inverted_triangle"

    # Apple (round)
    elif waist_ratio > 0.9:
        return "apple"

    # Athletic
    elif 0.85 <= sh_hip <= 1.15 and 0.75 <= waist_ratio <= 0.9:
        return "athletic"

    # Rectangle (default)
    else:
        return "rectangle"



# STYLE RECOMMENDATION

def recommend_style(body_shape):

    styles = {

        "hourglass": [
            "bodycon dress", "belted outfits", "wrap dress"
        ],

        "pear": [
            "A-line dress", "off-shoulder tops", "wide neckline"
        ],

        "inverted_triangle": [
            "flared pants", "V-neck tops", "skater skirts"
        ],

        "rectangle": [
            "layered outfits", "peplum tops", "structured jackets"
        ],

        "apple": [
            "empire waist dress", "loose tops", "flowy outfits"
        ],

        "athletic": [
            "crop tops", "fitted jeans", "structured outfits"
        ],

        "unknown": [
            "regular fit"
        ]
    }

    return styles.get(body_shape, ["regular fit"])