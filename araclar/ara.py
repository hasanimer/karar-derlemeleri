#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Karar derlemelerinde Türkçe harfe duyarsız, tekrarları birleştiren arama.

Kullanım:
  python3 araclar/ara.py [-d KOD] [-m MAHKEME] [-y YIL-YIL] [-b] [-n 20] [-c] TERİM...

  TERİM      Aranan sözcük. Tırnak içindeki bağımsız değişken öbektir ("icra inkar tazminati").
             Bir kararın eşleşmesi için BÜTÜN terimlerin o kararın alıntısında geçmesi gerekir.
             Büyük/küçük harf ve Türkçe harfler (ç ğ ı İ ö ş ü â î û) ayırt edilmez.
  -d KOD     Yalnız kodu bu parçayı içeren derlemeler (ör. kira, arabuluculuk, itiraz).
  -m MAHKEME Mahkeme/daire süzgeci (ör. "3. HD", hgk, ibk, "istanbul bam", danistay, aym).
  -y YIL     Yıl süzgeci: 2020-2026, 2020- , ya da tek yıl 2021. Yılı bilinmeyen künyeler elenir.
  -b         Yalnız başlıklarda ara: künye + konu yolu (alıntı metninde değil).
  -n N       En çok N sonuç göster (varsayılan 20).
  -c         Yalnız sayılar: derleme ve konu dizini başına eşleşme sayısı.

Çıktı (yıla göre yeniden eskiye, sonra dosya yoluna göre):
  <dosya>:<satır>  <künye>
    konu: <konu yolu>
    …<önceki 120 karakter>«eşleşme»<sonraki 120 karakter>…      (-b ile yazılmaz)
    (+3 aynı alıntı: <dosya:satır>, …)      aynı alıntı başka künye/konu altında da varsa
Son satır her zaman: N eşleşme, M gösterildi (K farklı alıntı)
Çıkış kodu: 0 eşleşme varsa, 1 yoksa, 2 kullanım hatasında.

Metinler derleyenin (Av. Hakan Dimdik) seçtiği alıntılardır; kararın tamamı değildir.
Yalnız Python 3 standart kitaplığı; kendi dizin dosyası yoktur. `rg` (ripgrep) kuruluysa
dosyalar onunla ön elemeden geçirilir, yoksa md/ baştan sona taranır.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import unicodedata

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = "md"
KARAR_TSV = os.path.join("dizin", "kararlar")
BAGLAM = 120          # eşleşmenin iki yanında gösterilen karakter
ES_LISTE = 5          # "aynı alıntı" satırında en çok kaç konum yazılır

# yapi.py ile aynı katlama (F)
_KATLA = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
    "Ç": "c", "Ğ": "g", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u", "Â": "a", "Î": "i", "Û": "u",
    "’": "'", "‘": "'", "ʼ": "'"})

# rg ön elemesi için: katlanmış harf -> o harfe katlanan bütün yazılışlar
_SINIF = {
    "i": "[iİıIîÎ]", "a": "[aAâÂ]", "u": "[uUüÜûÛ]", "c": "[cCçÇ]", "g": "[gGğĞ]",
    "o": "[oOöÖ]", "s": "[sSşŞ]", "'": "['’‘ʼ]",
}
_RG_OZEL = set("\\.+*?()|[]{}^$#&-~")


def F(s):
    """Katlama: Türkçe harfleri sadeleştir, küçült, boşlukları teke indir."""
    return " ".join(s.translate(_KATLA).lower().split())


_DEGISIM = (("ç", "c"), ("ğ", "g"), ("ı", "i"), ("ö", "o"), ("ş", "s"), ("ü", "u"), ("â", "a"), ("î", "i"),
            ("û", "u"), ("’", "'"), ("‘", "'"), ("ʼ", "'"))


