# Ek A — Raporda Geçen Sayıların Kaynağı

Bu ek, teknik notta ve iş planında geçen her sayısal değerin hangi veriden,
hangi kodla ve hangi çıktı dosyasından geldiğini gösterir. Amaç, değerlerin
bağımsız olarak yeniden üretilebilmesidir.

**Depo:** https://github.com/bahaEEM/axeon-edge-dogrulama

Depoda ham veri bulunmaz. Veri kümeleri `scripts/` altındaki betiklerle
kendi kaynaklarından indirilir. CWRU dosyaları için SHA-256 künye
doğrulaması yapılır; künye tutmazsa indirme betiği hata koduyla durur.

---

## A.1 Üretim zinciri

```
veri kumesi  ->  indirme betigi  ->  oznitelik cikarimi  ->  analiz  ->  cikti
```

| Adım | Betik | Ürettiği dosya |
|---|---|---|
| CWRU indirme | `scripts/indir_cwru.py` | `veri/cwru/*.mat` (16 dosya) |
| MAFAULDA indirme | `scripts/indir_mafaulda.py` | `veri/mafaulda/**` |
| CWRU öznitelik | `src/oznitelik_cikarimi.py` | `sonuc/oznitelikler.csv` |
| CWRU senaryo | `src/karsilastirma.py` | `sonuc/sonuclar.json` |
| CWRU istatistik | `src/istatistik.py` | `sonuc/istatistik.json` |
| MAFAULDA dengesizlik | `src/mafaulda_dengesizlik.py` | `sonuc/mafaulda_oznitelikler.csv`, `sonuc/mafaulda_rapor.json` |
| MAFAULDA sınıflandırıcı | `src/mafaulda_siniflandirici.py` | `sonuc/mafaulda_siniflandirici.json` |
| MAFAULDA kaçıklık | `src/mafaulda_kaciklik.py` | `sonuc/mafaulda_kaciklik_rapor.json` |

Betikler yukarıdaki sırayla çalıştırılır. Her biri bir öncekinin çıktısını
girdi olarak kullanır.

---

## A.2 Sayıların tek tek kaynağı

### Devreye alma senaryosu

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| A-donmuş yanlış alarm %62.1 | `sonuc/sonuclar.json` | `A-donmus... > yanlis_alarm` |
| A-sürekli yanlış alarm %0.0 | `sonuc/sonuclar.json` | `A-surekli... > yanlis_alarm` |
| B1 yanlış alarm %0.0 | `sonuc/sonuclar.json` | `B1... > yanlis_alarm` |
| B1 öğreniyor oranı %11.5 | `sonuc/sonuclar.json` | `B1... > ogreniyor_faz2` |
| B2 öğreniyor oranı %34.5 | `sonuc/sonuclar.json` | `B2... > ogreniyor_faz2` |
| Tespit oranı %92.0 | `sonuc/sonuclar.json` | `tespit_ortalama` |
| Kutu sayıları 1 / 1 / 2 / 4 | `sonuc/sonuclar.json` | `kutu_sayisi` |

**Nasıl hesaplanır.** Faz 1'de cihaz yük 0'daki sağlam kayıtlardan referans
öğrenir (14 blok). Faz 2'de yük 1, 2 ve 3'teki sağlam kayıtlar işlenir
(87 blok); bu fazda üretilen her alarm yanlış alarm sayılır. Faz 3'te aynı
yüklerde arızalı kayıtlar işlenir; üretilmeyen her alarm kaçırılmış arıza
sayılır. Kod: `src/karsilastirma.py`, `senaryo()` fonksiyonu.

### Güven aralıkları

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Wilson %95 [51.6 – 71.5] | `sonuc/istatistik.json` | `ana_tablo > A-donmus > yanlis_alarm_wilson95` |
| Kayıt bootstrap %95 [0.0 – 100.0] | `sonuc/istatistik.json` | `ana_tablo > A-donmus > yanlis_alarm_bootstrap95_kayit` |
| Bağımsız kayıt sayısı 3 | `sonuc/istatistik.json` | `yanlis_alarm_kayit_sayisi` |
| Yöntem farkı %62.6 ve aralığı | `sonuc/istatistik.json` | `farklar` |

