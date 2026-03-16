from recommender.ranking import recommend
from utils.visualizer import show_results


print("AI Fashion Recommendation System")
print("--------------------------------")

product_type = input("Enter clothing type: ")
color = input("Enter preferred color: ")

results = recommend(product_type, color, top_k=5)

if results is not None:

    print(results[["name","colour","brand","product_type"]])

    show_results(results)