def katla_esit(s):
    """F'nin harf eşlemesi, uzunluğu ve satır yapısını koruyarak (konumlar özgün metinle aynı kalır).
    str.translate'ten birkaç kat hızlıdır; sonuç aynıdır."""
    f = s.replace("I", "ı").replace("İ", "i").lower()
    for a, b in _DEGISIM:
        if a in f:
            f = f.replace(a, b)
    if len(f) != len(s):          # küçültünce uzunluğu değişen ender harfler
        f = "".join((c.translate(_KATLA).lower() or c)[0] for c in s)
    return f


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def sha16(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def binlik(n):
    return f"{n:,}".replace(",", ".")


# ----------------------------------------------------------------------------- bağımsız değişkenler

class Secenek:
    d = None
    m = None
    y = None
    b = False
    n = 20
    c = False
    terimler = ()


def kullanim_hatasi(ileti):
    sys.stderr.write("hata: " + ileti + "\n"
                     "kullanım: python3 araclar/ara.py [-d KOD] [-m MAHKEME] [-y 2020-2026] [-b] [-n 20] [-c] "
                     "TERİM...\n"
                     "ayrıntı: python3 araclar/ara.py -h\n")
    sys.exit(2)


def secenekleri_oku(argv):
    s = Secenek()
    terimler = []
    i, yalniz_terim = 0, False
    while i < len(argv):
        a = argv[i]
        i += 1
        if yalniz_terim or not a.startswith("-") or a == "-":
            terimler.append(a)
            continue
        if a == "--":
            yalniz_terim = True
            continue
        if a in ("-h", "--help", "--yardim"):
            sys.stdout.write(__doc__.lstrip("\n"))
            sys.exit(0)
        if a.startswith("--"):
            kullanim_hatasi(f"bilinmeyen seçenek: {a}")
        harfler = a[1:]
        j = 0
        while j < len(harfler):
            h = harfler[j]
            j += 1
            if h in "bc":
                setattr(s, h, True)
            elif h in "dmyn":
                deger = harfler[j:]
                j = len(harfler)
                if not deger:
                    if i >= len(argv):
                        kullanim_hatasi(f"-{h} bir değer ister")
                    deger = argv[i]
                    i += 1
                setattr(s, h, deger)
            else:
                kullanim_hatasi(f"bilinmeyen seçenek: -{h}")
    try:
        s.n = int(s.n)
        if s.n < 0:
            raise ValueError
    except ValueError:
        kullanim_hatasi("-n negatif olmayan bir tam sayı ister")
    if s.y is not None:
        m = re.fullmatch(r"\s*(\d{4})?\s*(?:(-)\s*(\d{4})?)?\s*", s.y)
        if not m or not (m.group(1) or m.group(3)):
            kullanim_hatasi("-y biçimi: 2020-2026, 2020- ya da 2021")
        alt = int(m.group(1)) if m.group(1) else 0
        ust = int(m.group(3)) if m.group(3) else (9999 if m.group(2) else alt)
        if alt > ust:
            alt, ust = ust, alt
        s.y = (alt, ust)
    if s.m is not None:
        s.m = re.sub(r"[^a-z0-9|]", "", F(s.m))
        if not s.m.replace("|", ""):
            kullanim_hatasi("-m boş olamaz")
    if s.d is not None:
        s.d = F(s.d).replace(" ", "-")
    s.terimler = [t for t in (F(x) for x in terimler) if t]
    if not s.terimler:
        kullanim_hatasi("en az bir arama terimi gerekir")
    return s


# ----------------------------------------------------------------------------- aday dosyalar

def kodlar(d):
    kok = os.path.join(KOK, MD)
    if not os.path.isdir(kok):
        sys.stderr.write(f"hata: {MD}/ dizini yok ({KOK}); önce `python3 yapi.py` çalıştırın\n")
        sys.exit(2)
    hepsi = sorted(x for x in os.listdir(kok) if os.path.isdir(os.path.join(kok, x)))
    secili = [k for k in hepsi if d is None or d in k]
    if not secili:
        sys.stderr.write(f"hata: -d {d}: böyle bir derleme kodu yok. Kodlar: {' '.join(hepsi)}\n")
        sys.exit(2)
    return secili


def rg_deseni(sozcuk):
    return "".join(_SINIF.get(c) or ("\\" + c if c in _RG_OZEL else c) for c in sozcuk)


def en_uzun_sozcuk(terim):
    return max(terim.split(" "), key=len)


def rg_ile(kod_listesi, terim):
    """rg varsa ilk terimi içeren dosyalar; rg yoksa ya da hata verirse None."""
    rg = shutil.which("rg")
    if not rg:
        return None
    # Öbekte satır sonu (yumuşak kırma) araya girebilir; bu yüzden öbeğin en uzun sözcüğü aranır.
    komut = [rg, "--no-config", "--no-ignore", "--no-messages", "-l", "-i", "-g", "*.md",
             "-g", "!00-icindekiler*", "-e", rg_deseni(en_uzun_sozcuk(terim)), "--"]
    komut += [MD + "/" + k for k in kod_listesi]
    try:
        p = subprocess.run(komut, cwd=KOK, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    if p.returncode not in (0, 1):
        return None
    return [x.replace(os.sep, "/") for x in p.stdout.decode("utf-8", "replace").splitlines() if x]


def yuru(kod_listesi):
    cikti = []
    for k in kod_listesi:
        for kok, dizinler, dosyalar in os.walk(os.path.join(KOK, MD, k)):
            dizinler.sort()
            for ad in dosyalar:
                if ad.endswith(".md") and not ad.startswith("00-icindekiler"):
                    cikti.append(os.path.relpath(os.path.join(kok, ad), KOK).replace(os.sep, "/"))
    return cikti


# ----------------------------------------------------------------------------- parça dosyası

_YAML_KACIS = re.compile(r"\\(.)")


def dosya_coz(satirlar):
    """(konu listesi, [(satır no, gövdenin ilk satır dizini, son satır dizini)]) döndürür."""
    konu, i, n = [], 0, len(satirlar)
    if satirlar and satirlar[0] == "---":
        i = 1
        konuda = False
        while i < n and satirlar[i] != "---":
            s = satirlar[i]
            if s == "konu:":
                konuda = True
            elif konuda and s.startswith("  - "):
                v = s[4:]
                if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                    v = _YAML_KACIS.sub(r"\1", v[1:-1])
                konu.append(v)
            else:
                konuda = False
            i += 1
        i += 1
    baslar = [j for j in range(i, n) if satirlar[j].startswith("## ")]
    kararlar = [(j + 1, j + 1, (baslar[k + 1] if k + 1 < len(baslar) else n))
                for k, j in enumerate(baslar)]
    return konu, kararlar


class Vurus:
    __slots__ = ("dosya", "satir", "kunye", "konu", "kesit", "es", "yil", "kod", "dizin")

    def konum(self):
        return f"{self.dosya}:{self.satir}"


def kesit(ozgun, katli, terim):
    p = katli.find(terim)
    if p < 0:
        return ""
    q = p + len(terim)
    a, b = max(0, p - BAGLAM), min(len(ozgun), q + BAGLAM)
    return (("…" if a > 0 else "") + ozgun[a:p] + "«" + ozgun[p:q] + "»" + ozgun[q:b]
            + ("…" if b < len(ozgun) else ""))


def dosyada_ara(yol, s, sozcukler):
    try:
        with open(os.path.join(KOK, yol), encoding="utf-8", newline="") as f:
            metin = f.read()
    except (OSError, UnicodeDecodeError):
        return []
    # ucuz ön eleme: her terimin her sözcüğü dosyada bir yerde geçmeli
    katli_dosya = katla_esit(metin)
    for w in sozcukler:
        if w not in katli_dosya:
            return []
    satirlar = metin.split("\n")
    katli_satirlar = katli_dosya.split("\n")
    if len(satirlar) != len(katli_satirlar):
        katli_satirlar = [katla_esit(x) for x in satirlar]
    konu, kararlar = dosya_coz(satirlar)
    konu_yolu = " › ".join(konu)
    katli_konu = katla_esit(konu_yolu)
    kod = yol.split("/")[1]
    dizin = yol.rsplit("/", 1)[0] + "/"
    cikti = []
    for satir, bas, son in kararlar:
        if s.b:
            katli = " ".join((katli_satirlar[satir - 1][3:] + " › " + katli_konu).split())
        else:
            katli = " ".join(" ".join(katli_satirlar[bas:son]).split())
        if any(t not in katli for t in s.terimler):
            continue
        kunye = satirlar[satir - 1][3:]
        govde = " ".join(" ".join(satirlar[bas:son]).split())
        ozgun = " ".join((kunye + " › " + konu_yolu).split()) if s.b else govde
        if len(ozgun) != len(katli):
            katli = katla_esit(ozgun)
        v = Vurus()
        v.dosya, v.satir, v.kunye, v.konu, v.kod, v.dizin = yol, satir, kunye, konu_yolu, kod, dizin
        # -b: aranan yer künye + konu yoludur, ikisi de 1. ve 2. satırda zaten yazılır; üçüncü satır yinelenmez
        v.kesit = "" if s.b else kesit(ozgun, katli, s.terimler[0])
        govde_norm = norm(govde)
        v.es = sha16(govde_norm) if govde_norm else ""
        v.yil = ""
        cikti.append(v)
    return cikti


# ----------------------------------------------------------------------------- künye dizini (yıl, mahkeme)

def tsv_yukle(kod):
    """dizin/kararlar/<kod>.tsv -> {(dosya, satır): (yıl, [mahkeme anahtarları])}; dosya yoksa None."""
    yol = os.path.join(KOK, KARAR_TSV, kod + ".tsv")
    try:
        f = open(yol, encoding="utf-8", newline="")
    except OSError:
        return None
    with f:
        baslik = f.readline().rstrip("\n").split("\t")
        try:
            si = {a: baslik.index(a) for a in ("kunye", "anahtar", "mahkeme", "daire", "yil", "dosya", "satir")}
        except ValueError:
            return None
        tablo = {}
        for satir in f:
            h = satir.rstrip("\n").split("\t")
            if len(h) < len(baslik):
                continue
            try:
                anahtar = (h[si["dosya"]], int(h[si["satir"]]))
            except ValueError:
                continue
            p = h[si["anahtar"]].split("|")
            birim = "|".join(p[:2]).replace("-", "")
            ad = re.sub(r"[^a-z0-9]", "", F(h[si["mahkeme"]] + " " + h[si["daire"]]))
            kayit = tablo.get(anahtar)
            if kayit is None:
                # künyenin kendisi de aranır ("anayasa mahkemesi", "asliye ticaret" gibi yazılışlar için)
                tablo[anahtar] = [h[si["yil"]], [birim, ad, re.sub(r"[^a-z0-9]", "", F(h[si["kunye"]]))]]
            else:
                if not kayit[0]:
                    kayit[0] = h[si["yil"]]
                kayit[1] += [birim, ad]
        return tablo


def mahkeme_uyar(desen, birimler):
    return any(desen.search(b) for b in birimler)


# ----------------------------------------------------------------------------- ana akış

def main(argv):
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    s = secenekleri_oku(argv)
    kod_listesi = kodlar(s.d)

    adaylar = rg_ile(kod_listesi, s.terimler[0])
    if adaylar is None:
        adaylar = yuru(kod_listesi)
    adaylar.sort()

    sozcukler = sorted({w for t in s.terimler for w in t.split(" ")}, key=len, reverse=True)
    vuruslar = []
    for yol in adaylar:
        vuruslar.extend(dosyada_ara(yol, s, sozcukler))

    # yıl ve mahkeme: yalnız eşleşme çıkan derlemelerin künye dizini okunur
    m_desen, m_rakamli = None, False
    if s.m is not None:
        m_desen = re.compile((r"(?<![0-9])" if s.m[0].isdigit() else "") + re.escape(s.m))
        m_rakamli = any(c.isdigit() for c in s.m)
        m_duz = re.compile((r"(?<![0-9])" if s.m[0].isdigit() else "") + re.escape(s.m.replace("|", "")))
    tablolar, eksik = {}, []
    for kod in sorted({v.kod for v in vuruslar}):
        tablolar[kod] = tsv_yukle(kod)
        if tablolar[kod] is None:
            eksik.append(kod)
    if eksik and (s.m is not None or s.y is not None):
        sys.stderr.write(f"hata: -m / -y için {KARAR_TSV}/<kod>.tsv gerekir; eksik: {' '.join(eksik)}\n")
        sys.exit(2)
    kalan = []
    for v in vuruslar:
        kayit = (tablolar.get(v.kod) or {}).get((v.dosya, v.satir))
        if kayit is not None:
            v.yil = kayit[0]
        if s.y is not None:
            if not v.yil.isdigit() or not (s.y[0] <= int(v.yil) <= s.y[1]):
                continue
        if m_desen is not None:
            # rakamlı süzgeç ("3. HD") yalnız ayrıştırılmış mahkeme/daireye bakar; künyenin tamamına değil
            alan = kayit[1] if kayit is None or not m_rakamli else [x for i, x in enumerate(kayit[1]) if i != 2]
            if kayit is None or not (mahkeme_uyar(m_desen, alan) or mahkeme_uyar(m_duz, alan)):
                continue
        kalan.append(v)
    vuruslar = kalan

    vuruslar.sort(key=lambda v: (-(int(v.yil) if v.yil.isdigit() else 0), v.dosya, v.satir))
    gruplar, es_yeri = [], {}
    for v in vuruslar:
        if v.es and v.es in es_yeri:
            gruplar[es_yeri[v.es]].append(v)
        else:
            if v.es:
                es_yeri[v.es] = len(gruplar)
            gruplar.append([v])

    cikti = []
    gosterilen = 0
    if s.c:
        derleme, yaprak = {}, {}
        for v in vuruslar:
            derleme[v.kod] = derleme.get(v.kod, 0) + 1
            yaprak[v.dizin] = yaprak.get(v.dizin, 0) + 1
        farkli = {}
        for g in gruplar:
            farkli[g[0].kod] = farkli.get(g[0].kod, 0) + 1
        for kod in sorted(derleme):
            cikti.append(f"{kod}  {binlik(derleme[kod])} eşleşme ({binlik(farkli.get(kod, 0))} farklı alıntı)")
            for d in sorted(x for x in yaprak if x.split("/")[1] == kod):
                cikti.append(f"  {d}  {binlik(yaprak[d])}")
    else:
        for g in gruplar[:s.n]:
            v = g[0]
            cikti.append(f"{v.konum()}  {v.kunye}")
            cikti.append(f"  konu: {v.konu}")
            if v.kesit:
                cikti.append("  " + v.kesit)
            if len(g) > 1:
                diger = [x.konum() for x in g[1:]]
                liste = ", ".join(diger[:ES_LISTE]) + (", …" if len(diger) > ES_LISTE else "")
                cikti.append(f"  (+{len(diger)} aynı alıntı: {liste})")
            gosterilen += 1
    cikti.append(f"{binlik(len(vuruslar))} eşleşme, {binlik(gosterilen)} gösterildi "
                 f"({binlik(len(gruplar))} farklı alıntı)")
    try:
        sys.stdout.write("\n".join(cikti) + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
    return 0 if vuruslar else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
