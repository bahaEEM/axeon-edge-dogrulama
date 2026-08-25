# AXEON-Edge — Ön Doğrulama Bulguları ve Rapor Revizyon Temeli

**Tarih:** 24–25 Ağustos 2026
**Kapsam:** Bu belge, teknik notun ve iş planının hangi cümlelerinin neye göre
revize edileceğini belirler. Her bulgu için üç soru ayrı ayrı cevaplanmıştır:
*ne çıktı*, *neyi kanıtlar*, *neyi değiştirir*.

**Kaynak etiketleri:** `[ÖLÇÜLDÜ]` `[VERİSETİ]` `[HESAP]` `[KARAR]` `[HENÜZ YOK]`

**Kural:** Bu belgedeki hiçbir sayı elle yazılmamıştır. Hepsi `sonuc/*.json`
dosyalarından, onlar da `src/*.py` betiklerinden üretilmiştir. Tekrar üretim
talimatı Bölüm 9'dadır.

---

## 1. Ne yapıldı — özet

Önceki oturumda üretilmiş olan simülasyon çalışması, temiz bir makinede
sıfırdan kurulup doğrulandı; sonra istatistiksel olarak sınandı; sonra CWRU'da
bulunmayan **dengesizlik** sınıfı ikinci bir kamuya açık veri kümesinden
indirilip analiz edildi.

Dört iş yapıldı:

1. **Tekrar üretim.** Kod ve veri sıfırdan kuruldu, sayılar birebir doğrulandı.
2. **İstatistiksel sınama.** Mevcut tablodaki oranlara güven aralığı,
   yöntem farklarına bootstrap, eşiğe ROC, mimariye ablasyon eklendi.
3. **Yeni veri.** MAFAULDA dengesizlik verisi indirildi ve analiz edildi.
4. **Sınıflandırıcı denemesi.** Karar ağacı, kayıt düzeyinde çapraz doğrulama
   ve görülmemiş çalışma noktası testiyle sınandı.

---

## 2. Nereden — veri kaynakları ve künye

### 2.1 CWRU (Case Western Reserve University Bearing Data Center)

- **Adres:** `https://engineering.case.edu/sites/default/files/{no}.mat`
- **Ne içerir:** 2 hp Reliance Electric indüksiyon motoru, tahrik ucu rulmanı
  SKF 6205-2RS JEM. Elektro-erozyonla açılmış tekil kusurlar.
- **İndirilen:** 16 dosya — sağlam (97, 98, 99, 100), iç bilezik (105–108),
  bilya (118–121), dış bilezik (130–133); her sınıf 4 yük kademesinde.
- **Doğrulama:** Her dosyanın SHA-256 değeri beklenen künyeyle karşılaştırıldı,
  **16/16 birebir eşleşti** `[ÖLÇÜLDÜ]`. Betik künye tutmazsa çıkış kodu 1
  verip durur (`scripts/indir_cwru.py`).
- **Neden bu veri:** Rulman arızasında akademik referansı en yüksek açık küme.
- **Sınırı:** Dengesizlik ve eksen kaçıklığı **yok**. Arızalar ani ve yapay.
  Yük 4 ayrık kademe. Kayıtlar ~10 s.

### 2.2 MAFAULDA (UFRJ SMT — Machinery Fault Database)

- **Adres:** `https://www02.smt.ufrj.br/~offshore/mfs/database/mafaulda/`
- **Ne içerir:** SpectraQuest MFS-ABVT düzeneği. 8 sütun, 250.000 örnek,
  50 kHz, 5 s. Sütun 0 takometre; 1–3 underhang ivmeölçer (eksenel, radyal,
  teğetsel); 4–6 overhang ivmeölçer; 7 mikrofon. Dosya adı = mil devri (Hz).
- **İndirilen:** 7 dengesizlik kütlesi (6–35 g) × 4 eşleşen devir (~20/30/40/50 Hz)
  = 28 kayıt (554 MB); `normal.tgz` içinden 49 sağlam kayıt (325 MB), bunların
  **32'si** eşleşen 19–52 Hz bandında; yatay eksen kaçıklığı 4 kademe × 2 devir
  = 8 kayıt (110 MB). Toplam **68 kayıt, ~990 MB** `[VERİSETİ]`.
- **Neden tam arşiv değil:** Tam paket 5,8 GB; bağlantı hızı ölçüldü,
  **167.633 B/s** `[ÖLÇÜLDÜ]` — 17,6 MB'lık bir dosya 105 saniye, tamamı
  10 saatten uzun sürer. Dengesizlik sorusu **sabit devirde** sorulduğundan
  eşleşmiş devir zorunlu, tam kapsam değil `[KARAR]`.
- **Neden bu veri:** CWRU'da olmayan tam da bizim v1 hedef sınıfımız burada var.

### 2.3 Henüz alınmayan

- **Dikey** eksen kaçıklığı (6 kademe): sunucu dizin listesini vermedi `[HENÜZ YOK]`
- IMS/NASA run-to-failure (1,08 GB): erişilebilirliği doğrulandı, indirilmedi
- MAFAULDA underhang/overhang rulman kümeleri (3,4 + 3,7 GB): kapsam dışı bırakıldı

---

