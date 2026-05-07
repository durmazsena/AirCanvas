"""
canvas_manager.py — Tuval Yöneticisi (Object-Based Rendering)

Bu modül çizim tuvalini (canvas) yönetir.
Phase 2-3: Nesne tabanlı görüntüleme + Jest tabanlı etkileşim.

Sorumlulukları:
  - Stroke nesnelerini bir liste olarak yönetme
  - Aktif stroke'a nokta ekleme / yeni stroke başlatma
  - Her karede tüm stroke'ları yeniden çizme (render)
  - Maskeyi kamera karesinin üzerine bindirme (overlay)
  - Ekranı temizleme (tüm stroke'ları silme)
  - Pinch ile stroke seçme ve sürükleme (grab & drag)
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from stroke import Stroke


class CanvasManager:
    """Stroke nesneleri üzerinden nesne tabanlı tuval yönetimi."""

    # Varsayılan çizim rengi: Mavi-Mor tonunda parlak bir renk (BGR)
    DEFAULT_COLOR: Tuple[int, int, int] = (255, 50, 120)
    DEFAULT_THICKNESS: int = 4

    def __init__(self, width: int, height: int) -> None:
        """
        Tuval yöneticisini başlatır.

        Args:
            width: Tuval genişliği (piksel).
            height: Tuval yüksekliği (piksel).
        """
        self._width: int = width
        self._height: int = height

        # Tamamlanmış stroke'ların listesi
        self._strokes: List[Stroke] = []

        # Şu an çizilmekte olan aktif stroke (None = çizim yapılmıyor)
        self._active_stroke: Optional[Stroke] = None

        # Aktif çizim ayarları
        self._color: Tuple[int, int, int] = self.DEFAULT_COLOR
        self._thickness: int = self.DEFAULT_THICKNESS
        self._brush_type: str = "normal"

        # ── Phase 3: Grab & Drag durumu ──────────────────────────────
        # Şu an tutularak sürüklenen stroke (None = sürükleme yok)
        self._grabbed_stroke: Optional[Stroke] = None
        # Sürükleme sırasında önceki referans noktası (delta hesabı için)
        self._drag_prev_point: Optional[Tuple[int, int]] = None

    def add_point(self, point: Tuple[int, int]) -> None:
        """
        Yeni bir çizim noktası ekler. Eğer aktif stroke yoksa
        yeni bir stroke başlatır.

        Args:
            point: (x, y) piksel koordinatı.
        """
        if self._active_stroke is None:
            # Yeni bir stroke başlat
            self._active_stroke = Stroke(
                color=self._color,
                thickness=self._thickness,
                brush_type=self._brush_type,
            )

        self._active_stroke.add_point(point)

    def lift_pen(self) -> None:
        """
        Kalemi kaldırır — parmak ucu algılanmadığında çağrılır.
        Aktif stroke'u tamamlanmış listeye taşır ve yeni bir
        stroke başlamaya hazırlar.
        """
        if self._active_stroke is not None and not self._active_stroke.is_empty:
            self._strokes.append(self._active_stroke)
        self._active_stroke = None

    def render(self) -> np.ndarray:
        """
        Tüm stroke'ları sıfırdan temiz bir maske üzerine çizer.
        Her karede çağrılır — nesne tabanlı rendering'in kalbi.

        Returns:
            Tüm stroke'ların çizildiği tuval maskesi (siyah arkaplan).
        """
        # Her karede temiz bir maske oluştur
        canvas: np.ndarray = np.zeros(
            (self._height, self._width, 3), dtype=np.uint8
        )

        # Tamamlanmış tüm stroke'ları çiz
        for stroke in self._strokes:
            stroke.draw(canvas)

        # Aktif (çizilmekte olan) stroke'u da çiz
        if self._active_stroke is not None:
            self._active_stroke.draw(canvas)

        return canvas

    def overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Tuval maskesini kamera karesinin üzerine bindirir.
        Maskedeki siyah pikseller (çizim olmayan alanlar) şeffaf
        olarak değerlendirilir.

        Args:
            frame: Üzerine bindirme yapılacak BGR kare.

        Returns:
            Çizim katmanı eklenmiş yeni kare.
        """
        # Stroke'ları temiz bir maskeye çiz
        canvas: np.ndarray = self.render()

        # Maskedeki siyah olmayan piksellerin bulunduğu bölgeyi tespit et
        gray: np.ndarray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)

        # Kare üzerinde çizim olan bölgeleri maskeyle değiştir
        mask_inv: np.ndarray = cv2.bitwise_not(mask)
        frame_bg: np.ndarray = cv2.bitwise_and(frame, frame, mask=mask_inv)
        canvas_fg: np.ndarray = cv2.bitwise_and(canvas, canvas, mask=mask)

        combined: np.ndarray = cv2.add(frame_bg, canvas_fg)
        return combined

    def clear(self) -> None:
        """Tüm stroke'ları temizler."""
        self._strokes.clear()
        self._active_stroke = None

    @property
    def strokes(self) -> List[Stroke]:
        """Tamamlanmış stroke listesini döndürür (okunabilir erişim)."""
        return self._strokes

    @property
    def stroke_count(self) -> int:
        """Toplam stroke sayısını döndürür (aktif dahil)."""
        count: int = len(self._strokes)
        if self._active_stroke is not None:
            count += 1
        return count

    def set_color(self, color: Tuple[int, int, int]) -> None:
        """
        Aktif çizim rengini değiştirir. Yeni stroke'lar bu renkte olacak.

        Args:
            color: Yeni renk (BGR formatında).
        """
        self._color = color

    def set_thickness(self, thickness: int) -> None:
        """
        Aktif çizim kalınlığını değiştirir.

        Args:
            thickness: Yeni kalınlık (piksel).
        """
        self._thickness = thickness

    def set_brush_type(self, brush_type: str) -> None:
        """
        Aktif fırça tipini değiştirir.

        Args:
            brush_type: Fırça tipi ("normal", "neon", "rainbow").
        """
        self._brush_type = brush_type

    # ── Phase 4: Silgi ───────────────────────────────────────────────
    #
    # Silgi, stroke noktalarını fiziksel olarak kaldırır.
    # Silgi yarıçapı içindeki noktalar silinir,
    # stroke ortasından bölünürse iki ayrı stroke'a ayrılır.
    # Bu sayede sürükleme (drag) ile çakışma olmaz.

    ERASER_RADIUS: int = 20  # Silgi boyutu (piksel)

    def erase_at(self, point: Tuple[int, int]) -> None:
        """
        Verilen noktanın çevresindeki stroke noktalarını gerçekten siler.
        Stroke ortasından silinirse, stroke ikiye (veya daha fazlasına) bölünür.

        Args:
            point: (x, y) silgi merkez koordinatı.
        """
        ex, ey = point
        r_sq: int = self.ERASER_RADIUS ** 2
        new_strokes: List[Stroke] = []

        for stroke in self._strokes:
            # Noktaları silgi dışında/kalanlar olarak grupla
            segments: List[List[Tuple[int, int]]] = []
            current_seg: List[Tuple[int, int]] = []

            for px, py in stroke.points:
                dist_sq = (px - ex) ** 2 + (py - ey) ** 2
                if dist_sq > r_sq:
                    # Silgi dışında — koru
                    current_seg.append((px, py))
                else:
                    # Silgi içinde — sil, segmenti bitir
                    if current_seg:
                        segments.append(current_seg)
                        current_seg = []

            # Son segmenti ekle
            if current_seg:
                segments.append(current_seg)

            # Her segmenti ayrı bir stroke olarak oluştur
            for seg in segments:
                if len(seg) >= 2:
                    new_stroke = Stroke(
                        color=stroke.color,
                        thickness=stroke.thickness,
                        brush_type=stroke.brush_type,
                    )
                    new_stroke.points = seg
                    new_strokes.append(new_stroke)

        self._strokes = new_strokes

    # ── Phase 3: Grab & Drag (Tut ve Sürükle) ───────────────────────

    # Bounding box etrafındaki tolerans (piksel) — seçimi kolaylaştırır
    GRAB_MARGIN: int = 25

    def find_stroke_at(self, point: Tuple[int, int]) -> Optional[Stroke]:
        """
        Verilen noktaya en yakın (üstteki) stroke'u bulur.
        Bounding box + tolerans ile hit-test yapar.
        En son çizilen stroke önceliklidir (üstte görünür).

        Args:
            point: (x, y) piksel koordinatı (pinch orta noktası).

        Returns:
            Bulunan Stroke nesnesi veya None.
        """
        x, y = point

        # Ters sırada ara — en son çizilen (üstteki) stroke önce bulunur
        for stroke in reversed(self._strokes):
            min_x, min_y, max_x, max_y = stroke.get_bounding_box()

            # Tolerans ekle
            if (min_x - self.GRAB_MARGIN <= x <= max_x + self.GRAB_MARGIN
                    and min_y - self.GRAB_MARGIN <= y <= max_y + self.GRAB_MARGIN):
                return stroke

        return None

    def start_drag(self, grab_point: Tuple[int, int]) -> bool:
        """
        Pinch algılandığında sürükleme başlatır.
        grab_point'teki stroke'u bulup tutar.

        Args:
            grab_point: Pinch orta noktası (x, y).

        Returns:
            True: Bir stroke tutuldu. False: O noktada stroke yok.
        """
        stroke = self.find_stroke_at(grab_point)
        if stroke is not None:
            self._grabbed_stroke = stroke
            self._drag_prev_point = grab_point
            return True
        return False

    def update_drag(self, current_point: Tuple[int, int]) -> None:
        """
        Sürükleme devam ederken çağrılır.
        Tutulan stroke'u delta (fark) kadar ötelenmiş halde günceller.

        Args:
            current_point: Şu anki pinch orta noktası (x, y).
        """
        if self._grabbed_stroke is None or self._drag_prev_point is None:
            return

        # Delta hesapla
        dx: int = current_point[0] - self._drag_prev_point[0]
        dy: int = current_point[1] - self._drag_prev_point[1]

        # Stroke'u ötelendir
        self._grabbed_stroke.translate(dx, dy)

        # Referans noktasını güncelle
        self._drag_prev_point = current_point

    def end_drag(self) -> None:
        """Sürükleme işlemini sonlandırır."""
        self._grabbed_stroke = None
        self._drag_prev_point = None

    @property
    def is_dragging(self) -> bool:
        """Şu an bir stroke sürükleniyor mu?"""
        return self._grabbed_stroke is not None

