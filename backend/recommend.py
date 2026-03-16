import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

DATA_PATH = "data/fashion_with_clusters.csv"
EMB_PATH = "data/fashion_embeddings.npy"

df = pd.read_csv(DATA_PATH)
embeddings = np.load(EMB_PATH)


def recommend(item_index, top_k=5):

    query_vector = embeddings[item_index].reshape(1, -1)

    similarities = cosine_similarity(query_vector, embeddings)[0]

    similar_indices = similarities.argsort()[::-1][1:top_k+1]

    return df.iloc[similar_indices]