## 3. Nasıl — yöntem

**Öznitelikler (11 adet, her iki veri kümesinde aynı fonksiyon):**
`rms, hiz_rms, a1x, a1x_rms, a2x_a1x, a3x_a1x, altharmonik, thd, kurtosis,
crest, rulman_bant`

**Karar mimarisi:** Kutu başına Welford (n, ortalama, m2 — örnek saklanmaz),
log domeninde z-skor, 4σ kurar / 2,5σ düşürür histerezis, son 8 bloğun 5'i
oylaması, öğrenilmemiş kutu "alarm" değil **"öğreniyor"** döndürür, alarm
aktifken öğrenme donar.

**CWRU protokolü:** Faz 1 devreye alma (yük 0, sağlam, 14 blok) → Faz 2 sağlıklı
işletme (yük 1-2-3, 87 blok; buradaki her alarm yanlış alarmdır) → Faz 3 arıza
(aynı yükler, sınıf başına ~87 blok).

**MAFAULDA işleme:** 50 kHz'de 4096'lık blok 12,2 Hz çözünürlük verir; bu
1× ile 2×'i ayırmaya **yetmez**. 8 kat FIR desimasyon → 6250 Hz, çözünürlük
**1,53 Hz** `[KARAR]`. 60 kayıt × 7 blok × 2 kanal = 840 satır
(+ kaçıklık için ayrıca 8 kayıt × 7 blok × 2 kanal = 112 satır).

**İstatistik:** Wilson skor aralığı (blok düzeyi), kayıt düzeyinde bootstrap
(2000 tur, tohum 20260824), Cohen d, Spearman ρ.

---

## 4. Bulgular

### B1 — Çalışma tekrar üretilebilir

**Ne çıktı.** Temiz makinede (Python 3.13.7, numpy 2.5.2, scipy 1.18.1) sıfırdan
üretilen öznitelik tablosu, orijinaliyle karşılaştırıldı: 450×18 boyut aynı,
metin sütunları aynı, **en büyük bağıl fark 7,0×10⁻¹³** `[ÖLÇÜLDÜ]`.
Ana karşılaştırma tablosunun dört satırı da birebir yeniden üretildi.

**Neyi kanıtlar.** Sonuçlar makineye, kütüphane sürümüne ve operatöre bağlı
değil. Hakem aynı komutu çalıştırıp aynı sayıları görebilir.

**Neyi değiştirir.** Raporda "sonuçlar tekrar üretilebilir" cümlesi artık
kurulabilir ve künye tablosuyla desteklenir. Bu, önceki hâlde yoktu.

---

### B2 — CWRU'daki ana ticari iddia kayıt düzeyinde desteklenmiyor

**Ne çıktı** `[HESAP]`:

| Yöntem | Yanlış alarm | Wilson %95 (blok) | Bootstrap %95 (kayıt) | Bağımsız kayıt |
|---|---|---|---|---|
| A-donmuş | %62,1 | [51,6 – 71,5] | **[0,0 – 100,0]** | 3 |
| A-sürekli | %0,0 | [0,0 – 4,2] | [0,0 – 0,0] | 3 |
| B1 | %0,0 | [0,0 – 4,2] | [0,0 – 0,0] | 3 |
| B2 | %0,0 | [0,0 – 4,2] | [0,0 – 0,0] | 3 |

Yöntem farkı: A-donmuş − B1 = %62,6, kayıt düzeyi %95 aralığı **[0,0 – 100,0]**,
yani **sıfırı içeriyor**.

**Neden bu kadar geniş.** Faz 2'deki 87 blok bağımsız değil; sadece **3 kayıttan**
(sağlam yük 1, 2, 3) alınmış ardışık pencereler. Yanlış alarmlar yük 2 ve 3'te
yoğunlaşıyor, yük 1'de hiç yok. Üç kayıt yeniden örneklendiğinde sonuç %0 ile
%100 arasında salınıyor. **Etkin örneklem 87 değil 3'tür.**

**Neyi kanıtlar.** Blok düzeyinde fark çok belirgin; kayıt düzeyinde
**gösterilemiyor**. Bu, iddianın yanlış olduğunu değil, bu veri setinin iddiayı
taşıyacak kadar bağımsız kayıt içermediğini kanıtlar.

**Neyi değiştirir.** Teknik notta **"%62,1 yanlış alarm"** rakamı, yanına
şu üç şey yazılmadan kullanılamaz: (a) etkin örneklemin 3 kayıt olduğu,
(b) kayıt düzeyi güven aralığının sıfırı içerdiği, (c) bunun bir veri sınırı
olduğu. Hakem bu hesabı kendisi yapacaktır; önden yazmak elimizi güçlendirir,
yazmamak raporu savunmasız bırakır.

---

### B3 — %62,1 rakamı eşik seçimine bağlı

**Ne çıktı** `[ÖLÇÜLDÜ]` — Z eşiği taraması:

| z | A-donmuş (yanlış alarm / tespit) | B1 |
|---|---|---|
| 3,0 | %92,0 / %92,0 | %0,0 / %92,0 |
| 3,5 | %64,4 / %92,0 | %0,0 / %92,0 |
| **4,0** | **%62,1 / %92,0** | %0,0 / %92,0 |
| 4,5 | %44,8 / %92,0 | %0,0 / %92,0 |
| **5,0** | **%0,0 / %92,0** | %0,0 / %92,0 |

