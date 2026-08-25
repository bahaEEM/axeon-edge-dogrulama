# Veri Kaynakları

Bu depo hiçbir ham veri dosyası içermez. Kullanılan iki veri kümesi de
kamuya açıktır ve `scripts/` altındaki betiklerle kendi kaynaklarından
indirilir. Bu tercih bilinçlidir: her iki kümenin de yeniden dağıtım
koşulları açıkça tanımlanmamıştır, dolayısıyla veriyi depoya kopyalamak
yerine indirme yolu belgelenmiştir.

---

## 1. CWRU Bearing Data Center

**Kurum:** Case Western Reserve University, Case School of Engineering
**Adres:** https://engineering.case.edu/bearingdatacenter
**Doğrudan dosya adresi:** `https://engineering.case.edu/sites/default/files/{no}.mat`
**İndirme betiği:** `scripts/indir_cwru.py`

### Deney düzeneği

2 hp Reliance Electric indüksiyon motoru, 4 kutuplu. Tahrik ucu (drive end)
rulmanı SKF 6205-2RS JEM. Arızalar elektro-erozyon ile açılmış tekil
kusurlardır. Kayıtlarda tahrik ucu ve fan ucu ivme sinyalleri ile motor
devri bulunur.

### Kullanılan dosyalar

| Sınıf | Dosya no (yük 0/1/2/3) | Örnekleme |
|---|---|---|
| Sağlam | 97, 98, 99, 100 | 48 kHz, dört kat FIR desimasyon ile 12 kHz |
| İç bilezik 0.007" | 105, 106, 107, 108 | 12 kHz |
| Bilya 0.007" | 118, 119, 120, 121 | 12 kHz |
| Dış bilezik 0.007" @6:00 | 130, 131, 132, 133 | 12 kHz |

Yük 0-3 sırasıyla 0-3 hp yüke karşılık gelir. Kayıt künyesindeki gerçek
devirler 1797, 1772, 1750, 1730 d/dk, yani 29.95, 29.53, 29.17, 28.81 Hz.
Toplam yayılım 1.14 Hz. Şebeke 60 Hz.

### Bütünlük doğrulaması

İndirme betiği her dosyanın SHA-256 değerini ve boyutunu kontrol eder.
Künye tutmazsa betik hata koduyla durur. Doğrulanan değerler
`scripts/indir_cwru.py` içinde tablo olarak gömülüdür.

Tüm 16 dosya için künye doğrulaması yapılmış ve eşleşmiştir.

### Kullanım koşulları

Veri kümesinin sayfasında açık bir lisans metni veya yeniden dağıtım izni
bulunmamaktadır. Bu nedenle:

- Ham `.mat` dosyaları bu depoya **eklenmemiştir**.
- Veriye erişim doğrudan kurum sunucusundan yapılır.
- Akademik yayınlarda kaynak gösterimi beklenir.

### Bu veri kümesinin sınırları

- Dengesizlik ve eksen kaçıklığı sınıfları **yoktur**, yalnızca rulman
  kusuru vardır.
- Arızalar tekil, yapay ve anidir. Yavaş gelişen arıza davranışı bu
  veriyle incelenemez.
- Yük dört ayrık kademedir, sürekli değişen yük profili yoktur.
- Kayıtlar yaklaşık 10 saniyedir, bağımsız kayıt sayısı sınırlıdır.

---

## 2. MAFAULDA (Machinery Fault Database)

**Kurum:** Universidade Federal do Rio de Janeiro, SMT (Signal, Multimedia
and Telecommunications Laboratory)
**Adres:** https://www02.smt.ufrj.br/~offshore/mfs/page_01.html
**İndirme betiği:** `scripts/indir_mafaulda.py`

### Deney düzeneği

SpectraQuest Machinery Fault Simulator, Alignment-Balance-Vibration (ABVT)
düzeneği. Her kayıt 8 sütun, 250.000 örnek, 50 kHz örnekleme, 5 saniye.

