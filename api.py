"""
api.py — AirCanvas REST API

FastAPI tabanlı mikroservis. Dış uygulamaların AirCanvas motorunu
kullanmasını sağlar.

Başlatma:
    uvicorn api:app --host 0.0.0.0 --port 8000

Swagger dökümantasyonu:
    http://localhost:8000/docs

Temel akış:
    1. İstemci POST /api/process ile frame gönderir (base64 JPEG)
    2. Sunucu frame'i engine ile işler
    3. İşlenmiş frame + stroke verileri JSON olarak döner
"""

import base64
import time
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine import AirCanvasEngine


# ── FastAPI Uygulaması ───────────────────────────────────────────────

app = FastAPI(
    title="AirCanvas API",
    description="Gesture-controlled AR drawing engine. "
                "Send a camera frame, get back a processed frame with drawings.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Oturum Yönetimi ─────────────────────────────────────────────────

# Her session_id için ayrı bir engine instance
_sessions: Dict[str, AirCanvasEngine] = {}
# Son erişim zamanı (temizlik için)
_session_timestamps: Dict[str, float] = {}
# Maksimum oturum ömrü (saniye)
SESSION_TTL: int = 600  # 10 dakika


def _get_engine(session_id: str, width: int, height: int) -> AirCanvasEngine:
    """Oturum engine'ini döndürür. Yoksa oluşturur."""
    if session_id not in _sessions:
        _sessions[session_id] = AirCanvasEngine(width=width, height=height)
    _session_timestamps[session_id] = time.time()
    return _sessions[session_id]


def _cleanup_sessions() -> None:
    """Süresi dolmuş oturumları temizler."""
    now = time.time()
    expired = [
        sid for sid, ts in _session_timestamps.items()
        if now - ts > SESSION_TTL
    ]
    for sid in expired:
        if sid in _sessions:
            _sessions[sid].release()
            del _sessions[sid]
        if sid in _session_timestamps:
            del _session_timestamps[sid]


# ── Pydantic Modelleri ───────────────────────────────────────────────

class FrameRequest(BaseModel):
    """Frame işleme isteği."""
    session_id: str = Field(description="Benzersiz oturum kimliği")
    frame: str = Field(description="Base64 kodlanmış JPEG frame")
    width: int = Field(default=1920, description="Frame genişliği (piksel)")
    height: int = Field(default=1080, description="Frame yüksekliği (piksel)")


class StrokeData(BaseModel):
    """Tek bir stroke'un veri modeli."""
    points: List[List[int]]
    color: List[int]
    thickness: int
    brush_type: str
    point_count: int
    bounding_box: List[int]


class FrameResponse(BaseModel):
    """Frame işleme yanıtı."""
    processed_frame: str = Field(description="Base64 kodlanmış JPEG (işlenmiş)")
    gesture: str = Field(description="Algılanan jest")
    fingers: List[int] = Field(description="Parmak durumları")
    strokes: List[StrokeData] = Field(description="Tüm stroke verileri")
    active_color: List[int] = Field(description="Aktif renk [B, G, R]")
    active_brush: str = Field(description="Aktif fırça tipi")
    active_thickness: int = Field(description="Aktif çizgi kalınlığı")
    stroke_count: int = Field(description="Toplam stroke sayısı")
    is_eraser: bool = Field(description="Silgi modu aktif mi")


class ColorRequest(BaseModel):
    """Renk değiştirme isteği."""
    color: List[int] = Field(description="Yeni renk [B, G, R]", min_length=3, max_length=3)


class BrushRequest(BaseModel):
    """Fırça değiştirme isteği."""
    brush_type: str = Field(description="Fırça tipi: normal, neon, rainbow, eraser")


class ThicknessRequest(BaseModel):
    """Kalınlık değiştirme isteği."""
    thickness: int = Field(description="Yeni kalınlık (2-16)", ge=2, le=16)


class SessionInfo(BaseModel):
    """Oturum bilgisi."""
    session_id: str
    stroke_count: int
    active_color: List[int]
    active_brush: str
    active_thickness: int
    width: int
    height: int


# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────

def _decode_frame(frame_b64: str) -> np.ndarray:
    """Base64 string'i BGR numpy dizisine çevirir."""
    frame_bytes = base64.b64decode(frame_b64)
    np_arr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Geçersiz frame verisi.")
    return frame


def _encode_frame(frame: np.ndarray) -> str:
    """BGR numpy dizisini base64 JPEG string'e çevirir."""
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def _require_session(session_id: str) -> AirCanvasEngine:
    """Oturumun var olduğunu kontrol eder, yoksa hata fırlatır."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Oturum bulunamadı: {session_id}",
        )
    _session_timestamps[session_id] = time.time()
    return _sessions[session_id]


# ── API Endpointleri ─────────────────────────────────────────────────

@app.post("/api/process", response_model=FrameResponse)
async def process_frame(req: FrameRequest):
    """
    Tek bir frame'i işler.

    - Frame base64 JPEG olarak gönderilir
    - Motor jest algılama, çizim ve palet etkileşimi uygular
    - İşlenmiş frame + tüm stroke verileri döner
    """
    _cleanup_sessions()

    frame = _decode_frame(req.frame)
    engine = _get_engine(req.session_id, req.width, req.height)

    result = engine.process_frame(frame)

    return FrameResponse(
        processed_frame=_encode_frame(result["processed_frame"]),
        gesture=result["gesture"],
        fingers=result["fingers"],
        strokes=result["strokes"],
        active_color=result["active_color"],
        active_brush=result["active_brush"],
        active_thickness=result["active_thickness"],
        stroke_count=result["stroke_count"],
        is_eraser=result["is_eraser"],
    )


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Oturum bilgilerini döndürür."""
    engine = _require_session(session_id)
    return SessionInfo(
        session_id=session_id,
        stroke_count=engine._canvas.stroke_count,
        active_color=list(engine._palette.active_color),
        active_brush=engine._palette.active_brush,
        active_thickness=engine._palette.active_thickness,
        width=engine.width,
        height=engine.height,
    )


@app.get("/api/sessions/{session_id}/strokes")
async def get_strokes(session_id: str):
    """Oturumun tüm stroke verilerini JSON olarak döndürür."""
    engine = _require_session(session_id)
    return {"strokes": engine.get_strokes_json()}


@app.post("/api/sessions/{session_id}/color")
async def set_color(session_id: str, req: ColorRequest):
    """Aktif rengi değiştirir."""
    engine = _require_session(session_id)
    engine.set_color(tuple(req.color))
    return {"status": "ok", "color": req.color}


@app.post("/api/sessions/{session_id}/brush")
async def set_brush(session_id: str, req: BrushRequest):
    """Aktif fırça tipini değiştirir."""
    engine = _require_session(session_id)
    engine.set_brush(req.brush_type)
    return {"status": "ok", "brush_type": req.brush_type}


@app.post("/api/sessions/{session_id}/thickness")
async def set_thickness(session_id: str, req: ThicknessRequest):
    """Aktif çizgi kalınlığını değiştirir."""
    engine = _require_session(session_id)
    engine.set_thickness(req.thickness)
    return {"status": "ok", "thickness": req.thickness}


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str):
    """Oturumdaki tüm çizimleri temizler."""
    engine = _require_session(session_id)
    engine.clear()
    return {"status": "ok", "message": "Tuval temizlendi."}


@app.get("/api/health")
async def health():
    """Sunucu sağlık kontrolü."""
    return {
        "status": "ok",
        "active_sessions": len(_sessions),
    }