**Neyi kanıtlar.** z = 5,0'da dondurulmuş referans da %0 yanlış alarm veriyor ve
tespiti hiç düşmüyor. "Dondurulmuş referans yük değişiminde çöker" iddiası bu
veri setinde **yalnızca 4σ civarındaki eşikler için** geçerli.

**Neyi değiştirir.** 4σ'nın bir **karar** olduğu, optimum olmadığı raporda
açıkça yazılmalı. Rakiplerle karşılaştırma, "onların eşiği kötü seçilmiş"
argümanına dayanamaz — çünkü eşiği değiştirmek serbesttir. Ürünün gerçek
üstünlüğü eşiğin **elle seçilmesine gerek kalmaması** olarak kurulmalı;
"aynı eşikte daha az yanlış alarm" olarak değil.

---

### B4 — Mimari bileşenleri bu veride katkı göstermiyor

**Ne çıktı** `[ÖLÇÜLDÜ]` — B1 üzerinde ablasyon:

| Kurulum | Yanlış alarm | Tespit | Öğreniyor |
|---|---|---|---|
| tam (referans) | %0,0 | %92,0 | %11,5 |
| log domeni KAPALI | %0,0 | %92,0 | %11,5 |
| histerezis KAPALI | %0,0 | %92,0 | %11,5 |
| N-of-M oylama KAPALI | %1,1 | %100,0 | %11,5 |
| rejim katmanı KAPALI | %0,0 | %92,0 | %0,0 |

**Neyi kanıtlar.** Log domeni, histerezis ve rejim katmanı bu veri setinde
ölçülebilir katkı sağlamıyor. Tek etkisi görülen bileşen N-of-M oylaması:
kapatıldığında tespit %92→%100 çıkıyor, yanlış alarm %0→%1,1 oluyor. Yani
oylama, %8 tespit karşılığında %1,1 yanlış alarm satın alıyor.

**Neyi değiştirir.** Bileşenlerin gerekçesi raporda **teorik** olarak
sunulmalı (çarpık dağılım, yavaş gelişen arıza, tek blok gürültüsü),
"CWRU'da ölçüldü" olarak değil. CWRU bu gerekçeleri test edecek koşulları
içermiyor: arıza ani, yük ayrık, kayıt kısa. Rejim katmanının değeri yavaş
gelişen arızada ortaya çıkar; o veri IMS/NASA'da var, henüz işlenmedi.

---

### B5 — Ürünün temel fizik varsayımı doğrulandı

**Ne çıktı** `[ÖLÇÜLDÜ]` — underhang radyal, ortalama `a1x`:

| Devir | 0 g | 6 g | 10 g | 15 g | 20 g | 25 g | 30 g | 35 g | Spearman |
|---|---|---|---|---|---|---|---|---|---|
| 20 Hz | 0,0299 | 0,0441 | 0,1196 | 0,1305 | 0,1791 | 0,4872 | 0,4181 | 0,7162 | ρ=+0,98 (p<0,001) |
| 30 Hz | 0,1363 | 0,3179 | 0,4162 | 0,5808 | 0,7167 | 0,8171 | 0,8712 | 0,9853 | **ρ=+1,00** |
| 40 Hz | 0,1382 | 0,1800 | 0,2707 | 0,7950 | 1,0323 | 1,4743 | 1,3335 | 2,0448 | ρ=+0,98 |
| 50 Hz | 0,2054 | 0,4607 | 1,0124 | 1,3251 | 1,7100 | 1,4969 | 2,4439 | 2,8933 | ρ=+0,98 |

30 Hz'de sıralama kusursuz monoton. 20 Hz'de 0 g'den 35 g'ye genlik **47 kat**
artıyor.

**Neyi kanıtlar.** Dengesizlik şiddeti ile 1× genliği arasındaki monoton ilişki
— ürünün üzerine kurulduğu fiziksel varsayım — ilk kez doğrudan ölçümle
doğrulandı. CWRU ile bu **hiç** yapılamıyordu, çünkü orada dengesizlik sınıfı yok.

**Neyi değiştirir.** İş planı 4.3'teki *"geç evre rulman kusurunun kamuya açık
veri kümeleriyle doğrulanması — en az iki bağımsız veri kümesi"* taahhüdünün
ikinci kümesi artık elde. Daha önemlisi, v1 hedef sınıfı hakkında ilk kez
somut cümle kurulabiliyor. Teknik notta "dengesizlik hakkında bir şey
söylenemez" sınırı **kaldırılmalı**, yerine bu tablo konmalı.

---

### B6 — Sonuç sensör konumuna bağlı

**Ne çıktı** `[ÖLÇÜLDÜ]`. Aynı arıza, aynı kayıt, farklı ivmeölçer.
Overhang radyal kanalda aynı analiz: ρ = +0,36 (p=0,385) / +0,83 (p=0,010) /
+0,45 (p=0,260) / +0,95 (p<0,001). Underhang'de dört devirde de ρ ≥ +0,98.

