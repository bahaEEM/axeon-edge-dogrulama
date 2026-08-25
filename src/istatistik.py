# -*- coding: utf-8 -*-
"""AXEON-Edge - istatistiksel saglamlastirma katmani.

Amac: karsilastirma tablosundaki oranlara guven araligi eklemek.
Bu modul sunu ekler:
  * Wilson skor guven araligi (blok duzeyi)
  * Kayit duzeyinde bootstrap (bloklar bagimsiz DEGIL)
  * ROC / tespit-yanlis alarm egrisi (Z esigi taramasi)
  * Ablasyon tablosu

Kural: uretilen her sayi bu betikten cikar, elle yazilmaz.
"""
import copy
import json
import math

import numpy as np
import pandas as pd

import axeon_dogrulama as A
from pathlib import Path

KOK   = Path(__file__).resolve().parents[1]
VERI  = KOK / "veri"
SONUC = KOK / "sonuc"


OZ = A.OZNITELIK_ADLARI
MIN_OGRENME = 10
Z_KUR, Z_DUSUR = 4.0, 2.5
OY_M, OY_K = 8, 5
SD_TABAN, EPS = 0.02, 1e-12
KUTU_HZ = 1.0
ARIZA_SINIFLARI = ["ic_bilezik", "bilya", "dis_bilezik"]

TOHUM = 20260824          # bootstrap tekrar uretilebilirligi icin sabit
BOOTSTRAP_TUR = 2000


class Cihaz:
    """Orijinal karsilastirma.py ile ayni davranis, ablasyon icin parametreli."""

    def __init__(self, kutu_fn, surekli_ogren=True, z_kur=Z_KUR, z_dusur=Z_DUSUR,
                 oy_m=OY_M, oy_k=OY_K, log_domeni=True, histerezis=True, oylama=True):
        self.kutu_fn = kutu_fn
        self.surekli = surekli_ogren
        self.z_kur, self.z_dusur = z_kur, z_dusur
        self.oy_m, self.oy_k = oy_m, oy_k
        self.log_domeni = log_domeni
        self.histerezis = histerezis
        self.oylama = oylama
        self.ref, self.gecmis, self.alarm = {}, [], False

    def _don(self, v):
        return math.log(max(v, EPS)) if self.log_domeni else float(v)

    def ogret(self, s):
        k = self.kutu_fn(s)
        for oz in OZ:
            self.ref.setdefault((k, oz), A.Welford()).guncelle(self._don(s[oz]))

    def isle(self, s, ogrenmeye_izin=True):
        k = self.kutu_fn(s)
        ws = [self.ref.get((k, oz)) for oz in OZ]
        ogrenilmis = all(w is not None and w.n >= MIN_OGRENME for w in ws)

        if ogrenilmis:
            zmax = 0.0
            for oz, w in zip(OZ, ws):
                sd = max(w.sd, SD_TABAN * abs(w.ortalama), EPS)
                zmax = max(zmax, abs(self._don(s[oz]) - w.ortalama) / sd)
            esik = (self.z_dusur if self.alarm else self.z_kur) if self.histerezis else self.z_kur
            ham = 1 if zmax > esik else 0

            if self.oylama:
                self.gecmis.append(ham)
                if len(self.gecmis) > self.oy_m:
                    self.gecmis.pop(0)
                if len(self.gecmis) == self.oy_m:
                    if sum(self.gecmis) >= self.oy_k:
                        self.alarm = True
                    elif sum(self.gecmis) <= self.oy_m - self.oy_k:
                        self.alarm = False
            else:
                self.alarm = bool(ham)
            cikti = "alarm" if self.alarm else "normal"
        else:
            cikti = "ogreniyor"

        if ogrenmeye_izin and self.surekli and cikti != "alarm":
            self.ogret(s)
        return cikti


