# -*- coding: utf-8 -*-
"""
AXEON-Edge — Cihaz ustu ogrenen referans mimarisinin kamuya acik veri
kumesiyle dogrulanmasi.

Bu betik, gomulu tarafta calisacak karar mimarisinin PC karsiligidir.
Amac, donanim uretilmeden once mimarinin iki iddiasini olcmek:

  IDDIA A  Rejim-kosullu referans, calisma noktasi degistiginde yanlis
           alarmi bastirir. Klasik tek referansli esik bastiramaz.
  IDDIA B  Ayni mimari, gorulmemis bir calisma noktasinda gercek arizayi
           yakalar.

Veri: Case Western Reserve University Bearing Data Center, 12k Drive End.
      Ayni motor dort ayri yuk noktasinda: 1797 / 1772 / 1750 / 1730 d/dk.
      Bu, sabit devirli bir asenkron motorun kayma araligina karsilik gelir
      (yaklasik %3,7) ve tam olarak sahada karsilasilacak durumdur.

Gomulu kodla ortak olan cekirdek: welford_guncelle() fonksiyonu, kutu basina
YALNIZCA UC SAYI (n, ortalama, m2) tutar. Ornekler saklanmaz.
"""

import numpy as np
from scipy.io import loadmat
from scipy.signal import get_window
import os, json, math

# ----------------------------------------------------------------------
# 0. SABITLER
# ----------------------------------------------------------------------
BLOK_N        = 4096      # blok basina ornek
MIN_OGRENME   = 20        # bir kutunun ogrenilmis sayilmasi icin gereken blok
Z_KUR         = 4.0       # alarmi kuran z esigi
Z_DUSUR       = 2.5       # alarmi dusuren z esigi (histerezis)
OY_M          = 8         # son M blok
OY_K          = 5         # bunlarin K tanesi asarsa alarm
SD_TABAN_ORAN = 0.02      # standart sapma tabani (sifira bolmeyi onler)
DEVIR_ARAMA   = (20.0, 35.0)   # Hz, 1200-2100 d/dk
HARMONIK_SAY  = 6         # devir tahmininde kullanilan harmonik sayisi
EPS           = 1e-12

# CWRU surucu ucu rulmani SKF 6205-2RS JEM, carpanlar CWRU dokumantasyonundan
BPFO_CARPAN = 3.5848
BPFI_CARPAN = 5.4152


# ----------------------------------------------------------------------
# 1. WELFORD — gomulu kodun birebir karsiligi
# ----------------------------------------------------------------------
class Welford:
    """Cevrimici ortalama ve varyans. Kutu basina yalnizca uc sayi tutar.

    Gomulu C karsiligi:
        typedef struct { uint32_t n; float mean; float m2; } welford_t;
    """
    __slots__ = ("n", "ortalama", "m2")

    def __init__(self):
        self.n = 0
        self.ortalama = 0.0
        self.m2 = 0.0

    def guncelle(self, x):
        self.n += 1
        d = x - self.ortalama
        self.ortalama += d / self.n
        d2 = x - self.ortalama
        self.m2 += d * d2

    @property
    def sd(self):
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0

    def ogrenildi_mi(self, esik=MIN_OGRENME):
        return self.n >= esik


