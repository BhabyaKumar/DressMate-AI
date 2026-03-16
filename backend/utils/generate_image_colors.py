import pandas as pd
from color_extractor import get_dominant_color, color_name

df = pd.read_csv("data/fashion_with_types.csv")

colors = []

for path in df["image_path"]:

    rgb = get_dominant_color(path)

    if rgb is None:
        colors.append("unknown")
    else:
        colors.append(color_name(rgb))

df["image_color"] = colors

df.to_csv("data/fashion_with_colors.csv", index=False)

print("Image colors extracted.")