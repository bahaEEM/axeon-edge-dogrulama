# -*- coding: utf-8 -*-
"""
ANA DENEY — sahadaki dagitim senaryosunun birebir benzetimi.

Senaryo (uc faz, hepsi ayni cihaz omru icinde):
  FAZ 1  Devreye alma. Cihaz makineye takilir ve o andaki calisma noktasinda
         (yuk 0) referansini ogrenir.
  FAZ 2  Saglikli isletme. Makine yuk 1, 2 ve 3'e gecer. ARIZA YOKTUR.
         Bu fazda uretilen her alarm YANLIS ALARMDIR.
  FAZ 3  Ariza. Ayni yuk noktalarinda rulman kusuru olan kayitlar gelir.
         Bu fazda uretilmeyen her alarm KACIRILMIS ARIZADIR.

Karsilastirilan dort yontem:
  A-donmus    Devreye almada bir kez ogrenir, sonra referans dondurulur.
              Rakip urunlerin yaptigi budur (Siemens SM1281, Sick MPB10:
              kullanicinin tetikledigi tek seferlik ogretme adimi).
  A-surekli   Tek referans ama surekli ogrenir.
  B1          Rejim-kosullu, rejim TAHMIN EDILEN devirden. Bugun yapabildigimiz.
  B2          Rejim-kosullu, rejim GERCEK calisma noktasindan (oracle).
              Rejim mukemmel gozlenebilseydi ulasilacak ust sinir.

Ogrenme kurali (FAZ 2): alarm aktifken referans GUNCELLENMEZ. Aksi halde
yavas gelisen ariza referansa emilir ("kaynayan kurbaga" problemi).
"""
import pandas as pd, numpy as np, math, json
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


class Cihaz:
    def __init__(self, kutu_fn, surekli_ogren=True):
        self.kutu_fn = kutu_fn
        self.surekli = surekli_ogren
        self.ref, self.gecmis, self.alarm = {}, [], False

    def ogret(self, s):
        k = self.kutu_fn(s)
        for oz in OZ:
            self.ref.setdefault((k, oz), A.Welford()).guncelle(math.log(max(s[oz], EPS)))

    def isle(self, s, ogrenmeye_izin=True):
        k = self.kutu_fn(s)
        ws = [self.ref.get((k, oz)) for oz in OZ]
        ogrenilmis = all(w is not None and w.n >= MIN_OGRENME for w in ws)

        if ogrenilmis:
            zmax = 0.0
            for oz, w in zip(OZ, ws):
                sd = max(w.sd, SD_TABAN * abs(w.ortalama), EPS)
                zmax = max(zmax, abs(math.log(max(s[oz], EPS)) - w.ortalama) / sd)
            esik = Z_DUSUR if self.alarm else Z_KUR
            self.gecmis.append(1 if zmax > esik else 0)
            if len(self.gecmis) > OY_M:
                self.gecmis.pop(0)
            if len(self.gecmis) == OY_M:
                if sum(self.gecmis) >= OY_K:
                    self.alarm = True
                elif sum(self.gecmis) <= OY_M - OY_K:
                    self.alarm = False
            cikti = "alarm" if self.alarm else "normal"
        else:
            cikti = "ogreniyor"

        # alarm yokken ogren; alarm varken referansi dondur
        if ogrenmeye_izin and self.surekli and cikti != "alarm":
            self.ogret(s)
        return cikti


def senaryo(df, kutu_fn, surekli):
    c = Cihaz(kutu_fn, surekli)
    # FAZ 1 — devreye alma, yuk 0, saglam
    for _, s in df[(df.etiket == "saglam") & (df.yuk == 0)].iterrows():
        c.ogret(s)
    n_devreye = len(df[(df.etiket == "saglam") & (df.yuk == 0)])

    # FAZ 2 — saglikli isletme, yuk 1-2-3
    faz2 = df[(df.etiket == "saglam") & (df.yuk.isin([1, 2, 3]))].sort_values(["yuk", "blok"])
    k2 = [c.isle(s) for _, s in faz2.iterrows()]

    # FAZ 3 — ariza, ayni yuklerde. Her sinif icin cihaz FAZ 2 sonrasi durumdan devam eder.
    faz3 = {}
    import copy
    for sinif in ["ic_bilezik", "bilya", "dis_bilezik"]:
        c3 = copy.deepcopy(c)
        c3.gecmis, c3.alarm = [], False
        alt = df[(df.etiket == sinif) & (df.yuk.isin([1, 2, 3]))].sort_values(["yuk", "blok"])
        kk = [c3.isle(s, ogrenmeye_izin=False) for _, s in alt.iterrows()]
        faz3[sinif] = {
            "tespit": kk.count("alarm") / max(len(kk), 1),
            "ogreniyor": kk.count("ogreniyor") / max(len(kk), 1),
            "n": len(kk),
        }
    return {
        "n_devreye_alma_blok": n_devreye,
        "yanlis_alarm": k2.count("alarm") / max(len(k2), 1),
        "ogreniyor_faz2": k2.count("ogreniyor") / max(len(k2), 1),
        "n_faz2": len(k2),
        "kutu_sayisi": len({k for k, _ in c.ref}),
        **{f"tespit_{s}": v["tespit"] for s, v in faz3.items()},
        **{f"ogreniyor_{s}": v["ogreniyor"] for s, v in faz3.items()},
        "tespit_ortalama": float(np.mean([v["tespit"] for v in faz3.values()])),
    }


if __name__ == "__main__":
    df = pd.read_csv(SONUC / "oznitelikler.csv")
    yontemler = {
        "A-donmus  tek referans, devreye almada dondurulmus": (lambda s: 0, False),
        "A-surekli tek referans, surekli ogrenen":            (lambda s: 0, True),
        "B1  rejim-kosullu, TAHMIN EDILEN devirden":          (lambda s: int(round((s["tahmin_hz"] or 0)/KUTU_HZ)), True),
        "B2  rejim-kosullu, GERCEK calisma noktasi (oracle)": (lambda s: int(s["yuk"]), True),
    }
    print("="*112)
    print(f"{'YONTEM':<52}{'YANLIS':>9}{'ogreniyor':>11}{'TESPIT':>9}{'ic':>7}{'bilya':>7}{'dis':>7}{'kutu':>6}")
    print(f"{'':<52}{'ALARM':>9}{'(faz 2)':>11}{'ort.':>9}{'bilezik':>7}{'':>7}{'bilezik':>7}{'':>6}")
    print("-"*112)
    tablo = {}
    for ad, (fn, sur) in yontemler.items():
        r = senaryo(df, fn, sur); tablo[ad] = r
        print(f"{ad:<52}{r['yanlis_alarm']*100:>8.1f}%{r['ogreniyor_faz2']*100:>10.1f}%"
              f"{r['tespit_ortalama']*100:>8.1f}%{r['tespit_ic_bilezik']*100:>6.0f}%"
              f"{r['tespit_bilya']*100:>6.0f}%{r['tespit_dis_bilezik']*100:>6.0f}%{r['kutu_sayisi']:>6}")
    print("="*112)
    print(f"FAZ 1: {tablo[list(tablo)[0]]['n_devreye_alma_blok']} blok  |  "
          f"FAZ 2: {tablo[list(tablo)[0]]['n_faz2']} saglam blok  |  "
          f"FAZ 3: her sinif icin ~87 blok")
    json.dump(tablo, open(SONUC / "sonuclar.json", "w", encoding="utf8"), indent=2, ensure_ascii=False)
