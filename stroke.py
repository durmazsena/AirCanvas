"""
stroke.py — Çizgi Veri Sınıfı (Stroke Data Class)

Tek bir çizim öğesini (stroke) temsil eder.
Her stroke: koordinat dizisi, renk, kalınlık ve fırça tipi içerir.

Fırça Tipleri:
  - "normal"  : Düz çizgi
  - "neon"    : Parlayan neon efekti (çift katmanlı glow)
  - "rainbow" : Gökkuşağı — renk her noktada değişir
"""

import cv2
import numpy as np
from typing import List, Tuple

# Fırça tipi sabitleri
BRUSH_NORMAL: str = "normal"
BRUSH_NEON: str = "neon"
BRUSH_RAINBOW: str = "rainbow"


class Stroke:
    """Tek bir çizim çizgisini temsil eden veri sınıfı."""

    def __init__(
        self,
        color: Tuple[int, int, int] = (255, 50, 120),
        thickness: int = 4,
        brush_type: str = BRUSH_NORMAL,
    ) -> None:
        """
        Yeni bir Stroke nesnesi oluşturur.

        Args:
            color: Çizgi rengi (BGR formatında).
            thickness: Çizgi kalınlığı (piksel).
            brush_type: Fırça tipi ("normal", "neon", "rainbow").
        """
        self.points: List[Tuple[int, int]] = []
        self.color: Tuple[int, int, int] = color
        self.thickness: int = thickness
        self.brush_type: str = brush_type

    def add_point(self, point: Tuple[int, int]) -> None:
        """Stroke'a yeni bir koordinat noktası ekler."""
        self.points.append(point)

    # ── Çizim (Render) ───────────────────────────────────────────────

    def draw(self, canvas: np.ndarray) -> None:
        """
        Fırça tipine göre stroke'u tuval üzerine çizer.

        Args:
            canvas: Üzerine çizim yapılacak numpy görüntü dizisi.
        """
        if len(self.points) < 2:
            if len(self.points) == 1:
                cv2.circle(canvas, self.points[0],
                           self.thickness // 2, self.color, cv2.FILLED)
            return

        if self.brush_type == BRUSH_NEON:
            self._draw_neon(canvas)
        elif self.brush_type == BRUSH_RAINBOW:
            self._draw_rainbow(canvas)
        else:
            self._draw_normal(canvas)

    def _draw_normal(self, canvas: np.ndarray) -> None:
        """Düz çizgi — standart render."""
        for i in range(1, len(self.points)):
            cv2.line(canvas, self.points[i - 1], self.points[i],
                     self.color, self.thickness, cv2.LINE_AA)

    def _draw_neon(self, canvas: np.ndarray) -> None:
        """
        Neon efekti — 3 katmanlı parlama.
        Dış katman: kalın, yarı-şeffaf halo.
        Orta katman: orta kalınlık.
        İç katman: ince, parlak çekirdek (beyaza yakın).
        """
        # Dış halo (geniş, soluk)
        glow_color = tuple(min(255, c // 2 + 30) for c in self.color)
        for i in range(1, len(self.points)):
            cv2.line(canvas, self.points[i - 1], self.points[i],
                     glow_color, self.thickness * 4, cv2.LINE_AA)

        # Orta katman (normal renk)
        for i in range(1, len(self.points)):
            cv2.line(canvas, self.points[i - 1], self.points[i],
                     self.color, self.thickness * 2, cv2.LINE_AA)

        # İç çekirdek (parlak beyaz)
        core_color = tuple(min(255, c + 120) for c in self.color)
        for i in range(1, len(self.points)):
            cv2.line(canvas, self.points[i - 1], self.points[i],
                     core_color, max(1, self.thickness // 2), cv2.LINE_AA)

    def _draw_rainbow(self, canvas: np.ndarray) -> None:
        """
        Gökkuşağı efekti — her segment farklı bir renkte.
        HSV hue değeri noktadan noktaya kayarak değişir.
        """
        total = len(self.points)
        for i in range(1, total):
            # Hue: 0-179 arası (OpenCV HSV), noktaya göre kayar
            hue: int = int((i / total) * 179)
            hsv_pixel = np.uint8([[[hue, 255, 255]]])
            bgr_pixel = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)
            segment_color = tuple(int(c) for c in bgr_pixel[0][0])

            cv2.line(canvas, self.points[i - 1], self.points[i],
                     segment_color, self.thickness, cv2.LINE_AA)

    # ── Geometri ─────────────────────────────────────────────────────

    def get_bounding_box(self) -> Tuple[int, int, int, int]:
        """
        Stroke'un sınırlayıcı kutusunu hesaplar.

        Returns:
            (min_x, min_y, max_x, max_y). Boş stroke için (0, 0, 0, 0).
        """
        if not self.points:
            return (0, 0, 0, 0)

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def translate(self, dx: int, dy: int) -> None:
        """Stroke'un tüm noktalarını (dx, dy) kadar öteler."""
        self.points = [(x + dx, y + dy) for x, y in self.points]

    @property
    def is_empty(self) -> bool:
        """Stroke boş mu?"""
        return len(self.points) == 0

    # ── Serileştirme ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """
        Stroke'u JSON-uyumlu sözlük olarak döndürür.
        API yanıtlarında kullanılır.
        """
        return {
            "points": self.points,
            "color": list(self.color),
            "thickness": self.thickness,
            "brush_type": self.brush_type,
            "point_count": len(self.points),
            "bounding_box": list(self.get_bounding_box()),
        }

    def __repr__(self) -> str:
        return (f"Stroke(points={len(self.points)}, color={self.color}, "
                f"brush={self.brush_type})")
