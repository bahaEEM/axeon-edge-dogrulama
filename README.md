# AXEON-Edge — Ön Doğrulama Çalışması

Dönen ekipmanlarda cihaz üstünde öğrenen kestirimci bakım mimarisinin,
kamuya açık titreşim veri kümeleri üzerinde sınanması.

Bu depo, AXEON-Edge teknik notunda ve iş planında yer alan sayısal
iddiaların üretildiği kodu, veri künyelerini ve analiz çıktılarını içerir.
Amacı, raporda geçen her rakamın hangi veriden, hangi kodla ve hangi
varsayımlarla elde edildiğinin bağımsız olarak doğrulanabilmesidir.

Depoda ham veri bulunmaz. Veri kümeleri `scripts/` altındaki betiklerle
kendi kaynaklarından indirilir.

---

## Neyi sınıyoruz

Ürün iki katmanlıdır. Birinci katman, cihaz makineye takıldığında o
makinenin normalini öğrenir ve sonraki ölçümlerin bu normale uzaklığına
bakar. İkinci katman, sapma tespit edildikten sonra imzayı bilinen bir
arıza sınıfına eşler.

Sınanan sorular:

1. Devreye almada dondurulmuş tek bir referans, yük değiştiğinde yanlış
   alarm verir mi?
2. Çalışma noktasına göre koşullandırılmış referans bunu çözer mi?
3. Dengesizlik şiddeti ile titreşim imzası arasında kullanılabilir bir
   ilişki var mı?
4. Sabit eğitilmiş bir sınıflandırıcı, eğitimde görülmemiş çalışma
   noktasında çalışır mı?

---

## Özet sonuçlar

Ayrıntılar ve güven aralıkları için `belge/RAPOR_TEMELI.md`.

**Tekrar üretilebilirlik.** Çalışma temiz bir makinede sıfırdan kuruldu.
Üretilen öznitelik tablosu ile önceki tablo arasındaki en büyük bağıl fark
7.0e-13, yani kayan nokta gürültüsü düzeyinde.

**CWRU üzerinde devreye alma senaryosu.** Dondurulmuş referans yük
değişiminde %62.1 yanlış alarm üretiyor, çalışma noktasına koşullandırılmış
referans %0.0 üretiyor. Ancak bu farkın kayıt düzeyindeki %95 güven aralığı
sıfırı içeriyor: Faz 2'deki 87 blok yalnızca 3 bağımsız kayıttan geliyor.
Ayrıca fark eşiğe bağlı; z eşiği 5.0 seçildiğinde dondurulmuş referans da
%0.0 yanlış alarm veriyor. Bu iki nokta raporda açıkça belirtilmiştir.

**MAFAULDA üzerinde dengesizlik.** Dengesizlik kütlesi arttıkça 1× genliği
monoton artıyor. Spearman katsayısı dört devir noktasında sırasıyla +0.98,
+1.00, +0.98, +0.98. Ürünün dayandığı fiziksel varsayım bu veriyle
doğrulanmıştır.

**Sensör konumu.** Aynı kayıtta underhang radyal kanalda ilişki güçlüyken
overhang radyal kanalda kayboluyor (Spearman +0.36, p=0.385'e kadar
düşüyor). Montaj noktası bir kurulum tercihi değil, tasarım kısıtıdır.

**Sınıflandırıcı.** Kayıtlar katmanlara karışık dağıldığında derinliği 2
olan karar ağacı %86.0 tespit, %7.8 yanlış pozitif veriyor. Bütün bir
çalışma noktası eğitimden çıkarıldığında yanlış pozitif %25.0'a çıkıyor ve
bir devir noktasında %100'e ulaşıyor. Sabit eğitilmiş küresel bir
sınıflandırıcı görülmemiş çalışma noktasında güvenilir değildir; bu sonuç
cihaz üstünde öğrenen birinci katmanın gerekçesidir.

---

## Depo yapısı

```
src/
  axeon_dogrulama.py           cekirdek modul: Welford, spektrum, devir
                               tahmini, 11 oznitelik, karar motoru
  oznitelik_cikarimi.py        CWRU kayitlarindan oznitelik tablosu
  karsilastirma.py             uc fazli devreye alma senaryosu, dort yontem
  istatistik.py                Wilson araligi, kayit duzeyi bootstrap,
                               ROC taramasi, ablasyon
  mafaulda_dengesizlik.py      kutle-genlik monotonlugu, kurtosis, ayirt
                               edicilik
  mafaulda_siniflandirici.py   etki buyuklugu ve karar agaci sinamalari
  mafaulda_kaciklik.py         dengesizlik ile eksen kacikligi ayrimi

scripts/
  indir_cwru.py                16 dosya, SHA-256 dogrulamali
  indir_mafaulda.py            hedefli ornekleme ile indirme

sonuc/                         uretilen tablolar ve JSON ciktilari
belge/
  RAPOR_TEMELI.md              bulgular; her biri icin ne cikti, neyi
                               kanitlar, neyi degistirir
  EK_A_SAYILARIN_KAYNAGI.md    raporda gecen her sayinin hangi veriden,
                               hangi kodla ve hangi ciktidan geldigi
  VERI_KAYNAKLARI.md           veri kunyeleri, kullanim kosullari, sinirlar
veri/                          indirilen veri buraya gelir, depoya dahil degil
```

