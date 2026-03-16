import numpy as np
import pandas as pd

from feature_extraction import extract_features

DATA_PATH = "data/clean_fashion_dataset.csv"
SAVE_PATH = "data/fashion_embeddings.npy"

df = pd.read_csv(DATA_PATH)

embeddings = []

for path in df["image_path"]:

    try:
        features = extract_features(path)
        embeddings.append(features)

    except:
        embeddings.append(np.zeros(2048))

embeddings = np.array(embeddings)

np.save(SAVE_PATH, embeddings)

print("Embeddings saved.")
print("Shape:", embeddings.shape)