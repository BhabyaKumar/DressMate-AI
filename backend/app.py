"""
FashionAI Backend - FastAPI Server
===================================
Integrates all backend modules into a REST API for the frontend.

Setup:
  pip install fastapi uvicorn python-multipart scikit-learn numpy pandas
              pillow opencv-python-headless tensorflow

Run:
  uvicorn app:app --reload --port 8000

Then open the frontend HTML files (served via any static file server or
just opened from the file system). The API base URL is http://localhost:8000
"""

import os
import io
import uuid
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd
import cv2
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATA_PATH  = DATA_DIR / "fashion_with_clusters.csv"
EMB_PATH   = DATA_DIR / "fashion_embeddings.npy"

# ── lazy-load heavy assets ─────────────────────────────────────────────────
_df         = None
_embeddings = None
_resnet     = None

def get_data():
    global _df, _embeddings
    if _df is None:
        if not DATA_PATH.exists():
            raise HTTPException(500, f"Dataset not found at {DATA_PATH}. "
                                     "Run generate_embeddings.py and cluster_embeddings.py first.")
        _df = pd.read_csv(DATA_PATH)
        _df = _df.fillna("")
    if _embeddings is None:
        if not EMB_PATH.exists():
            raise HTTPException(500, f"Embeddings not found at {EMB_PATH}. "
                                     "Run generate_embeddings.py first.")
        _embeddings = np.load(EMB_PATH)
    return _df, _embeddings


def get_resnet():
    """Lazy-load ResNet50 only when needed (heavy import)."""
    global _resnet
    if _resnet is None:
        from tensorflow.keras.applications import ResNet50
        _resnet = ResNet50(weights="imagenet", include_top=False, pooling="avg")
    return _resnet


# ── helper utilities ───────────────────────────────────────────────────────

def extract_features_from_array(img_array: np.ndarray) -> np.ndarray:
    """Extract ResNet50 features from an RGB numpy array (H×W×3)."""
    from tensorflow.keras.applications.resnet50 import preprocess_input
    img = Image.fromarray(img_array).resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)
    arr = preprocess_input(arr)
    model = get_resnet()
    features = model.predict(arr, verbose=0)
    return features.flatten()


def find_similar_items(query_vector: np.ndarray, embeddings: np.ndarray, top_k: int = 8) -> np.ndarray:
    similarities = cosine_similarity(query_vector.reshape(1, -1), embeddings)[0]
    sorted_indices = np.argsort(similarities)[::-1]
    return sorted_indices[:top_k], similarities[sorted_indices[:top_k]]


def detect_product_type(text: str) -> str:
    text = str(text).lower()
    mapping = {
        "kurta": ["kurta", "kurti"],
        "dress": ["dress", "gown"],
        "shirt": ["shirt"],
        "tshirt": ["tshirt", "t-shirt"],
        "jeans": ["jeans"],
        "top": ["top"],
        "saree": ["saree"],
        "skirt": ["skirt"],
        "jacket": ["jacket"],
        "leggings": ["leggings"],
        "shorts": ["shorts"],
        "pants": ["trousers", "pants"],
    }
    for ptype, keywords in mapping.items():
        if any(k in text for k in keywords):
            return ptype
    return "other"


