import pandas as pd
from product_type_detection import detect_product_type

DATA_PATH = "data/clean_fashion_dataset.csv"

df = pd.read_csv(DATA_PATH)

# Create search_text column if it doesn't exist
df["search_text"] = (
    df["name"].fillna("") + " " +
    df["description"].fillna("") + " " +
    df["p_attributes"].fillna("")
)

# Detect product type
df["product_type"] = df["search_text"].apply(detect_product_type)

df.to_csv("data/fashion_with_types.csv", index=False)

print("Product types added.")
print(df["product_type"].value_counts())