**Neyi kanıtlar.** Montaj noktası, dengesizlik–1× ilişkisinin görünüp
görünmemesini belirliyor. Yanlış konumda ilişki istatistiksel anlamlılığını
kaybediyor.

**Neyi değiştirir.** Montaj noktası bir kurulum detayı değil, **tasarım
kısıtıdır**. İş planı 4.3'teki "montaj tekrarlanabilirliği testi" iş paketi
artık sayısal gerekçeye sahip; bu iş paketinin gerekçesi rapora bu tabloyla
yazılmalı. Ayrıca ürün kılavuzunda montaj noktası bir öneri değil **şart**
olarak tanımlanmalı.

---

### B7 — Kurtosis beklentisi doğrulandı ama sınırlı

**Ne çıktı** `[ÖLÇÜLDÜ]` — underhang radyal:

| Küme | ortalama | medyan | std | n |
|---|---|---|---|---|
| sağlam (0 g) | 4,142 | 4,030 | 0,661 | 224 |
| 6 g | 3,621 | 3,308 | **1,448** | 28 |
| 10 g | 3,922 | 2,647 | **2,780** | 28 |
| 15 g | 2,724 | 2,320 | 1,130 | 28 |
| 20 g | 2,276 | 2,140 | 0,567 | 28 |
| 25 g | 1,984 | 1,878 | 0,330 | 28 |
| 30 g | 2,017 | 1,894 | 0,307 | 28 |
| 35 g | 2,104 | 2,015 | 0,244 | 28 |

**Neyi kanıtlar.** Mimari notundaki "sağlam ≈3,0, saf dengesizlik →1,5"
beklentisinin **yönü doğru** (3,98 → 1,98). Ancak 6 g ve 10 g'de kurtosis
ayırt etmiyor ve standart sapması devasa (1,448 ve 2,780).

**Neyi değiştirir.** Kurtosis'in "dışlayıcı öznitelik" olarak sunulduğu her
cümleye **şiddet koşulu** eklenmeli: düşük şiddette (≤10 g bu düzenekte)
kullanılamaz. Overhang kanalda kurtosis hiç düşmüyor (2,301 → 2,882), yani
bu iddia da konuma bağlı.

---

### B8 — MAFAULDA etki büyüklükleri kayıt düzeyinde ayakta kaldı

**Ne çıktı** `[HESAP]` — underhang radyal, **32 sağlam + 28 dengesiz kayıt**
(840 blok):

| Öznitelik | d (blok) | Kayıt düzeyi %95 | Sıfır dışında |
|---|---|---|---|
| a1x_rms | +2,78 | [+1,99, +4,01] | evet |
| hiz_rms | +2,08 | [+1,60, +2,88] | evet |
| a1x | +1,58 | [+1,22, +2,17] | evet |
| crest | −1,57 | [−2,76, −0,89] | evet |
| rms | +1,32 | [+0,94, +1,85] | evet |
| kurtosis | −1,32 | [−3,27, −0,55] | evet |
| a3x_a1x | −1,00 | [−1,77, −0,75] | evet |
| thd | −0,97 | [−1,52, −0,77] | evet |
| altharmonik | −0,86 | [−1,31, −0,65] | evet |
| a2x_a1x | −0,71 | [−1,03, −0,49] | evet |
| **rulman_bant** | +0,42 | [−0,09, +0,95] | **hayır** |

**Neyi kanıtlar.** B2'nin aksine bu bulgular istatistiksel olarak ayakta duruyor.
Fark, burada 60 bağımsız kayıt olması; CWRU'da 3 vardı. `a2x_a1x` ve `a3x_a1x`
dengesizlikte **düşüyor** — 1× büyüdüğü için oran küçülüyor; bu fiziksel olarak
doğru ve dengesizliğin 1× baskın olduğu klasik beklentisiyle uyumlu.
`rulman_bant`ın sıfırı içermesi **doğru davranıştır**: rulman özniteliği
dengesizliği görmemeli. Bu bir sağlamlık kontrolüdür ve geçmiştir.

**ÖNEMLİ — küçük örneklem uyarısı.** Bu tablo ilk turda **4 sağlam kayıtla**
hesaplanmıştı; `normal.tgz` tamamlanıp sağlam örneklem 32 kayda çıkınca sayılar
belirgin biçimde **değişti** `[ÖLÇÜLDÜ]`:

| Öznitelik | 4 kayıtla | 32 kayıtla | Değişim |
|---|---|---|---|
| a2x_a1x | −1,81 | **−0,71** | %61 zayıfladı |
| thd | −2,07 | **−0,97** | %53 zayıfladı |
| a3x_a1x | −2,04 | **−1,00** | %51 zayıfladı |
| altharmonik | −1,56 | −0,86 | %45 zayıfladı |
| a1x_rms | +2,54 | +2,78 | güçlendi |
| hiz_rms | +1,53 | +2,08 | güçlendi |
| a1x | +1,15 | +1,58 | güçlendi |

Yani **oran temelli öznitelikler** (a2x_a1x, thd, a3x_a1x) küçük sağlam
örneklemde olduğundan güçlü görünüyordu; **genlik temelli öznitelikler**
(a1x_rms, hiz_rms, a1x) ise olduğundan zayıf. Sıralama tersine döndü:
artık en güçlü ayırıcılar genlik temelli olanlar.

