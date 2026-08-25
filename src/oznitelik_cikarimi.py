# -*- coding: utf-8 -*-
"""AXEON-Edge dogrulama deneyleri — CWRU 12k Drive End veri kumesi."""
import numpy as np, math, json, os
from scipy.io import loadmat
from scipy.signal import decimate, get_window
import axeon_dogrulama as A
from pathlib import Path

KOK   = Path(__file__).resolve().parents[1]
VERI  = KOK / "veri"
SONUC = KOK / "sonuc"


BLOK   = 4096          # oznitelik blogu (0,34 s @12 kHz)
DEVIR_PENCERE = 1<<17  # devir tahmini penceresi (10,9 s) — v2
FS     = 12000
F_SEBEKE = 60.0        # CWRU: ABD sebekesi

KAYITLAR = [
 # dosya      etiket        yuk  etiket_rpm  indirgeme
 ("97.mat",  "saglam",       0, 1796, 4),
 ("98.mat",  "saglam",       1, 1772, 4),
 ("99.mat",  "saglam",       2, 1750, 4),
 ("100.mat", "saglam",       3, 1725, 4),
 ("105.mat", "ic_bilezik",   0, 1797, 1),
 ("106.mat", "ic_bilezik",   1, 1772, 1),
 ("107.mat", "ic_bilezik",   2, 1750, 1),
 ("108.mat", "ic_bilezik",   3, 1730, 1),
 ("118.mat", "bilya",        0, 1797, 1),
 ("119.mat", "bilya",        1, 1772, 1),
 ("120.mat", "bilya",        2, 1750, 1),
 ("121.mat", "bilya",        3, 1730, 1),
 ("130.mat", "dis_bilezik",  0, 1797, 1),
 ("131.mat", "dis_bilezik",  1, 1772, 1),
 ("132.mat", "dis_bilezik",  2, 1750, 1),
 ("133.mat", "dis_bilezik",  3, 1730, 1),
]

def sinyal_yukle(dosya, dec):
    x,_ = A.mat_yukle(str(VERI / "cwru" / dosya))
    if dec > 1:
        x = decimate(x, dec, ftype="fir", zero_phase=True)   # 48 kHz -> 12 kHz
    return x

def spek(x, N):
    xs = x[:N] - x[:N].mean()
    g = np.abs(np.fft.rfft(xs*np.hanning(N)))*2/(N*0.5)
    f = np.fft.rfftfreq(N, 1/FS)
    return f, g

def devir_tahmin(f, g, arama=(27.5, 30.5), H=8, maskele=True, tol=1.5):
    """Harmonik CARPIM spektrumu (log toplami = geometrik ortalama).

    v1'de harmoniklerin genlikleri TOPLANIYORDU. Bu, tek bir cok guclu cizginin
    (sebekenin iki kati) butun aileyi tasimasina izin verir ve tahminci
    sebeke/2'ye kilitlenir. Carpim kullanildiginda eksik bir harmonik skoru
    cokertir; yanlis aile hicbir zaman kazanamaz.

    Ikinci degisiklik: pencere 2,73 s'den 10,9 s'ye cikarildi. Kayma bandini
    (1,18 Hz) bolumlemek icin gereken cozunurluk bunu zorunlu kiliyor.
    """
    df = f[1] - f[0]
    ad = np.arange(max(int(arama[0]/df), 1), int(arama[1]/df))
    if len(ad) < 3:
        return None, 0.0
    sk = np.zeros(len(ad))
    for j, i in enumerate(ad):
        fa = f[i]; lp = 0.0; c = 0
        for h in range(1, H+1):
            fh = h*fa
            if maskele and min(abs(fh - k*F_SEBEKE) for k in range(1, 8)) < tol:
                continue                      # sebeke harmonigi: sayma
            idx = int(round(fh/df))
            if idx >= len(g)-1: break
            lp += np.log(g[idx-1:idx+2].max() + 1e-14); c += 1
        sk[j] = lp/c if c else -99.0
    j = int(np.argmax(sk))
    if 0 < j < len(sk)-1:
        y0, y1, y2 = sk[j-1], sk[j], sk[j+1]; p = (y0 - 2*y1 + y2)
        d = float(np.clip(0.5*(y0-y2)/p, -0.5, 0.5)) if abs(p) > 1e-12 else 0.0
    else:
        d = 0.0
    m = np.ones(len(sk), bool); m[np.abs(f[ad]-f[ad[j]]) < 0.03*f[ad[j]]] = False
    guven = float(sk[j] - np.max(sk[m])) if m.any() else 9.0
    return float(f[ad[j]] + d*df), guven

def kayit_isle(dosya, etiket, yuk, rpm, dec):
    x = sinyal_yukle(dosya, dec)
    n_blok = len(x)//BLOK
    satirlar=[]
    for b in range(n_blok):
        blok = x[b*BLOK:(b+1)*BLOK]
        f,g = spek(blok, BLOK)
        # devir tahmini: blogu ortalayan uzun pencereden.
        # Pencere kayittan uzun olamaz; mevcut uzunlukla sinirlanir (5-11 s).
        pen_n = min(DEVIR_PENCERE, len(x))
        p0 = min(max(0, (b*BLOK) - pen_n//2), max(0, len(x) - pen_n))
        pen = x[p0:p0+pen_n]
        if len(pen) >= (1 << 15):          # en az 2,7 s olmadan tahmin yapma
            fp, gp = spek(pen, len(pen))
            t, gv = devir_tahmin(fp, gp)
        else:
            t, gv = None, 0.0
        oz = A.oznitelikler(blok, FS, f, g, t)
        oz.update(dosya=dosya, etiket=etiket, yuk=yuk, gercek_hz=rpm/60.0,
                  tahmin_hz=t, guven=gv, blok=b)
        satirlar.append(oz)
    return satirlar

if __name__ == "__main__":
    tum=[]
    for dosya,etiket,yuk,rpm,dec in KAYITLAR:
        s = kayit_isle(dosya,etiket,yuk,rpm,dec)
        tum += s
        print(f"  {dosya:>8}  {etiket:<12} yuk{yuk}  {len(s):>3} blok")
    import pandas as pd
    df = pd.DataFrame(tum)
    SONUC.mkdir(exist_ok=True)
    df.to_csv(SONUC / "oznitelikler.csv", index=False)
    print(f"\nToplam {len(df)} blok, {df.etiket.nunique()} sinif -> sonuc/oznitelikler.csv")
