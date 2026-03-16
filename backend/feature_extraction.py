import numpy as np
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
from tensorflow.keras.preprocessing import image

# Load pretrained ResNet50
model = ResNet50(weights="imagenet", include_top=False, pooling="avg")

def extract_features(img_path):

    img = image.load_img(img_path, target_size=(224, 224))
    img = image.img_to_array(img)

    img = np.expand_dims(img, axis=0)
    img = preprocess_input(img)

    features = model.predict(img, verbose=0)

    return features.flatten()