**Neyi değiştirir.** Teknik nota "hangi öznitelik dengesizliği ayırıyor"
sorusunun sayısal cevabı girebilir; **32 kayıtlı sürüm** kullanılmalıdır.
Öznitelik önceliklendirmesi `a1x_rms → hiz_rms → a1x` sırasına göre yapılmalı,
oran temelli özniteliklere ikincil rol verilmelidir. Ayrıca bu tablo, raporda
küçük örneklem uyarısının somut örneği olarak kullanılabilir.

---

### B9 — Sınıflandırıcı iş planı hedefini tutmuyor

İki ayrı test yapıldı ve **birbirinden çok farklı sonuç verdiler**. Fark,
bulgunun kendisidir.

**Test 1 — kayıt düzeyinde çapraz doğrulama** (StratifiedGroupKFold, 5 katman;
aynı kaydın blokları tek katmanda kalır, her katmanda iki sınıf da bulunur).
Devirler katmanlara **karışık** dağılır `[ÖLÇÜLDÜ]`:

| Kanal / derinlik | Tespit (en kötü katman) | Yanlış pozitif (en kötü) |
|---|---|---|
| underhang, derinlik 2 | %86,0 (%66,7) | %7,8 (%22,4) |
| underhang, derinlik 3 | %86,0 (%66,7) | %7,8 (%16,7) |
| overhang, derinlik 2 | %90,1 (%78,6) | %8,3 (%21,4) |

**Test 2 — görülmemiş devir** (üç devirde eğit, dördüncüde test et):

| Dışarıda | underhang d2 | underhang d3 | overhang d2 |
|---|---|---|---|
| 20 Hz | %71,4 / %0,0 | %71,4 / %0,0 | %91,8 / %26,2 |
| 30 Hz | %100,0 / **%100,0** | %100,0 / **%90,0** | %89,8 / %4,3 |
| 40 Hz | %49,0 / %0,0 | %85,7 / %1,4 | %36,7 / %4,3 |
| 50 Hz | %100,0 / %0,0 | %100,0 / %0,0 | %100,0 / **%54,8** |
| **ortalama** | **%80,1 / %25,0** | **%89,3 / %22,9** | **%79,6 / %22,4** |

**Neyi kanıtlar.** Sınıflandırıcı, gördüğü çalışma noktaları arasında
**ara değer bulabiliyor** (Test 1: %86–90 tespit, %8 yanlış pozitif — kabul
edilebilir sınırlarda). Ama bütün bir çalışma noktası eğitimden çıkarıldığında
**dışdeğerleme yapamıyor**: 30 Hz dışarıda bırakıldığında sağlam blokların
%90–100'ü alarm veriyor, 40 Hz dışarıda bırakıldığında tespit %36,7'ye düşüyor.

**Bu, mimarinin aleyhine değil LEHİNE bir sonuçtur** ve rapordaki en değerli
argümanlardan biri olabilir. Küresel, sabit eğitilmiş bir sınıflandırıcı
görülmemiş çalışma noktasında çöküyor. Ürünün 1. katmanı tam olarak bu yüzden
vardır: her makinenin kendi normalini kendi çalışma noktasında öğrenir, o
noktayı "görülmemiş" olmaktan çıkarır. Rakiplerin sabit eşikli yaklaşımının
neden saha koşullarında bozulduğunun deneysel karşılığı budur.

**Neyi değiştirir.** Üç şey:

1. Teknik notta sınıflandırıcı başarımı **iki sayıyla birlikte** verilmelidir:
   karışık katmanda %86 / %7,8, görülmemiş çalışma noktasında %80 / %25.
   Tek başına birincisini vermek yanıltıcı, tek başına ikincisini vermek
   haksız olur.
2. İş planı 4.3'teki *"eğitimde görülmemiş montajda tespit ≥ %90"* hedefi,
   **küresel sınıflandırıcıyla tutturulamaz**. Hedef ya cihaz-üstü öğrenen
   mimariye göre yeniden tanımlanmalı ya da "sapma tespiti" ile "sınıf
   atama" başarımı ayrı ayrı hedeflenmelidir.
3. Bu sonuç, 1. katmanın (cihazda öğrenen baseline) gerekliliğinin **deneysel
   gerekçesi** olarak rapora girmelidir. Şu ana kadar bu gerekçe yalnızca
   teorikti.

**Örneklem etkisi.** İlk turda sağlam örneklem 4 kayıttı ve yanlış pozitif
%25 (en kötü %100) çıkıyordu. 32 kayda çıkınca **%7,8'e (en kötü %22,4)**
düştü `[ÖLÇÜLDÜ]`. Önceki rakam büyük ölçüde örneklem yetersizliğiydi;
bu, raporda küçük örneklemle sonuç yayımlamanın riskine somut örnektir.

**Metodolojik düzeltme.** İlk turda kullanılan katman kurgusu hatalıydı: 32
sağlam kayıtla dilimleme 28 dengesiz kaydı bölemiyor, bazı katmanlarda test
kümesinde hiç dengesiz kayıt kalmıyordu (tespit `nan`). `StratifiedGroupKFold`
ile değiştirildi. Ayrıca ilk turda Test 1 ile Test 2 aynı sayıları veriyordu —
kayıt kimlikleri sıralı olduğundan katman kurgusu ikisini de devire göre
bölüyordu. Düzeltmeden sonra ikisi **gerçekten farklı** testler oldu ve
yukarıdaki ayrım ortaya çıktı.

