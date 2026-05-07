# 🎨 AirCanvas — Havada Çizim SDK'sı

**AirCanvas**, web kamerası ve el takibi ile havada çizim yapmanızı sağlayan bir AR (Artırılmış Gerçeklik) çizim motorudur. MediaPipe'ın el landmark algılama teknolojisini kullanarak, parmaklarınızla ekranda çizim yapabilir, nesneleri sürükleyebilir, renkler ve fırçalar arasında geçiş yapabilirsiniz.

> **Donanım ve yazılım gereksinimi yok** — sadece bir web kamerası ve Python yeterli.

---

## ✨ Özellikler

| Özellik | Açıklama |
|---|---|
| ✏️ **Havada Çizim** | İşaret parmağıyla ekranda serbest çizim |
| 🎨 **8 Renk Paleti** | Sol panelden dwell-time ile renk seçimi |
| 🖌️ **3 Fırça Tipi** | Düz, Neon (parlama efekti), Gökkuşağı |
| 🧽 **Piksel Silgi** | Gerçek nokta silme — stroke'u bölerek kısmi silme |
| ✋ **Jest Kontrol** | 5 farklı el jesti ile tam kontrol |
| 🤏 **Tut ve Sürükle** | Pinch jesti ile çizimleri taşıma |
| 📏 **Kalınlık Ayarı** | Sağ panelden çizgi kalınlığını değiştirme |
| 🧹 **Ekran Temizleme** | Açık el jesti ile tüm tuvali temizleme |

---

## 🛠️ Kurulum

### Gereksinimler

- Python 3.10+
- Web kamerası
- macOS / Linux / Windows

### Adımlar

```bash
# 1. Projeyi klonla
git clone https://github.com/kullaniciadi/aircanvas.git
cd aircanvas

# 2. Sanal ortam oluştur
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Bağımlılıkları yükle
pip install -r requirements.txt
```

### Model Dosyası

MediaPipe Hand Landmarker modeli gereklidir. Proje dizininde `hand_landmarker.task` dosyası bulunmalıdır:

