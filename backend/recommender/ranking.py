import pandas as pd
import numpy as np

from recommender.similarity import find_similar_items


def recommend(product_type, color, top_k=5):

    df = pd.read_csv("data/fashion_with_clusters.csv")
    embeddings = np.load("data/fashion_embeddings.npy")

    filtered = df[
        (df["product_type"].str.lower() == product_type.lower()) &
        (df["image_color"].str.lower() == color.lower())
    ]

    if len(filtered) == 0:
        print("No matching items found")
        return None

    query_index = filtered.index[0]

    similar_indices = find_similar_items(query_index, embeddings, top_k)

    results = df.loc[similar_indices]

    return results