---

### B10 — Metodolojik düzeltme: kayıt kimliği çakışması

**Ne çıktı.** İlk turda kayıt kimliği olarak dosya adı kullanılmıştı. MAFAULDA'da
aynı dosya adı (örneğin `49.9712.csv`) birden fazla kütle klasöründe bulunduğu
için 28 dengesiz kayıt 22 gibi görünüyor, farklı kütlelerin blokları tek kayıt
sayılıyordu. Kimlik `etiket_kütle_devir` olarak düzeltildi ve analiz yeniden
koşturuldu.

**Neyi kanıtlar.** Kayıt düzeyi analizlerinde kimlik tanımı sonucu değiştirir.
Düzeltme sonrası etki büyüklükleri pratikte aynı kaldı, çapraz doğrulama
sayıları değişti (tespit %88,2 → %82,1; yanlış pozitif %37,5 → %25,0).

**Neyi değiştirir.** Rapora giren tüm çapraz doğrulama sayıları **düzeltme
sonrası** sürümden alınmalıdır. Bu belgedeki tablolar düzeltilmiş sürümdür.

---

### B11 — Dengesizlik ile eksen kaçıklığı ayrımı

**Veri.** MAFAULDA yatay eksen kaçıklığı, 4 kademe (0,5 / 1,0 / 1,5 / 2,0 mm) ×
2 devir (30, 50 Hz) = 8 kayıt `[VERİSETİ]`. Karşılaştırma yalnızca **üç sınıfın
da bulunduğu** devir bantlarında yapıldı, aksi hâlde devir farkı sınıf farkı gibi
görünürdü. Dikey kaçıklık listesi alınamadı, henüz yok.

**Ne çıktı** `[ÖLÇÜLDÜ]` — underhang radyal, sınıf ortalamaları:

| Sınıf | a1x | a2x_a1x | a3x_a1x | thd | kurtosis | n blok | n kayıt |
|---|---|---|---|---|---|---|---|
| sağlam | 0,1622 | 0,1658 | 0,1921 | 0,3705 | 4,14 | 112 | 16 |
| dengesiz | 1,1463 | 0,0387 | 0,0304 | 0,0835 | 2,03 | 98 | 14 |
| kaçıklık | 0,1650 | 0,1711 | 0,1329 | 0,4294 | 3,97 | 44 | 8 |

Dengesiz–kaçıklık ayrımı (Cohen d, kayıt düzeyi %95 bootstrap):

| Öznitelik | d | Kayıt %95 | Sıfır dışında |
|---|---|---|---|
| a1x_rms | −4,08 | [−8,33, −2,81] | evet |
| thd | +2,35 | [+1,81, +5,38] | evet |
| crest | +2,19 | [+1,48, +3,48] | evet |
| kurtosis | +2,17 | [+1,84, +6,66] | evet |
| a3x_a1x | +2,12 | [+1,01, +4,78] | evet |
| **a2x_a1x** | **+2,10** | **[+1,23, +4,33]** | **evet** |
| hiz_rms | −2,16 | [−3,45, −1,66] | evet |
| altharmonik | +1,79 | [+1,23, +3,37] | evet |
| a1x | −1,59 | [−2,52, −1,25] | evet |
| rms | −1,32 | [−2,05, −0,91] | evet |
| rulman_bant | −0,51 | [−1,53, +0,46] | hayır |

**Doğrulanan taraf.** `a2x_a1x` dengesizlik ile kaçıklığı gerçekten
ayırıyor: kaçıklıkta oran 0,1711, dengesizlikte 0,0387 — **4,4 kat fark**, kayıt
düzeyinde güven aralığı sıfırı dışlıyor. Mimari notundaki klasik beklenti bu
yönde doğrulandı. `kurtosis` de ayırıyor (kaçıklık 3,97, dengesizlik 2,03), yani
B7'deki "dengesizlik kurtosis'i düşürür" bulgusunun aynası.

**Düzeltilmesi gereken taraf.** Beklenti "kaçıklıkta 2× baskın"
şeklinde kurulmuştu. Mutlak değere bakıldığında bu **doğrulanmıyor**:
kaçıklıkta 2× genliği ≈ 0,1650 × 0,1711 = **0,0282**, sağlamda ≈ 0,1622 ×
0,1658 = **0,0269**. Yani kaçıklık, sağlamda olmayan bir 2× yükselmesi
üretmiyor `[HESAP]`. Ayrımı yaratan şey, **dengesizliğin 1×'i çok büyütüp
oranı çökertmesi**.

Dolayısıyla `a2x_a1x` bir **kaçıklık tespit edicisi değil**, bir
**dengesizlik dışlayıcısıdır**. Bu ayrım ürün mantığı açısından önemlidir:
düşük `a2x_a1x` "dengesizlik var" der; yüksek `a2x_a1x` "dengesizlik yok" der,
"kaçıklık var" demez.

