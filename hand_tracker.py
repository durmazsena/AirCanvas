"""
hand_tracker.py — MediaPipe Hand Landmarker Sarmalayıcı (Wrapper)

Bu modül MediaPipe Tasks API (HandLandmarker) çözümünü yönetir.
Dışarıya SADECE temizlenmiş veri döndürür:
  - İşaret parmağı ucu koordinatları (Landmark 8)
  - Parmak durumu dizisi [Başparmak, İşaret, Orta, Yüzük, Serçe]
  - Algılanan jest bilgisi (DRAW, IDLE, NAVIGATE, CLEAR, PINCH)
  - Pinch mesafesi

Phase 3: Jest tabanlı durum makinesi ve parmak durum algılama.
Not: MediaPipe >= 0.10.x sürümlerinde mp.solutions kaldırıldı,
     bunun yerine mp.tasks.python.vision API'si kullanılır.
"""

import math
import os
import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Optional, Tuple, List

# ── Landmark İndeksleri ──────────────────────────────────────────────
# Parmak ucu (Tip) landmark'ları
THUMB_TIP: int = 4
INDEX_FINGER_TIP: int = 8
MIDDLE_FINGER_TIP: int = 12
RING_FINGER_TIP: int = 16
PINKY_TIP: int = 20

# Parmak alt eklem (PIP / IP) landmark'ları — açık/kapalı karşılaştırması için
THUMB_IP: int = 3        # Başparmak: IP eklemi (yatay karşılaştırma)
INDEX_FINGER_PIP: int = 6
MIDDLE_FINGER_PIP: int = 10
RING_FINGER_PIP: int = 14
PINKY_PIP: int = 18

# ── Jest Sabitleri ───────────────────────────────────────────────────
PINCH_THRESHOLD: float = 0.05  # Normalize mesafe eşiği (pinch algılama)


