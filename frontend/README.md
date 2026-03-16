# FashionAI — Backend Integration Guide

## Project Structure

```
fashionai/
├── backend/
│   ├── app.py                    ← FastAPI server (NEW)
│   ├── requirements.txt          ← Python dependencies (NEW)
│   ├── recommender/
│   │   ├── similarity.py
│   │   └── ranking.py
│   ├── utils/
│   │   ├── color_extractor.py
│   │   └── image_loader.py
│   ├── vision/
│   │   └── skin_tone_detector.py
│   ├── feature_extraction.py
│   ├── product_type_detection.py
│   └── data/                     ← ⚠️  You must generate these files first
│       ├── fashion_with_clusters.csv
│       └── fashion_embeddings.npy
│
└── frontend/
    ├── api.js                    ← Shared API client (NEW)
    ├── index.html
    ├── image_upload_page.html    ← Calls /api/recommend/image
    ├── system_feedback.html      ← Loading animation
    ├── recommendation_results.html ← Renders API results
    ├── browse_products.html      ← Calls /api/products with filters
    ├── product_detail.html       ← Calls /api/products/{id}
    ├── my_wardrobe.html          ← Reads localStorage wardrobe IDs → API
    └── gemini_stylist.html       ← AI chat (independent)
```

---

## Step 1 — Prepare the Data

Run these scripts **once** to generate the dataset files the API needs:

```bash
cd backend

# 1. Clean your raw dataset
python clean_dataset.py

# 2. Generate ResNet50 embeddings (requires TensorFlow + GPU recommended)
python generate_embeddings.py

# 3. Cluster embeddings into style groups
python cluster_embeddings.py

# 4. Extract dominant colors per image
python utils/generate_image_colors.py
```

This produces:
- `data/fashion_with_clusters.csv`
- `data/fashion_embeddings.npy`

---

## Step 2 — Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## Step 3 — Start the Backend Server

```bash
cd backend
uvicorn app:app --reload --port 8000
```

The API will be live at **http://localhost:8000**

You can verify it with:
```
http://localhost:8000/health        → { "status": "healthy" }
http://localhost:8000/api/stats     → dataset stats
http://localhost:8000/docs          → Swagger interactive API docs
```

---

## Step 4 — Serve the Frontend

Open the frontend files using any static server. The simplest option:

```bash
cd frontend
python -m http.server 3000
```

Then open **http://localhost:3000** in your browser.

> ⚠️ Do NOT open HTML files directly via `file://` — CORS will block API calls.

---

## API Endpoints

| Method | Endpoint | Used by | Description |
|--------|----------|---------|-------------|
| POST | `/api/recommend/image` | Upload page | Upload photo → similar items |
| GET  | `/api/recommend/text?product_type=&color=` | Browse | Filter-based recommendations |
| GET  | `/api/products` | Browse | Paginated catalogue with filters |
| GET  | `/api/products/{id}` | Product detail | Single product + similar items |
| POST | `/api/analyze/skin-tone` | Upload page | Skin tone detection |
| GET  | `/api/stats` | Dashboard | Dataset statistics |
| GET  | `/health` | All pages | Server health check |

---

## How the Frontend ↔ Backend Flow Works

```
User uploads photo
      ↓
image_upload_page.html
  → calls API.recommendByImage(file)
  → stores results in sessionStorage
  → navigates to system_feedback.html
      ↓
system_feedback.html
  → plays animated loading sequence
  → redirects to recommendation_results.html
      ↓
recommendation_results.html
  → reads results from sessionStorage
  → renders product cards from real API data
  → user clicks card → product_detail.html?id=123
      ↓
product_detail.html
  → calls API.getProduct(123)
  → renders product info + similar items
  → "Save" button → stores id in localStorage
      ↓
my_wardrobe.html
  → reads IDs from localStorage
  → calls API.getProduct(id) for each
  → renders saved items
```

---

## Changing the API URL

If you deploy the backend to a server (not localhost), update the `API_BASE`
constant at the top of `frontend/api.js`:

```javascript
const API_BASE = "https://your-server.com";  // change this
```