**Nasıl hesaplanır.** Wilson skor aralığı blok sayısı üzerinden hesaplanır.
Bootstrap ise kayıt düzeyinde yapılır: aynı kayıttan alınan ardışık bloklar
bağımsız olmadığı için yeniden örnekleme blokları değil kayıtları seçer.
2000 tur, tohum 20260824. Kod: `src/istatistik.py`, `wilson()` ve
`kayit_bootstrap()` fonksiyonları.

### Eşik taraması

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| z = 3.0 ... 6.0 için yanlış alarm ve tespit | `sonuc/istatistik.json` | `roc` |

**Nasıl hesaplanır.** Aynı senaryo, alarm kuran z eşiği 2.0'dan 6.0'a
taranarak tekrarlanır. Alarm düşüren eşik her adımda kuran eşikten 1.5
küçük tutulur. Kod: `src/istatistik.py`.

### Ablasyon

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Bileşen kapatıldığında yanlış alarm ve tespit | `sonuc/istatistik.json` | `ablasyon` |

**Nasıl hesaplanır.** B1 yöntemi üzerinde log domeni, histerezis ve N-of-M
oylaması tek tek kapatılarak senaryo tekrarlanır. Rejim katmanının
kapatılması A-sürekli yöntemine karşılık gelir. Kod: `src/istatistik.py`,
`Cihaz` sınıfının `log_domeni`, `histerezis`, `oylama` parametreleri.

### Dengesizlik monotonluğu

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Devir noktası başına Spearman katsayısı | `sonuc/mafaulda_rapor.json` | `S1_monotonluk > *_spearman_rho` |
| Kütle kademesi başına 1× genliği | `sonuc/mafaulda_rapor.json` | `S1_monotonluk > *_a1x_ort` |

**Nasıl hesaplanır.** Her devir noktasında, sekiz kütle kademesinin
(0, 6, 10, 15, 20, 25, 30, 35 g) ortalama 1× genlikleri hesaplanır ve kütle
ile genlik arasındaki Spearman sıra korelasyonu bulunur. Kod:
`src/mafaulda_dengesizlik.py`.

### Kurtosis

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Küme başına ortalama, medyan, standart sapma | `sonuc/mafaulda_rapor.json` | `S2_kurtosis` |

### Öznitelik ayırt ediciliği

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Cohen d (blok düzeyi) | `sonuc/mafaulda_siniflandirici.json` | `*_radyal > etki_buyuklugu > * > d_blok` |
| Kayıt düzeyi %95 aralığı | aynı dosya | `* > kayit_bootstrap95` |
| Aralığın sıfırı dışlayıp dışlamadığı | aynı dosya | `* > sifir_disinda` |

**Nasıl hesaplanır.** Cohen d, havuzlanmış standart sapma ile hesaplanır.
Güven aralığı için sağlam ve dengesiz kayıtlar ayrı ayrı, kayıt düzeyinde
yeniden örneklenir ve her turda d yeniden hesaplanır. 2000 tur.

### Sınıflandırıcı

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Karışık katmanda tespit ve yanlış pozitif | `sonuc/mafaulda_siniflandirici.json` | `*_radyal > kayit_cv > derinlik_2` |
| Görülmemiş çalışma noktasında tespit ve yanlış pozitif | aynı dosya | `*_radyal > gorulmemis_devir > derinlik_2` |

**Nasıl hesaplanır.** İki ayrı sınama yapılır.

Birincisinde `StratifiedGroupKFold` ile beş katmanlı çapraz doğrulama
uygulanır. Grup değişkeni kayıt kimliğidir, dolayısıyla aynı kaydın
blokları hem eğitimde hem testte bulunamaz. Devir noktaları katmanlara
karışık dağılır.

İkincisinde bir devir noktası tümüyle eğitimden çıkarılır ve model yalnızca
o noktada sınanır. Bu, eğitimde hiç görülmemiş bir çalışma noktasına
karşılık gelir.

