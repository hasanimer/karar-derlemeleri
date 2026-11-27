#!/usr/bin/env python3
"""Doğrulanmış (kesin) Bedesten bağlantılarını üretilmiş ağaca işler; yapi.py de aynı işlevleri kullanır.

Bağlantılar kaynak metinden ayrı metadata'dır: tek kaynak veri/bedesten/eslesmeler/parti-*.jsonl dosyalarıdır.
Markdown'da künye satırının altına bir satır eklenir:

    ## <künye>

    [UYAP – Kararın tam metni](https://mevzuat.adalet.gov.tr/ictihat/<documentId>)

    <alıntı>

Künye, alıntı, kimlik (id) ve metin özeti (es) değişmez. Eklenen satırlar yüzünden kayıtların `satir`
değeri (sürüme özgüdür) ve parça dosyalarının bayt sayıları yeniden hesaplanır. Bağlantı satırları
çıkarıldığında md dosyası bağlantısız hâline bayt bayt döner (`ayikla`). Yalnız standart kitaplık kullanır.

Kullanım:  python3 araclar/bedesten_bagla.py [--denetle]
"""
import collections
import glob
import gzip
import hashlib
import io
import json
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONEK = "[UYAP – Kararın tam metni]("
URL_KALIP = re.compile(r"^https://mevzuat\.adalet\.gov\.tr/ictihat/[0-9]{5,12}$")
ESLESME_DIZIN = "veri/bedesten/eslesmeler"


def baglanti_satiri(url):
    if not URL_KALIP.match(url or ""):
        raise ValueError(f"geçersiz bağlantı: {url!r}")
    return f"{ONEK}{url})"


def baglanti_mi(s):
    return s.startswith(ONEK) and s.endswith(")") and URL_KALIP.match(s[len(ONEK):-1]) is not None


