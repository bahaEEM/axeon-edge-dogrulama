# -*- coding: utf-8 -*-
"""MAFAULDA dengesizlik analizi.

Cevaplanacak sorular:
  S1. Dengesizlik siddeti (kutle) artarken a1x ve a1x_rms monoton artiyor mu?
  S2. Kurtosis dengesizlikte dusuyor mu? (beklenti: saglam ~3.0, saf
      dengesizlik ->1.5). Dogrulanirsa kurtosis DISLAYICI olarak kullanilabilir.
  S3. Hangi oznitelik saglam/dengesiz ayrimini en iyi yapiyor?

Veri: MAFAULDA (UFRJ SMT), SpectraQuest MFS-ABVT duzenegi.
  8 sutun, 250000 ornek, 50 kHz, 5 s.
  sutun 0      : takometre
  sutun 1,2,3  : underhang ivmeolcer (eksenel, radyal, tegetsel)
  sutun 4,5,6  : overhang  ivmeolcer (eksenel, radyal, tegetsel)
  sutun 7      : mikrofon

Dosya adi = mil devri (Hz). Dengesizlik radyal yonde gorunur, bu yuzden
iki radyal kanal da hesaplanir ve ayri ayri raporlanir - kanal secimi
sonucu belirlemesin diye.

CWRU hattiyla tutarlilik icin ayni oznitelik fonksiyonu kullanilir.
50 kHz'de 4096'lik blok 12.2 Hz cozunurluk verir; bu 1x ile 2x'i ayirmaya
yetmez. Bu yuzden 8 kat desimasyon -> 6250 Hz, cozunurluk 1.53 Hz.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import decimate
from scipy.stats import spearmanr

import axeon_dogrulama as A

KOK = Path(__file__).resolve().parents[1] / "veri" / "mafaulda"
CIKTI = Path(__file__).resolve().parents[1] / "sonuc"

FS_HAM = 50000.0
DEC = 8
FS = FS_HAM / DEC          # 6250 Hz
BLOK = 4096                # 1.53 Hz cozunurluk
KANALLAR = {"underhang_radyal": 2, "overhang_radyal": 5}


def devir_hz(yol):
    return float(yol.stem)


def nominal(h):
    return int(round(h / 10.0) * 10)


def kayit_oku(yol):
    d = pd.read_csv(yol, header=None, dtype=np.float64).values
    if d.shape[1] != 8:
        raise ValueError("beklenmeyen sutun sayisi: {}".format(d.shape))
    return d


def bloklar(x):
    n = len(x) // BLOK
    return [x[i * BLOK:(i + 1) * BLOK] for i in range(n)]


def kayit_isle(yol, etiket, kutle_g):
    ham = kayit_oku(yol)
    f1x = devir_hz(yol)
    satirlar = []
    for kanal_ad, idx in KANALLAR.items():
        x = decimate(ham[:, idx], DEC, ftype="fir", zero_phase=True)
        for bi, b in enumerate(bloklar(x)):
            f, g = A.spektrum(b, FS)
            oz = A.oznitelikler(b, FS, f, g, f1x)
            oz.update(etiket=etiket, kutle_g=kutle_g, devir_hz=f1x,
                      nominal_hz=nominal(f1x), kanal=kanal_ad, blok=bi,
                      dosya=yol.name,
                      # kayit kimligi kutleyi de icermeli: ayni dosya adi
                      # (ornegin 49.9712.csv) birden fazla kutle klasorunde var
                      kayit_id="{}_{}g_{}".format(etiket, kutle_g, yol.stem))
            satirlar.append(oz)
    return satirlar


def topla():
    gorevler = []
    # normal.tgz'den cikan tam kume (49 kayit). Tek tek indirilen normal_csv
    # bunun alt kumesi oldugu icin kullanilmaz - ayni kayit iki kez girmesin.
    normal_kok = KOK / "normal_full" / "normal"
    if not normal_kok.exists():
        normal_kok = KOK / "normal_csv"
    for p in sorted(normal_kok.glob("*.csv")):
        if 19 <= devir_hz(p) <= 52:          # eslesen devir araligi
            gorevler.append((p, "saglam", 0))
    for d in sorted((KOK / "imbalance_csv").glob("*g")):
        kutle = int(re.sub(r"\D", "", d.name))
        for p in sorted(d.glob("*.csv")):
            gorevler.append((p, "dengesiz", kutle))

    print("{} kayit islenecek".format(len(gorevler)))
    hepsi = []
    for p, et, k in gorevler:
        try:
            s = kayit_isle(p, et, k)
            hepsi.extend(s)
            print("  {:<28}{:<10}{:>4}g  {:>6.2f} Hz  {} satir".format(
                p.name, et, k, devir_hz(p), len(s)), flush=True)
        except Exception as e:
            print("  HATA {}: {}".format(p.name, e), flush=True)
    return pd.DataFrame(hepsi)


def main():
    CIKTI.mkdir(exist_ok=True)
    df = topla()
    df.to_csv(CIKTI / "mafaulda_oznitelikler.csv", index=False)
    print("\n{} blok -> sonuc/mafaulda_oznitelikler.csv".format(len(df)))

    rapor = {"blok_sayisi": int(len(df)), "fs_hz": FS, "blok_n": BLOK,
             "cozunurluk_hz": FS / BLOK}

    # ---------------- S1: kutle-a1x monotonlugu ----------------
    print("\n" + "=" * 92)
    print("S1  DENGESIZLIK KUTLESI ARTARKEN 1x GENLIGI - devir noktasi basina")
    print("=" * 92)
    mono = {}
    for kanal in KANALLAR:
        print("\n--- kanal: {} ---".format(kanal))
        print("{:<10}{:>9}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}"
              .format("devir", "0g", "6g", "10g", "15g", "20g", "25g", "30g", "35g"))
        for nh in sorted(df.nominal_hz.unique()):
            alt = df[(df.kanal == kanal) & (df.nominal_hz == nh)]
            if alt.empty:
                continue
            satir, kutleler, ortalamalar = "{:<10}".format(str(nh) + " Hz"), [], []
            for k in [0, 6, 10, 15, 20, 25, 30, 35]:
                v = alt[alt.kutle_g == k]["a1x"]
                if len(v):
                    m = float(v.mean())
                    satir += "{:>10.4f}".format(m)
                    kutleler.append(k)
                    ortalamalar.append(m)
                else:
                    satir += "{:>10}".format("-")
            if len(kutleler) >= 4:
                rho, p = spearmanr(kutleler, ortalamalar)
                satir += "   rho={:+.2f} p={:.3f}".format(rho, p)
                mono["{}_{}Hz".format(kanal, nh)] = {
                    "spearman_rho": float(rho), "p": float(p),
                    "kutleler": kutleler, "a1x_ort": ortalamalar}
            print(satir)
    rapor["S1_monotonluk"] = mono

    # ---------------- S2: kurtosis ----------------
    print("\n" + "=" * 92)
    print("S2  KURTOSIS - saglam vs dengesiz (beklenti: saglam ~3.0, dengesizlik dusurur)")
    print("=" * 92)
    kurt = {}
    for kanal in KANALLAR:
        alt = df[df.kanal == kanal]
        s = alt[alt.etiket == "saglam"]["kurtosis"]
        print("\n--- kanal: {} ---".format(kanal))
        print("{:<12}{:>10}{:>10}{:>10}{:>8}".format("kume", "ortalama", "medyan", "std", "n"))
        print("{:<12}{:>10.3f}{:>10.3f}{:>10.3f}{:>8}".format(
            "saglam (0g)", s.mean(), s.median(), s.std(), len(s)))
        kurt[kanal] = {"saglam": {"ort": float(s.mean()), "medyan": float(s.median()),
                                  "std": float(s.std()), "n": int(len(s))}}
        for k in [6, 10, 15, 20, 25, 30, 35]:
            v = alt[alt.kutle_g == k]["kurtosis"]
            if len(v):
                print("{:<12}{:>10.3f}{:>10.3f}{:>10.3f}{:>8}".format(
                    "{}g".format(k), v.mean(), v.median(), v.std(), len(v)))
                kurt[kanal]["{}g".format(k)] = {
                    "ort": float(v.mean()), "medyan": float(v.median()),
                    "std": float(v.std()), "n": int(len(v))}
    rapor["S2_kurtosis"] = kurt

    # ---------------- S3: ayirt edicilik ----------------
    print("\n" + "=" * 92)
    print("S3  OZNITELIK AYIRT EDICILIGI - saglam vs dengesiz (ayni devir bandinda)")
    print("=" * 92)
    ayirt = {}
    for kanal in KANALLAR:
        print("\n--- kanal: {} ---".format(kanal))
        print("{:<14}{:>12}{:>12}{:>10}{:>26}".format(
            "oznitelik", "saglam ort", "dengesiz ort", "|d|", "yorum"))
        alt = df[df.kanal == kanal]
        for oz in A.OZNITELIK_ADLARI:
            a = alt[alt.etiket == "saglam"][oz].values
            b = alt[alt.etiket == "dengesiz"][oz].values
            if len(a) < 3 or len(b) < 3:
                continue
            # Cohen d (havuzlanmis std)
            sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 +
                          (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
            d = (b.mean() - a.mean()) / (sp + 1e-12)
            yorum = ("cok guclu" if abs(d) > 1.5 else
                     "guclu" if abs(d) > 0.8 else
                     "orta" if abs(d) > 0.5 else "zayif")
            print("{:<14}{:>12.4f}{:>12.4f}{:>10.2f}{:>26}".format(
                oz, a.mean(), b.mean(), abs(d), yorum))
            ayirt.setdefault(kanal, {})[oz] = {
                "saglam_ort": float(a.mean()), "dengesiz_ort": float(b.mean()),
                "cohen_d": float(d)}
    rapor["S3_ayirt_edicilik"] = ayirt

    with open(CIKTI / "mafaulda_rapor.json", "w", encoding="utf8") as f:
        json.dump(rapor, f, indent=2, ensure_ascii=False)
    print("\nsonuc/mafaulda_rapor.json yazildi.")


if __name__ == "__main__":
    main()
