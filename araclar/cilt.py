#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cilt.py: md/ altındaki parça dosyalarından yükleme ciltleri üretir.

Kullanım:
    python3 araclar/cilt.py [kod ...] [--zip] [--cikti DİZİN]

Kod verilmezse derlemeler.tsv içindeki bütün derlemeler işlenir. Her derleme için
`yukle/<kod>/<kod>.c<NN>-<MM>.md` dosyaları yazılır (NN = cilt no, MM = cilt sayısı). Bir cilt en çok
3.000.000 bayttır. Ciltler dosya yükleyen ürünler (NotebookLM, ChatGPT, Claude Projects vb.) içindir;
depoda tutulmaz (yukle/ git tarafından yok sayılır).

Ciltlerde md/ parçalarından farklı olarak:
  - her künyenin altında bir kaynak satırı vardır: *[kod:sıra] kısa ad › konu yolu*
  - konu başlıkları derinliğine göre `#`, `##`, ... ile, künyeler bir alt düzeyde yazılır
  - uzun paragraflardaki yumuşak satır kırmaları geri alınır (paragraf tek satırdır)

`--zip` verilirse her derleme için `yukle/<kod>-yukle.zip` de yazılır (ciltler + dizin/konular.tsv +
TALIMAT.txt + AGENTS.md; sabit zaman damgası, sıralı adlar).