def baglantilari_oku(kok=KOK):
    """id -> bedesten_url; yalnız match_status == 'kesin' ve kimliği/adresi tutarlı kayıtlar."""
    out = {}
    for p in sorted(glob.glob(os.path.join(kok, ESLESME_DIZIN, "parti-*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                if o.get("match_status") != "kesin":
                    continue
                doc, url = o.get("bedesten_document_id"), o.get("bedesten_url")
                if not doc or url != f"https://mevzuat.adalet.gov.tr/ictihat/{doc}":
                    raise ValueError(f"{p}: {o.get('id')}: kimlik/adres tutarsız")
                if o["id"] in out and out[o["id"]] != url:
                    raise ValueError(f"{o['id']}: iki farklı bağlantı")
                out[o["id"]] = url
    # elle resmî kaynaktan doğrulanmış kayıtlar (pilot, veri/bedesten/dogrulanmis.jsonl)
    p = os.path.join(kok, "veri", "bedesten", "dogrulanmis.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                url = f"https://mevzuat.adalet.gov.tr/ictihat/{o.get('bedesten_document_id')}"
                if o.get("status") == "official_verified" and o.get("bedesten_url") == url:
                    if o["id"] in out and out[o["id"]] != url:
                        raise ValueError(f"{o['id']}: elle doğrulanan ile parti bağlantısı farklı")
                    out[o["id"]] = url
    return out


def ayikla(satirlar):
    """Bağlantı satırlarını (ve ardındaki boş satırı) çıkarır. -> (yeni satırlar, eski->yeni satır eşlemi)"""
    yeni, esle, i = [], {}, 0
    while i < len(satirlar):
        s = satirlar[i]
        if baglanti_mi(s) and i >= 2 and satirlar[i - 1] == "" and satirlar[i - 2].startswith("## ") \
                and i + 1 < len(satirlar) and satirlar[i + 1] == "":
            i += 2
            continue
        esle[i + 1] = len(yeni) + 1
        yeni.append(s)
        i += 1
    return yeni, esle


def gz(veri):
    b = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=b, compresslevel=9, mtime=0) as g:
        g.write(veri)
    return b.getvalue()


def json_satir(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def _oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return f.read()


def _yaz(yol, metin):
    veri = metin.encode("utf-8") if isinstance(metin, str) else metin
    try:
        with open(yol, "rb") as f:
            if f.read() == veri:
                return False
    except FileNotFoundError:
        pass
    tmp = yol + ".tmp"
    with open(tmp, "wb") as f:
        f.write(veri)
    os.replace(tmp, yol)
    return True


def uygula(kok=KOK, baglantilar=None, sessiz=False):
    """Ağacı verilen bağlantı kümesine getirir (idempotent). -> istatistik sözlüğü"""
    if baglantilar is None:
        baglantilar = baglantilari_oku(kok)
    manifest_yol = os.path.join(kok, "veri", "manifest.json")
    manifest = json.loads(_oku(manifest_yol))
    ist = collections.Counter()
    yeni_satir = {}
    kullanilan = set()
    for d in manifest["derlemeler"]:
        kod = d["kod"]
        jyol = os.path.join(kok, "veri", d["dosya"])
        with gzip.open(jyol, "rt", encoding="utf-8") as f:
            ham = f.read()
        kayitlar = [json.loads(x) for x in ham.split("\n") if x]
        dosyalar = collections.defaultdict(list)
        for r in kayitlar:
            dosyalar[r["dosya"]].append(r)
        for dosya, rs in dosyalar.items():
            myol = os.path.join(kok, dosya)
            metin = _oku(myol)
            satirlar = metin.split("\n")
            temiz, esle = ayikla(satirlar)
            ekle = {}
            for r in rs:
                s0 = esle.get(r["satir"])
                if s0 is None or temiz[s0 - 1] != "## " + r["kunye"]:
                    raise ValueError(f"{dosya}:{r['satir']}: '## {r['kunye']}' satırı bulunamadı")
                if r["id"] in baglantilar:
                    ekle[s0] = baglanti_satiri(baglantilar[r["id"]])
                    kullanilan.add(r["id"])
            cikti, kayma = [], {}
            for no, s in enumerate(temiz, 1):
                kayma[no] = len(cikti) + 1
                cikti.append(s)
                if no in ekle:
                    if no >= len(temiz) or temiz[no] != "":
                        raise ValueError(f"{dosya}:{no}: künyeden sonra boş satır yok")
                    cikti.append("")
                    cikti.append(ekle[no])
                    # ardındaki boş satır temiz[no] olarak zaten yazılacak; araya bir boş satır daha gerekir
                    if no + 1 < len(temiz) + 1:
                        pass
            # biçim: '## k', '', '[bağlantı]', '', paragraf -> yukarıda '## k','', '[b]' eklendi; temiz[no] ('') takip eder
            yeni = "\n".join(cikti)
            if _yaz(myol, yeni):
                ist["md_degisen"] += 1
            for r in rs:
                yeni_satir[r["id"]] = kayma[esle[r["satir"]]]
            ist["baglanti"] += len(ekle)
        # JSONL: yalnız satir değişir
        degisti = False
        for r in kayitlar:
            if r["satir"] != yeni_satir[r["id"]]:
                r["satir"] = yeni_satir[r["id"]]
                degisti = True
        if degisti:
            veri = gz(("\n".join(json_satir(r) for r in kayitlar) + "\n").encode("utf-8"))
            _yaz(jyol, veri)
            ist["jsonl_degisen"] += 1
        with open(jyol, "rb") as f:
            v = f.read()
        d["bayt"], d["sha256"] = len(v), hashlib.sha256(v).hexdigest()
        # dizin/kararlar/<kod>.tsv: son sütun satir
        tyol = os.path.join(kok, "dizin", "kararlar", kod + ".tsv")
        tsat = _oku(tyol).split("\n")
        bas = tsat[0].split("\t")
        i_id, i_sat = bas.index("id"), bas.index("satir")
        for j in range(1, len(tsat)):
            if tsat[j]:
                c = tsat[j].split("\t")
                c[i_sat] = str(yeni_satir[c[i_id]])
                tsat[j] = "\t".join(c)
        _yaz(tyol, "\n".join(tsat))
    eksik = set(baglantilar) - kullanilan
    if eksik:
        raise ValueError(f"{len(eksik)} bağlantının kaydı ağaçta yok (ör. {sorted(eksik)[:3]})")
    _yaz(manifest_yol, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    # konular.tsv: düğümün kendi parça dosyalarının bayt toplamı
    kyol = os.path.join(kok, "dizin", "konular.tsv")
    ksat = _oku(kyol).split("\n")
    bas = ksat[0].split("\t")
    i_kod, i_bol, i_yol, i_bayt = bas.index("kod"), bas.index("bolum"), bas.index("yol"), bas.index("bayt")
    for j in range(1, len(ksat)):
        if not ksat[j]:
            continue
        c = ksat[j].split("\t")
        if c[i_yol]:
            on = f"{c[i_kod]}.{c[i_bol]}."
            dz = os.path.join(kok, c[i_yol])
            c[i_bayt] = str(sum(os.path.getsize(os.path.join(dz, x)) for x in os.listdir(dz)
                                if x.startswith(on) and x.endswith(".md") and re.fullmatch(r"\d+\.md", x[len(on):])))
            ksat[j] = "\t".join(c)
    _yaz(kyol, "\n".join(ksat))
    # ornek.jsonl: satir alanı
    oyol = os.path.join(kok, "veri", "ornek.jsonl")
    osat = _oku(oyol).split("\n")
    for j, x in enumerate(osat):
        if x:
            r = json.loads(x)
            if r.get("id") in yeni_satir and r["satir"] != yeni_satir[r["id"]]:
                r["satir"] = yeni_satir[r["id"]]
                osat[j] = json_satir(r)
    _yaz(oyol, "\n".join(osat))
    if not sessiz:
        print(json.dumps(dict(ist), ensure_ascii=False))
    return ist


def denetle(kok=KOK, baglantilar=None):
    """Bütünlük: her kaydın satir'ı '## künye'yi gösterir; bağlantı yalnız kesin kayıtlarda ve doğru adresle;
    bağlantılar çıkarılınca md'de başka fark yok sayılmaz (bunu git ile karşılaştırarak denetle.py yapar);
    manifest sha256 ve bayt değerleri dosyalarla aynı. -> hata listesi"""
    if baglantilar is None:
        baglantilar = baglantilari_oku(kok)
    hatalar = []
    manifest = json.loads(_oku(os.path.join(kok, "veri", "manifest.json")))
    gorulen = set()
    toplam_kayit = 0
    for d in manifest["derlemeler"]:
        jyol = os.path.join(kok, "veri", d["dosya"])
        with open(jyol, "rb") as f:
            v = f.read()
        if len(v) != d["bayt"] or hashlib.sha256(v).hexdigest() != d["sha256"]:
            hatalar.append(f"manifest: {d['dosya']} bayt/sha256 tutmuyor")
        kayitlar = [json.loads(x) for x in gzip.decompress(v).decode("utf-8").split("\n") if x]
        if len(kayitlar) != d["kayit"]:
            hatalar.append(f"{d['dosya']}: kayıt sayısı {len(kayitlar)} != {d['kayit']}")
        toplam_kayit += len(kayitlar)
        tsv = {}
        tyol = os.path.join(kok, "dizin", "kararlar", d["kod"] + ".tsv")
        satir = _oku(tyol).split("\n")
        bas = satir[0].split("\t")
        for x in satir[1:]:
            if x:
                c = x.split("\t")
                tsv.setdefault(c[bas.index("id")], set()).add((c[bas.index("dosya")], int(c[bas.index("satir")])))
        onbellek = {}
        for r in kayitlar:
            if r["dosya"] not in onbellek:
                onbellek[r["dosya"]] = _oku(os.path.join(kok, r["dosya"])).split("\n")
            L = onbellek[r["dosya"]]
            if not (0 < r["satir"] <= len(L)) or L[r["satir"] - 1] != "## " + r["kunye"]:
                hatalar.append(f"{r['id']}: satir {r['satir']} künyeyi göstermiyor")
                continue
            if tsv.get(r["id"]) != {(r["dosya"], r["satir"])}:
                hatalar.append(f"{r['id']}: dizin/kararlar TSV satırı JSONL ile aynı değil")
            var = r["satir"] + 1 < len(L) and baglanti_mi(L[r["satir"] + 1])
            if r["id"] in baglantilar:
                gorulen.add(r["id"])
                if not var or L[r["satir"] + 1] != baglanti_satiri(baglantilar[r["id"]]):
                    hatalar.append(f"{r['id']}: bağlantı satırı yok ya da yanlış")
            elif var:
                hatalar.append(f"{r['id']}: kesin olmayan kayıtta bağlantı var")
        for dosya, L in onbellek.items():
            n = sum(1 for s in L if s.startswith(ONEK))
            m = sum(1 for s in L if baglanti_mi(s))
            if n != m:
                hatalar.append(f"{dosya}: biçimi bozuk bağlantı satırı")
    if set(baglantilar) - gorulen:
        hatalar.append(f"{len(set(baglantilar) - gorulen)} bağlantının kaydı yok")
    if toplam_kayit != manifest["toplam"]["kayit"]:
        hatalar.append("toplam kayıt sayısı manifest ile aynı değil")
    return hatalar


if __name__ == "__main__":
    if "--denetle" in sys.argv[1:]:
        h = denetle()
        print("\n".join(h[:50]) or "TAMAM")
        sys.exit(1 if h else 0)
    uygula()