def senaryo_detay(df, kutu_fn, surekli, **kw):
    """Uc fazli senaryo. Blok blok cikti dondurur, her blok kayit kimligiyle."""
    c = Cihaz(kutu_fn, surekli, **kw)

    faz1 = df[(df.etiket == "saglam") & (df.yuk == 0)]
    for _, s in faz1.iterrows():
        c.ogret(s)

    faz2 = df[(df.etiket == "saglam") & (df.yuk.isin([1, 2, 3]))].sort_values(["yuk", "blok"])
    faz2_kayitlari = [("saglam_yuk{}".format(s["yuk"]), c.isle(s)) for _, s in faz2.iterrows()]

    faz3 = {}
    for sinif in ARIZA_SINIFLARI:
        c3 = copy.deepcopy(c)
        c3.gecmis, c3.alarm = [], False
        alt = df[(df.etiket == sinif) & (df.yuk.isin([1, 2, 3]))].sort_values(["yuk", "blok"])
        faz3[sinif] = [("{}_yuk{}".format(sinif, s["yuk"]), c3.isle(s, ogrenmeye_izin=False))
                       for _, s in alt.iterrows()]

    return {
        "n_faz1": len(faz1),
        "faz2": faz2_kayitlari,
        "faz3": faz3,
        "kutu_sayisi": len({k for k, _ in c.ref}),
    }


def oran(kayitlar, hedef):
    if not kayitlar:
        return 0.0
    return sum(1 for _, c in kayitlar if c == hedef) / len(kayitlar)


