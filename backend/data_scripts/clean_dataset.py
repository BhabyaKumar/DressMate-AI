import pandas as pd
import os

DATA_PATH = "data/Fashion Dataset.csv"
IMAGE_FOLDER = "images"

df = pd.read_csv(DATA_PATH)

print("Original dataset size:", len(df))

# create image filename from dataset index
df["img_file"] = df.index.astype(str) + ".jpg"

# build local path
df["image_path"] = df["img_file"].apply(
    lambda x: os.path.join(IMAGE_FOLDER, x)
)

# keep only rows where the image exists
df = df[df["image_path"].apply(os.path.exists)]

print("Dataset after cleaning:", len(df))

# save cleaned dataset
df.to_csv("data/clean_fashion_dataset.csv", index=False)

print("Clean dataset saved.")