**Şiddet ilişkisi zayıf.** Kaçıklık kademesiyle `a2x_a1x`: 0,5 mm → 0,0944;
1,0 mm → 0,0787; 1,5 mm → 0,1913; 2,0 mm → 0,2889. 1,0 mm üstünde artıyor ama
**monoton değil**; B5'teki dengesizlik monotonluğuyla kıyaslanacak bir tutarlılık
yok `[ÖLÇÜLDÜ]`.

**Kanal bağımlılığı bir kez daha.** Overhang radyal kanalda **11 özniteliğin
11'inin** güven aralığı sıfırı içeriyor — dengesizlik ile kaçıklık o kanalda
hiç ayrılmıyor. Bu, B6'nın bağımsız ikinci doğrulamasıdır.

**Sınır ve doğrulama.** Bu karşılaştırma ilk turda yalnızca 2 sağlam kayıtla
yapılmıştı. `normal.tgz` tamamlanınca sağlam örneklem **16 kayda** çıkarıldı ve
sonuç **değişmedi**: kaçıklıkta 2× ≈ 0,0282, sağlamda ≈ 0,0269. Bulgu artık
yeterli sağlam örnekleme dayanıyor. Dikey kaçıklık verisi hâlâ yok.

**Neyi değiştirir.** Mimari notunda `a2x_a1x` "kaçıklık göstergesi" olarak
geçiyorsa **düzeltilmeli**, "dengesizlik dışlayıcısı" olarak yazılmalı. Kaçıklık
sınıfı v1 kapsamına alınacaksa mutlak 2× genliğinin bu düzenekte ayırt etmediği
not edilmeli; kaçıklık tespiti için başka bir öznitelik aranmalıdır.

---

## 5. Rapor revizyonu — somut değişiklik listesi

| # | Mevcut durum | Yapılacak |
|---|---|---|
| 1 | Teknik notta B1 için %68,4 ve "DESTEKLEMIYOR" ifadeleri var | Geçersiz. B1 = %0,0 yanlış alarm, %11,5 öğreniyor, %92,0 tespit |
| 2 | %62,1 çıplak veriliyor | Yanına Wilson [51,6–71,5], kayıt bootstrap [0–100], "etkin örneklem 3 kayıt" notu |
| 3 | 4σ örtük olarak optimum sunuluyor | "Karardır, optimum değildir" + ROC tablosu (B3) |
| 4 | Mimari bileşenleri gerekçelendirilmiş sayılıyor | Ablasyon tablosu (B4) + "bu veride katkı ölçülemedi" cümlesi |
| 5 | Dengesizlik hakkında iddia yok | B5 tablosu + ρ değerleri eklenecek |
| 6 | Montaj noktası kurulum detayı gibi | Tasarım kısıtı olarak yeniden yazılacak (B6) |
| 7 | Kurtosis koşulsuz dışlayıcı sunuluyor | "≤10 g'de kullanılamaz" koşulu eklenecek (B7) |
| 8 | Sınıflandırıcı başarımı hakkında sayı yok veya iyimser | B9'un **iki** tablosu birlikte: karışık katman %86/%7,8, görülmemiş çalışma noktası %80/%25 |
| 9 | `SINIRLAR.md` yok | Bölüm 6 ayrı dosyaya çıkarılacak |
| 10 | Rakip karşılaştırması "aynı eşikte daha az alarm" | "Eşiğin elle seçilmesine gerek yok" olarak yeniden kurulacak (B3) |
| 11 | `a2x_a1x` kaçıklık göstergesi olarak sunuluyor | "Dengesizlik dışlayıcısı" olarak düzeltilecek; mutlak 2×'in ayırt etmediği not edilecek (B11) |

---

## 6. Bu çalışmanın **gösteremediği** şeyler

Ayrı bir `SINIRLAR.md` dosyasına çıkarılacaktır.

- **Rejim katmanının üstünlüğü gösterilemedi.** CWRU'da sürekli öğrenen tek
  baseline da %0 yanlış alarm veriyor. Rejim katmanının değeri yavaş gelişen
  arızada ortaya çıkar; o veri işlenmedi.
- **Kaynayan kurbağa problemi test edilemedi.** CWRU'da arıza ani. Sürekli
  öğrenmenin yavaş gelişen arızayı yutup yutmadığı bilinmiyor.
- **Sınıflandırıcı doğrulanmadı** (B9).
- **Sağlam örneklem artık yeterli** (32 kayıt); önceki 4 kayıtlı sonuçlar
  geçersizdir ve bu belgede güncellenmiştir.
- **Montaj tekrarlanabilirliği ölçülemedi.** MAFAULDA'da tek montaj var.
  B6 sensör **konumunu** gösteriyor, aynı konuma tekrar tekrar montajın
  yayılımını değil.
- **Kaçıklığın kendisi tespit edilemiyor.** B11 dengesizliği kaçıklıktan
  ayırıyor, ama kaçıklığı sağlamdan ayıracak bir öznitelik gösterilemedi;
  mutlak 2× genliği sağlamla neredeyse aynı. Dikey kaçıklık verisi henüz yok.
