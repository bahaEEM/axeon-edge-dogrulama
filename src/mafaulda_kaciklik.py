# -*- coding: utf-8 -*-
"""MAFAULDA - dengesizlik ile eksen kacikligi ayrimi.

Soru: dengesizlik ile eksen kacikligi a2x/a1x oraniyla ayriliyor mu?
Klasik beklenti: kaciklikta 2x baskin, dengesizlikte 1x baskin.
Dogrulanirsa a2x_a1x bir AYIRICI oznitelik olur; dogrulanmazsa mimari
notundaki bu iddia duzeltilir.

Ayni oznitelik hatti, ayni desimasyon (50 kHz -> 6250 Hz), ayni blok (4096).
Karsilastirma yalnizca UC SINIFIN DA bulundugu devir bantlarinda yapilir;
aksi halde devir farki sinif farki gibi gorunur.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import axeon_dogrulama as A
from mafaulda_dengesizlik import KANALLAR, kayit_isle, devir_hz

KOK = Path(__file__).resolve().parents[1] / "veri" / "mafaulda"
SONUC = Path(__file__).resolve().parents[1] / "sonuc"
TOHUM = 20260824
BOOTSTRAP_TUR = 2000


def kaciklik_topla():
    satirlar = []
    kok = KOK / "misalignment_csv"
    if not kok.exists():
        return pd.DataFrame()
    for yon_dizin in sorted(kok.glob("*misalignment")):
        yon = "yatay" if yon_dizin.name.startswith("horizontal") else "dikey"
        for kad_dizin in sorted(yon_dizin.glob("*mm")):
            mm = float(re.sub(r"[^0-9.]", "", kad_dizin.name))
            for p in sorted(kad_dizin.glob("*.csv")):
                s = kayit_isle(p, "kaciklik", 0)
                for r in s:
                    r["kaciklik_mm"] = mm
                    r["kaciklik_yon"] = yon
                    r["kayit_id"] = "kaciklik_{}_{}mm_{}".format(yon, mm, p.stem)
                satirlar.extend(s)
                print("  {:<10}{:>6} mm  {:>7.2f} Hz  {} satir".format(
                    yon, mm, devir_hz(p), len(s)), flush=True)
    return pd.DataFrame(satirlar)


def cohen_d(a, b):
    sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 +
                  (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
    return (b.mean() - a.mean()) / (sp + 1e-12)


def kayit_bootstrap_d(df, oz, et_a, et_b, tur=BOOTSTRAP_TUR, tohum=TOHUM):
    ga = {k: g[oz].values for k, g in df[df.etiket == et_a].groupby("kayit_id")}
    gb = {k: g[oz].values for k, g in df[df.etiket == et_b].groupby("kayit_id")}
    ka, kb = list(ga), list(gb)
    if len(ka) < 2 or len(kb) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(tohum)
    out = []
    for _ in range(tur):
        a = np.concatenate([ga[ka[i]] for i in rng.integers(0, len(ka), len(ka))])
        b = np.concatenate([gb[kb[i]] for i in rng.integers(0, len(kb), len(kb))])
        out.append(cohen_d(a, b))
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)))


def main():
    print("Kaciklik kayitlari isleniyor...")
    kac = kaciklik_topla()
    if kac.empty:
        print("Kaciklik verisi yok.")
        return
    kac.to_csv(SONUC / "mafaulda_kaciklik_oznitelikler.csv", index=False)

    dig = pd.read_csv(SONUC / "mafaulda_oznitelikler.csv")
    for k in ["kaciklik_mm", "kaciklik_yon"]:
        if k not in dig.columns:
            dig[k] = np.nan
    df = pd.concat([dig, kac], ignore_index=True)

    # yalnizca uc sinifin da bulundugu devir bantlari
    bantlar = []
    for nh in sorted(df.nominal_hz.unique()):
        s = set(df[df.nominal_hz == nh].etiket.unique())
        if {"saglam", "dengesiz", "kaciklik"} <= s:
            bantlar.append(nh)
    print("\nUc sinifin da bulundugu devir bantlari: {}".format(bantlar))
    df = df[df.nominal_hz.isin(bantlar)]

    rapor = {"devir_bantlari": [int(b) for b in bantlar], "tohum": TOHUM}

    for kanal in KANALLAR:
        alt = df[df.kanal == kanal]
        print("\n" + "=" * 92)
        print("KANAL: {}".format(kanal))
        print("=" * 92)
        say = alt.groupby("etiket").kayit_id.nunique().to_dict()
        print("kayit sayisi: {}".format(say))

        print("\n--- Sinif ortalamalari (secilmis oznitelikler) ---")
        print("{:<12}{:>12}{:>12}{:>12}{:>12}{:>10}".format(
            "sinif", "a1x", "a2x_a1x", "a3x_a1x", "thd", "n blok"))
        ozet = {}
        for et in ["saglam", "dengesiz", "kaciklik"]:
            g = alt[alt.etiket == et]
            if g.empty:
                continue
            print("{:<12}{:>12.4f}{:>12.4f}{:>12.4f}{:>12.4f}{:>10}".format(
                et, g.a1x.mean(), g.a2x_a1x.mean(), g.a3x_a1x.mean(), g.thd.mean(), len(g)))
            ozet[et] = {o: float(g[o].mean()) for o in A.OZNITELIK_ADLARI}
            ozet[et]["n_blok"] = int(len(g))
            ozet[et]["n_kayit"] = int(g.kayit_id.nunique())

        print("\n--- DENGESIZ vs KACIKLIK ayrimi (Cohen d, kayit duzeyi %95) ---")
        print("{:<14}{:>12}{:>12}{:>10}{:>24}{:>14}".format(
            "oznitelik", "dengesiz", "kaciklik", "d", "kayit %95", "sifir disinda"))
        ayrim = {}
        for oz in A.OZNITELIK_ADLARI:
            a = alt[alt.etiket == "dengesiz"][oz].values
            b = alt[alt.etiket == "kaciklik"][oz].values
            if len(a) < 3 or len(b) < 3:
                continue
            d = cohen_d(a, b)
            lo, hi = kayit_bootstrap_d(alt, oz, "dengesiz", "kaciklik")
            disi = not (lo <= 0 <= hi) if not np.isnan(lo) else False
            print("{:<14}{:>12.4f}{:>12.4f}{:>10.2f}{:>24}{:>14}".format(
                oz, a.mean(), b.mean(), d,
                "[{:+.2f}, {:+.2f}]".format(lo, hi), "EVET" if disi else "hayir"))
            ayrim[oz] = {"dengesiz_ort": float(a.mean()), "kaciklik_ort": float(b.mean()),
                         "cohen_d": float(d), "kayit_bootstrap95": [lo, hi],
                         "sifir_disinda": bool(disi)}

        print("\n--- Kaciklik siddeti ile a2x_a1x ---")
        for mm in sorted(alt[alt.etiket == "kaciklik"].kaciklik_mm.dropna().unique()):
            g = alt[(alt.etiket == "kaciklik") & (alt.kaciklik_mm == mm)]
            print("  {:>4} mm : a1x {:.4f}  a2x_a1x {:.4f}  n={}".format(
                mm, g.a1x.mean(), g.a2x_a1x.mean(), len(g)))

        rapor[kanal] = {"ozet": ozet, "dengesiz_vs_kaciklik": ayrim}

    with open(SONUC / "mafaulda_kaciklik_rapor.json", "w", encoding="utf8") as f:
        json.dump(rapor, f, indent=2, ensure_ascii=False)
    print("\nsonuc/mafaulda_kaciklik_rapor.json yazildi.")


if __name__ == "__main__":
    main()
