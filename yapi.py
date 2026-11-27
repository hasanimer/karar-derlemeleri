#!/usr/bin/env python3
"""yapi.py: derlemeler.tsv + ara/<ad>/<ad>.md -> md/, dizin/, veri/ ve kılavuz dosyaları.

Kullanım:
  python3 yapi.py            her şeyi baştan üretir (md/, dizin/, veri/ silinip yeniden yazılır)
  python3 yapi.py --dogrula  üretilmiş ağacı denetler, log/yapi.log yazar; hata varsa sıfırdan farklı çıkar
  python3 yapi.py --help     kullanımı yazar, hiçbir şey üretmez

Elle düzeltme dosyaları (isteğe bağlı, ikisi de günlüğe yazılır):
  ek/<ad>.basliklar.tsv  "<başlık metni><SEKME><konu|kunye|alt|govde>": bir başlığın sınıfını değiştirir
  ek/<ad>.satirlar.tsv   "<kaynak satırı, olduğu gibi><SEKME><yerine yazılacak satır>": dönüştürücü çıktısındaki
                         bir satırı sınıflandırmadan önce değiştirir; her satır kaynakta tam bir kez geçmelidir

Yalnız standart kitaplık kullanır. Saat ve rastgelelik kullanılmaz: aynı girdi aynı baytları verir.
"""
import argparse
import bisect
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KOK, "araclar"))
import bedesten_bagla  # noqa: E402  (yalnız standart kitaplık; Bedesten bağlantıları metadata'dan okunur)
SURUM_TARIHI = "2026-11-27"          # sabit; saatten okunmaz
SURUM = "2026.11.27"
SEMA = 1
DEPO = "hasanimer/karar-derlemeleri"
DERLEYEN = "Av. Hakan Dimdik"
DERLEYEN_FM = "Av. Hakan Dimdik (x.com/hakandimdik)"
HAKLAR = "Derlemeler üzerindeki haklar derleyene aittir; atıf zorunludur."
UYARI = ("Derleyenin seçtiği alıntılardır; kararın tamamı değildir. Künyelerin çoğunda esas numarası "
         "ve tarih yoktur. Kullanmadan önce kararın tam metnini resmî kaynaktan doğrulayın.")
KISA_UYARI = "Seçme alıntılardır, kararın tamamı değildir; resmî kaynaktan doğrulayın."

HEDEF = 40000        # parça gövdesi hedefi (bayt)
TAVAN = 48000        # kuyruk birleştirme tavanı
KUYRUK = 8000
SAR_SINIR = 1200     # yumuşak satır kırma (karakter)
DIZIN_TAVAN = 48000  # 00-icindekiler*.md
YIL_ALT = 1900       # bundan küçük ya da sürüm yılından büyük yıl "yil_supheli" sayılır
BOS_BASLIK = "(boş başlık; kararlar sonraki başlıkta)"

SEMA_ANAHTARLARI = ["id", "kod", "derleme", "surum", "alan", "bolum", "konu", "konu_yolu", "sira", "tur",
                    "kunye", "mahkeme", "daire", "esas", "karar", "kararlar", "basvuru", "tarih", "yil",
                    "not", "anahtar", "bayrak", "metin", "metin_var", "kisaltma_var", "es", "tekrar_sira",
                    "tekrar_sayisi", "tekrar_konular", "dosya", "satir", "atif", "paylasim"]
TSV_KARAR = ["sira", "id", "kunye", "anahtar", "tur", "mahkeme", "daire", "esas", "karar", "tarih", "yil",
             "metin_var", "bayt", "es", "tekrar_sira", "dosya", "satir"]
TSV_KONU = ["kod", "duzey", "bolum", "yol", "baslik", "ara", "karar", "dosya", "bayt", "ust"]
REG_SUTUN = ["kod", "ad", "baslik", "kisa", "alan", "surum", "durum", "yerine", "seri", "sira", "yabanci_kunye"]


class YapiHatasi(Exception):
    pass


# ----------------------------------------------------------------------------- ortak yardımcılar

_KATLA = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
    "Ç": "c", "Ğ": "g", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u", "Â": "a", "Î": "i", "Û": "u",
    "’": "'", "‘": "'", "ʼ": "'"})


def F(s):
    """Katlama: Türkçe harfleri sadeleştir, küçült, boşlukları teke indir."""
    return " ".join(s.translate(_KATLA).lower().split())


