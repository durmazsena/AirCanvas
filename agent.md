# Proje Adı: AirCanvas SDK (AR-Drawing-as-a-Service)

## 1. Proje Vizyonu ve Amacı
Bu projenin amacı, modüler ve açık kaynaklı bir "Havada Yazı Yazma ve Çizim" motoru oluşturmaktır. Üçüncü parti görüntülü konuşma platformlarına (flört uygulamaları, uzaktan eğitim, iletişim araçları vb.) bir özellik katmanı olarak kolayca entegre edilmek üzere tasarlanmıştır.

Temel felsefe, standart piksel tabanlı boyama yerine **Nesne Tabanlı Görüntüleme (Object-Based Rendering)** yapmaktır. Çizilen çizgiler birer veri yapısı (koordinat dizileri) olarak kaydedilir, böylece çizildikten sonra taşınabilir, yeniden boyutlandırılabilir veya manipüle edilebilirler.

## 2. Temel Özellikler (Uygulanacaklar)
- **Havada Çizim (Air Drawing):** Sanal bir tuval (canvas) üzerinde işaret parmağı koordinatlarını kullanarak çizim yapma.
- **Dinamik Nesne Manipülasyonu:** Ekrandaki mevcut çizimleri seçme, tutma (çimdik hareketiyle) ve ekran üzerinde sürükleme.
- **Jest Tabanlı Durum Makinesi (State Machine):**
  - *Sadece işaret parmağı havada:* **Çizim Modu (Draw Mode)**
  - *İşaret + Orta parmak havada:* **Gezinme/Seçim/Renk Değiştirme Modu (Hover/Select/Color Change Mode)**
  - *İşaret + Başparmak birleşik (Çimdik/Pinch):* **Tut ve Sürükle Modu (Grab & Drag Mode)**
  - *Açık El / Yumruk:* **Silme/Ekranı Temizleme Komutu (Erase/Clear Screen)**
- **Gelişmiş Boru Hattı (Geleceğe Dönük Özellikler):** Yapay zeka ile şekil düzeltme (daireleri/dikdörtgenleri pürüzsüzleştirme) ve havada yazılan metinler için OCR (Optik Karakter Tanıma) entegrasyonu.

## 3. Teknoloji Yığını (Tech Stack)
- **Çekirdek Motor:** Python (MVP - Minimum Uygulanabilir Ürün için öncelikli) veya JavaScript/TypeScript (Nihai SDK için).
- **Görüntü İşleme (Computer Vision):** `MediaPipe Hands` (el eklem noktası tespiti için), `OpenCV` (kamera akışı ve görselleştirme için).
- **Mimari:** Çizgileri, durumları (state) ve tuvali yönetmek için Nesne Yönelimli Programlama (OOP) yapısı.

## 4. Sistem Mimarisi ve Modülerlik
Kod tabanı KESİNLİKLE modüler olmalıdır. El takip mantığı, çizim mantığı ile sıkı sıkıya bağlı (tightly coupled) olmamalıdır.
- `hand_tracker.py`: MediaPipe'ı yönetir. Sadece temizlenmiş verileri (parmak koordinatları, algılanan jestler) döndürür.
- `canvas_manager.py`: "Stroke" (Çizgi) nesnelerini yönetir; nokta ekleme, nesneleri taşıma ve ekranı temizleme mantığını yürütür.
- `stroke.py`: Tek bir çizim öğesini temsil eden veri sınıfı (`points[]`, `color`, `thickness` içerir).
- `main.py`: Ana giriş noktası. Kamerayı bağlar, kareleri (frames) `hand_tracker`a iletir, elde edilen koordinatları `canvas_manager`a aktarır ve son çıktıyı ekrana yansıtır.

## 5. Geliştirme Yol Haritası (Aşama Aşama)

