import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

DATA_PATH = "data/clean_fashion_dataset.csv"
EMB_PATH = "data/fashion_embeddings.npy"

df = pd.read_csv(DATA_PATH)
embeddings = np.load(EMB_PATH)

print("Embeddings shape:", embeddings.shape)

# number of clusters (style groups)
k = 20

kmeans = KMeans(n_clusters=k, random_state=42)

clusters = kmeans.fit_predict(embeddings)

df["cluster"] = clusters

df.to_csv("data/fashion_with_clusters.csv", index=False)

print("Clustering finished.")
print("Clusters created:", k)