def slug(s):
    t = re.sub(r"[^a-z0-9]+", "-", F(s)).strip("-")
    if len(t) > 40:
        i = t.rfind("-", 0, 41)
        t = t[:i] if i > 0 else t[:40]
    return t or "bolum"


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def TRUPPER(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def binlik(n):
    return f"{n:,}".replace(",", ".")


def mb(bayt):
    return "<0,1" if bayt < 50000 else f"{bayt / 1e6:.1f}".replace(".", ",")


def yq(s):
    """YAML çift tırnaklı değer."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sha16(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------- başlık sınıflayıcı

COURT = re.compile(r"^(Yarg[ıi]?tay|YİBK|HGK|İBK|\d+\. ?HD|Danıştay|AYM|Anayasa Mahkemesi|Uyuşmazlık Mahkemesi"
                   r"|Hukuk Bölümü|\S+( \S+)? BAM\b|\S+( \S+){0,2} \d+\.? ?(HD|Asliye|Sulh|İcra|Tüketici|İş|Aile)\b)")
ALT_RE = re.compile(r"^(Orijinal metin|Türkçe çevirisi|İngilizce çevirisi)")
STRUCT = re.compile(r"^(§|KISIM\b|[IVXLC]+\. |[A-ZÇĞİÖŞÜ]\. |\d+\. |\*?[a-zçğıöşü][.)] )")
KUNYE5 = re.compile(r"\d{4}/\d+\s*(E\b|K\b|Başvuru|sayılı)|B\.\s*No")
BASLIK = re.compile(r"^(#{1,6}) (.*)$")
NUMARALAYICI = re.compile(r"^(§\s*\d+\.?|KISIM\s+[IVXLC]+\s*[–-]?|[IVXLC]+\.|[A-ZÇĞİÖŞÜ]\.|\d+\.|\*?[a-zçğıöşü][.)])\s+")
SINIFLAR = {"konu": "KONU", "kunye": "KUNYE", "alt": "ALT", "govde": "GOVDE"}


def siniflandir(duzey, t, karar_acik, yabanci_kunye, gecersiz_kil=None):
    """(sınıf, kural) döndürür. sınıf: KONU | KUNYE | ALT | GOVDE. İlk uyan kural kazanır."""
    if gecersiz_kil and t in gecersiz_kil:
        return gecersiz_kil[t], 0
    if duzey <= 2:
        return "KONU", 1
    if COURT.search(t):
        return "KUNYE", 2
    if karar_acik and ALT_RE.search(t):
        return "ALT", 3
    if STRUCT.search(t):
        return "KONU", 4
    if KUNYE5.search(t):
        return "KUNYE", 5
    if not re.search(r"\d", t) and t == TRUPPER(t):
        return "KONU", 6
    return ("KUNYE" if yabanci_kunye else "GOVDE"), 7


# ----------------------------------------------------------------------------- künye ayrıştırıcı

_KORUNAN_PARANTEZ = ("Birinci Bölüm", "İkinci Bölüm", "Genel Kurul")
_TARIH = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4})(?!\d)")
_ILK_DERECE = re.compile(r"^(.+?\b(?:Asliye|Sulh|İcra|Tüketici|İş|Aile)\b.*?Mahkemesi)\b")
_ILK_DERECE2 = re.compile(r"^(.+?\b(?:Asliye|Sulh|İcra|Tüketici|İş|Aile)\b[^,\d]*)")


def _sondaki_parantez(s):
    """Sondaki dengeli parantezi ayırır: (baş, iç) ya da None."""
    t = s.rstrip()
    if not t.endswith(")"):
        return None
    d = 0
    for i in range(len(t) - 1, -1, -1):
        c = t[i]
        if c == ")":
            d += 1
        elif c == "(":
            d -= 1
            if d == 0:
                bas, ic = t[:i].rstrip(), t[i + 1:-1]
                return (bas, ic) if bas and ic else None
    return None


def _daire(kalan, kurallar):
    kalan = re.sub(r"^[,.]?\s*", "", kalan)
    for desen, deger in kurallar:
        m = re.match(desen, kalan)
        if m:
            return deger(m) if callable(deger) else deger
    return ""


_D_YARGITAY = [
    (r"(\d+)\. ?(HD|CD)\b", lambda m: f"{m.group(1)}. {m.group(2)}"),
    (r"(\d+)\. ?Hukuk Dairesi\b", lambda m: f"{m.group(1)}. HD"),
    (r"(\d+)\. ?Ceza Dairesi\b", lambda m: f"{m.group(1)}. CD"),
    (r"(HGK|Hukuk Genel Kurulu)\b", "HGK"),
    (r"(CGK|Ceza Genel Kurulu)\b", "CGK"),
    (r"(İBK|İçtihad[ıi] Birleştirme (Büyük )?(Genel )?Kurulu)\b", "İBK"),
    (r"Büyük Genel Kurulu?\b", "Büyük Genel Kurul"),
]
_D_DANISTAY = [
    (r"(\d+)\. ?(D\.|Daire(si)?\b)", lambda m: f"{m.group(1)}. D."),
    (r"(İDDK|İdar[ei] Dava Daireleri Kurulu)\b", "İDDK"),
    (r"(VDDK|Vergi Dava Daireleri Kurulu)\b", "VDDK"),
    (r"(İBK|İçtihatları Birleştirme Kurulu)\b", "İBK"),
]
_D_AYM = [(r"\(?(Birinci Bölüm|İkinci Bölüm|Genel Kurul)\b\)?", lambda m: m.group(1))]
_D_UYUSMAZLIK = [(r"(Hukuk Bölümü|Ceza Bölümü)", lambda m: m.group(1))]
_D_BAM = [(r"(\d+)\. ?(HD|CD)\b", lambda m: f"{m.group(1)}. {m.group(2)}")]


def kunye_coz(kunye, yabanci=False, yabanci_olabilir=False):
    """Künyeden alan çıkarır. Başlık metni değiştirilmez; her şey bir kopya üzerinde yapılır.
    Eksik numara, tarih ya da daire tahmin edilmez."""
    s = kunye.strip()
    bayrak = []
    r = {"tur": "", "mahkeme": "", "daire": "", "esas": "", "karar": "", "kararlar": [], "basvuru": "",
         "tarih": "", "yil": None, "not": "", "anahtarlar": [], "bayrak": bayrak}

    if yabanci:
        return _yabanci(s, r)

    # 1. not: sondaki parantez (önce; nottaki "RG gg.aa.yyyy" karar tarihi sanılmasın)
    p = _sondaki_parantez(s)
    if p and p[1] not in _KORUNAN_PARANTEZ:
        s, r["not"] = p
    # 2. dipnot rakamı
    m = re.search(r"(K\.)\d$", s)
    if m:
        s = s[:m.start()] + "K."
        bayrak.append("dipnot")
    # 3. yazım hataları (yalnız ayrıştırılan kopyada)
    s2 = re.sub(r"^Yarg(?:tay|itay)\b", "Yargıtay", s)
    s2 = re.sub(r"^Yargıtay\.", "Yargıtay", s2)
    s2 = re.sub(r"^İstambul\b", "İstanbul", s2)
    if " BAM" not in s2:
        s2 = re.sub(r"^(\S+) (\d+) HD\b", r"\1 BAM \2. HD", s2)
    if s2 != s:
        s = s2
        bayrak.append("yazim")
    # 4. mahkeme adı yazılmamış
    if re.match(r"(\d+\. ?HD|HGK|İBK)\b", s):
        s = "Yargıtay " + s
        bayrak.append("mahkeme_cikarim")
    elif re.match(r"YİBK\b", s):
        s = "Yargıtay İBK" + s[4:]
        bayrak.append("mahkeme_cikarim")
    elif s.startswith("Hukuk Bölümü"):
        s = "Uyuşmazlık Mahkemesi " + s
        bayrak.append("mahkeme_cikarim")
    # 5-7. tür, mahkeme, daire
    m = re.match(r"Yargıtay\b", s)
    if m:
        r["tur"], r["mahkeme"] = "yargitay", "Yargıtay"
        r["daire"] = _daire(s[m.end():], _D_YARGITAY)
    elif s.startswith("Danıştay"):
        r["tur"], r["mahkeme"] = "danistay", "Danıştay"
        r["daire"] = _daire(s[len("Danıştay"):], _D_DANISTAY)
    elif re.match(r"(AYM|Anayasa Mahkemesi)\b", s):
        m = re.match(r"(AYM|Anayasa Mahkemesi)\b", s)
        r["tur"], r["mahkeme"] = "aym", "AYM"
        r["daire"] = _daire(s[m.end():], _D_AYM)
    elif s.startswith("Uyuşmazlık"):
        m = re.match(r"Uyuşmazlık Mahkemesi\b", s)
        r["tur"], r["mahkeme"] = "uyusmazlik", "Uyuşmazlık Mahkemesi"
        r["daire"] = _daire(s[m.end():] if m else "", _D_UYUSMAZLIK)
    else:
        m = re.match(r"(\S+(?: \S+)?) BAM\b", s)
        if m:
            r["tur"], r["mahkeme"] = "bam", m.group(1) + " BAM"
            r["daire"] = _daire(s[m.end():], _D_BAM)
        else:
            m = _ILK_DERECE.match(s) or _ILK_DERECE2.match(s)
            if m:
                r["tur"], r["mahkeme"] = "ilk-derece", m.group(1).strip().rstrip(",")
            elif yabanci_olabilir:
                r["not"] = ""
                del bayrak[:]
                return _yabanci(kunye.strip(), r)
            else:
                raise YapiHatasi(f"künyede tanınmayan mahkeme: {kunye!r}")
    # 8. esas
    m = re.search(r"(\d{4}/\d+(?:-\d+)?)\s*E\b", s)
    if m:
        r["esas"] = m.group(1)
    # 10. başvuru (9'daki "sahipsiz numara" denetiminden önce bilinmeli)
    m = re.search(r"B(?:aşvuru)?\.? ?No:? ?(\d{4}/\d+)", s) or re.search(r"(\d{4}/\d+) Başvuru", s)
    if m:
        r["basvuru"] = m.group(1)
    # 9. karar numaraları
    ks = re.findall(r"(\d{4}/\d+)\s*K\b", s)
    if len(ks) > 1:
        bayrak.append("cok_karar")
    if not ks:
        m = re.search(r"(\d{4}/\d+)\s*$", s)
        if m and m.group(1) != r["basvuru"]:
            ks = [m.group(1)]
            bayrak.append("k_eki_yok")
        else:
            m = re.search(r"(?<![/\d])(\d+)\s*K\b", s)
            if m:
                ks = ["?/" + m.group(1)]
                bayrak.append("yil_yok")
            elif not r["basvuru"]:
                bayrak.append("karar_no_yok")
    r["kararlar"] = ks
    r["karar"] = ks[0] if ks else ""
    # 11. tarih
    r["tarih"] = _tarih(s)
    # 12. yıl (yaklaşık)
    for v in (r["tarih"], r["karar"], r["basvuru"], r["esas"]):
        if v and v[:4].isdigit():
            r["yil"] = int(v[:4])
            break
    _yil_denetle(r)
    _anahtar(r)
    return r


def _yil_denetle(r):
    """Akla yatmayan yıl (yazım hatası) tahmin edilmez: yil boş kalır, bayrak konur; künye ve karar no değişmez."""
    if r["yil"] is not None and not (YIL_ALT <= r["yil"] <= int(SURUM_TARIHI[:4])):
        r["yil"] = None
        r["bayrak"].append("yil_supheli")


def _parantez_disi_virgul(s):
    d = 0
    for i, c in enumerate(s):
        if c == "(":
            d += 1
        elif c == ")":
            d = max(0, d - 1)
        elif c == "," and d == 0:
            return i
    return -1


def _tarih(s):
    for m in _TARIH.finditer(s):
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            continue
    return ""


def _yabanci(s, r):
    r["tur"] = "yabanci"
    v = _parantez_disi_virgul(s)
    r["mahkeme"] = (s if v < 0 else s[:v]).strip()
    r["tarih"] = _tarih(s)
    if r["tarih"]:
        r["yil"] = int(r["tarih"][:4])
    _yil_denetle(r)
    _anahtar(r)
    return r


def _anahtar(r):
    daire = r["daire"].replace(".", "").replace(" ", "")
    if r["tur"] in ("bam", "ilk-derece", "yabanci"):
        birim = slug((r["mahkeme"] + " " + daire).strip())
    else:
        birim = slug(daire) if daire else ""
    if r["kararlar"]:
        nolar = ["k" + k for k in r["kararlar"]]
    elif r["basvuru"]:
        nolar = ["b" + r["basvuru"]]
    elif r["esas"]:
        nolar = ["e" + r["esas"]]
    else:
        nolar = [""]
    r["anahtarlar"] = [f"{r['tur']}|{birim}|{no}" for no in nolar]


# ----------------------------------------------------------------------------- kayıt defteri

def tsv_oku(yol, baslikli=True):
    with open(yol, encoding="utf-8", newline="") as f:
        satirlar = [s for s in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if s and any(s)]
    return satirlar


def defter_oku():
    sat = tsv_oku(os.path.join(KOK, "derlemeler.tsv"))
    if sat[0] != REG_SUTUN:
        raise YapiHatasi(f"derlemeler.tsv başlık satırı beklenen gibi değil: {sat[0]}")
    indir = {s[0]: s[1] for s in tsv_oku(os.path.join(KOK, "indir.tsv"))}
    kaynak = {s[0]: (s[1], s[2]) for s in tsv_oku(os.path.join(KOK, "kaynaklar.tsv"))}
    seri_kaynak = {}
    for ad, v in kaynak.items():
        seri_kaynak[F(ad).split("_")[0]] = v
    D, kodlar, adlar = [], set(), set()
    for s in sat[1:]:
        s = s + [""] * (len(REG_SUTUN) - len(s))
        d = dict(zip(REG_SUTUN, s))
        if not re.fullmatch(r"[a-z0-9-]{1,24}", d["kod"]):
            raise YapiHatasi(f"geçersiz kod: {d['kod']!r}")
        if d["kod"] in kodlar:
            raise YapiHatasi(f"iki satır aynı kodu taşıyor: {d['kod']}")
        if d["ad"] in adlar:
            raise YapiHatasi(f"iki satır aynı adı taşıyor: {d['ad']}")
        kodlar.add(d["kod"])
        adlar.add(d["ad"])
        d["sira"] = int(d["sira"])
        d["yabanci_kunye"] = d["yabanci_kunye"] == "1"
        if d["durum"] not in ("guncel", "eski-surum"):
            raise YapiHatasi(f"{d['kod']}: durum guncel ya da eski-surum olmalı")
        d["girdi"] = os.path.join(KOK, "ara", d["ad"], d["ad"] + ".md")
        if not os.path.isfile(d["girdi"]):
            raise YapiHatasi(f"{d['kod']}: girdi yok: ara/{d['ad']}/{d['ad']}.md")
        if d["ad"] not in indir:
            raise YapiHatasi(f"{d['kod']}: indir.tsv içinde Drive kimliği yok")
        d["drive"] = indir[d["ad"]]
        k = kaynak.get(d["ad"]) or (seri_kaynak.get(d["seri"]) if d["seri"] else None)
        if not k:
            raise YapiHatasi(f"{d['kod']}: kaynaklar.tsv içinde gönderi yok")
        d["gonderi"] = k[1]
        d["kaynak_pdf"] = f"https://drive.google.com/file/d/{d['drive']}/view"
        d["paylasim"] = f"https://x.com/hakandimdik/status/{d['gonderi']}"
        d["dogrulama"] = dogrulama_sonucu(d["ad"])
        d["tam_ad"] = d["baslik"] if (not d["surum"] or d["baslik"].endswith(d["surum"])) \
            else f"{d['baslik']} ({d['surum']})"
        d["atif"] = f'{DERLEYEN}, "{d["tam_ad"]}", X (@hakandimdik), {SURUM_TARIHI[:4]}'
        D.append(d)
    if sorted(d["sira"] for d in D) != list(range(1, len(D) + 1)):
        raise YapiHatasi("derlemeler.tsv: sira sütunu 1..N olmalı")
    D.sort(key=lambda d: d["sira"])
    for d in D:
        if d["yerine"] and d["yerine"] not in kodlar:
            raise YapiHatasi(f"{d['kod']}: yerine={d['yerine']} diye bir kod yok")
    ara = os.path.join(KOK, "ara")
    for ad in sorted(os.listdir(ara)):
        if os.path.isdir(os.path.join(ara, ad)) and ad not in adlar:
            raise YapiHatasi(f"ara/{ad} için derlemeler.tsv içinde satır yok")
    return D


def dogrulama_sonucu(ad):
    yol = os.path.join(KOK, "log", ad + ".log")
    if not os.path.isfile(yol):
        return "bilinmiyor"
    son = ""
    with open(yol, encoding="utf-8") as f:
        for s in f:
            if s.startswith("=== yapi"):
                break
            if s.startswith("Sonuç:"):
                son = s[len("Sonuç:"):].strip()
    if not son:
        return "bilinmiyor"
    kisa = son.split("—")[0].split("(")[0].strip()
    return kisa.replace("I", "ı").replace("İ", "i").lower()


# ----------------------------------------------------------------------------- girdi modeli

class Dugum:
    __slots__ = ("duzey", "baslik", "ust", "cocuklar", "no", "bolum", "dizin", "yol", "konu", "notlar",
                 "kayitlar", "satir", "dosyalar", "bayt", "top_karar", "top_dosya", "not_kaydi", "derinlik")

    def __init__(self, duzey, baslik, ust, satir):
        self.duzey, self.baslik, self.ust, self.satir = duzey, baslik, ust, satir
        self.cocuklar, self.notlar, self.kayitlar, self.dosyalar = [], [], [], []
        self.bayt = 0
        self.not_kaydi = None


class Kayit:
    __slots__ = ("kunye", "paragraflar", "dugum", "yabanci", "satir_no", "alt_var", "sira", "konum", "metin",
                 "es", "id", "k", "dosya", "satir", "blok", "tur", "tekrar")

    def __init__(self, kunye, dugum, yabanci, satir_no):
        self.kunye, self.dugum, self.yabanci, self.satir_no = kunye, dugum, yabanci, satir_no
        self.paragraflar = []
        self.alt_var = False


class Model:
    pass


def gecersiz_kil_oku(ad):
    yol = os.path.join(KOK, "ek", ad + ".basliklar.tsv")
    if not os.path.isfile(yol):
        return None
    g = {}
    for s in tsv_oku(yol):
        if s[0].startswith("#") or len(s) < 2:
            continue
        if s[1] not in SINIFLAR:
            raise YapiHatasi(f"ek/{ad}.basliklar.tsv: bilinmeyen sınıf {s[1]!r}")
        g[s[0]] = SINIFLAR[s[1]]
    return g


def satir_yamalari_oku(ad):
    """ek/<ad>.satirlar.tsv: [(kaynak satırı, yeni satır)]. Satırlar olduğu gibi (kırpılmadan) okunur."""
    yol = os.path.join(KOK, "ek", ad + ".satirlar.tsv")
    if not os.path.isfile(yol):
        return []
    with open(yol, encoding="utf-8", newline="") as f:
        ham = unicodedata.normalize("NFC", f.read())
    if "\r" in ham:
        raise YapiHatasi(f"ek/{ad}.satirlar.tsv: CR satır sonu var")
    out, gorulen = [], set()
    for no, s in enumerate(ham.split("\n"), 1):
        if not s:
            continue
        p = s.split("\t")
        if len(p) != 2 or not p[0].strip() or not p[1].strip():
            raise YapiHatasi(f"ek/{ad}.satirlar.tsv:{no}: '<kaynak satırı><SEKME><yeni satır>' bekleniyor")
        if p[0] in gorulen:
            raise YapiHatasi(f"ek/{ad}.satirlar.tsv:{no}: aynı kaynak satırı iki kez yazılmış")
        gorulen.add(p[0])
        out.append((p[0], p[1]))
    return out


def satir_yamalarini_uygula(d, satirlar, bas):
    """Yamaları 'satirlar' üzerinde yerinde uygular (yalnız gövdede, bas'tan sonra).
    Her kaynak satırı tam bir kez geçmelidir. [(satır no, eski, yeni)] döndürür."""
    yamalar = satir_yamalari_oku(d["ad"])
    if not yamalar:
        return []
    yer = collections.defaultdict(list)
    aranan = {e for e, _ in yamalar}
    for i in range(bas, len(satirlar)):
        if satirlar[i] in aranan:
            yer[satirlar[i]].append(i)
    uygulanan = []
    for eski, yeni in yamalar:
        if len(yer[eski]) != 1:
            raise YapiHatasi(f"ek/{d['ad']}.satirlar.tsv: {eski!r} kaynakta {len(yer[eski])} kez geçiyor "
                             f"(tam 1 olmalı)")
        uygulanan.append((yer[eski][0] + 1, eski, yeni))
    for no, _, yeni in uygulanan:
        satirlar[no - 1] = yeni
    uygulanan.sort()
    return uygulanan


def oku(d):
    """Bir derlemeyi okur: KONU ağacı, belge sırasıyla kayıtlar, sınıflayıcı günlüğü."""
    kod = d["kod"]
    with open(d["girdi"], encoding="utf-8", newline="") as f:
        ham = f.read()
    if "\r" in ham:
        raise YapiHatasi(f"{kod}: girdide CR satır sonu var")
    satirlar = unicodedata.normalize("NFC", ham).split("\n")
    if satirlar[0] != "---":
        raise YapiHatasi(f"{kod}: ön bilgi (front matter) yok")
    son = satirlar.index("---", 1)
    sayfa = None
    for s in satirlar[1:son]:
        m = re.match(r"sayfa:\s*(\d+)", s)
        if m:
            sayfa = int(m.group(1))
    if sayfa is None:
        raise YapiHatasi(f"{kod}: ön bilgide sayfa yok")
    gk = gecersiz_kil_oku(d["ad"])
    yamalar = satir_yamalarini_uygula(d, satirlar, son + 1)
    kokd = Dugum(0, "", None, 0)
    yigin = [kokd]
    dugumler, kayitlar, gunluk = [], [], []
    say = collections.Counter()
    acik = None                      # açık karar
    for i in range(son + 1, len(satirlar)):
        s = satirlar[i]
        if not s.strip():
            continue
        m = BASLIK.match(s) if s[0] == "#" else None
        if m:
            L, t = len(m.group(1)), m.group(2).strip()
            if "\t" in t:
                raise YapiHatasi(f"{kod}: başlıkta sekme var (satır {i + 1})")
            sinif, kural = siniflandir(L, t, acik is not None, d["yabanci_kunye"], gk)
            if kural in (0, 6, 7):
                gunluk.append((i + 1, L, sinif, kural, t))
            if sinif == "ALT" and acik is None:
                raise YapiHatasi(f"{kod}: açık karar yokken ALT başlık (satır {i + 1}): {t}")
            say[sinif] += 1
            if sinif == "KONU":
                while yigin[-1].duzey >= L:
                    yigin.pop()
                n = Dugum(L, t, yigin[-1], i + 1)
                yigin[-1].cocuklar.append(n)
                yigin.append(n)
                dugumler.append(n)
                acik = None
            elif sinif == "KUNYE":
                if yigin[-1] is kokd:
                    raise YapiHatasi(f"{kod}: konu başlığından önce karar (satır {i + 1})")
                acik = Kayit(t, yigin[-1], kural == 7, i + 1)
                yigin[-1].kayitlar.append(acik)
                kayitlar.append(acik)
            elif sinif == "ALT":
                acik.paragraflar.append("### " + t)
                acik.alt_var = True
            else:                    # GOVDE: düz paragraf
                (acik.paragraflar if acik is not None else _notlar(yigin, kokd, kod, i)).append(t)
        else:
            (acik.paragraflar if acik is not None else _notlar(yigin, kokd, kod, i)).append(s.strip())
    # numaralama, yollar
    def numarala(n, bolum, yol, konu, derinlik):
        en = 3 if len(n.cocuklar) > 99 else 2
        for j, c in enumerate(n.cocuklar, 1):
            c.no = str(j).zfill(en)
            c.bolum = (bolum + "-" if bolum else "") + c.no
            c.dizin = c.no + "-" + slug(NUMARALAYICI.sub("", c.baslik))
            c.yol = yol + c.dizin + "/"
            c.konu = konu + [c.baslik]
            c.derinlik = derinlik + 1
            numarala(c, c.bolum, c.yol, c.konu, c.derinlik)
    numarala(kokd, "", f"md/{kod}/", [], 0)
    # kayıtlar: metin, es, id
    gorulen = collections.Counter()
    idler = set()
    konum = 0
    sira = 0
    tum = []
    for n in dugumler:
        if n.notlar:
            k = Kayit(None, n, False, n.satir)
            k.paragraflar = n.notlar
            k.tur = "konu-notu"
            k.sira = 0
            n.not_kaydi = k
            tum.append(k)
        for k in n.kayitlar:
            k.tur = ""
            sira += 1
            k.sira = sira
            tum.append(k)
    # belge sırası = ağacın ön-sıra gezintisi (bir düğümün kendi kararları alt başlıklarından önce gelir)
    if [k for k in tum if k.tur == ""] != kayitlar:
        raise YapiHatasi(f"{kod}: ağaç gezintisi belge sırasını vermiyor")
    for k in tum:
        konum += 1
        k.konum = konum
        k.metin = "\n\n".join(k.paragraflar)
        nm = norm(k.metin)
        k.es = sha16(nm) if nm else ""
        anahtar = k.dugum.bolum if k.kunye is None else norm(k.kunye)
        h = sha16(kod + "\x1f" + anahtar + "\x1f" + nm)
        gorulen[h] += 1
        k.id = f"{kod}:{h}" + (f"-{gorulen[h]}" if gorulen[h] > 1 else "")
        if k.id in idler:
            raise YapiHatasi(f"{kod}: yinelenen kimlik {k.id}")
        idler.add(k.id)
        if k.kunye is not None:
            k.k = kunye_coz(k.kunye, yabanci=k.yabanci, yabanci_olabilir=d["yabanci_kunye"])
            k.tur = k.k["tur"]
    M = Model()
    M.d, M.sayfa, M.kok, M.dugumler, M.kayitlar, M.tum, M.gunluk, M.say = \
        d, sayfa, kokd, dugumler, kayitlar, tum, gunluk, say
    M.yamalar = yamalar
    return M


def _notlar(yigin, kokd, kod, i):
    if yigin[-1] is kokd:
        raise YapiHatasi(f"{kod}: ilk başlıktan önce metin (satır {i + 1})")
    return yigin[-1].notlar


# ----------------------------------------------------------------------------- yumuşak satır kırma

_CUMLE = re.compile(r'(?<=[.;:!?…]) (?=[A-ZÇĞİÖŞÜ0-9"“(])')
_BLOK_BASI = re.compile(r"(?:[-+*>#=]|\d+[.)])(?: |$)")


def sar(satir, sinir=SAR_SINIR):
    """Uzun satırı cümle sonlarından tek satır sonuyla böler (boş satır yok: aynı paragraf kalır)."""
    n = len(satir)
    if n <= sinir:
        return satir
    aday = [m.start() for m in _CUMLE.finditer(satir)]
    yildiz = [m.start() for m in re.finditer(r"\*\*", satir)]

    def uygun(p):
        return (bisect.bisect_left(yildiz, p) % 2 == 0 and not _BLOK_BASI.match(satir, p + 1)
                and satir[p - 1] != " " and satir[p + 1:p + 2] != " ")
    parcalar, bas = [], 0
    while n - bas > sinir:
        ust = bas + sinir
        kes = -1
        j = bisect.bisect_right(aday, ust) - 1
        while j >= 0 and aday[j] > bas:
            if uygun(aday[j]):
                kes = aday[j]
                break
            j -= 1
        if kes < 0:
            p = satir.rfind(" ", bas + 1, ust + 1)
            while p > bas:
                if uygun(p):
                    kes = p
                    break
                p = satir.rfind(" ", bas + 1, p)
        if kes < 0:
            break
        parcalar.append(satir[bas:kes])
        bas = kes + 1
    parcalar.append(satir[bas:])
    return "\n".join(parcalar)


def blok_yaz(k):
    """Bir kararın parça dosyasındaki metni ('## künye' + paragraflar), sonunda boş satırla."""
    b = [] if k.kunye is None else ["## " + k.kunye]
    b.extend(sar(p) for p in k.paragraflar)
    return "".join(x + "\n\n" for x in b)


# ----------------------------------------------------------------------------- parçalama

def bildirim(d, n, parca=None, sira=None):
    s = f'> {DERLEYEN}, "{d["baslik"]}" › ' + " › ".join(n.konu)
    if parca:
        s += f" · parça {parca}"
    if sira:
        s += f" · sıra {sira}"
    return s + ". " + KISA_UYARI


def on_bilgi(d, n, parca, sira, karar_sayisi, onceki, sonraki):
    fm = ["---", "derleme: " + yq(d["baslik"]), "kod: " + d["kod"], "surum: " + yq(d["surum"]),
          "derleyen: " + yq(DERLEYEN_FM), "konu:"]
    fm += ["  - " + yq(t) for t in n.konu]
    fm += ["bolum: " + yq(n.bolum), "parca: " + yq(parca), "sira: " + yq(sira), f"karar_sayisi: {karar_sayisi}"]
    if onceki:
        fm.append("onceki: " + yq(onceki))
    if sonraki:
        fm.append("sonraki: " + yq(sonraki))
    fm += ["kaynak_pdf: " + yq(d["kaynak_pdf"]), "uyari: " + yq(UYARI), "---", ""]
    return "\n".join(fm) + "\n"


def paketle(n, d):
    """Bir yaprağın (düğümün kendi kararları) dosyalara dağıtımı: [[kayıt, ...], ...]."""
    birimler, bekleyen = [], []
    if n.not_kaydi is not None:
        bekleyen.append(n.not_kaydi)
    for k in n.kayitlar:
        bekleyen.append(k)
        if k.paragraflar:              # metinsiz künye kendinden sonraki birime yapışır
            birimler.append(bekleyen)
            bekleyen = []
    if bekleyen:
        birimler.append(bekleyen)
    if not birimler:
        return []
    bas = len(("# " + n.baslik + "\n\n" + bildirim(d, n, "0000/0000", "000000-000000") + "\n\n").encode("utf-8"))
    dosyalar, simdi, boy = [], [], bas
    for b in birimler:
        bb = sum(len(k.blok.encode("utf-8")) for k in b)
        if simdi and boy + bb > HEDEF:
            dosyalar.append((boy, simdi))
            simdi, boy = [], bas
        simdi.extend(b)
        boy += bb
    dosyalar.append((boy, simdi))
    # kuyruk kuralı: tavan, ön bilgi dahil bütün dosya için uygulanır ("en çok 48 KB" sözü tutsun diye)
    ad = f"{d['kod']}.{n.bolum}.0000.md"
    fm = len(on_bilgi(d, n, "0000/0000", "000000-000000", 9999, ad, ad).encode("utf-8"))
    if len(dosyalar) >= 2 and dosyalar[-1][0] < KUYRUK and fm + dosyalar[-2][0] + dosyalar[-1][0] - bas <= TAVAN:
        son = dosyalar.pop()
        onceki = dosyalar.pop()
        dosyalar.append((onceki[0] + son[0] - bas, onceki[1] + son[1]))
    return [x[1] for x in dosyalar]


def yaz(kok, goreli, metin):
    yol = os.path.join(kok, goreli)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    veri = metin.encode("utf-8") if isinstance(metin, str) else metin
    with open(yol, "wb") as f:
        f.write(veri)
    return len(veri)


def baglantili_blok(k, baglantilar):
    """Doğrulanmış Bedesten bağlantısı varsa künyenin altına ekler. Parçalama bağlantısız blokla yapılır,
    böylece bağlantı eklemek dosya sınırlarını değiştirmez (bkz. araclar/bedesten_bagla.py)."""
    url = baglantilar.get(getattr(k, "id", None)) if k.kunye is not None else None
    if not url:
        return k.blok
    bas = "## " + k.kunye + "\n\n"
    assert k.blok.startswith(bas)
    return bas + bedesten_bagla.baglanti_satiri(url) + "\n\n" + k.blok[len(bas):]


def parcalari_yaz(M, kok, baglantilar=None):
    """md/<kod>/ altındaki parça dosyalarını yazar; kayıtlara dosya ve satır atar."""
    baglantilar = baglantilar or {}
    d = M.d
    kod = d["kod"]
    for k in M.tum:
        k.blok = blok_yaz(k)
    toplam_dosya = toplam_bayt = 0
    boyutlar = []
    for n in M.dugumler:
        paket = paketle(n, d)
        en = max(3, len(str(len(paket))))
        adlar = [f"{kod}.{n.bolum}.{str(j).zfill(en)}.md" for j in range(1, len(paket) + 1)]
        for j, kayitlar in enumerate(paket):
            kararlar = [k for k in kayitlar if k.kunye is not None]
            sira = f"{kararlar[0].sira}-{kararlar[-1].sira}" if kararlar else ""
            parca = f"{j + 1}/{len(paket)}"
            fm = on_bilgi(d, n, parca, sira, len(kararlar), adlar[j - 1] if j > 0 else None,
                          adlar[j + 1] if j + 1 < len(paket) else None)
            parcalar = [fm, "# " + n.baslik + "\n\n",
                        bildirim(d, n, parca, sira) + "\n\n"]
            satir = sum(p.count("\n") for p in parcalar) + 1
            goreli = n.yol + adlar[j]
            for k in kayitlar:
                k.dosya, k.satir = goreli, satir
                blok = baglantili_blok(k, baglantilar)
                parcalar.append(blok)
                satir += blok.count("\n")
            metin = "".join(parcalar).rstrip("\n") + "\n"
            b = yaz(kok, goreli, metin)
            n.dosyalar.append(adlar[j])
            n.bayt += b
            boyutlar.append(b)
            toplam_dosya += 1
            toplam_bayt += b
    # alt ağaç toplamları
    def topla(n):
        n.top_karar, n.top_dosya = len(n.kayitlar), len(n.dosyalar)
        for c in n.cocuklar:
            topla(c)
            n.top_karar += c.top_karar
            n.top_dosya += c.top_dosya
    for c in M.kok.cocuklar:
        topla(c)
    M.dosya_sayisi, M.bayt, M.boyutlar = toplam_dosya, toplam_bayt, boyutlar


# ----------------------------------------------------------------------------- 00-icindekiler.md

def dizin_satiri(n, girinti, taban):
    """taban: bağlantıların göreli olduğu dizinden md/<kod>/ köküne ek yok (hep md/<kod>/ içinde)."""
    ad = n.baslik
    if n.dosyalar:
        ad = f"[{ad}]({n.yol[len(taban):]}{n.dosyalar[0]})"
    if n.cocuklar and n.dosyalar:
        say = f"{binlik(len(n.kayitlar))} karar · {len(n.dosyalar)} dosya; alt başlıklarıyla {binlik(n.top_karar)} karar"
    elif n.cocuklar:
        say = f"alt başlıklarıyla {binlik(n.top_karar)} karar · {binlik(n.top_dosya)} dosya"
    elif not n.dosyalar:
        say = BOS_BASLIK
    else:
        say = f"{binlik(len(n.kayitlar))} karar · {len(n.dosyalar)} dosya"
    return f"{'  ' * girinti}- {ad} — {say}"


def icindekiler_yaz(M, kok):
    d = M.d
    kod = d["kod"]
    taban = f"md/{kod}/"
    fm = "\n".join([
        "---", "derleme: " + yq(d["baslik"]), "kod: " + kod, "surum: " + yq(d["surum"]),
        "derleyen: " + yq(DERLEYEN_FM), "alan: " + yq(d["alan"]), f"sayfa: {M.sayfa}",
        f"karar_sayisi: {len(M.kayitlar)}", f"dosya_sayisi: {M.dosya_sayisi}",
        "kaynak_pdf: " + yq(d["kaynak_pdf"]), "paylasim: " + yq(d["paylasim"]),
        "surum_tarihi: " + yq(SURUM_TARIHI), "dogrulama: " + yq(d["dogrulama"]), "durum: " + yq(d["durum"]),
        "uyari: " + yq(UYARI), "---", ""]) + "\n"
    not_ = (f'> {DERLEYEN}, "{d["tam_ad"]}" · {binlik(M.sayfa)} sayfa · {binlik(len(M.kayitlar))} karar · '
            f'{binlik(M.dosya_sayisi)} dosya. {KISA_UYARI}')
    if d["durum"] == "eski-surum":
        not_ += f" ESKİ SÜRÜM; güncel hâli: [md/{d['yerine']}/](../{d['yerine']}/00-icindekiler.md)."
    aciklama = ("Bağlantı, başlığın ilk parça dosyasına gider; sonraki parçalar dosyanın `sonraki` alanındadır. "
                "Bağlantısız başlıkların kendi kararı yoktur, kararlar alt başlıklarındadır.")
    if any(not n.dosyalar and not n.cocuklar for n in M.dugumler):
        aciklama += (f" \"{BOS_BASLIK}\" yazan başlığın altında kaynakta karar da alt başlık da yoktur; "
                     f"dizini yoktur.")

    def agac(n, girinti, en_derin=None):
        out = [dizin_satiri(n, girinti, taban)]
        if en_derin is None or n.derinlik < en_derin:
            for c in n.cocuklar:
                out.extend(agac(c, girinti + 1, en_derin))
        return out
    satirlar = []
    for c in M.kok.cocuklar:
        satirlar.extend(agac(c, 0))
    tam = fm + f"# {d['baslik']}\n\n{not_}\n\n{aciklama}\n\n" + "\n".join(satirlar) + "\n"
    dosyalar = {}
    if len(tam.encode("utf-8")) <= DIZIN_TAVAN:
        dosyalar["00-icindekiler.md"] = tam
    else:
        satirlar = []
        for c in M.kok.cocuklar:
            alt = f"00-icindekiler-{c.no}.md"
            ilk = agac(c, 0, 2)
            if any(g.cocuklar for g in c.cocuklar):
                ilk[0] += f" · [tüm alt başlıklar]({alt})"
                govde = (fm + f"# {d['baslik']}: {c.baslik}\n\n{not_}\n\n"
                         f"[Derlemenin ana dizini](00-icindekiler.md). {aciklama}\n\n"
                         + "\n".join(agac(c, 0)) + "\n")
                dosyalar[alt] = govde
            satirlar.extend(ilk)
        dosyalar["00-icindekiler.md"] = (
            fm + f"# {d['baslik']}\n\n{not_}\n\n{aciklama} Bu dizinde ilk iki düzey vardır; her ana bölümün "
            f"bütün alt başlıkları \"tüm alt başlıklar\" bağlantısındaki dosyadadır.\n\n" + "\n".join(satirlar) + "\n")
    for ad, metin in dosyalar.items():
        yaz(kok, taban + ad, metin)
    return sorted(dosyalar)


# ----------------------------------------------------------------------------- kayıt nesnesi, TSV, JSONL

def kayit_nesnesi(k, d, tekrar):
    n = k.dugum
    ts, tn, tk = tekrar.get((d["kod"], k.konum), (0, 0, []))
    o = {"id": k.id, "kod": d["kod"], "derleme": d["baslik"], "surum": d["surum"] or None, "alan": d["alan"],
         "bolum": n.bolum, "konu": n.konu, "konu_yolu": " > ".join(n.konu), "sira": k.sira}
    if k.kunye is None:
        o.update({"tur": "konu-notu", "kunye": None, "mahkeme": None, "daire": None, "esas": None, "karar": None,
                  "kararlar": [], "basvuru": None, "tarih": None, "yil": None, "not": None, "anahtar": None,
                  "bayrak": []})
    else:
        r = k.k
        o.update({"tur": r["tur"], "kunye": k.kunye, "mahkeme": r["mahkeme"] or None, "daire": r["daire"] or None,
                  "esas": r["esas"] or None, "karar": r["karar"] or None, "kararlar": r["kararlar"],
                  "basvuru": r["basvuru"] or None, "tarih": r["tarih"] or None, "yil": r["yil"],
                  "not": r["not"] or None, "anahtar": r["anahtarlar"][0], "bayrak": r["bayrak"]})
    o.update({"metin": k.metin, "metin_var": bool(k.metin), "kisaltma_var": "…" in k.paragraflar, "es": k.es,
              "tekrar_sira": ts, "tekrar_sayisi": tn, "tekrar_konular": tk, "dosya": k.dosya, "satir": k.satir,
              "atif": d["atif"], "paylasim": d["paylasim"]})
    assert list(o) == SEMA_ANAHTARLARI
    return o


def json_satir(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def kararlar_tsv(M, tekrar):
    d = M.d
    out = ["\t".join(TSV_KARAR)]
    for k in M.kayitlar:
        r = k.k
        if "\t" in k.kunye or "\n" in k.kunye:
            raise YapiHatasi(f"{d['kod']}: künyede sekme ya da satır sonu")
        ts = tekrar.get((d["kod"], k.konum), (0, 0, []))[0]
        for j, a in enumerate(r["anahtarlar"]):
            karar = r["kararlar"][j] if r["kararlar"] else ""
            out.append("\t".join([
                str(k.sira), k.id, k.kunye, a, r["tur"], r["mahkeme"], r["daire"], r["esas"], karar, r["tarih"],
                str(r["yil"]) if r["yil"] else "", "1" if k.metin else "0", str(len(k.metin.encode("utf-8"))),
                k.es, str(ts), k.dosya, str(k.satir)]))
    return "\n".join(out) + "\n"


def gz(veri):
    b = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=b, compresslevel=9, mtime=0) as g:
        g.write(veri)
    return b.getvalue()


# ----------------------------------------------------------------------------- kılavuz metinleri

RESMI = ("karararama.yargitay.gov.tr, emsal.uyap.gov.tr, karararama.danistay.gov.tr, "
         "kararlarbilgibankasi.anayasa.gov.tr, mevzuat.gov.tr")
SON_CUMLE = (f"Bu metinler Av. Hakan Dimdik'in derlemelerinden seçme alıntılardır; kararın tam metnini ve "
             f"güncelliğini resmî kaynaktan doğrulayın ({RESMI}). Hukuki görüş değildir.")


def hukuki_dogruluk(S):
    return f"""- Metinler derleyenin seçtiği ALINTILARDIR, kararın tamamı değildir. Tek başına `…` satırı atlanmış metni, metin içindeki `...` gizlenmiş adı gösterir.
- Künyelerin çoğunda esas numarası ve tarih yoktur (yalnız %{S['esas_yuzde']}'inde E. vardır). Olmayan esas numarasını, tarihi, daireyi eklemeyin, künyeyi düzeltmeyin; bu depoda bulamadığınız bir kararı bu depoya dayandırmayın.
- Alıntıdan kararın sonucu (onama, bozma) çıkmıyorsa sonucu bilmediğinizi söyleyin.
- Altında metin olmayan künyeye ({binlik(S['metinsiz'])} tane) kaynak metin koymamıştır; çoğu art arda sıralanmış seri karardır, hangi komşu alıntıyı paylaştıkları yazmaz. Önceki ya da sonraki metni onlara mal etmeyin.
- Aynı alıntı birden çok konuda, aynı paragraf birçok künyenin altında tekrar eder (kayıtların yaklaşık %{S['tekrar_yuzde']}'i). Künye sayısı bağımsız karar sayısı değildir; `es` değeri aynı olanları bir kez sayın.
- Konu başlıkları derleyenin tasnifidir, mahkemenin cümlesi değildir.
- Merciin düzeyini her zaman belirtin (İBK, HGK, daire, BAM, ilk derece, yabancı/hakem). Çelişen alıntılar varsa ikisini de gösterin, yeni tarihliyi belirtin.
- Kararın güncelliği (içtihat ya da kanun değişikliği, sonraki İBK) bu depodan anlaşılamaz; bunu açıkça söyleyin. `ESKİ SÜRÜM` işaretli derlemeyi yalnız kullanıcı isterse kullanın.
- Bulamazsanız "derlemelerde bulamadım" deyin; genel bilgi veriyorsanız derleme dışı olduğunu ayırın.
- Her hukuki yanıtın sonuna şunu ekleyin: "{SON_CUMLE}"
"""


def agents_md(S):
    # 2. adımdaki `cut -f1,3,5,7,8` ve sütun adları dizin şemasıyla birlikte değişmeli
    assert [TSV_KONU[i - 1] for i in (1, 3, 4, 5, 7, 8)] == ["kod", "bolum", "yol", "baslik", "karar", "dosya"]
    return f"""# Karar Derlemeleri: yapay zekâ araçları için kılavuz

## Bu depo nedir
Av. Hakan Dimdik'in (x.com/hakandimdik) hazırlayıp X'te paylaştığı {S['derleme']} emsal karar derlemesinin Markdown çevirisi: {binlik(S['sayfa'])} sayfa, yaklaşık {S['bin']} bin karar alıntısı. Kararların seçimi, konulara göre tasnifi ve başlıklar derleyenin emeğidir; bu depo yalnız biçim dönüştürür. İndirme tarihi {S['tarih_tr']}'dır; sonraki kararlar ve mevzuat değişiklikleri burada yoktur.

## Yerleşim
- `dizin/derlemeler.md`: {S['derleme']} derleme, hukuk alanına göre, ana bölümleriyle. İlk okunacak dosya.
- `md/<kod>/00-icindekiler.md`: bir derlemenin konu başlıkları, karar ve dosya sayılarıyla.{S['iki_duzey']}
- `md/<kod>/<NN-konu>/…/<kod>.<bölüm>.<NNN>.md`: metin. Her dosya tek konudur, en çok {S['kb']} KB'tır, tek seferde okunur. `#` konu başlığı, `##` karar künyesi; künyenin altındaki paragraflar o karardan alıntıdır. Uzun paragraf birkaç satıra bölünmüş olabilir; paragraf sınırı boş satırdır.
- `dizin/konular.tsv`: bütün konu başlıkları. `ara` sütunu küçük harfli, Türkçe harfleri sadeleştirilmiş konu yoludur; boş başlıkta `yol` boştur.
- `dizin/kararlar/<kod>.tsv`: her künye numarası için bir satır (mahkeme, daire, karar no, yıl, dosya, satır). `anahtar` sütunu `<tür>|<birim>|k<karar no>` biçimindedir (birim: `3hd`, `hgk`, `ibk`, `istanbul-bam-12hd`).
- `veri/kararlar/<kod>.jsonl.gz`: aynı içerik kayıt kayıt (RAG ve analiz için). Önce `veri/README.md` dosyasını okuyun; kararları ayıklamak için `md/` altını ayrıştırmayın.
- `araclar/ara.py`: Türkçe harfe duyarsız, tekrarları birleştiren arama.

## En az belirteçle nasıl bulunur
1. Konu belliyse: `dizin/derlemeler.md` → ilgili `00-icindekiler.md` → dosya. Üç{S['dort_okuma']} okuma yeter.
2. Kavram araması: `python3 araclar/ara.py "icra inkar tazminati" likit`. Seçenekler: `-b` yalnız künye ve konu başlığında, `-c` yalnız sayılar, `-d kira` derleme, `-m hgk` merci, `-y 2020-` yıl, `-h` hepsi. Başlıklarda: `rg -i 'gorevli mahkeme' dizin/konular.tsv | cut -f1,3,5,7,8` (kod, bölüm, başlık, karar, dosya sayısı; 4. sütun yol).
3. Künye araması: `rg -w '{S['ornek_anahtar_rg']}' dizin/kararlar/`; yalnız numarayla `rg -w '{S['ornek_anahtar']}' dizin/kararlar/` (`-w` şart) ya da `python3 araclar/ara.py -b "HGK 2021/164 K."`. Satırdaki `dosya` ve `satir` ile yalnız o kararı okuyun.
4. Ham `rg`: `rg -i` Türkçe harfleri eşlemez. `[iİıI]`, `[aâ]`, `['’]` sınıflarını yazın; önce `rg -c` ile sayın; çıktıyı `rg -o '.{{0,150}}DESEN.{{0,150}}' -m 5` ile sınırlayın.
5. Bir dosyadaki kararlar: `rg -n '^## ' <dosya>`.
6. `dizin/*.tsv` dosyalarını baştan sona okumayın, yalnız aratın. Bir konuda çok dosya varsa hepsini açmadan önce aramayla daraltın; kaç dosyadan kaçını okuduğunuzu söyleyin.
7. Kabuk yoksa (web'den okuma): `dizin/derlemeler.md` → `md/<kod>/00-icindekiler.md` → oradaki bağlantı; dosyalar `sonraki` alanıyla birbirine bağlıdır. Dosya yükleyen ürünler için ciltler `python3 araclar/cilt.py <kod>` ile üretilir; oradaki `[kod:no]` derleme içi sıra numarasıdır, künye değildir.

## Nasıl atıf yapılır
`<künye, dosyada yazdığı gibi> — Av. Hakan Dimdik, "<derleme adı>" (<sürüm>), <konu yolu>; <dosya yolu>`
Örnek: `{S['ornek_atif']}`
Sürüm yoksa parantez yazılmaz. Konu yolu tam yazılabilir ya da numaralarla kısaltılabilir ({S['ornek_kisa_yol']}); dosya yolu tam yazılır.
Alıntıyı tırnak içinde, kelimesi kelimesine verin; özetliyorsanız özet olduğunu söyleyin. Dosya yolu ve sıra numarası sürüme özgüdür, kalıcı kimlik değildir. Derleyenin adı her zaman anılır.

## Hukuki doğruluk (zorunlu)
{hukuki_dogruluk(S)}
## Atıf ve haklar
Bu depoda yayımlanmak üzere derlemelerin Markdown ve yapılandırılmış veri biçimlerine dönüştürülmesi ve paylaşılması için Av. Hakan Dimdik'ten izin alınmıştır. Derlemeler üzerindeki haklar derleyene aittir; bu depo içerik üzerinde hak iddia etmez. Türetilen her çıktıda kaynak gösterin: Av. Hakan Dimdik, "<derlemenin adı>", X (@hakandimdik), {SURUM_TARIHI[:4]}.

## Depoyu değiştirirken
`md/`, `dizin/` ve `veri/` üretilmiş dosyalardır; elle düzenlemeyin. `derlemeler.tsv`, `cevir.sh` veya `yapi.py` dosyasını değiştirip `python3 yapi.py && python3 yapi.py --dogrula` çalıştırın. Künye ve alıntı metnine dokunmayın: yazım hatası düzeltmek, esas numarası eklemek, tekrarları silmek yasaktır. Depoya gömme (embedding), dizin veritabanı, yapay zekâ üretimi özet eklemeyin.
"""


def talimat_txt():
    return f"""Bu kaynaklar Av. Hakan Dimdik'in (x.com/hakandimdik) emsal karar derlemeleridir. Yanıt verirken:

1. Künyeyi (ör. Yargıtay 3. HD 2018/6854 K.) dosyada yazdığı gibi aktar. Olmayan esas numarasını, tarihi, daireyi ekleme; künyeyi düzeltme.
2. Metinler derleyenin seçtiği alıntılardır, kararın tamamı değildir. Alıntıyı tırnak içinde, kelimesi kelimesine ver; özetliyorsan özet olduğunu söyle.
3. Tek başına "…" satırı atlanmış metni, metin içindeki "..." gizlenmiş adı gösterir.
4. Altında metin olmayan künyeye kaynak metin koymamıştır (çoğu art arda sıralanmış seri karardır; hangi komşu alıntıyı paylaştığı yazmaz). Onu alıntısız an; önceki ya da sonraki metni ona mal etme.
5. Aynı paragraf birçok künyenin altında tekrar edebilir; künye sayısı bağımsız karar sayısı değildir.
6. Her atıfta derleyeni ve derlemeyi an: Av. Hakan Dimdik, "<derleme adı>", konu başlığı.
7. Kaynaklarda yoksa "derlemelerde bulamadım" de; genel bilgiyle doldurma.
8. Her yanıtın sonuna ekle: "{SON_CUMLE}"
"""


def llms_txt():
    ham = f"https://raw.githubusercontent.com/{DEPO}/main"
    return f"""# Karar Derlemeleri

> Av. Hakan Dimdik'in derleyip X'te paylaştığı emsal karar derlemelerinin Markdown çevirisi; metinler derleyenin seçtiği alıntılardır, kararın tamamı değildir, kullanmadan önce resmî kaynaktan doğrulayın. Markdown conversion of Turkish case-law compilations by attorney Hakan Dimdik: selected excerpts, not full decisions; verify every decision in the official sources before relying on it.

## Önce okunacaklar

- [Yapay zekâ araçları için kılavuz]({ham}/AGENTS.md)
- [Derleme ve konu dizini]({ham}/dizin/derlemeler.md)
- [Bütün konu başlıkları (TSV)]({ham}/dizin/konular.tsv)
- [Veri kümesi kılavuzu]({ham}/veri/README.md)
- [Veri kümesi bildirimi]({ham}/veri/manifest.json)

## Derleme dizinleri

- Ham metin: `{ham}/md/<kod>/00-icindekiler.md`
- İşlenmiş sayfa (göreli bağlantılar mutlak olur): `https://github.com/{DEPO}/blob/main/md/<kod>/00-icindekiler.md`
"""


def veri_readme(S, D, ist):
    taban = f"https://raw.githubusercontent.com/{DEPO}/v{SURUM}/veri/"
    alan = [
        ("id", "str", "`<kod>:<16 hex>`; kod + künye + metnin özeti. Künye ve metin değişmedikçe sürümler arasında sabittir. Aynı (künye, metin) çifti yinelenirse `-2`, `-3` eklenir."),
        ("kod", "str", "Derlemenin sürümsüz kısa kodu (`kira`, `itiraz`)."),
        ("derleme", "str", "Derlemenin tam adı."),
        ("surum", "str|null", "Derleyenin sürüm adı (`V7`, `Cilt 2`) ya da null."),
        ("alan", "str", "Hukuk alanı (7 gruptan biri)."),
        ("bolum", "str", "Konu ağacındaki yer (`01-03`). Sürüme özgüdür."),
        ("konu", "[str]", "Kökten yaprağa konu başlıkları, derleyenin yazdığı gibi."),
        ("konu_yolu", "str", "`konu` alanının ` > ` ile birleştirilmişi."),
        ("sira", "int", "Derleme içinde 1'den başlayan karar sırası (belge sırası). `konu-notu` kaydı karar değildir, sırası 0'dır. Sürüme özgüdür."),
        ("tur", "str", "`yargitay`, `bam`, `danistay`, `aym`, `uyusmazlik`, `ilk-derece`, `yabanci`, `konu-notu`."),
        ("kunye", "str|null", "Başlık, kaynakta yazdığı gibi. Hiç değiştirilmez. Konu notunda null."),
        ("mahkeme", "str|null", "`Yargıtay`, `<Şehir> BAM`, `Danıştay`, `AYM`, `Uyuşmazlık Mahkemesi`, ilk derece mahkemesinin adı; yabancı kararlarda parantez dışındaki ilk virgüle kadarki metin."),
        ("daire", "str|null", "`3. HD`, `HGK`, `İBK`, `13. D.`, `İDDK`, `Birinci Bölüm` vb.; künyede yoksa null."),
        ("esas", "str|null", "Künyede yazıyorsa esas numarası."),
        ("karar", "str|null", "İlk karar numarası. Yılı yazılmamışsa `?/N`."),
        ("kararlar", "[str]", "Künyedeki bütün karar numaraları."),
        ("basvuru", "str|null", "AYM bireysel başvuru numarası."),
        ("tarih", "str|null", "Künyede yazıyorsa karar tarihi (ISO)."),
        ("yil", "int|null", f"Tarihin, yoksa karar, başvuru ya da esas numarasının yılı. Yaklaşıktır. {YIL_ALT}'den küçük ya da sürüm yılından büyük çıkarsa (yazım hatası) null olur ve `yil_supheli` bayrağı konur."),
        ("not", "str|null", "Künyenin sonundaki parantez içi derleyen notu."),
        ("anahtar", "str|null", "ASCII arama anahtarı: `<tur>|<birim>|<no>`, ör. `yargitay|3hd|k2018/6854`."),
        ("bayrak", "[str]", "Ayrıştırma uyarıları: `cok_karar`, `k_eki_yok`, `yil_yok`, `karar_no_yok`, `dipnot`, `yazim`, `mahkeme_cikarim`, `yil_supheli`."),
        ("metin", "str", "Alıntı. Paragraflar `\\n\\n` ile ayrılır; Markdown işaretleri (`**kalın**`) korunur; `### …` ile başlayan paragraf FIDIC'teki özgün metin/çeviri ara başlığıdır. Metinsiz künyede boş dizgi."),
        ("metin_var", "bool", "Metin boş değilse true."),
        ("kisaltma_var", "bool", "Yalnız `…` olan bir paragraf (atlanmış metin) varsa true."),
        ("es", "str", "Metnin özeti (boşlukları sadeleştirilmiş metnin SHA-1'inin ilk 16 hanesi); metinsizde boş."),
        ("tekrar_sira", "int", "Aynı `es` değerini taşıyan kayıtlar içinde 0'dan başlayan sıra (derleme sırası, sonra karar sırası)."),
        ("tekrar_sayisi", "int", "Aynı metni taşıyan kayıt sayısı; metinsizde 0."),
        ("tekrar_konular", "[str]", "Aynı metnin geçtiği `<kod>/<bolum>` değerleri."),
        ("dosya", "str", "Depodaki parça dosyasının yolu. Sürüme özgüdür."),
        ("satir", "int", "O dosyada `## künye` satırının numarası. Sürüme özgüdür."),
        ("atif", "str", "Önerilen atıf metni."),
        ("paylasim", "str", "Derlemenin paylaşıldığı gönderi."),
    ]
    assert [a[0] for a in alan] == SEMA_ANAHTARLARI
    tablo = "\n".join(f"| `{a}` | {t} | {c} |" for a, t, c in alan)
    # yükleme parçaları alan tablosundan üretilir (şema değişirse birlikte değişir)
    kisa = {"str": "S", "str|null": "S", "int": "I", "int|null": "I", "bool": "B", "[str]": "L"}
    ogeler = [f'"{a}": {kisa[t]}' for a, t, _ in alan]
    f_sat, sat = [], "    "
    for o in ogeler:
        if len(sat) + len(o) + 2 > 100:
            f_sat.append(sat.rstrip())
            sat = "    "
        sat += o + ", "
    f_sat.append(sat.rstrip())
    features = "\n".join(f_sat)
    pd_dtype = ", ".join(f'"{a}": "{"string" if t == "str|null" else "Int64"}"'
                         for a, t, _ in alan if t in ("str|null", "int|null"))
    return f"""# Karar Derlemeleri: kayıt veri kümesi

**English abstract.** {ist['kayit']:,} records from {S['derleme']} Turkish case-law compilations prepared and shared by attorney Hakan Dimdik (x.com/hakandimdik): one JSON object per cited decision (court heading as written, parsed court / chamber / decision number where present, topic path, and the excerpt chosen by the compiler). The texts are selected excerpts, not full decisions; most headings carry no docket number or date. Publication in this repository is with the compiler's permission. Rights in the compilations belong to the compiler; attribution is required. Verify every decision in the official sources before relying on it.

## Toplamlar

Sürüm `{SURUM}`, şema `{SEMA}`. {S['derleme']} derleme · {binlik(ist['kayit'])} kayıt ({binlik(ist['karar'])} karar künyesi, {binlik(ist['konu_notu'])} konu notu) · metinli {binlik(ist['metinli'])} · farklı metin {binlik(ist['farkli'])} · metinsiz künye {binlik(ist['metinsiz'])}. Sıkıştırılmış toplam {mb(ist['gz_bayt'])} MB. Dosya başına sayılar ve SHA-256 özetleri `manifest.json` içindedir; `ornek.jsonl` biçimi görmek için küçük bir örnektir.

## Yükleme

Etiketli (değişmeyen) taban adres: `{taban}`

```python
import pandas as pd
taban = "{taban}"
# dtype verilmezse bir dosyada hep null olan metin sütunu ve null içeren yil sütunu float64 olur
tur = {{{pd_dtype}}}
df = pd.read_json(taban + "kararlar/kira.jsonl.gz", lines=True, compression="gzip", dtype=tur)
```

```python
import json, urllib.request
from datasets import Features, List, Value, load_dataset   # datasets >= 4; eskisinde List yerine Sequence
taban = "{taban}"
m = json.load(urllib.request.urlopen(taban + "manifest.json"))
# Şema açık verilmelidir: ilk satırlarda null olan sütunun türü kendiliğinden çıkarılamaz.
S, I, B, L = Value("string"), Value("int64"), Value("bool"), List(Value("string"))
features = Features({{
{features}
}})
ds = load_dataset("json", data_files=[taban + x["dosya"] for x in m["derlemeler"]], features=features,
                  split="train")
```

```sql
-- duckdb
INSTALL httpfs; LOAD httpfs;
SELECT kunye, konu_yolu FROM read_json_auto('{taban}kararlar/kira.jsonl.gz') WHERE yil >= 2024 LIMIT 10;
```

## Alanlar

Her satır bir JSON nesnesidir; anahtarlar bu sıradadır. Bir anahtarın adı ya da türü değişirse `sema` artar.

| Alan | Tür | Açıklama |
|---|---|---|
{tablo}

## Önerilen süzgeç

`tur != 'konu-notu' and metin_var and tekrar_sira == 0` → {binlik(ist['suzgec'])} satır: her farklı alıntı bir kez. Aynı metin başka künyelerin ya da konuların altında da geçiyorsa `tekrar_sayisi` ve `tekrar_konular` bunu gösterir; hiçbir kayıt silinmemiştir.

## Gömme (embedding) önerisi

- Gömülecek metin: `derleme + ' — ' + konu_yolu + '\\n' + kunye + '\\n' + metin`.
- Kayıtlar doğal parçalardır: metin ortancası {S['ortanca_kb']} KB, %99'u {S['p99_kb']} KB'ın altındadır, en büyüğü {S['enbuyuk_kb']} KB'tır.
- 512 belirteçlik modellerde `\\n\\n` üzerinden bölün ve bağlam satırını (derleme, konu yolu, künye) her parçada yineleyin.
- Yalnız `…` olan paragrafları atmayın; derleyenin metin atladığını gösterir.

## Bilinen sınırlar

- Metinler seçme alıntıdır; kararın sonucu (onama, bozma) çoğu zaman alıntıdan anlaşılmaz.
- Esas numarası yazan künye oranı %{S['esas_yuzde']}, tarih yazan künye oranı %{S['tarih_yuzde']}; çoğunda ikisi de yoktur. `yil` çoğunlukla karar numarasından türetilir, yaklaşıktır.
- `mahkeme`, `daire`, `karar` gibi alanlar künyeden düzenli ifadeyle çıkarılmıştır; eksik olan tahmin edilmez, şüpheli durumlar `bayrak` alanındadır. Asıl olan `kunye` alanıdır.
- {binlik(ist['metinsiz'])} künyenin altında metin yoktur (`metin_var` false); kaynak o künyenin altına metin koymamıştır. En çok {S['ms_ad']} derlemesindedir ({binlik(S['ms_sayi'])} künye); orada bunların {binlik(S['ms_seri'])} tanesi, art arda gelen 2 ile {S['ms_enuzun']} künyelik {binlik(S['ms_dizi'])} dizi hâlindedir (seri kararlar), yalnız {binlik(S['ms_tek'])} tanesi tek başınadır. Dizideki kararların hangi komşu alıntıyı paylaştığını kaynak söylemez; bu yüzden hiçbir metin kopyalanmamış, hiçbir grup çıkarılmamıştır. Önceki ya da sonraki kaydın metnini onlara mal etmeyin.
- `konu-notu` türündeki kayıt karar değildir: bir konu başlığı ile ilk künye arasındaki metindir, `sira` değeri 0'dır, `kunye` null'dır. Bu sürümde {binlik(ist['konu_notu'])} tane vardır.
- Sıra: bir derlemenin belge sırası `sira` alanıdır (JSONL satırları da bu sıradadır). Dosya yolundan sıralarken bir başlığın kendi dosyaları alt dizinlerinden önce gelir; düz alfabetik yol sıralaması bu sırayı vermez.
- Metin Unicode NFC biçimine getirilmiştir (dönüştürücü çıktısındaki birkaç ayrık harf+işaret çifti birleşik harfe çevrilir); bunun dışında künye ve metin kaynaktaki gibidir.{S['yama_cumle']}
- Kayıtların yaklaşık %{S['tekrar_yuzde']}'i başka bir kayıtla aynı metni taşır; künye sayısı bağımsız karar sayısı değildir.
- Paragraf sınırları PDF dönüştürmesinden gelir, sezgiseldir. PDF sayfa numarası tutulmaz.
- `ESKİ SÜRÜM` durumundaki derleme (`arsa-payi-ilk`) güncel hâliyle (`arsa-payi`) örtüşür.

## Hukuki doğruluk (sistem istemine yapıştırmak için)

{hukuki_dogruluk(S)}
## Atıf ve haklar

Bu derlemelerden yararlanırken kaynak olarak Av. Hakan Dimdik'i gösterin. Bu depoda yayımlanmak üzere derlemelerin Markdown ve yapılandırılmış veri biçimlerine dönüştürülmesi ve paylaşılması için Av. Hakan Dimdik'ten izin alınmıştır. Derlemeler üzerindeki haklar derleyene aittir; bu depo içerik üzerinde hak iddia etmez. Derleyenin talebi hâlinde içerik kaldırılır. Önerilen atıf biçimi her kaydın `atif` alanındadır: *Av. Hakan Dimdik, "<derlemenin adı>", X (@hakandimdik), {SURUM_TARIHI[:4]}.*

## Sürüm ve etiket

Her yeniden üretim `vYYYY.AA.GG` biçiminde etiketlenir; etiket `manifest.json` içindeki `surum` ile aynıdır. Yukarıdaki adresler etikete sabitlenmiştir. `id`, künye ve metin değişmedikçe sürümler arasında aynı kalır (kod sürüm numarası taşımaz). `sira`, `bolum`, `dosya` ve `satir` sürüme özgüdür; kalıcı kimlik olarak kullanmayın.
"""


README_UST = """# Karar Derlemeleri (Markdown)

**Derleyen: Av. Hakan Dimdik** ([@hakandimdik](https://x.com/hakandimdik))

Bu depodaki emsal karar derlemelerinin tamamını Av. Hakan Dimdik hazırlamış ve X hesabında herkesin yararlanması için paylaşmıştır. Kararların seçimi, konulara göre tasnifi ve başlıklandırılması onun emeğidir. Bu depo yalnızca biçim dönüştürür: PDF'leri, başlık hiyerarşisini koruyarak Markdown'a çevirir; arama, not alma (Obsidian) ve yapay zekâ araçlarına yükleme kolaylaşsın diye.

**{derleme} derleme · {sayfa} sayfa · yaklaşık {bin} bin karar künyesi.** İndirme ve dönüştürme tarihi: {tarih_tr}.

> **Atıf.** Bu derlemelerden yararlanırken kaynak olarak Av. Hakan Dimdik'i gösterin. Her derlemenin altında özgün PDF'in ve paylaşıldığı gönderinin bağlantısı vardır; güncel sürümler için özgün paylaşımlara bakın. Bu depoda yayımlanmak üzere derlemelerin Markdown ve yapılandırılmış veri biçimlerine dönüştürülmesi ve paylaşılması için Av. Hakan Dimdik'ten izin alınmıştır. Derlemeler üzerindeki haklar derleyene aittir; bu depo içerik üzerinde hak iddia etmez. Derleyenin talebi hâlinde içerik kaldırılır.
"""

README_DOGRULAMA = """## Dönüştürme ve doğrulama

Dönüştürme [pdf-md](https://github.com/hasanimer/pdf-md-skill) betiğiyle yapıldı. Her çıktı, PDF'ten ikinci bir motorla (`pdftotext`) çıkarılan metinle boşluklar atılarak karakter karakter karşılaştırıldı: {tam} derleme tam eşleşti.

- Kapak ve içindekiler sayfaları atlandı (ilk yer imine kadar), `Sayfa N / M` altbilgileri atıldı, karar künyelerinin sonundaki `:` silindi.
- *Arsa Payı Karşılığı İnşaat ve Kentsel Dönüşüm* derlemesindeki 3 fark kayıp değildir: başka yazı tipiyle basılmış `₺` ve `III` parçalarını başvuru metni satır sonuna atıyor, Markdown doğru yerde tutuyor.
- Yer imi sayısı ile başlık sayısı, Kira Hukuku V7 dışındaki tüm derlemelerde birebir tutuyor.
- `yapi.py` dönüştürücü çıktısını konu başlıklarına göre parçalara böler; `python3 yapi.py --dogrula` parça dosyalarından yeniden kurulan başlık dizisini ve boşluksuz metni dönüştürücü çıktısıyla karşılaştırır, dizinlerle veri kümesinin tutarlılığını ve üretimin yinelenebilirliğini denetler (`log/yapi.log`).

Her dosyanın yoklama, dönüştürme ve doğrulama çıktısı `log/<ad>.log` içindedir.

## Bilinen sınırlar

- Paragraf sınırları sezgiseldir; doğrulama yalnız metnin eksiksizliğini ölçer.
- *Kira Hukuku V7*'de s. 1061 ve s. 4301 çevresinde 12 punto kalın olmayan bir bölüm var. Gövde metni başlık sanılmasın diye bu stil başlık sayılmadı.{yama}
- Metin Unicode NFC biçimine getirilir (dönüştürücü çıktısındaki birkaç ayrık harf+işaret çifti birleşik harf olur); doğrulama da NFC'den sonra karşılaştırır. Kaynaktaki küçük kusurlar olduğu gibi kalır (ör. Boşanma derlemesinde `#` ile başlayan iki gövde satırı).
- Başlıklar biçimine göre sınıflanır (konu, karar künyesi, FIDIC'te özgün metin/çeviri ara başlığı). {govde}Sınıflayıcının kararsız kaldığı başlıklar `log/<ad>.log` içinde `=== yapi basliklar` altındadır; düzeltme `ek/<ad>.basliklar.tsv` (başlığın sınıfı) ya da `ek/<ad>.satirlar.tsv` (kaynak satırının kendisi) ile yapılır.
- Künyelerin yalnız %{esas_yuzde}'inde esas numarası vardır; {metinsiz} künyenin altında metin yoktur (çoğu art arda sıralanmış seri kararlardır; hangi komşu alıntıyı paylaştıklarını kaynak söylemez, metin kopyalanmamıştır). Kayıtların yaklaşık %{tekrar_yuzde}'i başka bir kayıtla aynı alıntıyı taşır; künye sayısı bağımsız karar sayısı değildir.
- Alınmayanlar: eski sürümler (Kira V2–V6, Tahkim V1), karar derlemesi olmayan paylaşımlar (dilekçe örnekleri, sunumlar, bilgi notları) ve Tasarrufun İptali derlemesi.
- X araması eksiksiz olmayabilir; Google Drive dışında bir bağlantıyla paylaşılmış derleme varsa burada yoktur.

## Atıf ve teşekkür

Derlemeleri hazırlayan ve bu depoda yayımlanmasına izin veren Av. Hakan Dimdik'e teşekkür ederiz.

- **Derlemeler:** Av. Hakan Dimdik — [x.com/hakandimdik](https://x.com/hakandimdik). `kaynaklar.tsv` her derlemenin paylaşıldığı gönderiyi, `indir.tsv` özgün PDF'in Drive kimliğini tutar.
- **Kira Hukuku derlemesi:** derleyenin belirttiği üzere Av. Yankı Büyüksezer'in paylaştığı kararlara da yer verilmiştir.
- **Dönüştürme:** [pdf-md](https://github.com/hasanimer/pdf-md-skill).

Önerilen atıf biçimi: *Av. Hakan Dimdik, "<derlemenin adı>", X (@hakandimdik), 2026.*

## Yeniden üretme

Özgün PDF'ler depoda tutulmaz (`pdf/` yok sayılır); `indir.tsv` içindeki Drive kimliklerinden yeniden indirilir.

```bash
./indir.sh
ls pdf/*.pdf | xargs -P 4 -n 1 ./cevir.sh
python3 yapi.py && python3 yapi.py --dogrula
python3 araclar/cilt.py            # isteğe bağlı: yükleme ciltleri (yukle/)
```

`cevir.sh` betiği `~/.claude/skills/pdf-md/scripts/pdf2md.py` yolunda arar; başka yerdeyse `PDF2MD` değişkeniyle verin; çıktıyı `ara/<ad>/` altına yazar (depoda tutulmaz). Dosyaya özel seçenekler `ek/<ad>.args` içindedir. `derlemeler.tsv` derlemelerin kayıt defteridir (kod, ad, başlık, alan, sürüm, sıra); `yapi.py` (yalnız Python standart kitaplığı) `md/`, `dizin/`, `veri/` ile `AGENTS.md`, `llms.txt`, `TALIMAT.txt` ve bu dosyayı baştan üretir. `kaynaklar.tsv` her derlemenin paylaşım bağlantısını ve gönderi kimliğini tutar.
"""


def readme_md(S, D, ist, modeller):
    ust = README_UST.format(derleme=S["derleme"], sayfa=binlik(S["sayfa"]), bin=S["bin"],
                            tarih_tr=S["tarih_tr"])
    out = [ust,
           "**Yapay zekâ araçları:** önce [AGENTS.md](AGENTS.md) dosyasını okuyun; konu dizini: "
           "[dizin/derlemeler.md](dizin/derlemeler.md).\n",
           f"""## Nasıl kullanılır

| Ne | Nerede | Kime |
|---|---|---|
| Okuma ve arama | `md/<kod>/`: konu başlığına göre klasörler, en çok {S['kb']} KB'lık dosyalar; her derlemenin dizini `00-icindekiler.md`, hepsinin dizini [dizin/derlemeler.md](dizin/derlemeler.md) | GitHub'da ya da klonda okuyanlar, Obsidian, kod yardımcıları |
| Yükleme dosyaları | `python3 araclar/cilt.py <kod>` ile `yukle/<kod>/` altında üretilen, en çok 3 MB'lık ciltler; yanında [TALIMAT.txt](TALIMAT.txt) ve [dizin/konular.tsv](dizin/konular.tsv) | NotebookLM, ChatGPT, Claude Projects gibi dosya yüklenen ürünler |
| Veri | `veri/kararlar/<kod>.jsonl.gz`: karar başına bir kayıt; [veri/README.md](veri/README.md) | Geliştiriciler (RAG, analiz) |

Dosya yüklenen ürünlerde (NotebookLM, ChatGPT, Claude Projects) üç adım:

1. Depoyu indirin, `python3 araclar/cilt.py kira` çalıştırın (kod, aşağıdaki tabloların "dizin" sütunundadır). Ciltler `yukle/kira/` altına yazılır; depoda tutulmaz.
2. Ciltleri ve `dizin/konular.tsv` dosyasını ürüne kaynak olarak yükleyin. Ürünlerin dosya boyutu ve sayısı sınırları değişir; yüklemeden önce ürünün güncel sınırına bakın, cilt sığmıyorsa `md/<kod>/` altındaki küçük dosyaları kullanın.
3. `TALIMAT.txt` içeriğini ürünün talimat kutusuna (Claude Projects'te proje talimatı, ChatGPT'de özel GPT ya da proje talimatı) yapıştırın; talimat kutusu yoksa (NotebookLM) dosyayı kaynak olarak ekleyin ve ilk iletide ona uyulmasını isteyin.

Kabuk erişimi olan yardımcılar için: `python3 araclar/ara.py "icra inkar tazminati"` Türkçe harfe duyarsız arar ve tekrar eden alıntıları birleştirir.

Dosyalarda `#` konu başlığı, `##` karar künyesidir (ör. `Yargıtay HGK 2021/164 K.`); künyenin altındaki paragraflar o karardan alıntıdır.
"""]
    alanlar = []
    for d in D:
        if d["alan"] not in alanlar:
            alanlar.append(d["alan"])
    for a in alanlar:
        out.append(f"## {a}\n\n| Derleme | Sayfa | Karar | MB | Dizin | Özgün PDF | Paylaşım |\n|---|--:|--:|--:|---|---|---|")
        for d in D:
            if d["alan"] != a:
                continue
            m = modeller[d["kod"]]
            ad = d["tam_ad"]
            if d["durum"] == "eski-surum":
                ad += f" — ESKİ SÜRÜM (güncel hâli: `{d['yerine']}`)"
            out[-1] += (f"\n| {ad} | {binlik(m['sayfa'])} | {binlik(m['karar'])} | {mb(m['bayt'])} | "
                        f"[{d['kod']}](md/{d['kod']}/00-icindekiler.md) | [PDF]({d['kaynak_pdf']}) | "
                        f"[gönderi]({d['paylasim']}) |")
        out[-1] += "\n"
    govde = ""
    if ist["govde"]:
        govde = (f"Künye biçiminde olmayan {ist['govde']} başlık satırı (Kira Hukuku V7'de başlık stiliyle yazılmış "
                 f"gövde cümleleri) düz paragraf olarak yazıldı. ")
    out.append(README_DOGRULAMA.format(tam=ist["tam_eslesme"], govde=govde, yama=S["yama_readme"], esas_yuzde=S["esas_yuzde"],
                                       metinsiz=binlik(ist["metinsiz"]), tekrar_yuzde=S["tekrar_yuzde"]))
    return "\n".join(out)


# ----------------------------------------------------------------------------- dizin/derlemeler.md

def derlemeler_md(S, D, modeller, ist):
    out = ["# Karar Derlemeleri: derleme ve konu dizini",
           f"Derleyen: {DERLEYEN_FM}. {S['derleme']} derleme · {binlik(S['sayfa'])} sayfa · "
           f"{binlik(ist['karar'])} karar alıntısı · {binlik(ist['dosya'])} dosya.",
           f"Metinler derleyenin seçtiği alıntılardır, kararın tamamı değildir; künyelerin çoğunda esas numarası "
           f"ve tarih yoktur. Kullanmadan önce resmî kaynaktan doğrulayın. Kılavuz: [AGENTS.md](../AGENTS.md).",
           ""]
    alan = None
    i = 0
    while i < len(D):
        d = D[i]
        if d["alan"] != alan:
            alan = d["alan"]
            out += [f"## {alan}", ""]
        if d["seri"]:
            grup = [x for x in D if x["seri"] == d["seri"]]
            ad = d["kisa"][:-len(d["surum"])].strip() if d["surum"] and d["kisa"].endswith(d["surum"]) else d["kisa"]
            out.append(f"### {ad} ({len(grup)} cilt)")
            for x in grup:
                m = modeller[x["kod"]]
                ust = "; ".join(c["baslik"] for c in m["ust"])
                alt = sum(c["alt"] for c in m["ust"])
                out.append(f"- [{x['surum'] or x['kod']}](../md/{x['kod']}/00-icindekiler.md) {ust} — "
                           f"{binlik(m['sayfa'])} s. · {binlik(m['karar'])} karar · {m['dosya']} dosya · "
                           f"{mb(m['bayt'])} MB · {alt} alt başlık")
            out.append("")
            i += len(grup)
            continue
        m = modeller[d["kod"]]
        out.append(f"### {d['baslik']} — [md/{d['kod']}/](../md/{d['kod']}/00-icindekiler.md)")
        s = (f"{binlik(m['sayfa'])} s. · {binlik(m['karar'])} karar · {binlik(m['dosya'])} dosya · "
             f"{mb(m['bayt'])} MB · sürüm: {d['surum'] or '–'}")
        if d["durum"] == "eski-surum":
            s += f" · ESKİ SÜRÜM, güncel hâli: {d['yerine']}"
        out.append(s)
        for c in m["ust"]:
            out.append(f"- {c['no']} {c['baslik']} — {binlik(c['karar'])} karar")
        out.append("")
        i += 1
    return "\n".join(out).rstrip("\n") + "\n"


# ----------------------------------------------------------------------------- günlük

def gunluk_yaz(M, tekrar):
    """log/<ad>.log sonundaki '=== yapi' bölümlerini yeniler (varsa eskisini değiştirir)."""
    d = M.d
    yol = os.path.join(KOK, "log", d["ad"] + ".log")
    eski = ""
    if os.path.isfile(yol):
        with open(yol, encoding="utf-8") as f:
            eski = f.read()
    m = re.search(r"^=== yapi", eski, re.M)
    if m:
        eski = eski[:m.start()]
    if eski and not eski.endswith("\n"):
        eski += "\n"
    out = ["=== yapi satirlar",
           "# ek/<ad>.satirlar.tsv ile sınıflandırmadan önce değiştirilen kaynak satırları",
           "# satır\tkaynakta\tyerine"]
    out += [f"{no}\t{eski}\t{yeni}" for no, eski, yeni in M.yamalar] or ["(yok)"]
    out += ["=== yapi basliklar",
           "# kural 0 (ek/<ad>.basliklar.tsv), 6 (rakamsız BÜYÜK HARF -> KONU) ve 7 (hiçbir kalıba uymayan) kararları",
           "# satır\tdüzey\tsınıf\tkural\tmetin"]
    out += [f"{s}\t{L}\t{sinif}\t{kural}\t{t}" for s, L, sinif, kural, t in M.gunluk] or ["(yok)"]
    bay = collections.Counter(b for k in M.kayitlar for b in k.k["bayrak"])
    tur = collections.Counter(k.tur for k in M.kayitlar)
    tek = sum(1 for k in M.tum if tekrar.get((d["kod"], k.konum), (0,))[0] > 0)
    out += ["=== yapi",
            f"kod: {d['kod']}",
            f"KONU: {M.say['KONU']}  KUNYE: {M.say['KUNYE']}  ALT: {M.say['ALT']}  GOVDE: {M.say['GOVDE']}",
            f"metinsiz künye: {sum(1 for k in M.kayitlar if not k.metin)}  konu notu: "
            f"{sum(1 for k in M.tum if k.kunye is None)}  tekrar (tekrar_sira > 0): {tek}",
            f"dosya: {M.dosya_sayisi}  bayt: {M.bayt}  en büyük dosya: {max(M.boyutlar) if M.boyutlar else 0}",
            "tür: " + "  ".join(f"{k}={v}" for k, v in sorted(tur.items())),
            "bayrak: " + ("  ".join(f"{k}={v}" for k, v in sorted(bay.items())) or "(yok)")]
    with open(yol, "w", encoding="utf-8") as f:
        f.write(eski + "\n".join(out) + "\n")


# ----------------------------------------------------------------------------- üretim

def yuzde(a, b, basamak=0):
    v = 100.0 * a / b if b else 0.0
    return (f"{v:.{basamak}f}").replace(".", ",")


def uret(kok, sessiz=False):
    """Bütün çıktıları 'kok' altına yazar. kok == KOK ise günlükler de yenilenir."""
    asil = os.path.abspath(kok) == KOK
    D = defter_oku()

    def bilgi(*a):
        if not sessiz:
            print(*a, file=sys.stderr, flush=True)

    # 1. geçiş: metin özetleri (tekrar grupları bütün derlemeleri ister)
    gruplar = collections.defaultdict(list)
    for d in D:
        M = oku(d)
        for k in M.tum:
            if k.es:
                gruplar[k.es].append((d["sira"], k.konum, d["kod"], k.dugum.bolum))
    tekrar = {}
    farkli = len(gruplar)
    for es in gruplar:
        g = sorted(gruplar[es])
        konular = sorted({f"{x[2]}/{x[3]}" for x in g})
        for j, x in enumerate(g):
            tekrar[(x[2], x[1])] = (j, len(g), konular)
    del gruplar

    # Bedesten eşleşmeleri (veri/bedesten/) üretilmez, elle/araçla tutulur: silinmez, bağlantılar oradan okunur
    baglantilar = bedesten_bagla.baglantilari_oku(KOK)
    for alt in ("md", "dizin", "veri"):
        p = os.path.join(kok, alt)
        if not os.path.isdir(p):
            continue
        if alt == "veri":
            for x in os.listdir(p):
                if x != "bedesten":
                    q = os.path.join(p, x)
                    shutil.rmtree(q) if os.path.isdir(q) else os.remove(q)
        else:
            shutil.rmtree(p)
    os.makedirs(kok, exist_ok=True)

    modeller, manifest_d, konu_sat = {}, [], ["\t".join(TSV_KONU)]
    ist = collections.Counter()
    metin_boy = []
    ornek = {"bayrak": {}, "metinsiz": None, "alt": None, "not": None, "tahkim": []}
    ornek_kira = None
    enbuyuk_dosya = 0
    ms, yamalar, iki_duzey = {}, [], []
    for d in D:
        kod = d["kod"]
        M = oku(d)
        parcalari_yaz(M, kok, baglantilar)
        ic_dosyalar = icindekiler_yaz(M, kok)
        yaz(kok, f"dizin/kararlar/{kod}.tsv", kararlar_tsv(M, tekrar))
        satirlar = []
        for k in M.tum:
            o = kayit_nesnesi(k, d, tekrar)
            s = json_satir(o)
            satirlar.append(s)
            if kod == "tahkim" and len(ornek["tahkim"]) < 150:
                ornek["tahkim"].append((o["id"], s))
            for b in o["bayrak"]:
                ornek["bayrak"].setdefault(b, (o["id"], s))
            if k.kunye is None:
                if ornek["not"] is None:
                    ornek["not"] = (o["id"], s)
            else:
                if not k.metin and ornek["metinsiz"] is None:
                    ornek["metinsiz"] = (o["id"], s)
                if k.alt_var and d["yabanci_kunye"] and ornek["alt"] is None:
                    ornek["alt"] = (o["id"], s)
                if kod == "kira" and ornek_kira is None:
                    ornek_kira = (k, o)
            if k.metin:
                metin_boy.append(len(k.metin.encode("utf-8")))
                if o["tekrar_sira"] == 0 and k.kunye is not None:
                    ist["suzgec"] += 1
        g = gz(("\n".join(satirlar) + "\n").encode("utf-8"))
        yaz(kok, f"veri/kararlar/{kod}.jsonl.gz", g)
        manifest_d.append({"kod": kod, "baslik": d["baslik"], "surum": d["surum"] or None, "alan": d["alan"],
                           "sayfa": M.sayfa, "dosya": f"kararlar/{kod}.jsonl.gz", "bayt": len(g),
                           "sha256": hashlib.sha256(g).hexdigest(), "kayit": len(M.tum), "md": f"md/{kod}/"})
        for n in M.dugumler:
            ara = " > ".join(" ".join(re.sub(r"[^a-z0-9]+", " ", F(NUMARALAYICI.sub("", t))).split())
                             for t in n.konu)
            yol = n.yol if (n.dosyalar or n.cocuklar) else ""    # boş başlığın dizini yoktur
            konu_sat.append("\t".join([kod, str(n.derinlik), n.bolum, yol, n.baslik, ara, str(len(n.kayitlar)),
                                       str(len(n.dosyalar)), str(n.bayt), n.ust.bolum if n.ust.duzey else ""]))
        modeller[kod] = {"sayfa": M.sayfa, "karar": len(M.kayitlar), "dosya": M.dosya_sayisi, "bayt": M.bayt,
                         "ust": [{"no": c.no, "baslik": c.baslik, "karar": c.top_karar, "alt": len(c.cocuklar)}
                                 for c in M.kok.cocuklar]}
        ist["kayit"] += len(M.tum)
        ist["karar"] += len(M.kayitlar)
        ist["konu_notu"] += sum(1 for k in M.tum if k.kunye is None)
        ist["metinli"] += sum(1 for k in M.tum if k.metin)
        ist["metinsiz"] += sum(1 for k in M.kayitlar if not k.metin)
        ist["esasli"] += sum(1 for k in M.kayitlar if k.k["esas"])
        ist["tarihli"] += sum(1 for k in M.kayitlar if k.k["tarih"])
        ist["dosya"] += M.dosya_sayisi
        ist["sayfa"] += M.sayfa
        ist["gz_bayt"] += len(g)
        ist["md_bayt"] += M.bayt
        ist["konu"] += M.say["KONU"]
        ist["alt"] += M.say["ALT"]
        ist["govde"] += M.say["GOVDE"]
        ist["yabanci"] += sum(1 for k in M.kayitlar if k.tur == "yabanci")
        ist["tam_eslesme"] += d["dogrulama"] == "tam eşleşme"
        ist["yil_supheli"] += sum(1 for k in M.kayitlar if "yil_supheli" in k.k["bayrak"])
        diziler, uz = [], 0                 # art arda gelen metinsiz künye dizilerinin uzunlukları
        for k in M.kayitlar + [None]:
            if k is not None and not k.metin:
                uz += 1
            elif uz:
                diziler.append(uz)
                uz = 0
        ms[kod] = diziler
        if M.yamalar:
            yamalar.append((d, M.yamalar))
        if "00-icindekiler.md" != ",".join(ic_dosyalar):
            iki_duzey.append(kod)
        enbuyuk_dosya = max([enbuyuk_dosya] + M.boyutlar)
        if asil:
            gunluk_yaz(M, tekrar)
        bilgi(f"  {kod}: {len(M.kayitlar)} karar, {M.dosya_sayisi} dosya")
        del M
    ist["farkli"] = farkli
    ist["enbuyuk_dosya"] = enbuyuk_dosya

    metin_boy.sort()
    k0, o0 = ornek_kira if ornek_kira else (None, None)
    S = {"derleme": len(D), "sayfa": ist["sayfa"], "bin": round(ist["karar"] / 1000),
         "tarih_tr": ".".join(reversed(SURUM_TARIHI.split("-"))),
         "kb": max(48, -(-enbuyuk_dosya // 1000)),
         "esas_yuzde": yuzde(ist["esasli"], ist["karar"], 1), "tarih_yuzde": yuzde(ist["tarihli"], ist["karar"], 1),
         "tekrar_yuzde": yuzde(ist["metinli"] - ist["farkli"], ist["kayit"]),
         "ortanca_kb": f"{metin_boy[len(metin_boy) // 2] / 1000:.1f}".replace(".", ","),
         "p99_kb": f"{metin_boy[int(len(metin_boy) * 0.99)] / 1000:.1f}".replace(".", ","),
         "enbuyuk_kb": f"{metin_boy[-1] / 1000:.1f}".replace(".", ","),
         "ornek_anahtar": "k2018/6854", "ornek_anahtar_rg": "yargitay\\|3hd\\|k2018/6854", "ornek_atif": "",
         "ornek_kisa_yol": "§1 › I", "metinsiz": ist["metinsiz"]}
    # metinsiz künyeler: en çok hangi derlemede, kaçı dizi hâlinde
    ms_kod = max(D, key=lambda d: (sum(ms[d["kod"]]), -d["sira"]))
    dz = ms[ms_kod["kod"]]
    S.update({"ms_ad": "*" + ms_kod["kisa"] + "*", "ms_sayi": sum(dz), "ms_seri": sum(x for x in dz if x > 1),
              "ms_dizi": sum(1 for x in dz if x > 1), "ms_tek": sum(1 for x in dz if x == 1),
              "ms_enuzun": max(dz) if dz else 0})
    S["iki_duzey"] = S["dort_okuma"] = ""
    if iki_duzey:
        kimde = ", ".join(f"`{k}`" for k in iki_duzey)
        S["iki_duzey"] = (f" {kimde} dizini iki düzeydir; alt başlıklar `00-icindekiler-<NN>.md` "
                          f"dosyalarındadır.")
        S["dort_okuma"] = f" ({kimde} için dört)"
    S["yama_readme"] = S["yama_cumle"] = ""
    if yamalar:
        liste = "; ".join(f"`{e}` → `{y}`" for d, ym in yamalar for _, e, y in ym)
        dosyalar = ", ".join(f"`ek/{d['ad']}.satirlar.tsv`" for d, _ in yamalar)
        n = sum(len(ym) for _, ym in yamalar)
        S["yama_readme"] = (f" Bu yüzden düz satır olarak çıkan {n} kaynak satırı elle düzeltildi ({dosyalar}): "
                            f"{liste}. Başlığa çevrilen satırlar konu başlığı ya da karar künyesi olarak işlenir; "
                            f"künyede baştaki liste tiresi ve sondaki iki nokta atılmıştır. Düzeltmeler "
                            f"`log/<ad>.log` içinde `=== yapi satirlar` altında, `log/yapi.log` içinde de yazılıdır.")
        S["yama_cumle"] = (f" Tek istisna: dönüştürücünün düz satır olarak çıkardığı {n} başlık satırı elle "
                           f"düzeltilmiştir ({liste}).")
    if k0 is not None:
        n = k0.dugum
        kisa_yol = " › ".join((NUMARALAYICI.match(t).group(1).rstrip(".") if NUMARALAYICI.match(t) else t)
                              for t in n.konu)
        S["ornek_anahtar"] = o0["anahtar"].split("|")[-1]
        S["ornek_anahtar_rg"] = o0["anahtar"].replace("|", "\\|")
        S["ornek_kisa_yol"] = kisa_yol
        S["ornek_atif"] = (f'{k0.kunye} — {DERLEYEN}, "{k0_baslik(D)}" ({o0["surum"]}), {kisa_yol}; {k0.dosya}')

    yaz(kok, "dizin/konular.tsv", "\n".join(konu_sat) + "\n")
    yaz(kok, "dizin/derlemeler.md", derlemeler_md(S, D, modeller, ist))
    manifest = {"surum": SURUM, "sema": SEMA, "depo": DEPO, "derleyen": DERLEYEN, "haklar": HAKLAR, "uyari": UYARI,
                "toplam": {"derleme": len(D), "kayit": ist["kayit"], "metinli": ist["metinli"],
                           "farkli_metin": ist["farkli"]},
                "derlemeler": manifest_d}
    yaz(kok, "veri/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    secim, gorulen = [], set()
    ekler = ornek["tahkim"] + [ornek["bayrak"][b] for b in sorted(ornek["bayrak"])] + \
        [x for x in (ornek["metinsiz"], ornek["alt"], ornek["not"]) if x]
    for kimlik, s in ekler:
        if kimlik not in gorulen:
            gorulen.add(kimlik)
            secim.append(s)
    yaz(kok, "veri/ornek.jsonl", "\n".join(secim) + "\n")
    yaz(kok, "veri/README.md", veri_readme(S, D, ist))
    yaz(kok, "AGENTS.md", agents_md(S))
    yaz(kok, "CLAUDE.md", "@AGENTS.md\n")
    yaz(kok, "llms.txt", llms_txt())
    yaz(kok, "TALIMAT.txt", talimat_txt())
    yaz(kok, "README.md", readme_md(S, D, ist, modeller))
    yaz(kok, ".ignore", "log/\nveri/ornek.jsonl\n")
    yaz(kok, ".rgignore", "log/\nveri/ornek.jsonl\n")
    yaz(kok, ".gitattributes", "*.gz binary\n")
    return D, ist, S


def k0_baslik(D):
    return next(d["baslik"] for d in D if d["kod"] == "kira")


# ----------------------------------------------------------------------------- doğrulama

KOK_DOSYALARI = ["AGENTS.md", "CLAUDE.md", "llms.txt", "TALIMAT.txt", "README.md", ".ignore", ".rgignore",
                 ".gitattributes"]


def agac_ozeti(kok):
    """Üretilen bütün dosyaların sha256'sı: {göreli yol: özet}."""
    oz = {}
    for alt in ("md", "dizin", "veri"):
        for dp, dn, fn in os.walk(os.path.join(kok, alt)):
            dn.sort()
            for f in sorted(fn):
                p = os.path.join(dp, f)
                with open(p, "rb") as fh:
                    oz[os.path.relpath(p, kok)] = hashlib.sha256(fh.read()).hexdigest()
    for f in KOK_DOSYALARI:
        p = os.path.join(kok, f)
        if os.path.isfile(p):
            with open(p, "rb") as fh:
                oz[f] = hashlib.sha256(fh.read()).hexdigest()
    return oz


_BOSLUK = re.compile(r"\s+")


def kaynak_dizisi(M):
    """Dönüştürücü çıktısından: [(sınıf, başlık, boşluksuz gövde)], belge sırasıyla."""
    out = []
    for n in M.dugumler:
        out.append(("KONU", n.baslik, _BOSLUK.sub("", "".join(n.notlar))))
        for k in n.kayitlar:
            parca = [("KUNYE", k.kunye, [])]
            for p in k.paragraflar:
                if p.startswith("### "):
                    parca.append(("ALT", p[4:], []))
                else:
                    parca[-1][2].append(p)
            out.extend((s, t, _BOSLUK.sub("", "".join(g))) for s, t, g in parca)
    return out


def parca_dizisi(kod):
    """Parça dosyalarından (yol sırasıyla; ön bilgi, H1 ve bildirim satırı atılarak) aynı dizi."""
    out = []
    with open(os.path.join(KOK, "dizin", "konular.tsv"), encoding="utf-8") as f:
        sat = [s.rstrip("\n").split("\t") for s in f][1:]
    for s in sat:
        if s[0] != kod:
            continue
        out.append(["KONU", s[4], []])
        dizin = os.path.join(KOK, s[3])
        # konular.tsv belge sırasındadır (ön-sıra): bir düğümün kendi dosyaları alt dizinlerinden önce okunur
        dosyalar = sorted(x for x in os.listdir(dizin) if x.endswith(".md") and x.startswith(kod + ".")) \
            if s[3] and os.path.isdir(dizin) else []
        for ad in dosyalar:
            with open(os.path.join(dizin, ad), encoding="utf-8") as f:
                L = bedesten_bagla.ayikla(f.read().split("\n"))[0]   # bağlantı satırları kaynakta yok
            i = L.index("---", 1) + 1
            while not L[i]:
                i += 1
            if L[i] != "# " + s[4]:
                raise YapiHatasi(f"{ad}: H1 konu başlığıyla aynı değil")
            i += 1
            while not L[i]:
                i += 1
            if not L[i].startswith("> "):
                raise YapiHatasi(f"{ad}: bildirim satırı yok")
            for x in L[i + 1:]:
                if x.startswith("## "):
                    out.append(["KUNYE", x[3:], []])
                elif x.startswith("### "):
                    out.append(["ALT", x[4:], []])
                else:
                    out[-1][2].append(x)
    return [(a, b, _BOSLUK.sub("", "".join(c))) for a, b, c in out]


def dogrula():
    hatalar, rapor = [], []

    def hata(s):
        hatalar.append(s)

    def denetim(no, ad, once):
        yeni = len(hatalar) - once
        rapor.append(f"[{'TAMAM' if yeni == 0 else 'HATA'}] {no}. {ad}" + (f" ({yeni} hata)" if yeni else ""))

    D = defter_oku()
    # --- 1. gidiş-dönüş
    once = len(hatalar)
    toplam = collections.Counter()
    sinif_say = {}
    yama_rapor = []
    for d in D:
        M = oku(d)
        yama_rapor += [f"    {d['kod']} satır {no}: {e!r} -> {y!r}" for no, e, y in M.yamalar]
        a = kaynak_dizisi(M)
        try:
            b = parca_dizisi(d["kod"])
        except (YapiHatasi, OSError, ValueError, IndexError) as e:
            hata(f"1 {d['kod']}: parça dosyaları okunamadı: {e}")
            continue
        if a != b:
            j = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            xa = a[j][:2] if j < len(a) else None
            xb = b[j][:2] if j < len(b) else None
            hata(f"1 {d['kod']}: gidiş-dönüş tutmuyor (öğe {j}: kaynak {xa!r}, parça {xb!r}; "
                 f"uzunluk {len(a)}/{len(b)})")
        c = collections.Counter(x[0] for x in a)
        c["GOVDE"] = M.say["GOVDE"]
        c["harf"] = sum(len(x[1]) + len(x[2]) for x in a)
        sinif_say[d["kod"]] = c
        toplam.update(c)
    denetim(1, "gidiş-dönüş: parça dosyalarından kurulan (sınıf, başlık, boşluksuz gövde) dizisi = ara/ "
            "(NFC ve ek/<ad>.satirlar.tsv düzeltmeleri uygulanmış girdi)", once)
    rapor.append(f"    karşılaştırmadan önce girdide değiştirilen satır: {len(yama_rapor)}"
                 + ("" if yama_rapor else " (yok)"))
    rapor.extend(yama_rapor)
    rapor.append(f"    KONU {toplam['KONU']}  KUNYE {toplam['KUNYE']}  ALT {toplam['ALT']}  GOVDE {toplam['GOVDE']}"
                 f"  boşluksuz karakter {toplam['harf']}")

    # --- 2, 6, 7. boyutlar, adlar
    once = len(hatalar)
    md_boy, uzun_satir, en_uzun_satir = [], 0, 0
    ad_hata = yol_hata = kalabalik = 0
    en_uzun_yol, en_kalabalik = 0, 0
    icindekiler_boy = []
    for dp, dn, fn in os.walk(os.path.join(KOK, "md")):
        dn.sort()
        if len(dn) + len(fn) > 150:
            kalabalik += 1
            hata(f"6 {os.path.relpath(dp, KOK)}: {len(dn) + len(fn)} girdi (> 150)")
        en_kalabalik = max(en_kalabalik, len(dn) + len(fn))
        for x in dn + fn:
            if not re.fullmatch(r"[a-z0-9._-]+", x):
                ad_hata += 1
                hata(f"6 geçersiz ad: {os.path.relpath(os.path.join(dp, x), KOK)}")
        for f in sorted(fn):
            p = os.path.join(dp, f)
            g = os.path.relpath(p, KOK)
            en_uzun_yol = max(en_uzun_yol, len(g))
            if len(g) > 200:
                yol_hata += 1
                hata(f"6 yol 200 karakteri aşıyor ({len(g)}): {g}")
            with open(p, "rb") as fh:
                v = fh.read()
            v_bag = v
            if not f.startswith("00-icindekiler"):   # sınır bağlantı satırları hariç ölçülür
                v = "\n".join(bedesten_bagla.ayikla(v.decode("utf-8").split("\n"))[0]).encode("utf-8")
            if len(v) > 49500:
                hata(f"2 {g}: {len(v)} bayt (> 49.500)")
            if f.startswith("00-icindekiler"):
                icindekiler_boy.append(len(v))
                if len(v) > 48000:
                    hata(f"7 {g}: {len(v)} bayt (> 48.000)")
                continue
            md_boy.append(len(v))
            if not v_bag.endswith(b"\n") or v_bag.endswith(b"\n\n") or b"\r" in v_bag:
                hata(f"2 {g}: satır sonu biçimi bozuk")
            t = v.decode("utf-8")
            govde = t[t.index("\n---\n", 4) + 5:]
            for s in govde.split("\n"):
                if len(s) > 1300:
                    uzun_satir += 1
                    hata(f"2 {g}: {len(s)} karakterlik gövde satırı (> 1.300)")
                if len(s) > en_uzun_satir:
                    en_uzun_satir = len(s)
    for alt in ("dizin", "veri"):
        for dp, dn, fn in os.walk(os.path.join(KOK, alt)):
            for f in fn:
                b = os.path.getsize(os.path.join(dp, f))
                if b > 45_000_000:
                    hata(f"2 {os.path.relpath(os.path.join(dp, f), KOK)}: {b} bayt (> 45 MB)")
    md_boy.sort()
    denetim("2/6", "boyut ve ad sınırları (md/ dosya <= 49.500 bayt, gövde satırı <= 1.300, dizin/veri <= 45 MB, "
            "adlar [a-z0-9._-], yol <= 200, dizin <= 150 girdi)", once)
    if md_boy:
        rapor.append(f"    parça dosyası {len(md_boy)}  toplam {sum(md_boy)} bayt  ortanca {md_boy[len(md_boy) // 2]}"
                     f"  en büyük {md_boy[-1]}  en küçük {md_boy[0]}  en uzun gövde satırı {en_uzun_satir}"
                     f"  en uzun yol {en_uzun_yol}  en kalabalık dizin {en_kalabalik}")

    # --- 3, 4, 5. TSV, JSONL, sayılar
    once = len(hatalar)
    tum_id = set()
    kayit_toplam = konu_notu_toplam = 0
    for d in D:
        kod = d["kod"]
        tsv_id, onbellek = [], (None, None)
        try:
            with open(os.path.join(KOK, "dizin", "kararlar", kod + ".tsv"), encoding="utf-8") as f:
                bas = f.readline().rstrip("\n").split("\t")
                if bas != TSV_KARAR:
                    hata(f"3 {kod}.tsv: başlık satırı farklı")
                for no, s in enumerate(f, 2):
                    c = s.rstrip("\n").split("\t")
                    if len(c) != len(TSV_KARAR):
                        hata(f"3 {kod}.tsv:{no}: {len(c)} sütun")
                        continue
                    if not tsv_id or tsv_id[-1] != c[1]:
                        tsv_id.append(c[1])
                    if onbellek[0] != c[15]:
                        p = os.path.join(KOK, c[15])
                        if not os.path.isfile(p):
                            hata(f"3 {kod}.tsv:{no}: dosya yok: {c[15]}")
                            onbellek = (c[15], [])
                            continue
                        with open(p, encoding="utf-8") as fh:
                            onbellek = (c[15], fh.read().split("\n"))
                    L = onbellek[1]
                    j = int(c[16])
                    if j < 1 or j > len(L) or L[j - 1] != "## " + c[2]:
                        hata(f"3 {kod}.tsv:{no}: {c[15]}:{j} satırı '## {c[2][:40]}' değil")
        except OSError as e:
            hata(f"3 {kod}.tsv okunamadı: {e}")
        if len(set(tsv_id)) != len(tsv_id):
            hata(f"4 {kod}: TSV'de kimlikler ardışık/tekil değil")
        # jsonl
        js_id, js_not = [], 0
        try:
            with gzip.open(os.path.join(KOK, "veri", "kararlar", kod + ".jsonl.gz"), "rt", encoding="utf-8",
                           newline="\n") as f:
                for no, s in enumerate(f, 1):
                    try:
                        o = json.loads(s)
                    except ValueError:
                        hata(f"5 {kod}.jsonl.gz:{no}: JSON ayrıştırılamadı")
                        continue
                    if list(o) != SEMA_ANAHTARLARI:
                        hata(f"5 {kod}.jsonl.gz:{no}: anahtarlar şemayla aynı değil")
                        continue
                    if o["id"] in tum_id:
                        hata(f"4 yinelenen kimlik: {o['id']}")
                    tum_id.add(o["id"])
                    if o["tur"] == "konu-notu":
                        js_not += 1
                    else:
                        js_id.append(o["id"])
        except OSError as e:
            hata(f"5 {kod}.jsonl.gz okunamadı: {e}")
        kayit_toplam += len(js_id) + js_not
        konu_notu_toplam += js_not
        ks = None
        try:
            with open(os.path.join(KOK, "md", kod, "00-icindekiler.md"), encoding="utf-8") as f:
                m = re.search(r"^karar_sayisi: (\d+)$", f.read(), re.M)
                ks = int(m.group(1)) if m else None
        except OSError:
            pass
        if not (len(tsv_id) == len(js_id) == ks):
            hata(f"4 {kod}: TSV kimlik {len(tsv_id)}, JSONL (konu notu hariç) {len(js_id)}, karar_sayisi {ks}")
        elif tsv_id != js_id:
            hata(f"4 {kod}: TSV ve JSONL kimlik sırası farklı")
        if kod in sinif_say and sinif_say[kod]["KUNYE"] != len(js_id):
            hata(f"4 {kod}: kaynakta {sinif_say[kod]['KUNYE']} künye, JSONL'de {len(js_id)}")
    bos_yol = 0
    with open(os.path.join(KOK, "dizin", "konular.tsv"), encoding="utf-8") as f:
        for no, sat in enumerate(f, 1):
            c = sat.rstrip("\n").split("\t")
            if no == 1:
                continue
            if c[3]:
                if not os.path.isdir(os.path.join(KOK, c[3])):
                    hata(f"3 konular.tsv:{no}: dizin yok: {c[3]}")
            else:
                bos_yol += 1
                if c[6] != "0" or c[7] != "0":
                    hata(f"3 konular.tsv:{no}: yol boş ama karar/dosya sayısı sıfır değil")
    denetim("3/4/5", "konular.tsv yolları var; dizin/kararlar satırları dosyadaki '## künye' satırını gösteriyor; TSV = JSONL = karar_sayisi; "
            "kimlikler tekil; JSONL şeması", once)
    rapor.append(f"    kayıt {kayit_toplam}  (karar {kayit_toplam - konu_notu_toplam}, konu notu {konu_notu_toplam})"
                 f"  tekil kimlik {len(tum_id)}  boş başlık (yol boş) {bos_yol}")

    # --- 7. kılavuz boyutları
    once = len(hatalar)
    sinirlar = [("AGENTS.md", 6500, "bayt"), ("dizin/derlemeler.md", 25000, "bayt"), ("llms.txt", 2000, "bayt"),
                ("veri/ornek.jsonl", 400000, "bayt"), ("TALIMAT.txt", 1400, "karakter")]
    olcum = []
    for ad, sinir, birim in sinirlar:
        p = os.path.join(KOK, ad)
        if not os.path.isfile(p):
            hata(f"7 {ad} yok")
            continue
        with open(p, "rb") as f:
            v = f.read()
        b = len(v) if birim == "bayt" else len(v.decode("utf-8"))
        olcum.append(f"{ad} {b} {birim}")
        if b > sinir:
            hata(f"7 {ad}: {b} {birim} (> {sinir})")
    with open(os.path.join(KOK, "CLAUDE.md"), encoding="utf-8") as f:
        if f.read() != "@AGENTS.md\n":
            hata("7 CLAUDE.md tek satır '@AGENTS.md' değil")
    denetim(7, "kılavuz ve dizin boyutları (AGENTS.md <= 6.500, dizin/derlemeler.md <= 25.000, 00-icindekiler*.md "
            "<= 48.000, llms.txt <= 2.000, TALIMAT.txt <= 1.400 karakter, ornek.jsonl < 400.000)", once)
    rapor.append("    " + "  ".join(olcum) + f"  README.md {os.path.getsize(os.path.join(KOK, 'README.md'))} bayt"
                 + (f"  en büyük 00-icindekiler {max(icindekiler_boy)} bayt" if icindekiler_boy else ""))

    # --- 8. yinelenebilirlik: farklı özet tohumuyla ayrı süreçte ikinci üretim
    once = len(hatalar)
    rapor_ek = ""
    gecici = tempfile.mkdtemp(prefix="yapi-dogrula-")
    try:
        ortam = dict(os.environ, PYTHONHASHSEED="20261127")
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--cikti", gecici], env=ortam,
                           capture_output=True, text=True)
        if r.returncode != 0:
            hata(f"8 ikinci üretim başarısız: {r.stderr.strip()[-500:]}")
        else:
            a, b = agac_ozeti(KOK), agac_ozeti(gecici)
            fark = sorted(set(a) ^ set(b)) + sorted(k for k in a if k in b and a[k] != b[k])
            for k in fark[:20]:
                hata(f"8 iki üretim arasında fark: {k}")
            if len(fark) > 20:
                hata(f"8 ... toplam {len(fark)} farklı dosya")
            rapor_ek = f"    karşılaştırılan dosya {len(a)}, farklı {len(fark)}"
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    denetim(8, "iki üretim bayt bayt aynı (ayrı süreç, farklı PYTHONHASHSEED; sha256)", once)
    rapor.append(rapor_ek)

    metin = ["yapi.py --dogrula", f"sürüm {SURUM}", ""] + [x for x in rapor if x] + [""]
    metin += ["HATALAR:"] + hatalar if hatalar else ["Sonuç: TAMAM, bütün denetimler geçti."]
    if hatalar:
        metin.append(f"Sonuç: {len(hatalar)} HATA")
    cikti = "\n".join(metin) + "\n"
    with open(os.path.join(KOK, "log", "yapi.log"), "w", encoding="utf-8") as f:
        f.write(cikti)
    sys.stdout.write(cikti)
    return 1 if hatalar else 0


def secenekler(argv):
    p = argparse.ArgumentParser(
        prog="yapi.py",
        description="derlemeler.tsv + ara/<ad>/<ad>.md -> md/, dizin/, veri/ ve kılavuz dosyaları. "
                    "Seçenek verilmezse her şeyi baştan üretir (md/, dizin/, veri/ silinip yeniden yazılır).",
        epilog="Elle düzeltme: ek/<ad>.basliklar.tsv (başlık sınıfı), ek/<ad>.satirlar.tsv (kaynak satırı).",
        usage="python3 yapi.py [-h] [--dogrula | --cikti DİZİN]", add_help=False)
    p.add_argument("-h", "--help", action="help", help="bu yardımı yazar ve çıkar; hiçbir şey üretmez")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dogrula", action="store_true",
                   help="üretilmiş ağacı denetler, log/yapi.log yazar; hata varsa sıfırdan farklı çıkar")
    g.add_argument("--cikti", metavar="DİZİN",
                   help="çıktıları depo yerine DİZİN altına yazar, günlüklere dokunmaz (yinelenebilirlik denetimi)")
    return p.parse_args(argv)


def main(argv):
    s = secenekler(argv)          # --help ve bilinmeyen seçenek burada çıkar; hiçbir şey yazılmaz
    try:
        if s.dogrula:
            return dogrula()
        if s.cikti:
            uret(s.cikti, sessiz=True)
            return 0
        D, ist, S = uret(KOK)
        print(f"{len(D)} derleme · {binlik(ist['sayfa'])} sayfa · {binlik(ist['karar'])} karar "
              f"({binlik(ist['yabanci'])} yabancı) · {binlik(ist['konu'])} konu · {binlik(ist['dosya'])} dosya · "
              f"{mb(ist['md_bayt'])} MB md · {mb(ist['gz_bayt'])} MB veri · en büyük dosya "
              f"{binlik(ist['enbuyuk_dosya'])} bayt · metinsiz künye {binlik(ist['metinsiz'])} · konu notu "
              f"{binlik(ist['konu_notu'])} · yil_supheli {binlik(ist['yil_supheli'])}")
        return 0
    except YapiHatasi as e:
        print("HATA:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