```bash
# Model yoksa indir
wget -q https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

---

## 🚀 Çalıştırma

```bash
python3 main.py
```

Uygulama açıldığında kamera görüntüsü ile birlikte yan paneller ve durum bilgisi ekranda görünür.

**Çıkmak için:** `q` tuşuna basın.
**Tuvali temizlemek için:** `c` tuşuna basın veya açık el jesti yapın.

---

## 🤚 Jest Rehberi

Sistem, elinizin 4 parmağını (işaret, orta, yüzük, serçe) izler. Başparmak sadece pinch (çimdik) algılamada kullanılır.

### Jestler

| Jest | Parmaklar | Davranış |
|---|---|---|
| ✏️ **Çizim** | Sadece işaret parmağı `[1,0,0,0]` | Parmak ucuyla çizim yapar |
| ✌️ **Gezinme** | İşaret + Orta `[1,1,0,0]` | Çizim yapmadan hareket eder, palet etkileşimi aktif |
| ✊ **Bekleme** | Yumruk `[0,0,0,0]` | Hiçbir şey yapmaz, çizim durur |
| 🖐️ **Temizle** | Tüm parmaklar `[1,1,1,1]` | Açık avucuyla ekranın %50'sini süpür |
| 🤏 **Sürükle** | Başparmak + İşaret birleşik | Çizimi tutup sürükler |

### Güvenlik Mekanizmaları

- **DRAW debounce (5 kare):** Çizim moduna geçmek için 5 ardışık kare gerekir — anlık gürültü filtrelenir.
- **PINCH debounce (5 kare):** Sürükleme moduna yanlışlıkla girmeyi önler.
- **CLEAR süpürme (ekranın %50'si):** Açık avucuyla ekranı silme hareketi gerekir — sadece eli açmak temizlemez.

---

## 🎨 Araç Çubuğu (UI)

### Sol Panel — Renkler

8 yuvarlak renk butonu. **Nasıl seçilir:**

1. ✌️ Gezinme moduna geç (2 parmak)
2. Parmağını istediğin rengin üzerine getir
3. ~0.7 saniye bekle (sarı dolum çemberi dolar)
4. Renk seçilir ✅

### Sağ Panel — Fırçalar ve Araçlar

| Buton | Açıklama |
|---|---|
| **Düz** | Standart düz çizgi |
| **Neon** | 3 katmanlı parlama efekti |
| **Gökkuşağı** | HSV renk geçişli çizgi |
| **Silgi** | Piksel seviyesinde gerçek silme |
| **[+]** | Çizgi kalınlığını artır |
| **[-]** | Çizgi kalınlığını azalt |

Fırça/silgi seçimi de aynı dwell-time mantığıyla çalışır.

### Silgi Modu

- Sağ panelden **Silgi** butonunu seç
- İşaret parmağıyla çizimlerin üstünden geç
- Parmağın geçtiği noktalar fiziksel olarak silinir
- Stroke ortadan bölünürse iki ayrı nesneye ayrılır
- Silgi modundan çıkmak için herhangi bir fırça seçin (Düz/Neon/Gökkuşağı)

---

## 📁 Proje Yapısı

```
aircanvas/
├── main.py              # Ana uygulama döngüsü ve durum makinesi
├── hand_tracker.py      # MediaPipe el takibi, parmak algılama, jest motoru
├── canvas_manager.py    # Tuval yönetimi, stroke render, silgi, sürükleme
├── stroke.py            # Stroke veri sınıfı ve fırça efektleri (neon, rainbow)
├── ui_palette.py        # Yan panel UI, butonlar, dwell-time seçim
├── hand_landmarker.task # MediaPipe model dosyası
├── requirements.txt     # Python bağımlılıkları
├── agent.md             # Proje vizyon ve yol haritası
└── README.md            # Bu dosya
```

### Modül Diyagramı

```
┌──────────┐     ┌───────────────┐     ┌────────────────┐
│  Kamera  │────▶│ HandTracker   │────▶│    main.py     │
│ (cv2)    │     │ (MediaPipe)   │     │ (Durum Makinesi)│
└──────────┘     └───────────────┘     └───────┬────────┘
                                               │
                          ┌────────────────────┼──────────────┐
                          ▼                    ▼              ▼
                   ┌─────────────┐    ┌──────────────┐  ┌──────────┐
                   │CanvasManager│    │  UIPalette   │  │  Stroke  │
                   │(Render/Silgi│    │(Renk/Fırça)  │  │(Veri/Efekt│
                   │/Sürükleme)  │    │              │  │          │
                   └─────────────┘    └──────────────┘  └──────────┘
```

---

## 🔧 Bağımlılıklar

```
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
```

---

## 🧪 Teknik Detaylar

### El Takibi
- **MediaPipe Tasks API** (`HandLandmarker`) kullanılır — eski `mp.solutions` API'si değil.
- 21 el landmark'ı algılanır, parmak durumları tip vs PIP karşılaştırmasıyla belirlenir.
- Başparmak durum dizisine dahil değildir (güvenilmez) — sadece pinch mesafesinde kullanılır.

### Render Sistemi
- Nesne tabanlı render: Her karede tüm `Stroke` nesneleri temiz siyah bir maskeye çizilir.
- Overlay: Siyah olmayan pikseller kamera karesinin üzerine bindirilir.
- Fırça efektleri `Stroke.draw()` metodu içinde her fırça tipine özel render ile yapılır.

### Silgi
- Gerçek nokta silme: Silgi yarıçapı içindeki noktalar stroke'tan fiziksel olarak kaldırılır.
- Bölme: Stroke ortasından silinirse, kalan parçalar ayrı `Stroke` nesnelerine dönüşür.
- Sürükleme uyumlu: Hayalet siyah stroke yok — silinen bölge gerçekten boş.

### Debounce Sistemi
- Her jest geçişinde sayaç tabanlı debounce uygulanır.
- Anlık parmak pozisyonu değişiklikleri (gürültü) filtrelenir.
- Üç satırlık temiz implementasyon:
  ```python
  draw_count  = draw_count + 1  if gesture == "DRAW"  else 0
  pinch_count = pinch_count + 1 if gesture == "PINCH" else 0
  clear_count = clear_count + 1 if gesture == "CLEAR" else 0
  ```

---

## 📋 Geliştirme Yol Haritası

- [x] **Phase 1:** Temel el takibi ve çizim
- [x] **Phase 2:** Nesne tabanlı Stroke sistemi
- [x] **Phase 3:** Jest algılama, durum makinesi, sürükleme
- [x] **Phase 4:** UI paleti, fırça efektleri, silgi, kalınlık
- [ ] **Phase 5:** API / Mikroservis arayüzü

---

## 📝 Lisans

Bu proje eğitim ve araştırma amaçlı geliştirilmiştir.

---

## 🙏 Teşekkürler

- [MediaPipe](https://developers.google.com/mediapipe) — El takibi modeli
- [OpenCV](https://opencv.org/) — Görüntü işleme
- [NumPy](https://numpy.org/) — Sayısal hesaplamalar
