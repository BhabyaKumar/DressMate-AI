def detect_product_type(text):

    text = str(text).lower()

    if "kurta" in text or "kurti" in text:
        return "kurta"

    elif "dress" in text or "gown" in text:
        return "dress"

    elif "shirt" in text:
        return "shirt"

    elif "tshirt" in text or "t-shirt" in text:
        return "tshirt"

    elif "jeans" in text:
        return "jeans"

    elif "top" in text:
        return "top"

    elif "saree" in text:
        return "saree"

    elif "skirt" in text:
        return "skirt"

    elif "jacket" in text:
        return "jacket"

    elif "leggings" in text:
        return "leggings"

    elif "shorts" in text:
        return "shorts"

    elif "trousers" in text or "pants" in text:
        return "pants"

    else:
        return "other"