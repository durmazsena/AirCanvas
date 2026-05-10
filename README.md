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
├── main.py              # Masaüstü uygulama (kamera döngüsü)
├── engine.py            # Çekirdek işleme motoru (tüm mantık burada)
├── api.py               # FastAPI REST API
├── hand_tracker.py      # MediaPipe el takibi, parmak algılama, jest motoru
├── canvas_manager.py    # Tuval yönetimi, stroke render, silgi, sürükleme
├── stroke.py            # Stroke veri sınıfı ve fırça efektleri (neon, rainbow)
├── ui_palette.py        # Yan panel UI, butonlar, dwell-time seçim
├── hand_landmarker.task # MediaPipe model dosyası
├── requirements.txt     # Python bağımlılıkları
└── README.md            # Bu dosya
```

### Modül Diyagramı

```
                  ┌─────────────────────────────────────┐
                  │          AirCanvasEngine             │
                  │  (engine.py — tüm mantık burada)    │
                  └──────┬──────────┬──────────┬────────┘
                         │          │          │
        ┌────────────────▼──┐  ┌────▼──────┐  ┌▼───────────┐
        │   HandTracker     │  │  Canvas   │  │ UIPalette  │
        │   (MediaPipe)     │  │  Manager  │  │ (Renk/Fırça│
        └───────────────────┘  └─────┬─────┘  └────────────┘
                                     │
                                ┌────▼─────┐
                                │  Stroke  │
                                │(Veri/Efekt│
                                └──────────┘
    ┌──────────┐                      ▲
    │ main.py  │──── process_frame ───┘
    │ (Kamera) │
    └──────────┘

    ┌──────────┐                      ▲
    │  api.py  │──── process_frame ───┘
    │ (FastAPI)│
    └──────────┘
```

---

## 🔧 Bağımlılıklar

```
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

---

## 🌐 API Kullanımı

AirCanvas bir REST API olarak da kullanılabilir. Geliştiriciler kendi uygulamalarına entegre edebilir.

### API Sunucusunu Başlatma

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Swagger dokümantasyonu: http://localhost:8000/docs

### API Endpointleri

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/process` | Frame gönder → işlenmiş frame + JSON al |
| `GET` | `/api/sessions/{id}` | Oturum bilgilerini al |
| `GET` | `/api/sessions/{id}/strokes` | Tüm stroke'ları JSON al |
| `POST` | `/api/sessions/{id}/color` | Renk değiştir |
| `POST` | `/api/sessions/{id}/brush` | Fırça değiştir |
| `POST` | `/api/sessions/{id}/thickness` | Kalınlık değiştir |
| `DELETE` | `/api/sessions/{id}` | Tuvali temizle |
| `GET` | `/api/health` | Sunucu sağlık kontrolü |

### Örnek İstemci (Python)

```python
import requests, base64, cv2

# Frame'i base64'e çevir
frame = cv2.imread("kare.jpg")
_, buffer = cv2.imencode('.jpg', frame)
frame_b64 = base64.b64encode(buffer).decode()

# Frame'i işle
response = requests.post("http://localhost:8000/api/process", json={
    "session_id": "user1",
    "frame": frame_b64,
    "width": 1920,
    "height": 1080,
})

data = response.json()
print(data["gesture"])        # "DRAW", "IDLE", ...
print(data["stroke_count"])   # 5
print(data["strokes"])        # [{points, color, brush_type}, ...]

# Renk değiştir
requests.post("http://localhost:8000/api/sessions/user1/color", json={
    "color": [0, 255, 0]
})
```

### Oturum Yönetimi

- Her `session_id` için ayrı bir motor instance oluşturulur
- Oturumlar 10 dakika inaktivite sonrası otomatik temizlenir
- Palet etkileşimi jest tabanlıdır (frame içinde çalışır)
- Renk/fırça/kalınlık API üzerinden de değiştirilebilir

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
- Temizleme jesti: Açık avuçla ekranın %50'sini süpürme hareketi gerekir.

---

## 📋 Geliştirme Yol Haritası

- [x] **Phase 1:** Temel el takibi ve çizim
- [x] **Phase 2:** Nesne tabanlı Stroke sistemi
- [x] **Phase 3:** Jest algılama, durum makinesi, sürükleme
- [x] **Phase 4:** UI paleti, fırça efektleri, silgi, kalınlık
- [x] **Phase 5:** API / Mikroservis arayüzü

---

## 📝 Lisans

Bu proje eğitim ve araştırma amaçlı geliştirilmiştir.

---

## 🙏 Teşekkürler

- [MediaPipe](https://developers.google.com/mediapipe) — El takibi modeli
- [OpenCV](https://opencv.org/) — Görüntü işleme
- [NumPy](https://numpy.org/) — Sayısal hesaplamalar
- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework

