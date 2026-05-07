"""
ui_palette.py — Sanal Araç Çubuğu (Estetik Yan Panel Tasarımı)

Sol kenar: Yuvarlak renk butonları (dikey sıralı)
Sağ kenar: Fırça tipi butonları (desen önizlemeli) + Kalınlık kontrolü

Seçim "dwell time" (üstünde bekleme) mantığıyla çalışır.
Parmak bir butonun üzerinde ~0.7sn tutulursa seçim onaylanır.
"""

import cv2
import math
import numpy as np
from typing import List, Tuple, Optional, Dict


# ── Fırça Tipleri ────────────────────────────────────────────────
BRUSH_NORMAL: str = "normal"
BRUSH_NEON: str = "neon"
BRUSH_RAINBOW: str = "rainbow"
BRUSH_ERASER: str = "eraser"

# ── Tasarım Sabitleri ────────────────────────────────────────────────
PANEL_WIDTH: int = 80            # Yan panel genişliği
BUTTON_RADIUS: int = 24          # Buton yarıçapı
BUTTON_SPACING: int = 70         # Butonlar arası dikey mesafe
PANEL_TOP_MARGIN: int = 60       # Üstten boşluk
DWELL_FRAMES: int = 20           # Seçim süresi (~0.7 sn @30fps)

# Kalınlık sınırları
MIN_THICKNESS: int = 2
MAX_THICKNESS: int = 16
THICKNESS_STEP: int = 2


class CircleButton:
    """Yuvarlak bir buton."""

    def __init__(
        self,
        cx: int, cy: int,
        radius: int,
        color: Tuple[int, int, int],
        label: str,
        button_type: str,   # "color", "brush", "thickness_up", "thickness_down"
        value: object,
    ) -> None:
        self.cx: int = cx
        self.cy: int = cy
        self.radius: int = radius
        self.color: Tuple[int, int, int] = color
        self.label: str = label
        self.button_type: str = button_type
        self.value: object = value

    def contains(self, point: Tuple[int, int]) -> bool:
        """Noktanın dairenin içinde olup olmadığını kontrol eder."""
        dx = point[0] - self.cx
        dy = point[1] - self.cy
        return (dx * dx + dy * dy) <= (self.radius + 8) ** 2  # +8 tolerans


