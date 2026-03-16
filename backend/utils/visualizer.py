import cv2
import matplotlib.pyplot as plt

def show_results(results):

    plt.figure(figsize=(15,5))

    for i, (_, row) in enumerate(results.iterrows()):

        img = cv2.imread(row["image_path"])

        if img is None:
            continue

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        plt.subplot(1, len(results), i+1)
        plt.imshow(img)

        title = f"{row['product_type']} | {row['colour']}"
        plt.title(title)

        plt.axis("off")

    plt.show()