---

## Çalıştırma

Python 3.11 veya üzeri gerekir.

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Veriyi indirin. CWRU yaklaşık 67 MB, MAFAULDA yaklaşık 990 MB.

```
python scripts/indir_cwru.py
python scripts/indir_mafaulda.py
```

`indir_cwru.py` her dosyanın SHA-256 değerini doğrular ve künye tutmazsa
hata koduyla durur. `indir_mafaulda.py` kesintiye uğrarsa inmiş dosyaları
atlayarak devam eder, tekrar çalıştırmak yeterlidir.

Analizleri sırayla çalıştırın:

```
python src/oznitelik_cikarimi.py
python src/karsilastirma.py
python src/istatistik.py
python src/mafaulda_dengesizlik.py
python src/mafaulda_siniflandirici.py
python src/mafaulda_kaciklik.py
```

Sonuçlar `sonuc/` altına yazılır. Bootstrap tohumu 20260824 ve tur sayısı
2000 koda sabitlenmiştir, dolayısıyla çıktılar koşudan koşuya değişmez.

---

## Yöntem notları

**Bloklama.** Öznitelikler 4096 örneklik bloklardan hesaplanır. CWRU'da
örnekleme 12 kHz, MAFAULDA'da ham veri 50 kHz'dir. 50 kHz'de 4096'lık blok
12.2 Hz çözünürlük verir ve bu 1× ile 2×'i ayırmaya yetmez; bu nedenle
MAFAULDA kayıtları sekiz kat FIR desimasyonla 6250 Hz'e indirilir ve
çözünürlük 1.53 Hz olur.

**Öznitelikler.** rms, hiz_rms, a1x, a1x_rms, a2x_a1x, a3x_a1x,
altharmonik, thd, kurtosis, crest, rulman_bant. Her ikisi de aynı
fonksiyonla hesaplanır.

**Bağımsızlık.** Aynı kayıttan alınan ardışık bloklar bağımsız değildir.
Bu nedenle tüm güven aralıkları ve çapraz doğrulama bölmeleri kayıt
düzeyinde yapılır. Blok düzeyinde hesaplanmış Wilson aralıkları yalnızca
karşılaştırma amacıyla ayrıca verilmiştir.

**Negatif sonuçlar.** Fayda göstermeyen bileşenler ve hedefi tutmayan
sonuçlar rapordan çıkarılmamıştır. Ablasyon tablosu ve görülmemiş çalışma
noktası testi bu kapsamdadır.

---

## Bilinen sınırlar

- Montaj tekrarlanabilirliği ölçülemedi; her iki veri kümesinde de tek
  montaj vardır.
- Yavaş gelişen arıza davranışı sınanamadı; her iki kümede de arızalar
  anidir. Bu sınama için IMS/NASA run-to-failure verisi gereklidir.
- Her iki veri kümesi de 60 Hz şebekeden alınmıştır. 50 Hz koşulları ayrıca
  sınanmalıdır.
- Simülasyon float64 ile çalışır. Gömülü platformda float32 kullanılacaktır
  ve bu farkın etkisi ölçülmemiştir.
- Dikey eksen kaçıklığı verisi henüz indirilmemiştir.

Sınırların tam listesi `belge/RAPOR_TEMELI.md` içindedir.

---

## Lisans

Tüm hakları saklıdır. Bu çalışma ticari bir ürünün geliştirilmesi
kapsamında üretilmiştir ve açık kaynak lisansı altında yayımlanmamıştır.
Görüntüleme ve doğrulama amaçlı çalıştırma izni verilmiştir; yeniden
dağıtım, ticari kullanım ve türetilmiş eser oluşturma yazılı izne tabidir.
Ayrıntılar için `LICENSE` dosyasına bakınız.

Bu depo hiçbir üçüncü taraf veri kümesini içermez. Kullanılan veri kümeleri
kendi kaynaklarından indirilir ve kendi koşullarına tabidir.
