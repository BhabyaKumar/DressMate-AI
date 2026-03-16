import cv2
import numpy as np
from sklearn.cluster import KMeans

def get_dominant_color(image_path, k=3):

    img = cv2.imread(image_path)

    if img is None:
        return None

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # reshape image into list of pixels
    pixels = img.reshape((-1, 3))

    # reduce pixels for speed
    pixels = pixels[np.random.choice(pixels.shape[0], 5000, replace=False)]

    kmeans = KMeans(n_clusters=k, n_init=10)
    kmeans.fit(pixels)

    colors = kmeans.cluster_centers_
    counts = np.bincount(kmeans.labels_)

    dominant = colors[np.argmax(counts)]

    return dominant

def color_name(rgb):

    r, g, b = rgb

    if r > 150 and g < 100 and b < 100:
        return "red"

    if g > 150 and r < 120:
        return "green"

    if b > 150 and r < 120:
        return "blue"

    if r > 150 and g > 150 and b < 100:
        return "yellow"

    if r < 80 and g < 80 and b < 80:
        return "black"

    if r > 200 and g > 200 and b > 200:
        return "white"

    return "other"