Sınıf sayıları eşit olmadığından doğruluk (accuracy) raporlanmaz; tespit
oranı ve yanlış pozitif oranı ayrı ayrı verilir. Kod:
`src/mafaulda_siniflandirici.py`.

### Dengesizlik ile kaçıklık ayrımı

| Rapordaki değer | Kaynak dosya | JSON alanı |
|---|---|---|
| Sınıf ortalamaları | `sonuc/mafaulda_kaciklik_rapor.json` | `*_radyal > ozet` |
| Ayrım için Cohen d ve aralığı | aynı dosya | `*_radyal > dengesiz_vs_kaciklik` |

**Nasıl hesaplanır.** Karşılaştırma yalnızca üç sınıfın da bulunduğu devir
bantlarıyla sınırlandırılır; aksi hâlde devir farkı sınıf farkı gibi
görünürdü. Kod: `src/mafaulda_kaciklik.py`.

---

## A.3 Ortak yöntem kararları

**Blok uzunluğu.** Öznitelikler 4096 örneklik bloklardan hesaplanır.

**Örnekleme hızı.** CWRU'da 12 kHz kullanılır; 48 kHz'de kaydedilmiş sağlam
dosyalar dört kat FIR desimasyonla 12 kHz'e indirilir. MAFAULDA'da ham veri
50 kHz'dir ve sekiz kat FIR desimasyonla 6250 Hz'e indirilir. Bu ikinci
karar zorunludur: 50 kHz'de 4096'lık blok 12.2 Hz çözünürlük verir ve bu
1× ile 2× harmoniğini ayırmaya yetmez. Desimasyon sonrası çözünürlük
1.53 Hz olur.

**Öznitelikler.** On bir öznitelik her iki veri kümesinde aynı fonksiyonla
hesaplanır: rms, hiz_rms, a1x, a1x_rms, a2x_a1x, a3x_a1x, altharmonik, thd,
kurtosis, crest, rulman_bant. Tanımlar `src/axeon_dogrulama.py` içindeki
`oznitelikler()` fonksiyonundadır.

**Bağımsızlık.** Aynı kayıttan alınan ardışık bloklar bağımsız değildir.
Bu nedenle bütün güven aralıkları ve çapraz doğrulama bölmeleri kayıt
düzeyinde yapılır. Blok düzeyinde hesaplanan Wilson aralıkları yalnızca
karşılaştırma amacıyla ayrıca verilir ve tek başına kullanılmaz.

**Rastgelelik.** Bootstrap tohumu 20260824, tur sayısı 2000; ikisi de koda
sabittir. Karar ağacı da aynı tohumu kullanır. Çıktılar koşudan koşuya
değişmez.

---

## A.4 Taşıma doğrulaması

Kod, önceki çalışma dizininden bu depo yapısına taşınmıştır. Taşımanın
davranışı değiştirmediği şöyle doğrulanmıştır: öznitelik tablosu yeni
yapıda sıfırdan üretilmiş ve taşımadan önceki tabloyla karşılaştırılmıştır.
Boyut ve etiket sütunları aynıdır, sayısal sütunlardaki en büyük bağıl fark
7.0e-13'tür. Bu, kayan nokta gürültüsü düzeyindedir.

Karşılaştırma referansı olarak kullanılan tablo depoda
`sonuc/referans_oznitelikler.csv` adıyla saklanmaktadır.

---

## A.5 Doğrulanmamış olanlar

Aşağıdaki konularda bu depoda sayı üretilmemiştir ve raporda da sayı
verilmemelidir:

- Montaj tekrarlanabilirliği. Her iki veri kümesinde de tek montaj vardır.
- Yavaş gelişen arıza davranışı. Her iki kümede de arızalar anidir.
- 50 Hz şebeke koşulları. Her iki küme de 60 Hz şebekeden alınmıştır.
- Gömülü platformda float32 aritmetiğinin etkisi.
- Dikey eksen kaçıklığı.
- Gerçek makinede saha davranışı.