| Sütun | İçerik |
|---|---|
| 0 | Takometre |
| 1, 2, 3 | Underhang ivmeölçer: eksenel, radyal, teğetsel |
| 4, 5, 6 | Overhang ivmeölçer: eksenel, radyal, teğetsel |
| 7 | Mikrofon |

Dosya adı mil devrini Hz cinsinden verir. Örnek: `29.4912.csv` kaydı
29.4912 Hz devirde alınmıştır.

### Kullanılan alt kümeler

| Küme | Kapsam | Kayıt |
|---|---|---|
| Sağlam | `normal.tgz` içindeki tüm kayıtlar | 49 |
| Dengesizlik | 6, 10, 15, 20, 25, 30, 35 g × dört devir noktası | 28 |
| Yatay kaçıklık | 0.5, 1.0, 1.5, 2.0 mm × iki devir noktası | 8 |
| Dikey kaçıklık | henüz indirilmedi | 0 |

### Neden tam arşiv indirilmedi

Tam paket 5.8 GB'dır. Ölçülen bağlantı hızı 167.633 B/s olduğundan tam
indirme 10 saatten uzun sürmektedir. Dengesizlik sorusu sabit devirde
sorulduğu için kütle kademeleri arasında eşleşmiş devir noktaları
zorunludur; tam kapsam ise gerekli değildir. Bu nedenle hedefli örnekleme
tercih edilmiştir.

Sağlam kayıtlar için tek tek indirme yerine `normal.tgz` arşivi alınmıştır;
49 kaydın tamamı 325 MB sıkıştırılmış olarak gelir, tek tek indirilmesi
860 MB tutardı.

### Sunucu davranışı

Sunucu ardışık isteklerde 403 dönebilmektedir. İndirme betiği istekler
arasında bekleme yapar, yeniden dener ve inmiş dosyaları atlar. Kesinti
durumunda betiği tekrar çalıştırmak yeterlidir.

### Kullanım koşulları

Sayfada açık bir lisans metni yoktur. Veri kümesi akademik kullanım için
yayımlanmıştır ve kaynak gösterimi beklenir. İletişim adresi veri kümesi
sayfasında verilmiştir. Ham CSV dosyaları bu depoya eklenmemiştir.

### Bu veri kümesinin sınırları

- Tek montaj düzeneği vardır. Montaj tekrarlanabilirliği bu veriyle
  ölçülemez.
- Arızalar kontrollü ve kalıcıdır, zaman içinde gelişmezler.
- Şebeke 60 Hz'dir.

---

## 3. Depoda bulunan türetilmiş dosyalar

`sonuc/` altındaki dosyalar ham veri değildir. Her biri, 4096 örneklik
bloklardan hesaplanmış istatistiklerden oluşur.

| Dosya | İçerik |
|---|---|
| `oznitelikler.csv` | CWRU, 450 blok × 11 öznitelik + etiketler |
| `mafaulda_oznitelikler.csv` | MAFAULDA sağlam ve dengesizlik, 840 blok |
| `mafaulda_kaciklik_oznitelikler.csv` | MAFAULDA kaçıklık, 112 blok |
| `referans_oznitelikler.csv` | Yapı taşınmadan önceki öznitelik tablosu, regresyon karşılaştırması için saklanmıştır |
| `*.json` | Analiz çıktıları, tüm tablolar ve güven aralıkları |

Bu dosyalar ham titreşim sinyalini içermez; sinyalden hesaplanmış özet
büyüklüklerdir. Kaynak veri kümelerinin yerine geçmezler ve onlardan
sinyal geri elde edilemez.

---

## 4. Henüz kullanılmayan kaynaklar

**IMS / NASA run-to-failure.** Center for Intelligent Maintenance Systems,
University of Cincinnati. NASA Prognostics Data Repository üzerinden
dağıtılmaktadır. Erişilebilirliği doğrulanmıştır, 1.08 GB. Yavaş gelişen
arıza davranışının incelenebileceği tek kaynaktır, henüz indirilmemiştir.
