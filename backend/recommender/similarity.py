import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def find_similar_items(query_index, embeddings, top_k=5):

    query_vector = embeddings[query_index].reshape(1, -1)

    similarities = cosine_similarity(query_vector, embeddings)[0]

    sorted_indices = np.argsort(similarities)[::-1]

    similar_indices = sorted_indices[1:top_k+1]

    return similar_indices