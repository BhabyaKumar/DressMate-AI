import numpy as np
from PIL import Image
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input

model = ResNet50(weights="imagenet", include_top=False, pooling="avg")

def extract_features(img_path):
    img = Image.open(img_path).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)
    arr = preprocess_input(arr)

    features = model.predict(arr, verbose=0)
    return features.flatten().astype(np.float32)