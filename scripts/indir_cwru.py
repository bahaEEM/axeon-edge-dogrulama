"""CWRU Bearing Data Center - veri indirme ve kunye dogrulama.

Kural: hash dogrulanmadan devam edilmez.
Sadece standart kutuphane kullanir.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

TABAN = "https://engineering.case.edu/sites/default/files/{}.mat"
HEDEF = Path(__file__).resolve().parents[1] / "veri" / "cwru"

# beklenen kunye: dosya -> (sha256 ilk 16 hane, bayt)
KUNYE = {
    "97": ("16bf48babcf1c7ac", 3903344),
    "98": ("37e6612c05e65c41", 7742720),
    "99": ("4b97e6b5361f45ef", 15503928),
    "100": ("88a5990cb541320e", 7770624),
    "105": ("f80b0ea04fd06b37", 2910768),
    "106": ("e5cec7cdd138e6cd", 2928192),
    "107": ("111ba8996a115684", 2931672),
    "108": ("d415f0e65128bfa0", 2950416),
    "118": ("b00628f8dd8d1d93", 2942112),
    "119": ("bc72d9df7668219e", 2914248),
    "120": ("e0b7a584c49af523", 2917752),
    "121": ("52f686e984ba8e9b", 2917752),
    "130": ("35a095307d097147", 2928192),
    "131": ("7883f7b83beadc54", 2938632),
    "132": ("17a69ed5d2270b42", 2914248),
    "133": ("53f076cb0d905cf4", 2942112),
}

SINIF = {
    "97": "saglam yuk0", "98": "saglam yuk1", "99": "saglam yuk2", "100": "saglam yuk3",
    "105": "ic bilezik yuk0", "106": "ic bilezik yuk1", "107": "ic bilezik yuk2", "108": "ic bilezik yuk3",
    "118": "bilya yuk0", "119": "bilya yuk1", "120": "bilya yuk2", "121": "bilya yuk3",
    "130": "dis bilezik yuk0", "131": "dis bilezik yuk1", "132": "dis bilezik yuk2", "133": "dis bilezik yuk3",
}


def sha16(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()[:16]


def main() -> int:
    HEDEF.mkdir(parents=True, exist_ok=True)
    tamam, hatali = [], []

    for no, (bekle_hash, bekle_boyut) in KUNYE.items():
        yol = HEDEF / f"{no}.mat"

        if not yol.exists() or yol.stat().st_size != bekle_boyut:
            url = TABAN.format(no)
            try:
                istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(istek, timeout=120) as cevap, open(yol, "wb") as f:
                    while True:
                        parca = cevap.read(1 << 16)
                        if not parca:
                            break
                        f.write(parca)
            except Exception as e:
                print(f"[HATA ] {no}.mat indirilemedi: {e}")
                hatali.append(no)
                continue

        boyut = yol.stat().st_size
        h = sha16(yol)
        if h == bekle_hash and boyut == bekle_boyut:
            print(f"[TAMAM] {no}.mat  {boyut:>9,}  {h}  {SINIF[no]}")
            tamam.append(no)
        else:
            print(f"[KUNYE UYUSMADI] {no}.mat")
            print(f"        beklenen: {bekle_hash} / {bekle_boyut:,}")
            print(f"        gelen   : {h} / {boyut:,}")
            hatali.append(no)

    print(f"\n{len(tamam)}/{len(KUNYE)} dosya kunyesi dogrulandi.")
    if hatali:
        print(f"SORUNLU: {', '.join(hatali)}")
        return 1
    print("Butun kunyeler beklenen degerlerle eslesti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
