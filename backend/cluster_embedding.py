import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

print("Loading dataset...")
df = pd.read_csv("data/fashion_with_colors.csv")

print("Loading embeddings...")
embeddings = np.load("data/fashion_embeddings.npy")

print("Running KMeans clustering...")

kmeans = KMeans(
    n_clusters=50,
    random_state=42,
    n_init=10
)

clusters = kmeans.fit_predict(embeddings)

df["cluster"] = clusters

df.to_csv("data/fashion_with_clusters.csv", index=False)

print("Clustering completed.")
print("Total clusters:", len(set(clusters)))