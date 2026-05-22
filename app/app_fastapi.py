import base64
import io
from pathlib import Path

import albumentations as A
from albumentations.pytorch import ToTensorV2
import cv2
from fastapi import FastAPI, File, UploadFile, Query
import faiss
import numpy as np
import pandas as pd
from PIL import Image
from pydantic import BaseModel
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F

app = FastAPI(title="Shopee Product Matching API", version="2.0")

# ==================== КОНФИГУРАЦИЯ ====================
IMG_SIZE = 336
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_PATH = "inference_model.pth"
INDEX_PATH = "inference_index.faiss"
DATABASE_CSV = "inference_database.csv"
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR.parent / "data" / "train_images"
DATASET_MEAN_COLOR = (192, 183, 178)

# ==================== Модель ====================
class DinoWithProjectorUnfrozen(nn.Module):
    """DINOv2 ViT-S/14 с обучаемым проектором и возможностью частичной разморозки последних блоков."""
    def __init__(self, img_size=IMG_SIZE, proj_dim=384, unfreeze_blocks=4):
        super().__init__()
        self.backbone = timm.create_model('vit_small_patch14_dinov2.lvd142m',
                                          pretrained=False, num_classes=0, img_size=img_size)
        # Заморозка бекбона
        for p in self.backbone.parameters():
            p.requires_grad = False
        # Разморозка последних unfreeze_blocks блоков
        if unfreeze_blocks > 0:
            for block in self.backbone.blocks[-unfreeze_blocks:]:
                for p in block.parameters():
                    p.requires_grad = True
        self.proj = nn.Sequential(
            nn.Linear(384, proj_dim),
            nn.BatchNorm1d(proj_dim)
        )

    def forward(self, x):
        return self.proj(self.backbone(x))

# ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
model = None
index = None
db = None
val_transforms = A.Compose([
    A.LongestMaxSize(max_size=IMG_SIZE),
    A.PadIfNeeded(IMG_SIZE, IMG_SIZE, 
                  border_mode=cv2.BORDER_CONSTANT, fill = DATASET_MEAN_COLOR),
    A.Normalize(),
    ToTensorV2()
])

# ==================== ЗАГРУЗКА ПРИ СТАРТЕ ====================
@app.on_event("startup")
async def startup_event():
    global model, index, db
    model = DinoWithProjectorUnfrozen()
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()

    index = faiss.read_index(INDEX_PATH)
    db = pd.read_csv(DATABASE_CSV)
    print("Model and index loaded.")

# ==================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ====================
def pil_to_base64(pil_image: Image.Image, format='JPEG') -> str:
    """Конвертирует PIL-изображение в base64-строку."""
    buffered = io.BytesIO()
    pil_image.save(buffered, format=format)
    img_bytes = buffered.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

def load_image_as_base64(image_path: str) -> str:
    base_dir = Path(IMAGES_DIR).resolve()
    full_path = (base_dir / image_path).resolve()

    # Проверяем, что итоговый путь находится внутри IMAGES_DIR
    if base_dir not in full_path.parents and full_path != base_dir:
        raise ValueError("Access denied: path traversal detected")

    if not full_path.exists():
        raise FileNotFoundError(f"Image not found: {full_path}")

    img = Image.open(full_path).convert('RGB')
    return pil_to_base64(img)

# ==================== МОДЕЛИ ДАННЫХ ====================
class SearchResult(BaseModel):
    label_group: str
    similarity: float
    image_base64: str            

class SearchResponse(BaseModel):
    query_base64: str          
    results: list[SearchResult]

# ==================== ПОИСК ====================
def search_similar(query_tensor, top_k=5):
    with torch.no_grad():
        emb = model(query_tensor.to(DEVICE))
    emb_norm = F.normalize(emb, p=2, dim=1).cpu().numpy()

    distances, indices = index.search(emb_norm, top_k + 1)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if len(results) >= top_k:
            break
        row = db.iloc[idx]
        try:
            img_b64 = load_image_as_base64(row['image'])
        except Exception as e:
            print(f"Warning: could not load {row['image']}: {e}")
            img_b64 = ""
        results.append(SearchResult(
            label_group=str(row['label_group']),
            similarity=float(dist),
            image_base64=img_b64
        ))
    return results

# ==================== ЭНДПОИНТЫ ====================
@app.post("/search", response_model=SearchResponse)
def search_image(file: UploadFile = File(...), top_k: int = Query(5, ge=1, le=20)):

    contents = file.file.read()
    
    nparr = np.frombuffer(contents, np.uint8)
    img_cv2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR) 
    if img_cv2 is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    img_cv2 = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB) 

    transformed = val_transforms(image=img_cv2)['image']
    query_tensor = transformed.unsqueeze(0)

    results = search_similar(query_tensor, top_k)

    query_pil = Image.fromarray(img_cv2)
    query_base64 = pil_to_base64(query_pil)

    return SearchResponse(query_base64=query_base64, results=results)
@app.get("/health")
async def health():
    return {"status": "ok"}