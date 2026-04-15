from recommend import recommend

results = recommend(100, top_k=5)

print(results[["name", "colour", "brand"]])