# ----------------------------------------------------------------------
# 2. VERI YUKLEME
# ----------------------------------------------------------------------
def mat_yukle(yol):
    """CWRU .mat dosyasindan surucu ucu ivme sinyalini ve etiket devrini alir.

    DIKKAT: bazi CWRU dosyalari birden fazla kaydin degiskenlerini icerir.
    Ornegin 99.mat hem X098_DE_time hem X099_DE_time tasir. Ilk eslesen
    degiskeni almak sessizce YANLIS kaydi okur. Bu nedenle degisken adi
    dosya numarasiyla eslestirilir.
    """
    m = loadmat(yol)
    numara = os.path.splitext(os.path.basename(yol))[0]
    onek = "X" + numara.zfill(3)
    anahtar = [k for k in m if k.startswith(onek) and k.endswith("_DE_time")]
    if not anahtar:                      # numarali eslesme yoksa tek adaya dus
        anahtar = [k for k in m if k.endswith("_DE_time")]
        if len(anahtar) != 1:
            raise KeyError(f"{yol}: DE kanali belirsiz -> {anahtar}")
    de = m[anahtar[0]]
    rpm_anahtar = [k for k in m if k.startswith(onek) and k.endswith("RPM")] \
                  or [k for k in m if k.endswith("RPM")]
    rpm = float(m[rpm_anahtar[0]].ravel()[0]) if rpm_anahtar else None
    return de.ravel().astype(np.float64), rpm


def ornekleme_hizi_belirle(x, rpm_etiket, adaylar=(12000.0, 48000.0)):
    """Ornekleme hizini etiket devrine karsi spektrumdan dogrular.

    Dosyada ornekleme hizi yazmiyor. Etiket devri biliniyor; dogru fs,
    mil frekansinin (rpm/60) civarinda belirgin bir tepe uretendir.
    """
    if rpm_etiket is None:
        return adaylar[0], None
    hedef = rpm_etiket / 60.0
    en_iyi, en_iyi_skor = adaylar[0], -1.0
    for fs in adaylar:
        n = min(len(x), 1 << 16)
        seg = x[:n] - x[:n].mean()
        w = get_window("hann", n)
        S = np.abs(np.fft.rfft(seg * w))
        f = np.fft.rfftfreq(n, 1.0 / fs)
        # hedefin +-%3 bandindaki enerji / genis bandin ortalamasi
        bant = (f > hedef * 0.97) & (f < hedef * 1.03)
        ref = (f > 5) & (f < 200)
        if bant.sum() == 0 or ref.sum() == 0:
            continue
        skor = S[bant].max() / (S[ref].mean() + EPS)
        if skor > en_iyi_skor:
            en_iyi, en_iyi_skor = fs, skor
    return en_iyi, en_iyi_skor


# ----------------------------------------------------------------------
# 3. SPEKTRUM
# ----------------------------------------------------------------------
def spektrum(blok, fs):
    """Ortalamasi cikarilmis, Hanning pencereli, genligi duzeltilmis spektrum.

    Hanning coherent gain 0,5 oldugundan genlikler 2 ile carpilir.
    """
    x = blok - blok.mean()                 # DC cikar: yoksa sensorun acisini olceriz
    w = get_window("hann", len(x))
    X = np.fft.rfft(x * w)
    genlik = np.abs(X) * 2.0 / (len(x) * 0.5)
    f = np.fft.rfftfreq(len(x), 1.0 / fs)
    return f, genlik