class UIPalette:
    """Yan panellerde yuvarlak butonlar ile estetik araç çubuğu."""

    def __init__(self, frame_width: int, frame_height: int) -> None:
        self._frame_width: int = frame_width
        self._frame_height: int = frame_height
        self._buttons: List[CircleButton] = []

        # Dwell-time durumu
        self._hovered_button: Optional[CircleButton] = None
        self._dwell_counter: int = 0

        # Aktif seçimler
        self.active_color: Tuple[int, int, int] = (255, 50, 120)
        self.active_brush: str = BRUSH_NORMAL
        self.active_thickness: int = 4

        self._create_buttons()

    def _create_buttons(self) -> None:
        """Sol (renkler) ve sağ (fırçalar + kalınlık) panel butonlarını oluşturur."""
        cx_left: int = PANEL_WIDTH // 2       # Sol panel merkez X
        cx_right: int = self._frame_width - PANEL_WIDTH // 2  # Sağ panel merkez X

        # ── Sol Panel: Renkler ───────────────────────────────────────
        colors: List[Dict] = [
            {"color": (255, 50, 120),  "label": "Mor"},
            {"color": (255, 100, 0),   "label": "Mavi"},
            {"color": (0, 200, 255),   "label": "Turkuaz"},
            {"color": (0, 255, 0),     "label": "Yesil"},
            {"color": (0, 255, 255),   "label": "Sari"},
            {"color": (0, 100, 255),   "label": "Turuncu"},
            {"color": (50, 50, 255),   "label": "Kirmizi"},
            {"color": (255, 255, 255), "label": "Beyaz"},
        ]

        y: int = PANEL_TOP_MARGIN
        for c in colors:
            self._buttons.append(CircleButton(
                cx=cx_left, cy=y, radius=BUTTON_RADIUS,
                color=c["color"], label=c["label"],
                button_type="color", value=c["color"],
            ))
            y += BUTTON_SPACING

        # ── Sağ Panel: Fırçalar + Silgi ─────────────────────────────
        brushes: List[Dict] = [
            {"color": (200, 200, 200), "label": "Duz",     "value": BRUSH_NORMAL},
            {"color": (0, 255, 100),   "label": "Neon",    "value": BRUSH_NEON},
            {"color": (200, 100, 255), "label": "Gkksg",   "value": BRUSH_RAINBOW},
            {"color": (80, 80, 220),   "label": "Silgi",   "value": BRUSH_ERASER},
        ]

        y = PANEL_TOP_MARGIN
        for b in brushes:
            self._buttons.append(CircleButton(
                cx=cx_right, cy=y, radius=BUTTON_RADIUS,
                color=b["color"], label=b["label"],
                button_type="brush", value=b["value"],
            ))
            y += BUTTON_SPACING

        # ── Sağ Panel: Kalınlık Kontrolleri ──────────────────────────
        y += 20  # Ekstra boşluk

        # Kalınlık artır (+)
        self._buttons.append(CircleButton(
            cx=cx_right, cy=y, radius=BUTTON_RADIUS,
            color=(100, 200, 100), label="+",
            button_type="thickness_up", value=None,
        ))
        y += BUTTON_SPACING

        # Kalınlık azalt (-)
        self._buttons.append(CircleButton(
            cx=cx_right, cy=y, radius=BUTTON_RADIUS,
            color=(100, 100, 200), label="-",
            button_type="thickness_down", value=None,
        ))

    def is_in_panel_zone(self, point: Tuple[int, int]) -> bool:
        """Noktanın sol veya sağ panel bölgesinde olup olmadığını kontrol eder."""
        x = point[0]
        return x < PANEL_WIDTH or x > self._frame_width - PANEL_WIDTH

    def update(self, fingertip: Optional[Tuple[int, int]]) -> Optional[str]:
        """
        Her karede çağrılır. Dwell-time ile seçimi yönetir.

        Returns:
            Seçim yapıldıysa bilgi mesajı, yoksa None.
        """
        if fingertip is None:
            self._hovered_button = None
            self._dwell_counter = 0
            return None

        # Hangi butonun üzerinde?
        current: Optional[CircleButton] = None
        for btn in self._buttons:
            if btn.contains(fingertip):
                current = btn
                break

        if current is None:
            self._hovered_button = None
            self._dwell_counter = 0
            return None

        # Aynı buton mu?
        if current is self._hovered_button:
            self._dwell_counter += 1
        else:
            self._hovered_button = current
            self._dwell_counter = 1

        # Dwell süresi doldu mu?
        if self._dwell_counter >= DWELL_FRAMES:
            self._dwell_counter = 0
            return self._apply_selection(current)

        return None

    def _apply_selection(self, btn: CircleButton) -> str:
        """Seçimi uygular ve bilgi mesajı döndürür."""
        if btn.button_type == "color":
            self.active_color = btn.value
            return f"Renk: {btn.label}"

        elif btn.button_type == "brush":
            self.active_brush = btn.value
            return f"Firca: {btn.label}"

        elif btn.button_type == "thickness_up":
            self.active_thickness = min(MAX_THICKNESS,
                                        self.active_thickness + THICKNESS_STEP)
            return f"Kalinlik: {self.active_thickness}"

        elif btn.button_type == "thickness_down":
            self.active_thickness = max(MIN_THICKNESS,
                                        self.active_thickness - THICKNESS_STEP)
            return f"Kalinlik: {self.active_thickness}"

        return ""

    # ── Render ────────────────────────────────────────────────────────

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Yan panelleri ve butonları çizer."""
        self._draw_panel_backgrounds(frame)
        self._draw_buttons(frame)
        self._draw_thickness_preview(frame)
        return frame

    def _draw_panel_backgrounds(self, frame: np.ndarray) -> None:
        """Yarı-saydam panel arkaplanları."""
        overlay = frame.copy()
        h = self._frame_height

        # Sol panel
        cv2.rectangle(overlay, (0, 0), (PANEL_WIDTH, h), (20, 20, 20), cv2.FILLED)
        # Sağ panel
        cv2.rectangle(overlay, (self._frame_width - PANEL_WIDTH, 0),
                      (self._frame_width, h), (20, 20, 20), cv2.FILLED)

        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # İnce ayırıcı çizgiler
        cv2.line(frame, (PANEL_WIDTH, 0), (PANEL_WIDTH, h), (60, 60, 60), 1)
        cv2.line(frame, (self._frame_width - PANEL_WIDTH, 0),
                 (self._frame_width - PANEL_WIDTH, h), (60, 60, 60), 1)

    def _draw_buttons(self, frame: np.ndarray) -> None:
        """Tüm butonları çizer."""
        for btn in self._buttons:
            center = (btn.cx, btn.cy)

            # ── Buton gövdesi ────────────────────────────────────────
            if btn.button_type == "brush":
                self._draw_brush_preview(frame, btn)
            else:
                cv2.circle(frame, center, btn.radius, btn.color, cv2.FILLED, cv2.LINE_AA)

            # ── Aktif seçim göstergesi (parlak beyaz halka) ──────────
            is_active = False
            if btn.button_type == "color" and btn.value == self.active_color:
                is_active = True
            elif btn.button_type == "brush" and btn.value == self.active_brush:
                is_active = True

            if is_active:
                cv2.circle(frame, center, btn.radius + 4, (255, 255, 255), 3, cv2.LINE_AA)

            # ── Kalınlık butonları için etiket ───────────────────────
            if btn.button_type in ("thickness_up", "thickness_down"):
                cv2.putText(frame, btn.label,
                            (btn.cx - 8, btn.cy + 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (255, 255, 255), 2, cv2.LINE_AA)

            # ── Dwell ilerleme çemberi ───────────────────────────────
            if btn is self._hovered_button and self._dwell_counter > 0:
                progress = self._dwell_counter / DWELL_FRAMES
                angle = int(360 * progress)
                cv2.ellipse(frame, center,
                            (btn.radius + 8, btn.radius + 8),
                            -90, 0, angle,
                            (0, 255, 255), 3, cv2.LINE_AA)

    def _draw_brush_preview(self, frame: np.ndarray, btn: CircleButton) -> None:
        """Fırça butonuna desen önizlemesi çizer."""
        center = (btn.cx, btn.cy)
        r = btn.radius

        if btn.value == BRUSH_NORMAL:
            # Düz dolu daire
            cv2.circle(frame, center, r, (200, 200, 200), cv2.FILLED, cv2.LINE_AA)
            # İçine küçük düz çizgi önizlemesi
            cv2.line(frame, (btn.cx - r // 2, btn.cy),
                     (btn.cx + r // 2, btn.cy),
                     (80, 80, 80), 3, cv2.LINE_AA)

        elif btn.value == BRUSH_NEON:
            # Neon glow efekti — 3 katman
            cv2.circle(frame, center, r, (0, 80, 0), cv2.FILLED, cv2.LINE_AA)
            cv2.circle(frame, center, r - 4, (0, 160, 60), cv2.FILLED, cv2.LINE_AA)
            cv2.circle(frame, center, r - 10, (0, 255, 100), cv2.FILLED, cv2.LINE_AA)
            # İç parlama çizgisi
            cv2.line(frame, (btn.cx - r // 2, btn.cy),
                     (btn.cx + r // 2, btn.cy),
                     (200, 255, 200), 2, cv2.LINE_AA)

        elif btn.value == BRUSH_RAINBOW:
            # Gökkuşağı — 6 dilimli daire
            for i in range(6):
                angle_start = i * 60
                hue = int((i / 6) * 179)
                hsv = np.uint8([[[hue, 255, 255]]])
                bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                seg_color = tuple(int(c) for c in bgr[0][0])
                cv2.ellipse(frame, center, (r, r), 0,
                            angle_start, angle_start + 60,
                            seg_color, cv2.FILLED, cv2.LINE_AA)

        elif btn.value == BRUSH_ERASER:
            # Silgi ikonu — dikdörtgen gövde + lastik uç
            cv2.circle(frame, center, r, (60, 60, 60), cv2.FILLED, cv2.LINE_AA)

            # Silgi gövdesi (açık pembe dikdörtgen)
            body_x1 = btn.cx - r // 2 + 2
            body_y1 = btn.cy - r // 3
            body_x2 = btn.cx + r // 2 + 4
            body_y2 = btn.cy + r // 3
            cv2.rectangle(frame, (body_x1, body_y1), (body_x2, body_y2),
                          (180, 160, 220), cv2.FILLED)

            # Lastik uç (koyu pembe sol kısım)
            tip_x2 = body_x1 + (body_x2 - body_x1) // 3
            cv2.rectangle(frame, (body_x1, body_y1), (tip_x2, body_y2),
                          (100, 80, 200), cv2.FILLED)

            # Alt çizgi (silme çizgisi göstergesi)
            cv2.line(frame, (btn.cx - r // 2, body_y2 + 4),
                     (btn.cx + r // 2 + 2, body_y2 + 4),
                     (150, 150, 150), 1, cv2.LINE_AA)

    def _draw_thickness_preview(self, frame: np.ndarray) -> None:
        """Sağ panelin alt kısmında aktif kalınlık önizlemesi gösterir."""
        # Kalınlık butonlarının altında küçük bir önizleme dairesi
        cx = self._frame_width - PANEL_WIDTH // 2
        cy = PANEL_TOP_MARGIN + BUTTON_SPACING * 5 + 40  # Butonların altı

        # Kalınlık değeri yazısı
        cv2.putText(frame, f"{self.active_thickness}px",
                    (cx - 18, cy - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (180, 180, 180), 1, cv2.LINE_AA)

        # Aktif renk + kalınlık ile örnek daire
        cv2.circle(frame, (cx, cy + 5), self.active_thickness,
                   self.active_color, cv2.FILLED, cv2.LINE_AA)

    @property
    def is_eraser(self) -> bool:
        """Şu an silgi modu aktif mi?"""
        return self.active_brush == BRUSH_ERASER

    @property
    def dwell_active(self) -> bool:
        """Şu an bekleme aktif mi?"""
        return self._hovered_button is not None and self._dwell_counter > 0