- **Kaçıklık şiddeti–öznitelik ilişkisi monoton değil** (B11).
- **50 Hz şebeke koşulları test edilmedi.** Her iki veri kümesi de 60 Hz
  şebekeden. Türkiye'de 100 Hz hattı 2 kutuplu motorun 2× harmoniğine çok
  yakın; maskeleme 50 Hz'de daha tehlikeli.
- **Gömülü uygulanabilirlik doğrulanmadı.** Simülasyon float64; MCU float32.
  Welford `m2` birikiminin float32'de taşıp taşmadığı, blok başına çevrim
  sayısı ölçülmedi.
- **Gerçek makinede hiç test edilmedi.**

---

## 7. Sıradaki işler — öncelik sırasıyla

1. ~~`normal.tgz`'yi tamamla~~ **YAPILDI.** Sağlam kayıt 4 → 32 (eşleşen
   devir bandında). Yanlış pozitif %25 → %7,8'e düştü; etki büyüklükleri
   yeniden hesaplandı (B8).
2. **MAFAULDA'da üç fazlı devreye alma protokolünü kur.** Ürünün gerçekten
   yaptığı şeyi ölç; küresel sınıflandırıcıyı değil.
3. **Eksen kaçıklığı analizi** (veri iniyor): `a2x_a1x` dengesizlik ile
   kaçıklığı ayırıyor mu?
4. **IMS/NASA** (1,08 GB): kaynayan kurbağa testi. İş planındaki en zayıf
   iddiaya sayısal dayanak verecek tek deney.
5. **pytest paketi** — özellikle daha önce karşılaşılan sekiz tuzak için.
6. **Veri sızıntısı denetiminin yazılı hâli.**
7. **50 Hz şebeke testi**, sentetik sinyalle.
8. **Teknik notun yeniden üretimi** — Bölüm 5'teki liste uygulanarak.

---

## 8. Elde ne var — depo yapısı

```
axeon-edge-dogrulama/
  README.md                    genel tanitim, calistirma, ozet sonuclar
  LICENSE                      tum haklari sakli, dogrulama izni verilmis
  requirements.txt             dogrulanan surumler
  belge/
    RAPOR_TEMELI.md            bu belge
    VERI_KAYNAKLARI.md         veri kunyeleri, kosullar, sinirlar
  src/
    axeon_dogrulama.py         cekirdek modul (onceki surumden degistirilmedi)
    oznitelik_cikarimi.py      CWRU oznitelik tablosu
    karsilastirma.py           uc fazli senaryo, dort yontem
    istatistik.py              Wilson, bootstrap, ROC, ablasyon
    mafaulda_dengesizlik.py    monotonluk, kurtosis, ayirt edicilik
    mafaulda_siniflandirici.py etki buyuklugu, karar agaci
    mafaulda_kaciklik.py       dengesizlik / kaciklik ayrimi
  scripts/
    indir_cwru.py              16 dosya, SHA-256 dogrulamali
    indir_mafaulda.py          hedefli ornekleme
  sonuc/
    oznitelikler.csv                    CWRU, 450 blok
    mafaulda_oznitelikler.csv           MAFAULDA saglam + dengesizlik, 840 blok
    mafaulda_kaciklik_oznitelikler.csv  MAFAULDA kaciklik, 112 blok
    referans_oznitelikler.csv           yapi tasinmadan onceki tablo
    sonuclar.json                       ana karsilastirma
    istatistik.json                     guven araliklari, ROC, ablasyon
    mafaulda_rapor.json                 monotonluk, kurtosis, ayirt edicilik
    mafaulda_siniflandirici.json        etki buyuklugu, capraz dogrulama
    mafaulda_kaciklik_rapor.json        kaciklik ayrimi
  veri/                        indirilen veri; depoya dahil degil
```

Ham veri depoda yer almaz. `sonuc/` altındaki tablolar 4096 örneklik
bloklardan hesaplanmış özet büyüklüklerdir; kaynak sinyali içermezler.

---

## 9. Tekrar üretim

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

python scripts/indir_cwru.py        16/16 kunye dogrulanmali
python scripts/indir_mafaulda.py

python src/oznitelik_cikarimi.py
python src/karsilastirma.py
python src/istatistik.py
python src/mafaulda_dengesizlik.py
python src/mafaulda_siniflandirici.py
python src/mafaulda_kaciklik.py
```

Bootstrap tohumu 20260824, tur sayısı 2000; her ikisi de koda sabittir.
Çıktılar koşudan koşuya değişmez.

Yapı taşındıktan sonra öznitelik tablosu yeniden üretilmiş ve taşımadan
önceki tabloyla karşılaştırılmıştır. En büyük bağıl fark 7.0e-13, yani
taşıma davranışı değiştirmemiştir.

---

## 10. Bir cümlede

**Ürünün fiziği doğrulandı, ticari argümanının gerekçesi değişti, cihaz-üstü
öğrenme gerekliliği deneysel dayanak kazandı.** Dengesizlik–1× ilişkisi güçlü ve monoton çıktı; buna karşılık
"rakipler yük değişiminde %62 yanlış alarm verir" iddiası hem istatistiksel
olarak (3 kayıt) hem de eşik seçimine bağlılık nedeniyle tek başına
savunulamaz durumda. Doğru argüman şudur: **eşiğin elle seçilmesine gerek
kalmaması.**
