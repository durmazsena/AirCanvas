"""
main.py — AirCanvas Ana Giriş Noktası

Uygulama döngüsü:
  1. Web kamerasını açar.
  2. Her kareyi HandTracker'a gönderir.
  3. Jest → Durum makinesi ile aksiyonu belirler.
  4. Palet etkileşimini yönetir (dwell-time ile renk/fırça seçimi).
  5. Sonucu ekranda gösterir.

Jestler:
  [1,0,0,0]  İşaret parmağı    → Çizim (DRAW)
  [0,0,0,0]  Yumruk            → Bekleme (IDLE)
  [1,1,0,0]  İşaret + Orta     → Gezinme (NAVIGATE) + Palet etkileşimi
  [1,1,1,1]  Tüm parmaklar     → Temizle (CLEAR)
  Pinch      Baş + İşaret      → Sürükle (PINCH)

Kısayollar:
  q — Çık
  c — Temizle
"""

import cv2
import numpy as np
from hand_tracker import HandTracker
from canvas_manager import CanvasManager
from ui_palette import UIPalette, PANEL_WIDTH

# ── Debounce Sabitleri ───────────────────────────────────────────────
DRAW_DEBOUNCE: int = 5
PINCH_DEBOUNCE: int = 5

# Süpürme ile temizleme ayarı (avucuyla ekranı silme hareketi)
SWEEP_RATIO: float = 0.5   # Ekran genişliğinin yüzde kaçı kaplanmalı

# ── Renk Paleti (BGR) ────────────────────────────────────────────────
COLORS: dict = {
    "DRAW":     (0, 255, 0),
    "IDLE":     (128, 128, 128),
    "NAVIGATE": (255, 200, 0),
    "CLEAR":    (0, 0, 255),
    "PINCH":    (255, 0, 255),
    "NONE":     (100, 100, 100),
}