class HandTracker:
    """MediaPipe HandLandmarker (Tasks API) ile el eklem noktalarını tespit eden sınıf."""

    def __init__(
        self,
        model_path: str = "hand_landmarker.task",
        max_hands: int = 1,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.7,
    ) -> None:
        """
        HandTracker'ı başlatır.

        Args:
            model_path: HandLandmarker .task model dosyasının yolu.
            max_hands: Aynı anda takip edilecek maksimum el sayısı.
            detection_confidence: El algılama için minimum güven eşiği.
            tracking_confidence: El takibi için minimum güven eşiği.
        """
        # Model dosyasının varlığını kontrol et
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"[HATA] Model dosyası bulunamadı: '{model_path}'. "
                "Lütfen hand_landmarker.task dosyasını proje dizinine indirin."
            )

        # VIDEO modunda yapılandır (kare kare sıralı işleme)
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

        # Kare zaman damgası sayacı (VIDEO modu için gerekli, ms cinsinden)
        self._timestamp_ms: int = 0

    def process(self, frame: np.ndarray) -> Optional[vision.HandLandmarkerResult]:
        """
        Bir BGR kareyi (frame) işleyerek HandLandmarker sonuçlarını döndürür.

        Args:
            frame: OpenCV BGR formatında bir görüntü karesi.

        Returns:
            HandLandmarkerResult nesnesi veya None.
        """
        # BGR → RGB dönüşümü ve MediaPipe Image oluşturma
        rgb_frame: np.ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image: mp.Image = mp.Image(
            image_format=mp.ImageFormat.SRGB, data=rgb_frame
        )

        # Zaman damgasını artır (her kare için benzersiz olmalı)
        self._timestamp_ms += 33  # ~30 FPS varsayımı

        # VIDEO modunda detect_for_video kullanılır
        result = self._landmarker.detect_for_video(mp_image, self._timestamp_ms)
        return result

    def get_index_finger_tip(
        self,
        result: Optional[vision.HandLandmarkerResult],
        frame_width: int,
        frame_height: int,
    ) -> Optional[Tuple[int, int]]:
        """
        HandLandmarker sonuçlarından işaret parmağı ucunun (Landmark 8)
        piksel koordinatlarını çıkarır.

        Args:
            result: HandLandmarker sonuç nesnesi.
            frame_width: Kare genişliği (piksel).
            frame_height: Kare yüksekliği (piksel).

        Returns:
            (x, y) piksel koordinatları veya el algılanmadıysa None.
        """
        if result is None or len(result.hand_landmarks) == 0:
            return None

        # İlk elin Landmark 8'ini al (INDEX_FINGER_TIP)
        hand_landmarks = result.hand_landmarks[0]
        index_tip = hand_landmarks[INDEX_FINGER_TIP]

        # Normalize koordinatları piksel koordinatlarına dönüştür
        x: int = int(index_tip.x * frame_width)
        y: int = int(index_tip.y * frame_height)

        return (x, y)

    # ── Phase 3: Parmak Durumu ve Jest Algılama ──────────────────────

    def get_finger_states(
        self, result: Optional[vision.HandLandmarkerResult]
    ) -> Optional[List[int]]:
        """
        Her parmağın açık (1) veya kapalı (0) olduğunu belirler.
        Uç noktanın (Tip) alt eklemin (PIP) üstünde olup olmadığına bakar.

        NOT: Başparmak bu diziye DAHİL DEĞİLDİR. Başparmağın yatay
        hareketi güvenilir açık/kapalı algılama için uygun değildir.
        Başparmak SADECE pinch mesafesi hesabında kullanılır.

        Args:
            result: HandLandmarker sonuç nesnesi.

        Returns:
            [İşaret, Orta, Yüzük, Serçe] — her biri 0 veya 1 (4 elemanlı).
            El algılanmadıysa None.
        """
        if result is None or len(result.hand_landmarks) == 0:
            return None

        lm = result.hand_landmarks[0]  # İlk elin landmark'ları
        fingers: List[int] = []

        # ── 4 parmak (Y ekseni karşılaştırması) ──────────────────────
        # Tip.y < PIP.y ise parmak açık (ekranda yukarı = küçük y değeri)
        # Başparmak kasıtlı olarak hariç tutuldu — sadece pinch için kullanılır
        tip_pip_pairs: List[Tuple[int, int]] = [
            (INDEX_FINGER_TIP, INDEX_FINGER_PIP),
            (MIDDLE_FINGER_TIP, MIDDLE_FINGER_PIP),
            (RING_FINGER_TIP, RING_FINGER_PIP),
            (PINKY_TIP, PINKY_PIP),
        ]

        for tip_idx, pip_idx in tip_pip_pairs:
            fingers.append(1 if lm[tip_idx].y < lm[pip_idx].y else 0)

        return fingers

    def get_pinch_distance(
        self, result: Optional[vision.HandLandmarkerResult]
    ) -> Optional[float]:
        """
        Başparmak ucu (Landmark 4) ile işaret parmağı ucu (Landmark 8)
        arasındaki normalize Öklid mesafesini hesaplar.

        Normalize koordinatlar kullanıldığı için elin kameraya
        uzaklığından bağımsızdır.

        Args:
            result: HandLandmarker sonuç nesnesi.

        Returns:
            Normalize mesafe (0.0 ~ 1.0 arası) veya el yoksa None.
        """
        if result is None or len(result.hand_landmarks) == 0:
            return None

        lm = result.hand_landmarks[0]
        thumb_tip = lm[THUMB_TIP]
        index_tip = lm[INDEX_FINGER_TIP]

        # 2D Öklid mesafesi (normalize koordinatlar üzerinde)
        distance: float = math.sqrt(
            (thumb_tip.x - index_tip.x) ** 2
            + (thumb_tip.y - index_tip.y) ** 2
        )
        return distance

    def get_gesture(
        self, result: Optional[vision.HandLandmarkerResult]
    ) -> str:
        """
        Parmak durumu dizisini ve pinch mesafesini yorumlayarak
        aktif jesti (modu) belirleyen durum makinesi.

        Parmak dizisi 4 elemanlıdır [İşaret, Orta, Yüzük, Serçe].
        Başparmak diziye dahil DEĞİLDİR — sadece pinch mesafesinde kullanılır.

        Döndürdüğü modlar:
          - "NONE"     : El algılanmadı.
          - "DRAW"     : Sadece işaret parmağı açık [1,0,0,0] → çizim yap.
          - "IDLE"     : Yumruk [0,0,0,0] → bekle, çizim yapma.
          - "NAVIGATE" : İşaret + Orta parmak açık [1,1,0,0] → gezinme modu.
          - "CLEAR"    : 4 parmak da açık [1,1,1,1] → ekranı temizle.
          - "PINCH"    : Başparmak + İşaret parmağı birleşik → tut ve sürükle.

        Args:
            result: HandLandmarker sonuç nesnesi.

        Returns:
            Jest adı (string).
        """
        fingers = self.get_finger_states(result)
        if fingers is None:
            return "NONE"

        pinch_dist = self.get_pinch_distance(result)

        # ── Pinch kontrolü (en yüksek öncelik) ──────────────────────
        # Başparmak ve işaret parmağı birbirine çok yakınsa → PINCH
        if pinch_dist is not None and pinch_dist < PINCH_THRESHOLD:
            return "PINCH"

        # ── Parmak dizisine göre mod belirleme ───────────────────────
        # fingers = [İşaret, Orta, Yüzük, Serçe] (4 elemanlı)

        # 4 parmak da açık → CLEAR
        if fingers == [1, 1, 1, 1]:
            return "CLEAR"

        # Sadece işaret parmağı açık → DRAW
        if fingers[0] == 1 and sum(fingers) == 1:
            return "DRAW"

        # İşaret + Orta parmak açık → NAVIGATE
        if fingers[0] == 1 and fingers[1] == 1 and sum(fingers) == 2:
            return "NAVIGATE"

        # Hiçbir parmak açık değil (yumruk) → IDLE
        if sum(fingers) == 0:
            return "IDLE"

        # Diğer tüm kombinasyonlar → IDLE (güvenli varsayılan)
        return "IDLE"

    def get_thumb_index_midpoint(
        self,
        result: Optional[vision.HandLandmarkerResult],
        frame_width: int,
        frame_height: int,
    ) -> Optional[Tuple[int, int]]:
        """
        Başparmak ve işaret parmağı uçlarının orta noktasını döndürür.
        Pinch (tut ve sürükle) modunda sürükleme referans noktası olarak kullanılır.

        Args:
            result: HandLandmarker sonuç nesnesi.
            frame_width: Kare genişliği (piksel).
            frame_height: Kare yüksekliği (piksel).

        Returns:
            (x, y) orta nokta piksel koordinatları veya None.
        """
        if result is None or len(result.hand_landmarks) == 0:
            return None

        lm = result.hand_landmarks[0]
        thumb = lm[THUMB_TIP]
        index = lm[INDEX_FINGER_TIP]

        mid_x: int = int(((thumb.x + index.x) / 2) * frame_width)
        mid_y: int = int(((thumb.y + index.y) / 2) * frame_height)

        return (mid_x, mid_y)

    # ── Görselleştirme ───────────────────────────────────────────────

    def draw_landmarks(
        self,
        frame: np.ndarray,
        result: Optional[vision.HandLandmarkerResult],
    ) -> np.ndarray:
        """
        Debug amacıyla el landmark noktalarını ve bağlantılarını kare üzerine çizer.

        Args:
            frame: Üzerine çizim yapılacak BGR kare.
            result: HandLandmarker sonuç nesnesi.

        Returns:
            Üzerine landmark çizilmiş kare.
        """
        if result is None or len(result.hand_landmarks) == 0:
            return frame

        h, w, _ = frame.shape

        for hand_landmarks in result.hand_landmarks:
            # Landmark noktalarını piksel koordinatlarına dönüştür
            points: List[Tuple[int, int]] = []
            for lm in hand_landmarks:
                px: int = int(lm.x * w)
                py: int = int(lm.y * h)
                points.append((px, py))
                # Her landmark için küçük bir daire çiz
                cv2.circle(frame, (px, py), 3, (0, 255, 255), cv2.FILLED)

            # El iskelet bağlantıları (MediaPipe Hand Connections)
            connections: List[Tuple[int, int]] = [
                (0, 1), (1, 2), (2, 3), (3, 4),        # Başparmak
                (0, 5), (5, 6), (6, 7), (7, 8),        # İşaret parmağı
                (0, 9), (9, 10), (10, 11), (11, 12),   # Orta parmak
                (0, 13), (13, 14), (14, 15), (15, 16), # Yüzük parmağı
                (0, 17), (17, 18), (18, 19), (19, 20), # Serçe parmağı
                (5, 9), (9, 13), (13, 17),              # Avuç içi
            ]
            for start_idx, end_idx in connections:
                if start_idx < len(points) and end_idx < len(points):
                    cv2.line(
                        frame,
                        points[start_idx],
                        points[end_idx],
                        (0, 200, 0),
                        2,
                        cv2.LINE_AA,
                    )

        return frame

    def release(self) -> None:
        """MediaPipe kaynaklarını serbest bırakır."""
        self._landmarker.close()