# ----------------------------------------------------------------------
# 4. TAKOMETRESIZ DEVIR TAHMINI
# ----------------------------------------------------------------------
def devir_tahmin(f, genlik, arama=DEVIR_ARAMA, H=HARMONIK_SAY):
    """Harmonik ailesi uydurmasiyla mil frekansini tahmin eder.

    En buyuk tepeyi dogrudan 1x kabul etmek yaygin ve yanlistir; rulman
    veya kanat gecis tepesi daha buyuk olabilir. Bunun yerine her aday
    frekans icin harmonik ailesinin toplam enerjisi hesaplanir; ailesi
    en guclu olan aday 1x kabul edilir.

    Dondurur: (tahmin_hz, guven). Guven = en iyi skor / ikinci en iyi skor.
    """
    df = f[1] - f[0]
    i0, i1 = int(arama[0] / df), int(arama[1] / df)
    i0 = max(i0, 1)
    adaylar = np.arange(i0, min(i1, len(f) - 1))
    if len(adaylar) < 3:
        return None, 0.0

    skorlar = np.zeros(len(adaylar))
    for j, i in enumerate(adaylar):
        fa = f[i]
        s = 0.0
        for h in range(1, H + 1):
            idx = int(round(h * fa / df))
            if idx >= len(genlik) - 1:
                break
            # +-1 bin tolerans: tam bine oturmayan harmonigi kacirmamak icin
            s += genlik[idx - 1:idx + 2].max() / h      # yuksek harmonik daha az agirlikli
        skorlar[j] = s

    en_iyi = int(np.argmax(skorlar))
    # ayni tepenin komsulugunu ikinci en iyi saymamak icin +-%5 bastir
    maske = np.ones(len(skorlar), bool)
    fb = f[adaylar[en_iyi]]
    maske[np.abs(f[adaylar] - fb) < 0.05 * fb] = False
    ikinci = skorlar[maske].max() if maske.any() else EPS
    guven = float(skorlar[en_iyi] / (ikinci + EPS))

    # parabolik interpolasyon: bin altinda cozunurluk
    j = en_iyi
    if 0 < j < len(skorlar) - 1:
        y0, y1, y2 = skorlar[j - 1], skorlar[j], skorlar[j + 1]
        payda = (y0 - 2 * y1 + y2)
        delta = 0.5 * (y0 - y2) / payda if abs(payda) > EPS else 0.0
        delta = float(np.clip(delta, -0.5, 0.5))
    else:
        delta = 0.0
    tahmin = float(f[adaylar[en_iyi]] + delta * df)
    return tahmin, guven


# ----------------------------------------------------------------------
# 5. OZNITELIKLER
# ----------------------------------------------------------------------
def bant_genlik(f, genlik, merkez, bagil_tol=0.02):
    if merkez is None or merkez <= 0:
        return 0.0
    m = np.abs(f - merkez) <= max(bagil_tol * merkez, f[1] - f[0])
    return float(genlik[m].max()) if m.any() else 0.0


def oznitelikler(blok, fs, f, genlik, f1x):
    """On bir oznitelik. Hepsi pozitif; log domeninde degerlendirilecek."""
    x = blok - blok.mean()
    rms = float(np.sqrt(np.mean(x ** 2)))
    tepe = float(np.max(np.abs(x)))
    sd = x.std() + EPS
    kurtosis = float(np.mean(((x - x.mean()) / sd) ** 4))
    crest = tepe / (rms + EPS)

    # hiz RMS 10-1000 Hz: ivme spektrumu 2*pi*f'e bolunur (frekans domeninde integral)
    m = (f >= 10) & (f <= 1000)
    hiz = genlik[m] / (2 * np.pi * np.maximum(f[m], EPS))
    hiz_rms = float(np.sqrt(np.sum(hiz ** 2) / 2.0))

    a1 = bant_genlik(f, genlik, f1x)
    a2 = bant_genlik(f, genlik, 2 * f1x if f1x else None)
    a3 = bant_genlik(f, genlik, 3 * f1x if f1x else None)
    a05 = bant_genlik(f, genlik, 0.5 * f1x if f1x else None)
    a15 = bant_genlik(f, genlik, 1.5 * f1x if f1x else None)
    harm = sum(bant_genlik(f, genlik, h * f1x) ** 2 for h in range(2, 6)) if f1x else 0.0

    # rulman bandi: mil frekansinin 10-40 kati arasindaki enerji
    if f1x:
        mb = (f >= 10 * f1x) & (f <= min(40 * f1x, f[-1]))
        rulman_bant = float(np.sqrt(np.sum(genlik[mb] ** 2))) if mb.any() else 0.0
    else:
        rulman_bant = 0.0

    return {
        "rms":          rms,
        "hiz_rms":      hiz_rms,
        "a1x":          a1,
        "a1x_rms":      a1 / (rms + EPS),
        "a2x_a1x":      a2 / (a1 + EPS),
        "a3x_a1x":      a3 / (a1 + EPS),
        "altharmonik":  (a05 + a15) / (a1 + EPS),
        "thd":          math.sqrt(harm) / (a1 + EPS),
        "kurtosis":     kurtosis,
        "crest":        crest,
        "rulman_bant":  rulman_bant,
    }