Yalnız Python 3 standart kitaplığı kullanır. Çıktı belirlenimlidir: saat ve rastgelelik yoktur.
"""

import os
import re
import sys
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAVAN = 3_000_000                 # bir cildin en büyük boyutu (bayt)
DEVAM = " (devam)"
RESMI = ("karararama.yargitay.gov.tr, emsal.uyap.gov.tr, karararama.danistay.gov.tr, "
         "kararlarbilgibankasi.anayasa.gov.tr, mevzuat.gov.tr")
# yapi.py içindeki NUMARALAYICI ile aynı desen
NUMARALAYICI = re.compile(r"^(§\s*\d+\.?|KISIM\s+[IVXLC]+\s*[–-]?|[IVXLC]+\.|[A-ZÇĞİÖŞÜ]\.|\d+\.|"
                          r"\*?[a-zçğıöşü][.)])\s+")
ON_BILGI_ANAHTARLARI = ("derleme", "kod", "surum", "derleyen", "kaynak_pdf", "paylasim", "surum_tarihi", "uyari")
ZIP_TARIHI = (1980, 1, 1, 0, 0, 0)


class CiltHatasi(Exception):
    pass


# ----------------------------------------------------------------------------- yardımcılar

def binlik(n):
    return f"{n:,}".replace(",", ".")


def yq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yq_coz(s):
    """YAML çift tırnaklı değeri (yapi.py'nin yazdığı biçim) çözer."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return re.sub(r"\\(.)", r"\1", s[1:-1])
    return s


def kes(s, sinir):
    """Metni kelime sınırında en çok `sinir` karaktere indirir; kestiyse sonuna … koyar."""
    if len(s) <= sinir:
        return s
    i = s.rfind(" ", 0, sinir + 1)
    if i <= 0:
        i = sinir
    return s[:i].rstrip(" ,;:–-") + "…"


def numaralayici(baslik):
    """Başlığın baştaki numaralayıcısı ('§4', 'KISIM I', 'II', 'A', '3', 'a)'); yoksa None."""
    m = NUMARALAYICI.match(baslik)
    if not m:
        return None
    t = re.sub(r"\s*[–-]$", "", m.group(1).strip())
    t = t.rstrip(".").lstrip("*")
    if t.startswith("§"):
        t = "§" + t[1:].strip()
    return re.sub(r"\s+", " ", t)


def kaynak_yolu(konu):
    """Kaynak satırındaki konu yolu: h1 etiketi › ara düzey numaralayıcıları › en içteki başlık."""
    out = []
    for i, t in enumerate(konu[:-1]):
        out.append(numaralayici(t) or kes(t, 40))
    out.append(kes(konu[-1], 140))
    return " › ".join(out)


def oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return f.read()


def yaz(yol, metin):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    veri = metin.encode("utf-8")
    with open(yol, "wb") as f:
        f.write(veri)
    return len(veri)


def on_bilgi_oku(satirlar, ad):
    """(anahtar -> ham değer satırı, konu listesi, ön bilgiden sonraki ilk satırın dizini)."""
    if not satirlar or satirlar[0] != "---":
        raise CiltHatasi(f"{ad}: ön bilgi yok")
    try:
        son = satirlar.index("---", 1)
    except ValueError:
        raise CiltHatasi(f"{ad}: ön bilgi kapanmıyor")
    alan, konu = {}, []
    for s in satirlar[1:son]:
        if s.startswith("  - "):
            konu.append(yq_coz(s[4:]))
        else:
            a, _, d = s.partition(":")
            alan[a] = d.strip()
    return alan, konu, son + 1


# ----------------------------------------------------------------------------- girdi

class Dugum:
    __slots__ = ("bolum", "yol", "baslik", "konu", "derinlik", "cocuk_var", "parcalar")


class Parca:
    """Bir parça dosyasının ciltteki karşılığı."""
    __slots__ = ("metin", "bayt", "ilk", "son", "karar")


def defter_oku():
    yol = os.path.join(KOK, "derlemeler.tsv")
    sat = [s.split("\t") for s in oku(yol).split("\n") if s.strip()]
    bas = sat[0]
    D = []
    for s in sat[1:]:
        d = dict(zip(bas, s + [""] * (len(bas) - len(s))))
        d["sira"] = int(d["sira"])
        D.append(d)
    D.sort(key=lambda d: d["sira"])
    return D


def konular_oku():
    """dizin/konular.tsv: kod -> belge sırasıyla düğümler (kararı olmayan başlıklar dahil)."""
    yol = os.path.join(KOK, "dizin", "konular.tsv")
    if not os.path.isfile(yol):
        raise CiltHatasi("dizin/konular.tsv yok; önce `python3 yapi.py` çalıştırın")
    sat = [s.split("\t") for s in oku(yol).split("\n") if s]
    bas = sat[0]
    i_kod, i_bolum, i_yol, i_baslik, i_ust = (bas.index(x) for x in ("kod", "bolum", "yol", "baslik", "ust"))
    K = {}
    for s in sat[1:]:
        n = Dugum()
        n.bolum, n.yol, n.baslik = s[i_bolum], s[i_yol], s[i_baslik]
        n.derinlik = n.bolum.count("-") + 1
        n.cocuk_var = False
        n.parcalar = []
        liste = K.setdefault(s[i_kod], [])
        sozluk = {x.bolum: x for x in liste}
        ust = s[i_ust] if len(s) > i_ust else ""
        if ust:
            if ust not in sozluk:
                raise CiltHatasi(f"{s[i_kod]}: {n.bolum} için üst başlık {ust} bulunamadı")
            sozluk[ust].cocuk_var = True
            n.konu = sozluk[ust].konu + [n.baslik]
        else:
            n.konu = [n.baslik]
        if len(n.konu) != n.derinlik:
            raise CiltHatasi(f"{s[i_kod]}: {n.bolum} derinliği konu yoluyla uyuşmuyor")
        liste.append(n)
    return K


def parca_cevir(yol, d, n):
    """Bir parça dosyasını cilt metnine çevirir (künye düzeyi, kaynak satırı, yumuşak kırma geri alınır)."""
    ad = os.path.basename(yol)
    kod = d["kod"]
    L = oku(yol).split("\n")
    alan, konu, i = on_bilgi_oku(L, ad)
    if konu != n.konu or yq_coz(alan.get("bolum", "")) != n.bolum:
        raise CiltHatasi(f"{ad}: ön bilgideki konu/bölüm dizinle uyuşmuyor")
    while i < len(L) and not L[i]:
        i += 1
    if i >= len(L) or L[i] != "# " + n.baslik:
        raise CiltHatasi(f"{ad}: H1 konu başlığıyla aynı değil")
    i += 1
    while i < len(L) and not L[i]:
        i += 1
    if i >= len(L) or not L[i].startswith("> "):
        raise CiltHatasi(f"{ad}: bildirim satırı yok")
    i += 1
    sira = yq_coz(alan.get("sira", ""))
    beklenen = int(alan.get("karar_sayisi", "0"))
    ilk = son = 0
    if sira:
        a, _, b = sira.partition("-")
        ilk, son = int(a), int(b)
        if son - ilk + 1 != beklenen:
            raise CiltHatasi(f"{ad}: sıra aralığı karar sayısıyla uyuşmuyor")
    elif beklenen:
        raise CiltHatasi(f"{ad}: karar var ama sıra aralığı yok")
    d_kunye = "#" * min(6, n.derinlik + 1) + " "
    d_alt = "#" * min(6, n.derinlik + 2) + " "
    kaynak = f"{d['kisa']} › {kaynak_yolu(n.konu)}"
    out, blok, no = [], [], ilk - 1

    def kapat():
        if not blok:
            return
        nonlocal no
        if len(blok) == 1 and blok[0].startswith("## "):
            no += 1
            out.append(d_kunye + blok[0][3:])
            out.append(f"*[{kod}:{no:05d}] {kaynak}*")
        elif len(blok) == 1 and blok[0].startswith("### "):
            out.append(d_alt + blok[0][4:])
        else:
            out.append(" ".join(blok))      # yumuşak kırma: tek boşluğun yerine konmuş satır sonu
        blok.clear()
    for s in L[i:]:
        if s:
            blok.append(s)
        else:
            kapat()
    kapat()
    if no != son and sira:
        raise CiltHatasi(f"{ad}: {beklenen} karar beklenirken {no - ilk + 1} künye bulundu")
    p = Parca()
    p.metin = "".join(x + "\n\n" for x in out)
    p.bayt = len(p.metin.encode("utf-8"))
    p.ilk, p.son, p.karar = (ilk, son, beklenen) if sira else (0, 0, 0)
    return p


def derleme_oku(d, dugumler):
    kod = d["kod"]
    kok = os.path.join(KOK, "md", kod)
    ic = os.path.join(kok, "00-icindekiler.md")
    if not os.path.isfile(ic):
        raise CiltHatasi(f"{kod}: md/{kod}/00-icindekiler.md yok; önce `python3 yapi.py` çalıştırın")
    alan, _, _ = on_bilgi_oku(oku(ic).split("\n"), f"md/{kod}/00-icindekiler.md")
    for a in ON_BILGI_ANAHTARLARI:
        if a not in alan:
            raise CiltHatasi(f"{kod}: 00-icindekiler.md ön bilgisinde {a} yok")
    if yq_coz(alan["derleme"]) != d["baslik"]:
        raise CiltHatasi(f"{kod}: md/ ile derlemeler.tsv başlığı uyuşmuyor; `python3 yapi.py` çalıştırın")
    toplam = 0
    for n in dugumler:
        dizin = os.path.join(KOK, n.yol)
        on_ek = f"{kod}.{n.bolum}."
        # dugumler belge sırasındadır (konular.tsv, ön-sıra): bir başlığın kendi dosyaları alt dizinlerindeki
        # dosyalardan önce okunur. Düz yol sıralaması (sorted) bu sırayı vermez. Boş başlığın yolu boştur.
        adlar = sorted(x for x in os.listdir(dizin) if x.startswith(on_ek) and x.endswith(".md")) \
            if n.yol and os.path.isdir(dizin) else []
        n.parcalar = [parca_cevir(os.path.join(dizin, x), d, n) for x in adlar]
        toplam += sum(p.karar for p in n.parcalar)
    if toplam != int(alan.get("karar_sayisi", "-1")):
        raise CiltHatasi(f"{kod}: parçalardaki karar sayısı ({toplam}) dizindekiyle uyuşmuyor")
    sira = 0
    for n in dugumler:                   # sıra numaraları kesintisiz 1..N olmalı
        for p in n.parcalar:
            if p.karar:
                if p.ilk != sira + 1:
                    raise CiltHatasi(f"{kod}: sıra numaraları kesintili ({n.bolum}, {p.ilk})")
                sira = p.son
    return alan, toplam


# ----------------------------------------------------------------------------- cilt metni

def bas_kismi(d, alan, cilt, sira, karar):
    """Ön bilgi + başlık + üç satırlık bildirim."""
    fm = ["---", "derleme: " + alan["derleme"], "kod: " + d["kod"], "surum: " + alan["surum"],
          "derleyen: " + alan["derleyen"], "cilt: " + yq(cilt), "sira: " + yq(sira), f"karar_sayisi: {karar}",
          "kaynak_pdf: " + alan["kaynak_pdf"], "paylasim: " + alan["paylasim"],
          "surum_tarihi: " + alan["surum_tarihi"], "uyari: " + alan["uyari"], "---", ""]
    surum = f" ({d['surum']})" if d["surum"] and not d["baslik"].endswith(d["surum"]) else ""
    kapsam = f"sıra {sira} · {binlik(karar)} karar" if sira else "karar yok"
    # örnek konum gerçek bir sıra numarası olsun: bu ciltteki ilk karar (sıra 1'den başlar)
    ornek_sira = int(sira.split("-")[0]) if sira else 1
    bildirim = [
        f"> Av. Hakan Dimdik (x.com/hakandimdik), \"{d['baslik']}{surum}\" · cilt {cilt} · {kapsam}. "
        f"Kararların seçimi, tasnifi ve başlıklar derleyenin emeğidir.",
        f"> Künyenin altındaki `[{d['kod']}:{ornek_sira:05d}]` derleme içi sıra numarasıdır, künye değildir. Tek "
        f"başına `…` satırı atlanmış metni, metin içindeki `...` gizlenmiş adı gösterir. Altında metin olmayan "
        f"künyeye kaynak metin koymamıştır (çoğu art arda sıralanmış seri karardır; hangi komşu alıntıyı "
        f"paylaştığı yazmaz); önceki ya da sonraki metni ona mal etmeyin.",
        f"> Seçme alıntılardır, kararın tamamı değildir; kararın tam metnini ve güncelliğini resmî kaynaktan "
        f"doğrulayın ({RESMI}). Hukuki görüş değildir.",
    ]
    return "\n".join(fm) + "\n" + f"# {d['baslik']} — cilt {cilt}\n\n" + "\n".join(bildirim) + "\n\n"


def icindekiler_satiri(n, ilk, son, karar, devam):
    kapsam = f"sıra {ilk}-{son} · {binlik(karar)} karar" if karar else "karar yok"
    return f"{'  ' * (n.derinlik - 1)}- {n.baslik}{DEVAM if devam else ''} — {kapsam}"


def baslik_ust_siniri(n, sozluk):
    """Bir birimin cilde ekleyebileceği başlık ve içindekiler baytlarının üst sınırı."""
    b = 0
    for i in range(1, n.derinlik + 1):
        t = n.konu[i - 1]
        b += len(("#" * i + " " + t + DEVAM + "\n\n").encode("utf-8"))
        if i <= 2:
            b += len((" " * 2 + "- " + t + DEVAM + " — sıra 9999999-9999999 · 9.999.999 karar\n").encode("utf-8"))
    return b


def ciltlere_dagit(d, alan, dugumler):
    """Açgözlü dağıtım. Dönen: [[(düğüm, parça | None), ...], ...]."""
    sozluk = {n.bolum: n for n in dugumler}
    sabit = len((bas_kismi(d, alan, "99/99", "9999999-9999999", 9999999)
                 + "**Bu ciltteki konular**\n\n\n").encode("utf-8"))
    butce = TAVAN - sabit
    ciltler, simdi, boy = [], [], 0
    bekleyen = []                         # kararı da alt başlığı da olmayan başlıklar: sonraki birime yapışır

    def kapat():
        nonlocal simdi, boy
        if simdi:
            ciltler.append(simdi)
        simdi, boy = [], 0
    for n in dugumler:
        if not n.parcalar:
            if not n.cocuk_var:
                bekleyen.append(n)
            continue
        on = [(b, None) for b in bekleyen]
        on_boy = sum(baslik_ust_siniri(b, sozluk) for b in bekleyen)
        bekleyen = []
        bu = baslik_ust_siniri(n, sozluk)
        toplam = on_boy + bu + sum(p.bayt for p in n.parcalar)
        if boy + toplam <= butce:
            simdi += on + [(n, p) for p in n.parcalar]
            boy += toplam
            continue
        kapat()
        if toplam <= butce:
            simdi = on + [(n, p) for p in n.parcalar]
            boy = toplam
            continue
        # tavandan büyük yaprak: parça dosyası sınırlarından bölünür
        simdi, boy = list(on), on_boy
        yeni = True
        for p in n.parcalar:
            ek = p.bayt + (bu if yeni else 0)
            if simdi and not yeni and boy + ek > butce:
                kapat()
                yeni = True
                ek = p.bayt + bu
            if ek > butce:
                raise CiltHatasi(f"{d['kod']}: tek parça dosyası cilt tavanından büyük ({n.bolum})")
            if yeni and boy + ek > butce:      # yalnız boş başlıklarla dolu olamaz; güvenlik için
                kapat()
            simdi.append((n, p))
            boy += ek
            yeni = False
    if bekleyen:
        if not simdi and ciltler:
            simdi = ciltler.pop()
        simdi += [(b, None) for b in bekleyen]
    kapat()
    return ciltler


def cilt_metni(d, alan, girdiler, no, adet, gorulen, sozluk):
    """Bir cildin tam metni. `gorulen`: önceki ciltlerde başlığı yazılmış bölümler (burada güncellenir)."""
    govde, onceki = [], []
    ust = {}                              # bolum -> [ilk, son, karar] (h1/h2, bu ciltte)
    ust_sira = []
    devamlar = set()
    ilk = son = karar = 0
    for n, p in girdiler:
        yol = [sozluk["-".join(n.bolum.split("-")[:i])] for i in range(1, n.derinlik + 1)]
        ortak = 0
        while ortak < len(yol) and ortak < len(onceki) and yol[ortak] is onceki[ortak]:
            ortak += 1
        for a in yol[ortak:]:
            devam = a.bolum in gorulen
            if devam:
                devamlar.add(a.bolum)
            govde.append("#" * min(6, a.derinlik) + " " + a.baslik + (DEVAM if devam else "") + "\n\n")
            if a.derinlik <= 2:
                ust[a.bolum] = [0, 0, 0]
                ust_sira.append(a)
        onceki = yol
        if p is None:
            continue
        govde.append(p.metin)
        if p.karar:
            ilk = ilk or p.ilk
            son = p.son
            karar += p.karar
            for a in yol[:2]:
                u = ust[a.bolum]
                u[0] = u[0] or p.ilk
                u[1] = p.son
                u[2] += p.karar
    for n, _ in girdiler:
        for i in range(1, n.derinlik + 1):
            gorulen.add("-".join(n.bolum.split("-")[:i]))
    sira = f"{ilk}-{son}" if karar else ""
    icindekiler = ["**Bu ciltteki konular**", ""]
    icindekiler += [icindekiler_satiri(a, *ust[a.bolum], a.bolum in devamlar) for a in ust_sira]
    metin = (bas_kismi(d, alan, f"{no}/{adet}", sira, karar) + "\n".join(icindekiler) + "\n\n" + "".join(govde))
    return metin.rstrip("\n") + "\n", karar


# ----------------------------------------------------------------------------- ana akış

def derleme_yaz(d, dugumler, cikti):
    kod = d["kod"]
    alan, toplam = derleme_oku(d, dugumler)
    sozluk = {n.bolum: n for n in dugumler}
    ciltler = ciltlere_dagit(d, alan, dugumler)
    if len(ciltler) > 99:
        raise CiltHatasi(f"{kod}: 99'dan çok cilt çıktı")
    hedef = os.path.join(cikti, kod)
    if os.path.isdir(hedef):              # yalnız bu aracın yazdığı dosyalar silinir
        for x in sorted(os.listdir(hedef)):
            if re.fullmatch(re.escape(kod) + r"\.c\d{2}-\d{2}\.md", x):
                os.remove(os.path.join(hedef, x))
    gorulen, adlar, sayac, en_buyuk, bayt = set(), [], 0, 0, 0
    for j, girdiler in enumerate(ciltler, 1):
        metin, karar = cilt_metni(d, alan, girdiler, j, len(ciltler), gorulen, sozluk)
        b = len(metin.encode("utf-8"))
        if b > TAVAN:
            raise CiltHatasi(f"{kod}: cilt {j} tavanı aşıyor ({b} bayt)")
        ad = f"{kod}.c{j:02d}-{len(ciltler):02d}.md"
        yaz(os.path.join(hedef, ad), metin)
        adlar.append(ad)
        sayac += karar
        en_buyuk = max(en_buyuk, b)
        bayt += b
    if sayac != toplam:
        raise CiltHatasi(f"{kod}: ciltlerdeki karar sayısı ({sayac}) beklenenle ({toplam}) uyuşmuyor")
    return adlar, toplam, en_buyuk, bayt


def zip_yaz(kod, adlar, cikti):
    """<kod>-yukle.zip: ciltler + konular.tsv + TALIMAT.txt + AGENTS.md; sabit zaman, sıralı adlar."""
    girdiler = [(a, os.path.join(cikti, kod, a)) for a in adlar]
    girdiler += [("konular.tsv", os.path.join(KOK, "dizin", "konular.tsv")),
                 ("TALIMAT.txt", os.path.join(KOK, "TALIMAT.txt")),
                 ("AGENTS.md", os.path.join(KOK, "AGENTS.md"))]
    for ad, yol in girdiler:
        if not os.path.isfile(yol):
            raise CiltHatasi(f"{kod}: zip için {ad} bulunamadı")
    hedef = os.path.join(cikti, f"{kod}-yukle.zip")
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for ad, yol in sorted(girdiler):
            bilgi = zipfile.ZipInfo(ad, date_time=ZIP_TARIHI)
            bilgi.compress_type = zipfile.ZIP_DEFLATED
            bilgi.create_system = 3
            bilgi.external_attr = 0o100644 << 16
            with open(yol, "rb") as f:
                z.writestr(bilgi, f.read(), compresslevel=9)
    return hedef


def main(argv):
    zip_iste, cikti, kodlar = False, os.path.join(KOK, "yukle"), []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__.strip())
            return 0
        if a == "--zip":
            zip_iste = True
        elif a == "--cikti":
            i += 1
            if i >= len(argv):
                print("cilt.py: --cikti bir dizin ister", file=sys.stderr)
                return 2
            cikti = os.path.abspath(argv[i])
        elif a.startswith("-"):
            print(f"cilt.py: bilinmeyen seçenek: {a}", file=sys.stderr)
            return 2
        else:
            kodlar.append(a)
        i += 1
    try:
        D = defter_oku()
        bilinen = {d["kod"] for d in D}
        for k in kodlar:
            if k not in bilinen:
                raise CiltHatasi(f"bilinmeyen kod: {k} (geçerli kodlar derlemeler.tsv içindedir)")
        K = konular_oku()
        top_cilt = top_bayt = 0
        for d in D:
            if kodlar and d["kod"] not in kodlar:
                continue
            adlar, karar, en_buyuk, bayt = derleme_yaz(d, K.get(d["kod"], []), cikti)
            top_cilt += len(adlar)
            top_bayt += bayt
            ek = ""
            if zip_iste:
                ek = " · " + os.path.basename(zip_yaz(d["kod"], adlar, cikti))
            print(f"{d['kod']}: {len(adlar)} cilt · {binlik(karar)} karar · en büyük cilt "
                  f"{binlik(en_buyuk)} bayt{ek}")
        print(f"Toplam {top_cilt} cilt, {binlik(top_bayt)} bayt → {cikti}")
    except CiltHatasi as e:
        print(f"cilt.py: HATA: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
