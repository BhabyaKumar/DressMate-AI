import pandas as pd


def load_dataset(path):

    # Load CSV file into pandas dataframe
    df = pd.read_csv(path)

    print("Dataset loaded successfully")
    print("Total products:", len(df))

    # Replace missing values with empty string
    df["name"] = df["name"].fillna("")
    df["description"] = df["description"].fillna("")
    df["p_attributes"] = df["p_attributes"].fillna("")

    # Create a single searchable text column
    df["search_text"] = (
        df["name"] +
        " " +
        df["description"] +
        " " +
        df["p_attributes"]
    )

    return df