OZNITELIK_ADLARI = ["rms", "hiz_rms", "a1x", "a1x_rms", "a2x_a1x", "a3x_a1x",
                    "altharmonik", "thd", "kurtosis", "crest", "rulman_bant"]


# ----------------------------------------------------------------------
# 6. BLOKLAMA VE OZNITELIK CIKARIMI
# ----------------------------------------------------------------------
def kayit_isle(yol, etiket, kaynak_devir=None):
    x, rpm = mat_yukle(yol)
    if kaynak_devir:
        rpm = kaynak_devir
    fs, _ = ornekleme_hizi_belirle(x, rpm)
    satirlar = []
    n_blok = len(x) // BLOK_N
    for b in range(n_blok):
        blok = x[b * BLOK_N:(b + 1) * BLOK_N]
        f, g = spektrum(blok, fs)
        f1x, guven = devir_tahmin(f, g)
        oz = oznitelikler(blok, fs, f, g, f1x)
        oz.update({
            "dosya": os.path.basename(yol),
            "etiket": etiket,
            "gercek_rpm": rpm,
            "fs": fs,
            "tahmin_hz": f1x,
            "guven": guven,
            "blok": b,
        })
        satirlar.append(oz)
    return satirlar


# ----------------------------------------------------------------------
# 7. KARAR MOTORU — iki yontem
# ----------------------------------------------------------------------
def kutu_indeksi(tahmin_hz, kutu_genisligi_hz):
    if tahmin_hz is None:
        return None
    return int(round(tahmin_hz / kutu_genisligi_hz))


class KararMotoru:
    """Rejim-kosullu (rejim=True) veya klasik tek referansli (rejim=False)."""

    def __init__(self, rejim=True, kutu_genisligi=0.5, min_ogrenme=MIN_OGRENME):
        self.rejim = rejim
        self.kutu_genisligi = kutu_genisligi
        self.min_ogrenme = min_ogrenme
        self.referans = {}      # (kutu, oznitelik) -> Welford
        self.gecmis = []        # son M kararin z asimi
        self.alarm = False

    def _kutu(self, satir):
        if not self.rejim:
            return 0
        k = kutu_indeksi(satir["tahmin_hz"], self.kutu_genisligi)
        return k if k is not None else -999

    def ogret(self, satir):
        k = self._kutu(satir)
        for oz in OZNITELIK_ADLARI:
            w = self.referans.setdefault((k, oz), Welford())
            w.guncelle(math.log(max(satir[oz], EPS)))

    def degerlendir(self, satir):
        """Dondurur: 'ogreniyor' | 'normal' | 'alarm'"""
        k = self._kutu(satir)
        ws = [self.referans.get((k, oz)) for oz in OZNITELIK_ADLARI]
        if any(w is None or not w.ogrenildi_mi(self.min_ogrenme) for w in ws):
            return "ogreniyor"

        zler = []
        for oz, w in zip(OZNITELIK_ADLARI, ws):
            sd = max(w.sd, SD_TABAN_ORAN * abs(w.ortalama), EPS)
            z = abs(math.log(max(satir[oz], EPS)) - w.ortalama) / sd
            zler.append(z)
        zmax = max(zler)

        esik = Z_DUSUR if self.alarm else Z_KUR
        self.gecmis.append(1 if zmax > esik else 0)
        if len(self.gecmis) > OY_M:
            self.gecmis.pop(0)

        if len(self.gecmis) == OY_M:
            if sum(self.gecmis) >= OY_K:
                self.alarm = True
            elif sum(self.gecmis) <= OY_M - OY_K:
                self.alarm = False
        return "alarm" if self.alarm else "normal"