def detect_skin_tone_from_array(img_rgb: np.ndarray) -> str:
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    gray  = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        # fallback: use centre crop of image
        h, w = img_rgb.shape[:2]
        crop = img_rgb[h//4: 3*h//4, w//4: 3*w//4]
        brightness = np.mean(crop)
    else:
        x, y, w, h = faces[0]
        face = img_rgb[y:y+h, x:x+w]
        brightness = np.mean(face)

    if brightness > 200:
        return "Fair"
    elif brightness > 140:
        return "Medium"
    else:
        return "Dark"


def get_dominant_color_name(img_rgb: np.ndarray) -> str:
    pixels = img_rgb.reshape(-1, 3)
    if len(pixels) > 5000:
        idx = np.random.choice(len(pixels), 5000, replace=False)
        pixels = pixels[idx]
    kmeans = KMeans(n_clusters=3, n_init=10, random_state=42)
    kmeans.fit(pixels)
    dominant = kmeans.cluster_centers_[np.argmax(np.bincount(kmeans.labels_))]
    r, g, b = dominant
    if r > 150 and g < 100 and b < 100: return "red"
    if g > 150 and r < 120:             return "green"
    if b > 150 and r < 120:             return "blue"
    if r > 150 and g > 150 and b < 100: return "yellow"
    if r < 80  and g < 80  and b < 80:  return "black"
    if r > 200 and g > 200 and b > 200: return "white"
    if r > 150 and g > 100 and b < 100: return "orange"
    if r > 150 and b > 150 and g < 100: return "purple"
    if r > 180 and g > 130 and b > 100: return "peach"
    return "other"


def row_to_product(row, idx: int, score: float = 1.0) -> dict:
    """Convert a DataFrame row to a product dict for the frontend."""
    image_url = str(row.get("image_url", row.get("image_path", "")))

    if image_url and not image_url.startswith("http"):
        # Convert any local path like "Images\foo.jpg" or "Images/foo.jpg"
        # to a URL the browser can fetch: http://localhost:8000/images/foo.jpg
        filename = Path(image_url.replace("\\", "/")).name
        image_url = f"/images/{filename}"

    return {
        "id":           int(idx),
        "name":         str(row.get("name", "Fashion Item")),
        "brand":        str(row.get("brand", "")),
        "price":        str(row.get("price", row.get("selling_price", ""))),
        "colour":       str(row.get("colour", row.get("image_color", ""))),
        "product_type": str(row.get("product_type", "")),
        "description":  str(row.get("description", "")),
        "image_url":    image_url,
        "rating":       float(row.get("rating", 4.0) or 4.0),
        "cluster":      int(row.get("cluster", 0) or 0),
        "similarity":   round(float(score), 4),
    }


# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="FashionAI API",
    description="Backend for the AI Fashion Recommendation Frontend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # in production restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve local Images folder as static files ──────────────────────────────
# Checks common image folder locations relative to backend/
for _img_dir in ["Images", "images", "data/Images", "data/images"]:
    _img_path = BASE_DIR / _img_dir
    if _img_path.exists():
        app.mount("/images", StaticFiles(directory=str(_img_path)), name="images")
        print(f"✅ Serving images from: {_img_path}")
        break


# ── endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "FashionAI API is running"}


@app.get("/health")
def health():
    """Quick liveness check used by the frontend."""
    return {"status": "healthy"}


# ── 1. Image-based recommendation (core feature) ───────────────────────────
@app.post("/api/recommend/image")
async def recommend_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(8, ge=1, le=50),
):
    """
    Upload an image → get similar fashion items.
    The frontend calls this from image_upload_page.html after the user
    selects / drops a photo.
    """
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)

        # Analysis
        skin_tone = detect_skin_tone_from_array(img_arr)
        color     = get_dominant_color_name(img_arr)

        # Feature extraction + similarity search
        features = extract_features_from_array(img_arr)
        df, embeddings = get_data()
        indices, scores = find_similar_items(features, embeddings, top_k)

        products = [row_to_product(df.iloc[i], int(df.index[i]), float(s))
                    for i, s in zip(indices, scores)]

        return {
            "status":    "success",
            "skin_tone": skin_tone,
            "color":     color,
            "results":   products,
            "total":     len(products),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 2. Text-based recommendation ───────────────────────────────────────────
@app.get("/api/recommend/text")
def recommend_by_text(
    product_type: str = Query(..., description="e.g. dress, kurta, shirt"),
    color:        str = Query("", description="e.g. red, blue, black"),
    top_k:        int = Query(8, ge=1, le=50),
):
    """
    Filter by product_type & color, return similar items.
    Used by the browse page and search bar.
    """
    try:
        df, embeddings = get_data()

        mask = df["product_type"].str.lower() == product_type.lower()
        if color:
            mask &= df["image_color"].str.lower() == color.lower()

        filtered = df[mask]

        if filtered.empty:
            # relax color filter
            filtered = df[df["product_type"].str.lower() == product_type.lower()]

        if filtered.empty:
            return {"status": "success", "results": [], "total": 0}

        query_index = filtered.index[0]
        _, scores   = find_similar_items(embeddings[query_index], embeddings, top_k + 1)
        raw_indices, scores = find_similar_items(embeddings[query_index], embeddings, top_k + 1)

        products = []
        for i, s in zip(raw_indices, scores):
            if int(df.index[i]) == query_index:
                continue
            products.append(row_to_product(df.iloc[i], int(df.index[i]), float(s)))
            if len(products) >= top_k:
                break

        return {"status": "success", "results": products, "total": len(products)}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 3. Product catalogue (browse page) ─────────────────────────────────────
@app.get("/api/products")
def list_products(
    product_type: Optional[str] = Query(None),
    color:        Optional[str] = Query(None),
    brand:        Optional[str] = Query(None),
    sort:         str           = Query("relevance", enum=["relevance", "price_asc", "price_desc", "rating"]),
    page:         int           = Query(1, ge=1),
    per_page:     int           = Query(20, ge=1, le=100),
):
    """Paginated product listing for browse_products.html."""
    try:
        df, _ = get_data()
        mask   = pd.Series([True] * len(df), index=df.index)

        if product_type:
            mask &= df["product_type"].str.lower() == product_type.lower()
        if color:
            mask &= df.get("image_color", pd.Series([""] * len(df))).str.lower() == color.lower()
        if brand:
            mask &= df["brand"].str.lower().str.contains(brand.lower(), na=False)

        filtered = df[mask].copy()

        if sort == "price_asc":
            filtered["_price_num"] = pd.to_numeric(
                filtered.get("selling_price", filtered.get("price", pd.Series())), errors="coerce"
            )
            filtered = filtered.sort_values("_price_num", ascending=True)
        elif sort == "price_desc":
            filtered["_price_num"] = pd.to_numeric(
                filtered.get("selling_price", filtered.get("price", pd.Series())), errors="coerce"
            )
            filtered = filtered.sort_values("_price_num", ascending=False)
        elif sort == "rating":
            filtered = filtered.sort_values("rating", ascending=False) if "rating" in filtered else filtered

        total = len(filtered)
        start = (page - 1) * per_page
        page_df = filtered.iloc[start: start + per_page]

        products = [row_to_product(row, idx) for idx, row in page_df.iterrows()]

        return {
            "status":   "success",
            "results":  products,
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "pages":    (total + per_page - 1) // per_page,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 4. Single product detail ────────────────────────────────────────────────
@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    """Return one product + similar items. Used by product_detail.html."""
    try:
        df, embeddings = get_data()

        if product_id not in df.index:
            raise HTTPException(404, f"Product {product_id} not found")

        row     = df.loc[product_id]
        product = row_to_product(row, product_id)

        # similar items
        indices, scores = find_similar_items(embeddings[product_id], embeddings, 6)
        similar = [row_to_product(df.iloc[i], int(df.index[i]), float(s))
                   for i, s in zip(indices, scores) if int(df.index[i]) != product_id][:5]

        return {"status": "success", "product": product, "similar": similar}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 5. Skin-tone analysis only ──────────────────────────────────────────────
@app.post("/api/analyze/skin-tone")
async def analyze_skin_tone(file: UploadFile = File(...)):
    """Detect skin tone from uploaded photo."""
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)
        tone     = detect_skin_tone_from_array(img_arr)
        color    = get_dominant_color_name(img_arr)
        return {"status": "success", "skin_tone": tone, "dominant_color": color}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 6. Product-type detection from text ────────────────────────────────────
@app.get("/api/detect/product-type")
def detect_type(text: str = Query(...)):
    return {"status": "success", "product_type": detect_product_type(text)}


# ── 7. Dataset stats (dashboard / debug) ───────────────────────────────────
@app.get("/api/stats")
def get_stats():
    try:
        df, embeddings = get_data()
        return {
            "status":         "success",
            "total_products": int(len(df)),
            "embedding_dim":  int(embeddings.shape[1]) if embeddings.ndim > 1 else 0,
            "product_types":  df["product_type"].value_counts().to_dict() if "product_type" in df else {},
            "colors":         df["image_color"].value_counts().to_dict()  if "image_color"  in df else {},
            "brands":         int(df["brand"].nunique()) if "brand" in df else 0,
            "clusters":       int(df["cluster"].nunique()) if "cluster" in df else 0,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