### Phase 1 (Aşama 1): Çekirdek Yapı (MVP)
- OpenCV web kamerası akışını kur.
- MediaPipe Hands modülünü başlat.
- SADECE işaret parmağı ucunu (Landmark 8) takip et.
- Boş bir maske (tuval) üzerine temel kesintisiz çizgiler çiz ve bunu kamera akışının üzerine bindir (overlay).

### Phase 2 (Aşama 2): Nesneleştirme (Veri Katmanı)
- Çizim mantığını "pikselleri boyamak"tan "koordinatları kaydetmek" yönünde yeniden düzenle (Refactor).
- `Stroke` sınıfını oluştur.
- İşaret parmağı çizim yaparken, (x, y) koordinatlarını aktif `Stroke` nesnesine ekle.
- Her karede (frame) tüm `Stroke` nesnelerini ekrana çiz (render).

### Phase 3 (Aşama 3): Jestler ve Etkileşim
- **Parmak Durumu (Finger State) Algoritmasını Ekle:** El yumruk olduğunda bile çizim yapılmasını engellemek için parmakların açık/kapalı durumunu kontrol et. Uç noktaların (Tip) alt eklemlere göre Y eksenindeki konumuna bakarak durumu `[Başparmak, İşaret, Orta, Yüzük, Serçe]` için `1` (açık) ve `0` (kapalı) dizisi olarak döndür.
- **Mesafe Hesaplaması:** "Tutma" (Pinch) hareketini algılamak için Başparmak (Landmark 4) ile İşaret Parmağı (Landmark 8) arasındaki mesafeyi hesapla.
- **Durum Makinesi (State Machine) Oluştur:** Elde edilen parmak dizisine göre modları belirle:
  - `[0, 1, 0, 0, 0]` -> Çizim Modu (Sadece işaret parmağı havada).
  - `[0, 0, 0, 0, 0]` -> Bekleme Modu (Yumruk - İşaret parmağı algılansa bile çizim yapılmaz).
  - `[0, 1, 1, 0, 0]` -> Gezinme/Renk Seçim Modu (Çizim durur).
  - `[1, 1, 1, 1, 1]` -> Ekranı Temizleme Modu (Tüm parmaklar açık).
- **"Tut ve Sürükle" (Grab & Drag) Mantığını Uygula:** Eğer sistem "Tutma" hareketini algılarsa ve parmaklar mevcut bir `Stroke` üzerinde çimdikleme yaparsa, o çizginin tüm (x, y) koordinatlarını elin hareketine göre (Delta X, Delta Y) güncelle.

### Phase 4 (Aşama 4): Arayüz (UI) ve İyileştirme
- Ekranın üst kısmına sanal bir renk paleti ekle.
- Arayüz etkileşimini uygula: Palet üzerinde gezinmek aktif çizgi rengini değiştirsin.
- Yumruk veya açık el jesti ile "Tümünü Temizle" özelliğini ekle.

### Phase 5 (Aşama 5): Dışa Aktarma / Servise Hazır Hale Getirme
- API'yi belgelendir.
- Bir geliştiricinin motorumuza sadece bir `frame` (kare) gönderip, çizilmiş nesnelerin JSON verisiyle birlikte `processed_frame` (işlenmiş kare) geri alabileceği bir arayüz/mikroservis mimarisi oluştur.

## 6. Ajan Direktifleri (Yapay Zeka İçin Kurallar)
- Temiz, bol yorum satırı içeren, PEP8 standartlarına uygun kod yaz.
- Her zaman Tip Belirtme (Type Hinting) kullan (Örn: `def get_landmarks(image: np.ndarray) -> list:`).
- Yeni bir Phase'e (Aşamaya) başlamadan önce, uygulayacağın yaklaşımı kısaca açıkla.
- Düşük gecikme süresine (low latency) öncelik ver. Ana döngü (main loop) içinde ağır hesaplamalardan kaçın. Mesafeleri (çimdik hareketi için vb.) verimli bir şekilde hesapla.