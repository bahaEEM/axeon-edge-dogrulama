"""MAFAULDA veri kumesinden hedefli ornekleme ile indirme.

Kaynak: Machinery Fault Database, UFRJ SMT
        https://www02.smt.ufrj.br/~offshore/mfs/page_01.html

Tam arsiv 5.8 GB. Olculen baglanti hizinda (yaklasik 168 kB/s) bu 10 saatten
uzun surer. Bunun yerine hedefli ornekleme yapilir:

  saglam       normal.tgz icindeki 49 kaydin tamami (325 MB, tek istek)
  dengesizlik  7 kutle kademesi x 4 devir noktasi
  kaciklik     yatay ve dikey kademelerin tamami x 2 devir noktasi

Dosya adlari mil devrini (Hz) verir. Dengesizlik sorusu sabit devirde
sorulur, dolayisiyla kutle kademeleri arasinda eslesmis devir sarttir;
tam kapsam degil.

Sunucu ardisik isteklerde 403 dondurebilir. Betik indirilmis dosyalari
atlar, bu yuzden kesintiye ugrarsa tekrar calistirmak yeterlidir.

Kullanim:
    python scripts/indir_mafaulda.py                 hepsi
    python scripts/indir_mafaulda.py saglam          yalnizca saglam
    python scripts/indir_mafaulda.py dengesizlik kaciklik
"""
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

TABAN = "https://www02.smt.ufrj.br/~offshore/mfs/database/mafaulda"
HEDEF = Path(__file__).resolve().parents[1] / "veri" / "mafaulda"

KUTLELER = ["6g", "10g", "15g", "20g", "25g", "30g", "35g"]
DENGESIZLIK_DEVIRLERI = [20.0, 30.0, 40.0, 50.0]
KACIKLIK_DEVIRLERI = [30.0, 50.0]

BASLIK = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
BEKLE = 3.0
DENEME = 5


def _ac(url, zaman_asimi):
    son_hata = None
    for i in range(DENEME):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=BASLIK), timeout=zaman_asimi)
        except urllib.error.HTTPError as e:
            son_hata = e
            if e.code not in (403, 429, 500, 502, 503):
                raise
        except Exception as e:
            son_hata = e
        time.sleep(BEKLE * (i + 1))
    raise RuntimeError("{} -> {}".format(url, son_hata))


def listele(url):
    with _ac(url, 60) as c:
        return c.read().decode("utf8", "ignore")


def csv_adlari(url):
    return sorted(set(re.findall(r'href="([0-9.]+\.csv)"', listele(url))))


def mm_dizinleri(url):
    return sorted(set(re.findall(r'href="([0-9.]+mm/)"', listele(url))))


def hz(ad):
    return float(ad[:-4])


def en_yakin(adlar, hedef):
    return min(adlar, key=lambda a: abs(hz(a) - hedef))


def indir(url, yol, zaman_asimi=900):
    if yol.exists() and yol.stat().st_size > 1_000_000:
        return "atlandi", yol.stat().st_size
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".gecici")
    with _ac(url, zaman_asimi) as c, open(gecici, "wb") as f:
        while True:
            parca = c.read(1 << 16)
            if not parca:
                break
            f.write(parca)
    gecici.replace(yol)
    time.sleep(BEKLE)
    return "indi", yol.stat().st_size


def saglam_indir():
    print("--- saglam (normal.tgz, 49 kayit) ---")
    arsiv = HEDEF / "normal.tgz"
    durum, boyut = indir(TABAN + "/normal.tgz", arsiv, zaman_asimi=7200)
    print("normal.tgz  {}  {} bayt".format(durum, boyut))
    hedef = HEDEF / "normal_full"
    if not (hedef / "normal").exists():
        hedef.mkdir(parents=True, exist_ok=True)
        with tarfile.open(arsiv) as t:
            t.extractall(hedef)
    n = len(list((hedef / "normal").glob("*.csv")))
    print("cikarilan kayit: {}".format(n))
    return n


def dengesizlik_indir():
    print("--- dengesizlik (7 kutle x 4 devir) ---")
    n = 0
    for k in KUTLELER:
        adlar = csv_adlari("{}/imbalance/{}/".format(TABAN, k))
        for h in DENGESIZLIK_DEVIRLERI:
            ad = en_yakin(adlar, h)
            durum, _ = indir("{}/imbalance/{}/{}".format(TABAN, k, ad),
                             HEDEF / "imbalance_csv" / k / ad)
            print("{:<8}{:<14}{:>8.1f} Hz  {}".format(k, ad, hz(ad), durum), flush=True)
            n += 1
    return n


def kaciklik_indir():
    print("--- eksen kacikligi (yatay + dikey) ---")
    n = 0
    for kume in ["horizontal-misalignment", "vertical-misalignment"]:
        for kad in mm_dizinleri("{}/{}/".format(TABAN, kume)):
            adlar = csv_adlari("{}/{}/{}".format(TABAN, kume, kad))
            if not adlar:
                continue
            for h in KACIKLIK_DEVIRLERI:
                ad = en_yakin(adlar, h)
                durum, _ = indir("{}/{}/{}{}".format(TABAN, kume, kad, ad),
                                 HEDEF / "misalignment_csv" / kume / kad.rstrip("/") / ad)
                print("{:<26}{:<8}{:<14}{}".format(kume, kad.rstrip("/"), ad, durum), flush=True)
                n += 1
    return n


def main():
    istenen = sys.argv[1:] or ["saglam", "dengesizlik", "kaciklik"]
    HEDEF.mkdir(parents=True, exist_ok=True)
    isler = {"saglam": saglam_indir, "dengesizlik": dengesizlik_indir,
             "kaciklik": kaciklik_indir}
    for ad in istenen:
        if ad not in isler:
            print("bilinmeyen kume: {}".format(ad))
            return 2
        try:
            isler[ad]()
        except Exception as e:
            print("{} kumesi tamamlanamadi: {}".format(ad, e))
            print("sunucu kisitlamis olabilir; betigi tekrar calistirin, "
                  "inmis dosyalar atlanir.")
            return 1
    toplam = sum(f.stat().st_size for f in HEDEF.rglob("*.csv"))
    print("\nveri/mafaulda toplam csv: {} dosya, {:.0f} MB".format(
        len(list(HEDEF.rglob("*.csv"))), toplam / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
