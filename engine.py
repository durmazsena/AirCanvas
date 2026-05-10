"""
engine.py — AirCanvas İşleme Motoru

main.py'deki tüm işleme mantığını kapsülleyen durum-tutan (stateful) sınıf.
Tek bir frame alır, jest algılama + çizim + palet etkileşimi uygular,
sonucu hem görsel (frame) hem de veri (JSON) olarak döndürür.

Kullanım:
    engine = AirCanvasEngine(width=1920, height=1080)
    result = engine.process_frame(frame)
    # result["processed_frame"]  → çizim katmanlı BGR frame
    # result["gesture"]          → "DRAW", "IDLE", "NAVIGATE", ...
    # result["strokes"]          → [{"points": [...], ...}, ...]
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

from hand_tracker import HandTracker
from canvas_manager import CanvasManager
from ui_palette import UIPalette, PANEL_WIDTH


# ── Sabitler ─────────────────────────────────────────────────────────
DRAW_DEBOUNCE: int = 5
PINCH_DEBOUNCE: int = 5
SWEEP_RATIO: float = 0.5

# HUD renkleri (BGR)
HUD_COLORS: Dict[str, Tuple[int, int, int]] = {
    "DRAW":     (0, 255, 0),
    "IDLE":     (128, 128, 128),
    "NAVIGATE": (255, 200, 0),
    "CLEAR":    (0, 0, 255),
    "PINCH":    (255, 0, 255),
    "NONE":     (100, 100, 100),
}


class AirCanvasEngine:
    """
    AirCanvas işleme motoru.

    Tek bir oturum için tüm durumu (stroke'lar, debounce sayaçları,
    palet seçimleri) yönetir. Her karede `process_frame()` çağrılır.
    """

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        """
        Motoru başlatır.

        Args:
            width: Frame genişliği (piksel).
            height: Frame yüksekliği (piksel).
        """
        self._width: int = width
        self._height: int = height

        # Alt modüller
        self._tracker: HandTracker = HandTracker(max_hands=1)
        self._canvas: CanvasManager = CanvasManager(width=width, height=height)
        self._palette: UIPalette = UIPalette(frame_width=width, frame_height=height)

        # Debounce sayaçları
        self._draw_count: int = 0
        self._pinch_count: int = 0

        # Süpürme (temizleme jesti) durumu
        self._sweep_start_x: int = -1
        self._sweep_min_x: int = 99999
        self._sweep_max_x: int = 0

        # Son işlenen karenin bilgileri
        self._last_gesture: str = "NONE"
        self._last_fingers: Optional[List[int]] = None

    # ── Ana İşleme ───────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Tek bir BGR frame'i işler.

        Sırasıyla: el algılama → jest tespiti → debounce → palet →
        durum makinesi → render → HUD → sonuç döndürme.

        Args:
            frame: BGR formatında numpy dizisi (kamera karesi).

        Returns:
            İşleme sonuçları sözlüğü:
                processed_frame: Çizim + palet + HUD eklenmiş frame
                gesture: Algılanan jest ("DRAW", "IDLE", ...)
                fingers: Parmak durumu listesi [1,0,0,0]
                strokes: Tüm stroke'ların JSON listesi
                active_color: Aktif renk [B, G, R]
                active_brush: Aktif fırça tipi
                active_thickness: Aktif kalınlık
                stroke_count: Toplam stroke sayısı
                is_eraser: Silgi modu aktif mi
        """
        # ── 1. Algılama ──────────────────────────────────────────────
        result = self._tracker.process(frame)
        gesture = self._tracker.get_gesture(result)
        fingertip = self._tracker.get_index_finger_tip(
            result, self._width, self._height
        )
        fingers = self._tracker.get_finger_states(result)

        self._last_gesture = gesture
        self._last_fingers = fingers

        # ── 2. Debounce ──────────────────────────────────────────────
        self._draw_count = self._draw_count + 1 if gesture == "DRAW" else 0
        self._pinch_count = self._pinch_count + 1 if gesture == "PINCH" else 0

        # ── 3. Süpürme Takibi ────────────────────────────────────────
        sweep_dist = self._update_sweep(gesture, fingertip)
        sweep_threshold = int(self._width * SWEEP_RATIO)

        # ── 4. Palet Etkileşimi ──────────────────────────────────────
        palette_tip = fingertip if gesture == "NAVIGATE" else None
        selection = self._palette.update(palette_tip)
        if selection is not None:
            self._apply_palette_selection()

        in_panel = (fingertip is not None
                    and self._palette.is_in_panel_zone(fingertip))

        # ── 5. Durum Makinesi ────────────────────────────────────────
        self._handle_gesture(
            gesture, fingertip, frame,
            in_panel, sweep_dist, sweep_threshold,
            result,
        )

        # ── 6. Render ────────────────────────────────────────────────
        self._tracker.draw_landmarks(frame, result)
        output = self._canvas.overlay(frame)
        self._palette.render(output)
        self._draw_hud(output, gesture, fingers, sweep_dist, sweep_threshold)

        # ── 7. Sonuç ─────────────────────────────────────────────────
        return {
            "processed_frame": output,
            "gesture": gesture,
            "fingers": fingers if fingers else [],
            "strokes": self.get_strokes_json(),
            "active_color": list(self._palette.active_color),
            "active_brush": self._palette.active_brush,
            "active_thickness": self._palette.active_thickness,
            "stroke_count": self._canvas.stroke_count,
            "is_eraser": self._palette.is_eraser,
        }

    # ── Durum Makinesi ───────────────────────────────────────────────

    def _handle_gesture(
        self,
        gesture: str,
        fingertip: Optional[Tuple[int, int]],
        frame: np.ndarray,
        in_panel: bool,
        sweep_dist: int,
        sweep_threshold: int,
        tracker_result: object,
    ) -> None:
        """Jest'e göre uygun aksiyonu çalıştırır."""

        if gesture == "DRAW" and self._draw_count >= DRAW_DEBOUNCE:
            self._on_draw(fingertip, frame, in_panel)

        elif gesture == "DRAW":
            self._canvas.lift_pen()
            if fingertip is not None:
                cv2.circle(frame, fingertip, 8, (0, 200, 200), 2)

        elif gesture == "NAVIGATE":
            self._canvas.lift_pen()
            if self._canvas.is_dragging:
                self._canvas.end_drag()
            if fingertip is not None:
                cv2.circle(frame, fingertip, 12, (255, 200, 0), 2)

        elif gesture == "PINCH" and self._pinch_count >= PINCH_DEBOUNCE:
            self._on_pinch(tracker_result, frame)

        elif gesture == "PINCH":
            self._canvas.lift_pen()

        elif gesture == "CLEAR" and sweep_dist >= sweep_threshold:
            self._on_clear()

        else:
            # IDLE veya tanınmayan jest
            self._canvas.lift_pen()
            if self._canvas.is_dragging:
                self._canvas.end_drag()

    def _on_draw(
        self,
        fingertip: Optional[Tuple[int, int]],
        frame: np.ndarray,
        in_panel: bool,
    ) -> None:
        """Çizim veya silgi modunu işler."""
        if in_panel:
            self._canvas.lift_pen()
        elif fingertip is not None:
            if self._palette.is_eraser:
                self._canvas.lift_pen()
                self._canvas.erase_at(fingertip)
                cv2.circle(frame, fingertip,
                           self._canvas.ERASER_RADIUS, (0, 0, 255), 2)
                cv2.circle(frame, fingertip, 2, (0, 0, 255), cv2.FILLED)
            else:
                self._canvas.add_point(fingertip)
                cv2.circle(frame, fingertip, 8, (0, 255, 0), cv2.FILLED)

    def _on_pinch(self, tracker_result: object, frame: np.ndarray) -> None:
        """Pinch (sürükleme) modunu işler."""
        self._canvas.lift_pen()
        midpoint = self._tracker.get_thumb_index_midpoint(
            tracker_result, self._width, self._height
        )
        if midpoint is not None:
            if not self._canvas.is_dragging:
                self._canvas.start_drag(midpoint)
            else:
                self._canvas.update_drag(midpoint)
            cv2.circle(frame, midpoint, 10, (255, 0, 255), cv2.FILLED)

    def _on_clear(self) -> None:
        """Tuvali temizler ve süpürme durumunu sıfırlar."""
        self._canvas.lift_pen()
        if self._canvas.is_dragging:
            self._canvas.end_drag()
        self._canvas.clear()
        self._reset_sweep()

    # ── Süpürme Takibi ───────────────────────────────────────────────

    def _update_sweep(
        self, gesture: str, fingertip: Optional[Tuple[int, int]]
    ) -> int:
        """Süpürme mesafesini günceller ve döndürür."""
        if gesture == "CLEAR" and fingertip is not None:
            cx = fingertip[0]
            if self._sweep_start_x < 0:
                self._sweep_start_x = cx
                self._sweep_min_x = cx
                self._sweep_max_x = cx
            else:
                self._sweep_min_x = min(self._sweep_min_x, cx)
                self._sweep_max_x = max(self._sweep_max_x, cx)
        else:
            self._reset_sweep()

        return self._sweep_max_x - self._sweep_min_x

    def _reset_sweep(self) -> None:
        """Süpürme durumunu sıfırlar."""
        self._sweep_start_x = -1
        self._sweep_min_x = 99999
        self._sweep_max_x = 0

    # ── Palet ────────────────────────────────────────────────────────

    def _apply_palette_selection(self) -> None:
        """Palette yapılan seçimi canvas'a uygular."""
        self._canvas.set_color(self._palette.active_color)
        self._canvas.set_brush_type(self._palette.active_brush)
        self._canvas.set_thickness(self._palette.active_thickness)

    # ── HUD ──────────────────────────────────────────────────────────

    def _draw_hud(
        self,
        output: np.ndarray,
        gesture: str,
        fingers: Optional[List[int]],
        sweep_dist: int,
        sweep_threshold: int,
    ) -> None:
        """Ekrana durum bilgilerini yazar."""
        color = HUD_COLORS.get(gesture, (255, 255, 255))
        finger_str = str(fingers) if fingers else "[-]"
        hud_x = PANEL_WIDTH + 10

        cv2.putText(
            output, f"Mod: {gesture} | Parmaklar: {finger_str}",
            (hud_x, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA,
        )

        brush = self._palette.active_brush
        thickness = self._palette.active_thickness
        cv2.putText(
            output,
            f"Stroke: {self._canvas.stroke_count} | Firca: {brush} | Kalinlik: {thickness}px",
            (hud_x, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (200, 200, 200), 1, cv2.LINE_AA,
        )

        if gesture == "DRAW" and self._draw_count < DRAW_DEBOUNCE:
            cv2.putText(
                output, f"Cizim: {self._draw_count}/{DRAW_DEBOUNCE}",
                (hud_x, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 200, 200), 2, cv2.LINE_AA,
            )

        if gesture == "CLEAR" and 0 < sweep_dist < sweep_threshold:
            pct = int((sweep_dist / sweep_threshold) * 100)
            cv2.putText(
                output, f"Supurme: %{pct}",
                (hud_x, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 255), 2, cv2.LINE_AA,
            )

    # ── Veri Erişim Metotları ────────────────────────────────────────

    def get_strokes_json(self) -> List[dict]:
        """Tüm stroke'ları JSON-uyumlu liste olarak döndürür."""
        return [stroke.to_dict() for stroke in self._canvas.strokes]

    def clear(self) -> None:
        """Tuvali programatik olarak temizler."""
        self._canvas.clear()
        self._reset_sweep()

    def set_color(self, color: Tuple[int, int, int]) -> None:
        """Rengi programatik olarak değiştirir (API kullanımı için)."""
        self._palette.active_color = color
        self._canvas.set_color(color)

    def set_brush(self, brush_type: str) -> None:
        """Fırça tipini programatik olarak değiştirir."""
        self._palette.active_brush = brush_type
        self._canvas.set_brush_type(brush_type)

    def set_thickness(self, thickness: int) -> None:
        """Kalınlığı programatik olarak değiştirir."""
        self._palette.active_thickness = thickness
        self._canvas.set_thickness(thickness)

    def release(self) -> None:
        """MediaPipe kaynaklarını serbest bırakır."""
        self._tracker.release()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height