def wilson(basari, n, z=1.959963985):
    """%95 Wilson skor araligi. n kucukken normal yaklasim kullanilmaz."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = basari / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / payda
    return (max(0.0, merkez - yari), min(1.0, merkez + yari))


def kayit_bootstrap(kayitlar, hedef, tur=BOOTSTRAP_TUR, tohum=TOHUM):
    """Bloklar bagimsiz degil (ayni kayittan ardisik pencereler).
    Bu yuzden yeniden ornekleme KAYIT duzeyinde yapilir."""
    gruplar = {}
    for kid, c in kayitlar:
        gruplar.setdefault(kid, []).append(1 if c == hedef else 0)
    anahtarlar = list(gruplar)
    if not anahtarlar:
        return (float("nan"), float("nan"), 0)
    rng = np.random.default_rng(tohum)
    n_kayit = len(anahtarlar)
    oranlar = []
    for _ in range(tur):
        sec = rng.integers(0, n_kayit, n_kayit)
        havuz = []
        for i in sec:
            havuz.extend(gruplar[anahtarlar[i]])
        oranlar.append(sum(havuz) / len(havuz))
    return (float(np.percentile(oranlar, 2.5)),
            float(np.percentile(oranlar, 97.5)),
            n_kayit)


def fark_bootstrap(kayit_a, kayit_b, hedef, tur=BOOTSTRAP_TUR, tohum=TOHUM):
    """Iki yontemin farki. Kayit duzeyinde eslesmis yeniden ornekleme."""
    ga, gb = {}, {}
    for kid, c in kayit_a:
        ga.setdefault(kid, []).append(1 if c == hedef else 0)
    for kid, c in kayit_b:
        gb.setdefault(kid, []).append(1 if c == hedef else 0)
    anahtarlar = [k for k in ga if k in gb]
    rng = np.random.default_rng(tohum)
    n = len(anahtarlar)
    farklar = []
    for _ in range(tur):
        sec = rng.integers(0, n, n)
        ha, hb = [], []
        for i in sec:
            ha.extend(ga[anahtarlar[i]])
            hb.extend(gb[anahtarlar[i]])
        farklar.append(sum(ha) / len(ha) - sum(hb) / len(hb))
    return (float(np.percentile(farklar, 2.5)),
            float(np.percentile(farklar, 97.5)),
            float(np.mean(farklar)))


YONTEMLER = {
    "A-donmus":  (lambda s: 0, False),
    "A-surekli": (lambda s: 0, True),
    "B1":        (lambda s: int(round((s["tahmin_hz"] or 0) / KUTU_HZ)), True),
    "B2":        (lambda s: int(s["yuk"]), True),
}


def main():
    df = pd.read_csv(SONUC / "oznitelikler.csv")
    cikti = {"tohum": TOHUM, "bootstrap_tur": BOOTSTRAP_TUR}

    detaylar, tablo = {}, {}
    for ad, (fn, sur) in YONTEMLER.items():
        d = senaryo_detay(df, fn, sur)
        detaylar[ad] = d

        n2 = len(d["faz2"])
        ya = sum(1 for _, c in d["faz2"] if c == "alarm")
        w_alt, w_ust = wilson(ya, n2)
        b_alt, b_ust, n_kayit = kayit_bootstrap(d["faz2"], "alarm")

        tespitler = [oran(d["faz3"][s], "alarm") for s in ARIZA_SINIFLARI]
        tum_faz3 = [x for s in ARIZA_SINIFLARI for x in d["faz3"][s]]
        n3 = len(tum_faz3)
        t3 = sum(1 for _, c in tum_faz3 if c == "alarm")
        tw_alt, tw_ust = wilson(t3, n3)
        tb_alt, tb_ust, n_kayit3 = kayit_bootstrap(tum_faz3, "alarm")

        tablo[ad] = {
            "yanlis_alarm": ya / n2,
            "yanlis_alarm_n": n2,
            "yanlis_alarm_kayit_sayisi": n_kayit,
            "yanlis_alarm_wilson95": [w_alt, w_ust],
            "yanlis_alarm_bootstrap95_kayit": [b_alt, b_ust],
            "ogreniyor_faz2": oran(d["faz2"], "ogreniyor"),
            "tespit_ortalama": float(np.mean(tespitler)),
            "tespit_havuz": t3 / n3,
            "tespit_n": n3,
            "tespit_kayit_sayisi": n_kayit3,
            "tespit_wilson95": [tw_alt, tw_ust],
            "tespit_bootstrap95_kayit": [tb_alt, tb_ust],
            "kutu_sayisi": d["kutu_sayisi"],
        }
    cikti["ana_tablo"] = tablo

    farklar = {}
    for a, b in [("A-donmus", "A-surekli"), ("A-donmus", "B1"),
                 ("B1", "A-surekli"), ("B1", "B2")]:
        alt, ust, ort = fark_bootstrap(detaylar[a]["faz2"], detaylar[b]["faz2"], "alarm")
        farklar["{} - {} (yanlis alarm)".format(a, b)] = {
            "ortalama_fark": ort,
            "bootstrap95": [alt, ust],
            "sifir_disinda": not (alt <= 0 <= ust),
        }
    cikti["farklar"] = farklar

    roc = {}
    for ad in ["A-donmus", "B1"]:
        fn, sur = YONTEMLER[ad]
        egri = []
        for z in [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]:
            d = senaryo_detay(df, fn, sur, z_kur=z, z_dusur=max(z - 1.5, 0.5))
            tum3 = [x for s in ARIZA_SINIFLARI for x in d["faz3"][s]]
            egri.append({"z": z,
                         "yanlis_alarm": oran(d["faz2"], "alarm"),
                         "tespit": oran(tum3, "alarm")})
        roc[ad] = egri
    cikti["roc"] = roc

    ablasyon = {}
    for etiket, kw in [("tam (referans)", {}),
                       ("log domeni KAPALI", {"log_domeni": False}),
                       ("histerezis KAPALI", {"histerezis": False}),
                       ("N-of-M oylama KAPALI", {"oylama": False})]:
        d = senaryo_detay(df, YONTEMLER["B1"][0], YONTEMLER["B1"][1], **kw)
        tum3 = [x for s in ARIZA_SINIFLARI for x in d["faz3"][s]]
        ablasyon[etiket] = {"yanlis_alarm": oran(d["faz2"], "alarm"),
                            "tespit": oran(tum3, "alarm"),
                            "ogreniyor": oran(d["faz2"], "ogreniyor")}
    d = senaryo_detay(df, YONTEMLER["A-surekli"][0], YONTEMLER["A-surekli"][1])
    tum3 = [x for s in ARIZA_SINIFLARI for x in d["faz3"][s]]
    ablasyon["rejim katmani KAPALI"] = {"yanlis_alarm": oran(d["faz2"], "alarm"),
                                        "tespit": oran(tum3, "alarm"),
                                        "ogreniyor": oran(d["faz2"], "ogreniyor")}
    cikti["ablasyon"] = ablasyon

    with open(SONUC / "istatistik.json", "w", encoding="utf8") as f:
        json.dump(cikti, f, indent=2, ensure_ascii=False)

    print("=" * 104)
    print("ANA TABLO - %95 guven araliklariyle")
    print("=" * 104)
    print("{:<12}{:>14}{:>24}{:>26}{:>8}".format(
        "YONTEM", "YANLIS ALARM", "Wilson %95 (blok)", "Bootstrap %95 (kayit)", "kayit"))
    for ad, r in tablo.items():
        w = r["yanlis_alarm_wilson95"]
        b = r["yanlis_alarm_bootstrap95_kayit"]
        print("{:<12}{:>13.1f}%{:>24}{:>26}{:>8}".format(
            ad, r["yanlis_alarm"] * 100,
            "[{:5.1f}, {:5.1f}]".format(w[0] * 100, w[1] * 100),
            "[{:5.1f}, {:5.1f}]".format(b[0] * 100, b[1] * 100),
            r["yanlis_alarm_kayit_sayisi"]))
    print("\nFaz 2 blok sayisi: {}, bagimsiz KAYIT sayisi: {}".format(
        tablo["A-donmus"]["yanlis_alarm_n"], tablo["A-donmus"]["yanlis_alarm_kayit_sayisi"]))

    print("\n" + "=" * 104)
    print("YONTEMLER ARASI FARK - kayit duzeyinde bootstrap")
    print("=" * 104)
    for k, v in farklar.items():
        a, u = v["bootstrap95"]
        print("{:<42}{:>8.1f}%  [{:>6.1f}, {:>6.1f}]  {}".format(
            k, v["ortalama_fark"] * 100, a * 100, u * 100,
            "SIFIR DISINDA" if v["sifir_disinda"] else "sifiri iceriyor"))

    print("\n" + "=" * 104)
    print("ABLASYON (B1 uzerinde)")
    print("=" * 104)
    print("{:<26}{:>14}{:>10}{:>12}".format("kurulum", "yanlis alarm", "tespit", "ogreniyor"))
    for k, v in ablasyon.items():
        print("{:<26}{:>13.1f}%{:>9.1f}%{:>11.1f}%".format(
            k, v["yanlis_alarm"] * 100, v["tespit"] * 100, v["ogreniyor"] * 100))

    print("\n" + "=" * 104)
    print("ROC - Z esigi taramasi (yanlis alarm / tespit)")
    print("=" * 104)
    print("{:<6}{:>26}{:>26}".format("z", "A-donmus", "B1"))
    for i, e in enumerate(roc["A-donmus"]):
        z = e["z"]
        b = roc["B1"][i]
        isaret = "  <-- mevcut karar" if z == 4.0 else ""
        print("{:<6}{:>26}{:>26}{}".format(
            z,
            "{:5.1f}% / {:5.1f}%".format(e["yanlis_alarm"] * 100, e["tespit"] * 100),
            "{:5.1f}% / {:5.1f}%".format(b["yanlis_alarm"] * 100, b["tespit"] * 100),
            isaret))

    print("\nsonuc/istatistik.json yazildi.")


if __name__ == "__main__":
    main()