def main() -> None:
    """Ana uygulama döngüsü."""

    # ── Kamera ───────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[HATA] Kamera açılamadı.")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[BİLGİ] Kamera: {w}x{h}")

    # ── Modüller ─────────────────────────────────────────────────────
    tracker = HandTracker(max_hands=1)
    canvas = CanvasManager(width=w, height=h)
    palette = UIPalette(frame_width=w, frame_height=h)

    # ── Debounce Sayaçları ─────────────────────────────────────────
    draw_count: int = 0
    pinch_count: int = 0

    # ── Süpürme Takibi (temizleme jesti) ────────────────────────
    sweep_start_x: int = -1     # Süpürme başlangıç X konumu
    sweep_min_x: int = 99999    # Hareketteki minimum X
    sweep_max_x: int = 0        # Hareketteki maksimum X

    print("[BİLGİ] AirCanvas Phase 4 başlatıldı.")
    print("[BİLGİ] Jestler: 1 parmak→Çiz | 2 parmak→Gezin/Palet | Yumruk→Bekle | Açık el→Sil | Pinch→Sürükle")

    # ── Döngü ────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)

        # ── Algılama ─────────────────────────────────────────────────
        result = tracker.process(frame)
        gesture = tracker.get_gesture(result)
        fingertip = tracker.get_index_finger_tip(result, w, h)
        fingers = tracker.get_finger_states(result)

        # ── Debounce Güncelleme ──────────────────────────────────────
        draw_count = draw_count + 1 if gesture == "DRAW" else 0
        pinch_count = pinch_count + 1 if gesture == "PINCH" else 0

        # Süpürme takibi (CLEAR jesti için)
        if gesture == "CLEAR" and fingertip is not None:
            cx = fingertip[0]
            if sweep_start_x < 0:
                # Süpürme başlıyor
                sweep_start_x = cx
                sweep_min_x = cx
                sweep_max_x = cx
            else:
                sweep_min_x = min(sweep_min_x, cx)
                sweep_max_x = max(sweep_max_x, cx)
        else:
            # CLEAR dışında — süpürme sıfırla
            sweep_start_x = -1
            sweep_min_x = 99999
            sweep_max_x = 0

        # Süpürme mesafesi
        sweep_dist = sweep_max_x - sweep_min_x
        sweep_threshold = int(w * SWEEP_RATIO)

        # ── Palet Etkileşimi (NAVIGATE modunda) ──────────────────────
        # Palet üzerinde dwell-time ile renk/fırça seçimi
        palette_tip = fingertip if gesture == "NAVIGATE" else None
        selection = palette.update(palette_tip)

        if selection is not None:
            # Seçim yapıldı — canvas'a uygula
            canvas.set_color(palette.active_color)
            canvas.set_brush_type(palette.active_brush)
            canvas.set_thickness(palette.active_thickness)
            print(f"[BİLGİ] {selection} seçildi.")

        # Panel bölgesinde çizim engelleme
        in_panel = fingertip is not None and palette.is_in_panel_zone(fingertip)

        # ── Durum Makinesi ───────────────────────────────────────────

        if gesture == "DRAW" and draw_count >= DRAW_DEBOUNCE:
            # ÇİZİM veya SİLGİ — debounce onaylı
            if in_panel:
                canvas.lift_pen()
            elif fingertip is not None:
                if palette.is_eraser:
                    # SİLGİ MODU — noktaları gerçekten sil
                    canvas.lift_pen()
                    canvas.erase_at(fingertip)
                    cv2.circle(frame, fingertip, canvas.ERASER_RADIUS, (0, 0, 255), 2)
                    cv2.circle(frame, fingertip, 2, (0, 0, 255), cv2.FILLED)
                else:
                    # NORMAL ÇİZİM
                    canvas.add_point(fingertip)
                    cv2.circle(frame, fingertip, 8, (0, 255, 0), cv2.FILLED)

        elif gesture == "DRAW":
            # ÇİZİM BEKLEMESİ — debounce dolmadı
            canvas.lift_pen()
            if fingertip is not None:
                cv2.circle(frame, fingertip, 8, (0, 200, 200), 2)

        elif gesture == "NAVIGATE":
            # GEZİNME — 2 parmak açık, palet etkileşimi aktif
            canvas.lift_pen()
            if canvas.is_dragging:
                canvas.end_drag()
            if fingertip is not None:
                cv2.circle(frame, fingertip, 12, (255, 200, 0), 2)

        elif gesture == "PINCH" and pinch_count >= PINCH_DEBOUNCE:
            # SÜRÜKLEME — debounce onaylı
            canvas.lift_pen()
            midpoint = tracker.get_thumb_index_midpoint(result, w, h)
            if midpoint is not None:
                if not canvas.is_dragging:
                    if canvas.start_drag(midpoint):
                        print("[BİLGİ] Stroke yakalandı.")
                else:
                    canvas.update_drag(midpoint)
                cv2.circle(frame, midpoint, 10, (255, 0, 255), cv2.FILLED)

        elif gesture == "PINCH":
            # SÜRÜKLEME BEKLEMESİ
            canvas.lift_pen()

        elif gesture == "CLEAR" and sweep_dist >= sweep_threshold:
            # TEMİZLE — süpürme onaylı
            canvas.lift_pen()
            if canvas.is_dragging:
                canvas.end_drag()
            canvas.clear()
            print("[BİLGİ] Tuval temizlendi (süpürme).")
            sweep_start_x = -1
            sweep_min_x = 99999
            sweep_max_x = 0

        elif gesture == "IDLE":
            # BEKLEME
            canvas.lift_pen()
            if canvas.is_dragging:
                canvas.end_drag()

        else:
            # EL YOK veya diğer
            canvas.lift_pen()
            if canvas.is_dragging:
                canvas.end_drag()

        # ── Görselleştirme ───────────────────────────────────────────
        tracker.draw_landmarks(frame, result)
        output = canvas.overlay(frame)
        palette.render(output)

        # ── HUD (üst orta) ────────────────────────────────────────────
        color = COLORS.get(gesture, (255, 255, 255))
        finger_str = str(fingers) if fingers else "[-]"
        hud_x = PANEL_WIDTH + 10

        cv2.putText(output, f"Mod: {gesture} | Parmaklar: {finger_str}",
                    (hud_x, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        cv2.putText(output, f"Stroke: {canvas.stroke_count} | Firca: {palette.active_brush} | Kalinlik: {palette.active_thickness}px",
                    (hud_x, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

        if gesture == "DRAW" and draw_count < DRAW_DEBOUNCE:
            cv2.putText(output, f"Cizim: {draw_count}/{DRAW_DEBOUNCE}",
                        (hud_x, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 200), 2, cv2.LINE_AA)

        if gesture == "CLEAR" and sweep_dist > 0 and sweep_dist < sweep_threshold:
            pct = int((sweep_dist / sweep_threshold) * 100)
            cv2.putText(output, f"Supurme: %{pct}",
                        (hud_x, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)

        # ── Göster ───────────────────────────────────────────────────
        cv2.imshow("AirCanvas", output)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            canvas.clear()
            print("[BİLGİ] Tuval temizlendi (klavye).")

    # ── Temizlik ─────────────────────────────────────────────────────
    cap.release()
    tracker.release()
    cv2.destroyAllWindows()
    print("[BİLGİ] AirCanvas kapatıldı.")


if __name__ == "__main__":
    main()
