# -*- coding: utf-8 -*-
"""MAFAULDA - siniflandirici ve etki buyuklugu dogrulamasi.

Iki soru:
  A. Cohen d degerleri KAYIT duzeyinde bootstrap'lendiginde ayakta kaliyor mu?
     (Blok duzeyi etki buyuklugu yaniltir; ayni kayittan gelen bloklar
      birbirinin ayni degil ama bagimsiz da degil.)
  B. Derinligi 2-3 karar agaci saglam/dengesiz ayrimini yapabiliyor mu?
     Capraz dogrulama KAYIT duzeyinde: ayni kaydin bloklari hem egitimde
     hem testte bulunamaz. Ayrica GORULMEMIS DEVIR testi: uc devirde egit,
     dorduncude test et. Urunun asil iddiasi bu.

Sinif dagilimi: 32 saglam kayit, 28 dengesiz kayit. Dogruluk (accuracy)
yaniltici olur; tespit orani ve yanlis pozitif orani AYRI raporlanir.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

import axeon_dogrulama as A

SONUC = Path(__file__).resolve().parents[1] / "sonuc"
TOHUM = 20260824
BOOTSTRAP_TUR = 2000


def cohen_d(a, b):
    sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 +
                  (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
    return (b.mean() - a.mean()) / (sp + 1e-12)


def kayit_bootstrap_d(df, oz, tur=BOOTSTRAP_TUR, tohum=TOHUM):
    """Kayit duzeyinde yeniden ornekleme ile Cohen d guven araligi."""
    saglam = {k: g[oz].values for k, g in df[df.etiket == "saglam"].groupby("kayit_id")}
    dengesiz = {k: g[oz].values for k, g in df[df.etiket == "dengesiz"].groupby("kayit_id")}
    sk, dk = list(saglam), list(dengesiz)
    if len(sk) < 2 or len(dk) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(tohum)
    dler = []
    for _ in range(tur):
        a = np.concatenate([saglam[sk[i]] for i in rng.integers(0, len(sk), len(sk))])
        b = np.concatenate([dengesiz[dk[i]] for i in rng.integers(0, len(dk), len(dk))])
        if a.std(ddof=1) == 0 and b.std(ddof=1) == 0:
            continue
        dler.append(cohen_d(a, b))
    if not dler:
        return (float("nan"), float("nan"))
    return (float(np.percentile(dler, 2.5)), float(np.percentile(dler, 97.5)))


def olcum(y_gercek, y_tahmin):
    """Tespit orani = dengesiz bloklarda alarm; yanlis pozitif = saglamda alarm."""
    d = y_gercek == 1
    s = y_gercek == 0
    return {
        "tespit": float(y_tahmin[d].mean()) if d.any() else float("nan"),
        "yanlis_pozitif": float(y_tahmin[s].mean()) if s.any() else float("nan"),
        "n_dengesiz": int(d.sum()),
        "n_saglam": int(s.sum()),
    }


def main():
    df = pd.read_csv(SONUC / "mafaulda_oznitelikler.csv")
    rapor = {"tohum": TOHUM, "bootstrap_tur": BOOTSTRAP_TUR}

    for kanal in ["underhang_radyal", "overhang_radyal"]:
        alt = df[df.kanal == kanal].copy()
        alt["y"] = (alt.etiket == "dengesiz").astype(int)
        kanal_rapor = {}

        print("\n" + "=" * 96)
        print("KANAL: {}".format(kanal))
        print("=" * 96)
        print("kayit sayisi: saglam {}, dengesiz {} | blok: saglam {}, dengesiz {}".format(
            alt[alt.y == 0].kayit_id.nunique(), alt[alt.y == 1].kayit_id.nunique(),
            (alt.y == 0).sum(), (alt.y == 1).sum()))

        # ---------- A. Etki buyuklugu, kayit duzeyinde ----------
        print("\n--- A. Cohen d: blok duzeyi vs KAYIT duzeyi %95 bootstrap ---")
        print("{:<14}{:>10}{:>26}{:>16}".format("oznitelik", "d (blok)", "kayit %95", "sifir disinda"))
        d_rapor = {}
        for oz in A.OZNITELIK_ADLARI:
            a = alt[alt.y == 0][oz].values
            b = alt[alt.y == 1][oz].values
            d = cohen_d(a, b)
            lo, hi = kayit_bootstrap_d(alt, oz)
            disinda = not (lo <= 0 <= hi) if not np.isnan(lo) else False
            print("{:<14}{:>10.2f}{:>26}{:>16}".format(
                oz, d, "[{:+.2f}, {:+.2f}]".format(lo, hi), "EVET" if disinda else "hayir"))
            d_rapor[oz] = {"d_blok": float(d), "kayit_bootstrap95": [lo, hi],
                           "sifir_disinda": bool(disinda)}
        kanal_rapor["etki_buyuklugu"] = d_rapor

        # ---------- B1. Kayit duzeyinde capraz dogrulama ----------
        print("\n--- B1. Karar agaci, KAYIT duzeyinde capraz dogrulama ---")
        print("(her turda bir saglam + bir grup dengesiz kayit disarida birakilir)")
        ozn = A.OZNITELIK_ADLARI
        cv_rapor = {}
        # StratifiedGroupKFold: ayni kaydin bloklari tek katmanda kalir
        # (grup = kayit_id) ve her katmanda iki sinif da bulunur.
        bolucu = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=TOHUM)
        katmanlar = list(bolucu.split(alt[ozn], alt.y, groups=alt.kayit_id))
        for derinlik in [2, 3]:
            tespitler, yanlislar, yapraklar = [], [], []
            for eg_idx, te_idx in katmanlar:
                egitim, test = alt.iloc[eg_idx], alt.iloc[te_idx]
                if egitim[egitim.y == 0].empty or test[test.y == 0].empty                         or test[test.y == 1].empty:
                    continue
                agac = DecisionTreeClassifier(max_depth=derinlik, min_samples_leaf=5,
                                              class_weight="balanced", random_state=TOHUM)
                agac.fit(egitim[ozn], egitim.y)
                m = olcum(test.y.values, agac.predict(test[ozn]))
                tespitler.append(m["tespit"])
                yanlislar.append(m["yanlis_pozitif"])
                yapraklar.append(int(agac.get_n_leaves()))
            print("derinlik {}: tespit {:.1%} (min {:.1%}), yanlis pozitif {:.1%} "
                  "(maks {:.1%}), yaprak {}".format(
                      derinlik, np.mean(tespitler), np.min(tespitler),
                      np.mean(yanlislar), np.max(yanlislar), yapraklar))
            cv_rapor["derinlik_{}".format(derinlik)] = {
                "tespit_ort": float(np.mean(tespitler)), "tespit_min": float(np.min(tespitler)),
                "yanlis_pozitif_ort": float(np.mean(yanlislar)),
                "yanlis_pozitif_maks": float(np.max(yanlislar)),
                "tur_sayisi": len(tespitler), "yapraklar": yapraklar}
        kanal_rapor["kayit_cv"] = cv_rapor

        # ---------- B2. Gorulmemis devir testi ----------
        print("\n--- B2. GORULMEMIS DEVIR: uc devirde egit, dorduncude test et ---")
        print("(urunun asil iddiasi: egitimde gorulmemis calisma noktasinda calismak)")
        devir_rapor = {}
        for derinlik in [2, 3]:
            satir = []
            for nh in sorted(alt.nominal_hz.unique()):
                egitim = alt[alt.nominal_hz != nh]
                test = alt[alt.nominal_hz == nh]
                if test[test.y == 0].empty:
                    continue
                agac = DecisionTreeClassifier(max_depth=derinlik, min_samples_leaf=5,
                                              class_weight="balanced", random_state=TOHUM)
                agac.fit(egitim[ozn], egitim.y)
                m = olcum(test.y.values, agac.predict(test[ozn]))
                satir.append((nh, m["tespit"], m["yanlis_pozitif"]))
            print("derinlik {}:".format(derinlik))
            for nh, t, yp in satir:
                print("   {:>3} Hz disarida -> tespit {:>6.1%}   yanlis pozitif {:>6.1%}".format(
                    nh, t, yp))
            if satir:
                print("   ORTALAMA          tespit {:>6.1%}   yanlis pozitif {:>6.1%}".format(
                    np.mean([s[1] for s in satir]), np.mean([s[2] for s in satir])))
            devir_rapor["derinlik_{}".format(derinlik)] = [
                {"disarida_hz": int(nh), "tespit": float(t), "yanlis_pozitif": float(yp)}
                for nh, t, yp in satir]
        kanal_rapor["gorulmemis_devir"] = devir_rapor

        # ---------- Agacin kendisi ----------
        if kanal == "underhang_radyal":
            agac = DecisionTreeClassifier(max_depth=2, min_samples_leaf=5,
                                          class_weight="balanced", random_state=TOHUM)
            agac.fit(alt[ozn], alt.y)
            print("\n--- Tum veriyle egitilmis derinlik-2 agaci (MCU'da birkac if) ---")
            print(export_text(agac, feature_names=list(ozn)))
            kanal_rapor["agac_metni"] = export_text(agac, feature_names=list(ozn))

        rapor[kanal] = kanal_rapor

    with open(SONUC / "mafaulda_siniflandirici.json", "w", encoding="utf8") as f:
        json.dump(rapor, f, indent=2, ensure_ascii=False)
    print("\nsonuc/mafaulda_siniflandirici.json yazildi.")


if __name__ == "__main__":
    main()
