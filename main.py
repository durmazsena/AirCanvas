"""
main.py — AirCanvas Masaüstü Uygulaması

Web kamerasını açar ve AirCanvasEngine ile karesel işleme yapar.
Engine tüm mantığı (jest algılama, çizim, palet) yönetir.

Kısayollar:
  q — Çık
  c — Tuvali temizle
"""

import cv2
from engine import AirCanvasEngine


def main() -> None:
    """Kamera döngüsü — engine ile kare kare işleme."""

    # ── Kamera ───────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[HATA] Kamera açılamadı.")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[BİLGİ] Kamera: {w}x{h}")

    # ── Motor ────────────────────────────────────────────────────────
    engine = AirCanvasEngine(width=w, height=h)

    print("[BİLGİ] AirCanvas başlatıldı.")
    print("[BİLGİ] Jestler: 1 parmak→Çiz | 2 parmak→Gezin/Palet "
          "| Yumruk→Bekle | Açık el→Süpür→Sil | Pinch→Sürükle")

    # ── Döngü ────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)

        # Engine her şeyi halleder
        result = engine.process_frame(frame)

        cv2.imshow("AirCanvas", result["processed_frame"])

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            engine.clear()
            print("[BİLGİ] Tuval temizlendi (klavye).")

    # ── Temizlik ─────────────────────────────────────────────────────
    cap.release()
    engine.release()
    cv2.destroyAllWindows()
    print("[BİLGİ] AirCanvas kapatıldı.")


if __name__ == "__main__":
    main()
