import pandas as pd

df = pd.read_csv("data/Fashion Dataset.csv")

print(df["img"].head(10))