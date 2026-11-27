#!/usr/bin/env python3
"""Derleme künyelerini UYAP Bedesten belge kimlikleriyle ihtiyatlı biçimde eşleştirir.

Aşamalar (hepsi yeniden başlatılabilir):
  indeks   yerel Parquet veri setinden (Bedesten belge kimlikli) künye dizini kurar (DuckDB; metin yok)
  aday     derleme kayıtları için aday belgeleri bulur, yalnız aday belgelerin tam metnini ayrı tabloya alır
  calistir 10.000'lik partiler: eşleştir, yaz, uygula, denetle, checkpoint, commit, push
  uygula   veri/bedesten/eslesmeler/*.jsonl içindeki 'kesin' bağlantıları md/ ve dizin/veri dosyalarına işler
  denetle  veri bütünlüğü denetimi (bağlantılar çıkarılınca md özgün hâline döner mi, satır referansları doğru mu)

Kesin eşleşme kuralı (hepsi birlikte):
  * kaynak satırın belge kimliği Bedesten belge kimliğidir (veri setinin kaynağı Bedesten ile aynı kimlik uzayı;
    her partide rastgele örnek canlı Bedesten getDocumentContent ile ayrıca doğrulanır),
  * mahkeme türü + daire + karar yılı/numarası birebir aynı ve bu anahtarda TEK aday vardır,
  * künyede esas numarası ya da tarih yazıyorsa onlar da aynıdır,
  * alıntı metni tam metinde büyük ölçüde (5'li sözcük dizileri) geçer.
  * metnin başlığındaki karar no künyeyle tutar (farklıysa: metin_numarasi_farkli; BAM başlığında karar no yok/
    karartılmışsa: metinde_karar_no_yok; ikisinde de bağlantı yok).
Yalnız metin benzerliği ya da yalnız karar numarası kesin eşleşme için yetmez. Birden çok aday varsa
bağlantı eklenmez. Hiçbir kimlik ya da adres üretilmez; yalnız veri setinde bulunan kimlik kullanılır.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "araclar"))
import bedesten_bagla as BB  # noqa: E402

URL_BICIMI = "https://mevzuat.adalet.gov.tr/ictihat/{}"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"
KAYNAK = "hf:mrfg/turkish-court-decisions@e9062174adcdee8386b94cebd01df7264268e86b"
YONTEM = "anahtar(tur+daire+karar)+esas/tarih+alinti_5gram"
ESIK_KESIN = 0.80     # alıntı 5'li dizilerinin tam metinde bulunma oranı
ESIK_OLASI = 0.30
EN_AZ_SOZCUK = 12     # bundan kısa alıntı kesin eşleşmeye yetmez
TUR_KAYNAK = {"yargitay": "yargitay", "bam": "emsal", "danistay": "danistay"}
ENGEL_BAYRAK = {"cok_karar", "yil_supheli", "yazim", "karar_no_yok", "yil_yok", "mahkeme_cikarim", "k_eki_yok"}

_KATLA = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
    "Ç": "c", "Ğ": "g", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u", "Â": "a", "Î": "i", "Û": "u"})


def katla(s):
    s = unicodedata.normalize("NFC", str(s or "")).translate(_KATLA).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", katla(s)).strip("-")


def sozcukler(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = s.replace("&nbsp;", " ")
    return re.findall(r"[a-z0-9]+", katla(s))


def karar_no(s):
    m = re.fullmatch(r"\s*(\d{4})\s*/\s*(\d+)\s*", str(s or ""))
    return (int(m[1]), int(m[2])) if m else None


def no_metni(t):
    return f"{t[0]}/{t[1]}" if t else None


# ----------------------------------------------------------------------------- veri seti tarafı birim anahtarı

def birim_hf(source, court):
    c = " ".join(str(court or "").split())
    k = katla(c)
    if source == "yargitay":
        m = re.fullmatch(r"(\d+)\. (hukuk|ceza) dairesi", k)
        if m:
            return f"{int(m[1])}{'hd' if m[2] == 'hukuk' else 'cd'}"
        sabit = {"hukuk genel kurulu": "hgk", "ceza genel kurulu": "cgk",
                 "hukuk daireleri baskanlar kurulu": "hdbk", "ceza daireleri baskanlar kurulu": "cdbk",
                 "buyuk genel kurulu": "buyukgenelkurul"}
        if k in sabit:
            return sabit[k]
        if "ictihatlari birlestirme" in k:
            return "ibk"
        return None
    if source == "danistay":
        m = re.fullmatch(r"(?:danistay )?(\d+)\. daire(?: baskanligi)?", k)
        if m:
            return f"{int(m[1])}d"
        if "idar" in k and "dava daireleri kurulu" in k:
            return "iddk"
        if "vergi dava daireleri kurulu" in k:
            return "vddk"
        return None
    if source == "emsal":
        m = re.fullmatch(r"(.+?) bolge adliye mahkemesi (\d+)\. (hukuk|ceza) dairesi", k)
        if m:
            return f"{slug(m[1])}-bam-{int(m[2])}{'hd' if m[3] == 'hukuk' else 'cd'}"
        return None
    return None


def birim_derleme(r):
    a = r.get("anahtar") or ""
    p = a.split("|")
    return p[1] if len(p) == 3 and p[1] else None


# ----------------------------------------------------------------------------- derleme kayıtları

def derleme_kayitlari():
    """manifest sırası, sonra sira: sabit küresel sıra."""
    m = json.loads((ROOT / "veri/manifest.json").read_text(encoding="utf-8"))
    for d in m["derlemeler"]:
        with gzip.open(ROOT / "veri" / d["dosya"], "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def kayit_anahtari(r):
    """(kaynak, birim, (yıl, no)) ya da (None, neden)."""
    tur = r.get("tur")
    if tur not in TUR_KAYNAK:
        return None, "kapsam_disi"
    if set(r.get("bayrak") or []) & ENGEL_BAYRAK:
        return None, "hatali_kunye"
    k = karar_no(r.get("karar"))
    b = birim_derleme(r)
    if not k or not b or not r.get("daire") or len(r.get("kararlar") or []) != 1:
        return None, "hatali_kunye"
    return (TUR_KAYNAK[tur], b, k), None


# ----------------------------------------------------------------------------- indeks

def duck(db, read_only=False, threads=4, mem="6GB"):
    import duckdb
    con = duckdb.connect(str(db), read_only=read_only)
    con.execute(f"SET threads={int(threads)}")
    con.execute(f"SET memory_limit='{mem}'")
    return con


def indeks(a):
    veri = Path(a.veri)
    con = duck(a.db, threads=a.threads, mem=a.bellek)
    con.execute("DROP TABLE IF EXISTS karar")
    parts = []
    for src in ("yargitay", "emsal", "danistay"):
        files = sorted(str(p).replace("\\", "/") for p in (veri / "data" / src).glob("*.parquet"))
        if not files:
            raise SystemExit(f"{src}: parquet yok ({veri})")
        flist = "[" + ",".join(f"'{x}'" for x in files) + "]"
        parts.append(f"""SELECT source, document_id, court, birim_hf(source, court) AS birim,
              TRY_CAST(regexp_extract(karar_no, '^\\s*(\\d{{4}})\\s*/\\s*(\\d+)\\s*$', 1) AS INTEGER) AS k_yil,
              TRY_CAST(regexp_extract(karar_no, '^\\s*(\\d{{4}})\\s*/\\s*(\\d+)\\s*$', 2) AS BIGINT) AS k_no,
              esas_no, karar_no, karar_tarihi, text_len
            FROM read_parquet({flist})""")
    t0 = time.time()
    # birim_hf Python UDF'si yavaş olmasın diye önce tekil court değerlerine uygula
    con.execute("CREATE TEMP TABLE ham AS " + " UNION ALL ".join(p.replace("birim_hf(source, court)", "NULL::VARCHAR") for p in parts))
    courts = con.execute("SELECT DISTINCT source, court FROM ham").fetchall()
    con.execute("CREATE TEMP TABLE cb(source VARCHAR, court VARCHAR, birim VARCHAR)")
    con.executemany("INSERT INTO cb VALUES (?,?,?)", [(s, c, birim_hf(s, c)) for s, c in courts])
    con.execute("""CREATE TABLE karar AS SELECT h.source, h.document_id, h.court, cb.birim, h.k_yil, h.k_no,
                   h.esas_no, h.karar_no, h.karar_tarihi, h.text_len
                   FROM ham h LEFT JOIN cb ON h.source = cb.source AND h.court IS NOT DISTINCT FROM cb.court""")
    con.execute("CREATE INDEX karar_anahtar ON karar(source, birim, k_yil, k_no)")
    n = con.execute("SELECT count(*), count(birim), count(k_no) FROM karar").fetchone()
    con.execute("CREATE OR REPLACE TABLE bilgi AS SELECT ? AS kaynak, ? AS kuruldu, ? AS satir",
                [KAYNAK, datetime.datetime.now().isoformat(timespec="seconds"), n[0]])
    print(f"indeks: {n[0]:,} satır, birimli {n[1]:,}, karar no {n[2]:,} ({time.time()-t0:.0f} sn) -> {a.db}")


def aday(a):
    """Bütün derleme kayıtları için anahtar adaylarını bulur; yalnız aday belgelerin metnini çeker."""
    con = duck(a.db, threads=a.threads, mem=a.bellek)
    anahtarlar = set()
    for r in derleme_kayitlari():
        k, _ = kayit_anahtari(r)
        if k:
            anahtarlar.add((k[0], k[1], k[2][0], k[2][1]))
    con.execute("CREATE OR REPLACE TEMP TABLE ist(source VARCHAR, birim VARCHAR, k_yil INTEGER, k_no BIGINT)")
    con.executemany("INSERT INTO ist VALUES (?,?,?,?)", sorted(anahtarlar))
    con.execute("""CREATE OR REPLACE TABLE aday AS SELECT k.* FROM karar k JOIN ist USING (source, birim, k_yil, k_no)""")
    na = con.execute("SELECT count(*), count(DISTINCT document_id) FROM aday").fetchone()
    print(f"aday: {len(anahtarlar):,} tekil anahtar, {na[0]:,} aday satır")
    veri = Path(a.veri)
    con.execute("DROP TABLE IF EXISTS metin")
    con.execute("CREATE TABLE metin(source VARCHAR, document_id VARCHAR, text VARCHAR)")
    t0 = time.time()
    for src in ("yargitay", "emsal", "danistay"):
        for p in sorted((veri / "data" / src).glob("*.parquet")):
            f = str(p).replace("\\", "/")
            con.execute(f"""INSERT INTO metin SELECT p.source, p.document_id, p.text
                FROM read_parquet('{f}') p
                SEMI JOIN (SELECT DISTINCT source, document_id FROM aday) d
                ON p.source = d.source AND p.document_id = d.document_id""")
            print(f"  metin: {p.name} ({time.time()-t0:.0f} sn)", flush=True)
    con.execute("CREATE INDEX metin_id ON metin(source, document_id)")
    print("metin:", con.execute("SELECT count(*) FROM metin").fetchone()[0])


# ----------------------------------------------------------------------------- metin karşılaştırma

def dizi_kumesi(tokens, n=5):
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def kapsama(alinti, tam_kume):
    """Alıntıdaki 5'li sözcük dizilerinin tam metinde bulunma oranı. '…' ve '...' parçaları ayrı ele alınır."""
    parcalar = re.split(r"…|\.\.\.+|\*\*", alinti)
    toplam = bulunan = 0
    sozcuk = 0
    for p in parcalar:
        t = sozcukler(p)
        sozcuk += len(t)
        if len(t) < 5:
            continue
        for g in dizi_kumesi(t):
            toplam += 1
            bulunan += g in tam_kume
    return (bulunan / toplam if toplam else 0.0), sozcuk


# ----------------------------------------------------------------------------- eşleştirme

class Eslestirici:
    """Aday tablosu küçüktür (anahtar başına birkaç satır): belleğe alınır. Metinler parti parti çekilir."""

    def __init__(self, db, threads=2, mem="4GB"):
        self.con = duck(db, read_only=True, threads=threads, mem=mem)
        self.aday_tablo = defaultdict(list)
        for src, doc, court, b, y, n, esas, karar, tarih in self.con.execute(
                "SELECT source, document_id, court, birim, k_yil, k_no, esas_no, karar_no, karar_tarihi FROM aday "
                "ORDER BY document_id").fetchall():
            self.aday_tablo[(src, b, (y, n))].append((doc, court, esas, karar, tarih))
        self.kume_onbellek = {}
        self.baslik_onbellek = {}

    def adaylar(self, k):
        return self.aday_tablo.get(k, [])

    def yerel_bilgi(self, r, doc):
        k, _ = kayit_anahtari(r)
        for x in self.adaylar(k) if k else []:
            if x[0] == doc:
                return x[2], x[4]
        return None

    def metinleri_yukle(self, kayitlar):
        """Partideki tek adaylı kayıtların metinlerini tek sorguda alır (önbelleğe)."""
        iste = set()
        for r in kayitlar:
            k, _ = kayit_anahtari(r)
            if k:
                for x in self.adaylar(k):
                    if (k[0], x[0]) not in self.kume_onbellek:
                        iste.add((k[0], x[0]))
        if len(self.kume_onbellek) > 60000:
            self.kume_onbellek.clear()
            self.baslik_onbellek.clear()
        if not iste:
            return
        self.con.execute("CREATE OR REPLACE TEMP TABLE iste(source VARCHAR, document_id VARCHAR)")
        self.con.executemany("INSERT INTO iste VALUES (?,?)", sorted(iste))
        for src, doc, text in self.con.execute(
                "SELECT m.source, m.document_id, m.text FROM metin m JOIN iste USING (source, document_id)").fetchall():
            self.kume_onbellek[(src, doc)] = dizi_kumesi(sozcukler(text))
            self.baslik_onbellek[(src, doc)] = baslik_metni(text)

    def kume(self, src, doc):
        if (src, doc) not in self.kume_onbellek:
            row = self.con.execute("SELECT text FROM metin WHERE source=? AND document_id=?", [src, doc]).fetchone()
            self.kume_onbellek[(src, doc)] = dizi_kumesi(sozcukler(row[0] if row else ""))
            self.baslik_onbellek[(src, doc)] = baslik_metni(row[0] if row else "")
        return self.kume_onbellek[(src, doc)]

    def baslik_yukle(self, iste):
        """{(kaynak, belge)} başlıklarını tek sorguda önbelleğe alır."""
        iste = sorted(x for x in iste if x not in self.baslik_onbellek)
        if not iste:
            return
        self.con.execute("CREATE OR REPLACE TEMP TABLE bi(source VARCHAR, document_id VARCHAR)")
        self.con.executemany("INSERT INTO bi VALUES (?,?)", iste)
        for src, doc, text in self.con.execute(
                "SELECT m.source, m.document_id, m.text FROM metin m JOIN bi USING (source, document_id)").fetchall():
            self.baslik_onbellek[(src, doc)] = baslik_metni(text)

    def baslik(self, src, doc):
        if (src, doc) not in self.baslik_onbellek:
            row = self.con.execute("SELECT text FROM metin WHERE source=? AND document_id=?", [src, doc]).fetchone()
            self.baslik_onbellek[(src, doc)] = baslik_metni(row[0] if row else "")
        return self.baslik_onbellek[(src, doc)]

    def eslestir(self, r, simdi):
        o = {"id": r["id"], "match_status": None, "match_confidence": None, "match_method": None,
             "bedesten_document_id": None, "bedesten_url": None, "verified_at": None, "source_dataset": None,
             "aday_document_ids": [], "neden": None}
        k, neden = kayit_anahtari(r)
        if not k:
            o.update(match_status=neden, neden=neden)
            return o
        src = k[0]
        ad = self.adaylar(k)
        esas = r.get("esas")
        tarih = r.get("tarih")
        if esas:
            en = karar_no(esas)
            ad = [x for x in ad if karar_no(x[2]) == en]
        if tarih:
            ad = [x for x in ad if (x[4] or "") == tarih]
        o["source_dataset"] = KAYNAK
        o["match_method"] = YONTEM
        if not ad:
            o.update(match_status="eslesmedi", neden="veri_setinde_anahtar_yok" if not (esas or tarih)
                     else "esas_veya_tarih_uyusmuyor")
            return o
        ids = [x[0] for x in ad]
        o["aday_document_ids"] = ids
        if len(ad) > 1:
            o.update(match_status="cok_aday", neden=f"{len(ad)}_aday")
            return o
        doc = ad[0]
        metin = r.get("metin") or ""
        if not metin.strip():
            o.update(match_status="olasi", match_confidence=0.5, neden="alinti_yok")
            return o
        oran, sozcuk = kapsama(metin, self.kume(src, doc[0]))
        o["match_confidence"] = round(oran, 3)
        if oran >= ESIK_KESIN and sozcuk >= EN_AZ_SOZCUK:
            bneden = baslik_denetle(r, self.baslik(src, doc[0]))
            if bneden:
                o.update(match_status="olasi", neden=bneden, aday_document_ids=[doc[0]])
                return o
            o.update(match_status="kesin", bedesten_document_id=doc[0], bedesten_url=URL_BICIMI.format(doc[0]),
                     verified_at=simdi, neden=None, aday_document_ids=[],
                     dogrulanan={"daire": doc[1], "esas": doc[2] or None, "karar": doc[3],
                                 "tarih": doc[4] or None})
        elif oran >= ESIK_OLASI or sozcuk < EN_AZ_SOZCUK:
            o.update(match_status="olasi", neden="kisa_alinti" if sozcuk < EN_AZ_SOZCUK else "alinti_kismen_uyuyor")
        else:
            o.update(match_status="eslesmedi", neden="alinti_uyusmuyor")
        return o


# ----------------------------------------------------------------------------- canlı Bedesten doğrulaması

class GunlukTavanDoldu(Exception):
    pass


class Canli:
    """Tek iş parçacıklı, yavaş, kibar istemci: en az `aralik` saniye arayla, 429/5xx'te üstel geri çekilme
    ve kalıcı yavaşlama, günlük tavan. Her istek durum dizinindeki günlüğe yazılır. Önbellek: canli.jsonl."""

    def __init__(self, durum, aralik=16.0, gunluk_tavan=1000):
        self.durum = Path(durum)
        self.durum.mkdir(parents=True, exist_ok=True)
        self.aralik = max(16.0, float(aralik))   # 16 sn'den hızlı asla
        self.tavan = int(gunluk_tavan)
        self.son = 0.0
        self.sayac_yol = self.durum / "canli_sayac.json"
        self.gunluk = self.durum / "canli_istekler.log"
        self.onbellek_yol = self.durum / "canli.jsonl"
        self.onbellek = {}
        if self.onbellek_yol.exists():
            for line in self.onbellek_yol.open(encoding="utf-8"):
                o = json.loads(line)
                self.onbellek[o["document_id"]] = o
        self.sayac = json.loads(self.sayac_yol.read_text()) if self.sayac_yol.exists() else {}
        import sqlite3
        # resmî metin yalnız yerelde (depo dışında) tutulur: aynı belge için ikinci istek atılmaz
        self.metin_db = sqlite3.connect(str(self.durum / "canli_metin.sqlite"))
        self.metin_db.execute("CREATE TABLE IF NOT EXISTS metin(doc TEXT PRIMARY KEY, text TEXT)")
        if self.sayac.get("aralik"):
            self.aralik = max(self.aralik, float(self.sayac["aralik"]))

    def yerel_metin(self, doc):
        row = self.metin_db.execute("SELECT text FROM metin WHERE doc=?", (doc,)).fetchone()
        return row[0] if row else None

    def bugun(self):
        return datetime.date.today().isoformat()

    ayrilan = 0   # örnek kapısı için ayrılan istek hakkı

    def kalan(self):
        return self.tavan - self.ayrilan - int(self.sayac.get(self.bugun(), 0))

    def _say(self, ne, doc, kod):
        self.sayac[self.bugun()] = int(self.sayac.get(self.bugun(), 0)) + 1
        self.sayac["toplam"] = int(self.sayac.get("toplam", 0)) + 1
        self.sayac["aralik"] = self.aralik
        self.sayac_yol.write_text(json.dumps(self.sayac, indent=1))
        with self.gunluk.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{ne}\t{doc}\t{kod}\n")

    def getir(self, doc):
        import urllib.request
        import urllib.error
        import base64
        bekleme = 120
        for deneme in range(8):
            if self.kalan() <= 0:
                raise GunlukTavanDoldu()
            gecen = time.time() - self.son
            if gecen < self.aralik:
                time.sleep(self.aralik - gecen)
            body = json.dumps({"data": {"documentId": doc}, "applicationName": "UyapMevzuat"}).encode()
            req = urllib.request.Request(ENDPOINT, data=body, headers={
                "Content-Type": "application/json", "AdaletApplicationName": "UyapMevzuat",
                "Origin": "https://mevzuat.adalet.gov.tr", "Referer": "https://mevzuat.adalet.gov.tr/",
                "User-Agent": "karar-derlemeleri-eslestirme/1.0 (yavas; tek istek)"})
            self.son = time.time()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    j = json.load(resp)
                self._say("getDocumentContent", doc, 200)
            except urllib.error.HTTPError as e:
                self._say("getDocumentContent", doc, e.code)
                if e.code == 429 or e.code >= 500:
                    if e.code == 429:
                        self.aralik = min(60.0, self.aralik + 4)   # kalıcı yavaşlama
                    print(f"  [canlı] HTTP {e.code}; {bekleme} sn bekleniyor, aralık {self.aralik:.0f} sn", flush=True)
                    time.sleep(bekleme)
                    bekleme = min(bekleme * 2, 1800)
                    continue
                return None, f"http_{e.code}"
            except Exception as e:  # ağ hatası
                self._say("getDocumentContent", doc, type(e).__name__)
                print(f"  [canlı] ağ hatası {type(e).__name__}; {bekleme} sn", flush=True)
                time.sleep(bekleme)
                bekleme = min(bekleme * 2, 1800)
                continue
            d = (j or {}).get("data") or {}
            c = d.get("content") or ""
            try:
                t = base64.b64decode(c).decode("utf-8", "replace")
            except Exception:
                t = c
            if not t.strip():
                return None, "bos_icerik"
            return t, None
        return None, "yeniden_deneme_bitti"

    def dogrula(self, doc, r):
        """Belgenin resmî metni künyeyle ve alıntıyla uyuşuyor mu? Sonuç önbelleğe yazılır (metin yazılmaz)."""
        key = f"{doc}|{r['id']}"
        if key in self.onbellek:
            return self.onbellek[key]
        t = self.yerel_metin(doc)
        hata = None
        if t is None:
            t, hata = self.getir(doc)
            if t is not None:
                self.metin_db.execute("INSERT OR REPLACE INTO metin VALUES (?,?)", (doc, t))
                self.metin_db.commit()
        o = {"document_id": key, "doc": doc, "kayit": r["id"], "zaman": datetime.datetime.now().isoformat(timespec="seconds")}
        if hata:
            o.update(ok=False, neden=hata)
        else:
            import html as _html
            duz = _html.unescape(re.sub(r"<[^>]+>", " ", t))
            bas = " ".join(katla(duz[:1500]).split())
            y, n = karar_no(r["karar"])
            no_ok = re.search(rf"\b{y}\s*/\s*0*{n}\b", bas) is not None
            d_ok = daire_basta(r, bas)
            oran, _ = kapsama(r.get("metin") or "", dizi_kumesi(sozcukler(duz)))
            esas = re.search(r"(\d{4})\s*/\s*(\d+)\s*e\b", bas)
            o.update(ok=bool(no_ok and d_ok and oran >= ESIK_KESIN), karar_no_ok=no_ok, daire_ok=d_ok,
                     kapsama=round(oran, 3), esas=f"{esas[1]}/{int(esas[2])}" if esas else None,
                     baslik=" ".join(duz.split())[:160])
        self.onbellek[key] = o
        with self.onbellek_yol.open("a", encoding="utf-8") as f:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
        return o


_SIRA = {1: "birinci", 2: "ikinci", 3: "ucuncu", 4: "dorduncu", 5: "besinci", 6: "altinci", 7: "yedinci",
         8: "sekizinci", 9: "dokuzuncu", 10: "onuncu", 11: "onbirinci", 12: "onikinci", 13: "onucuncu",
         14: "ondorduncu", 15: "onbesinci", 16: "onaltinci", 17: "onyedinci"}


# ----------------------------------------------------------------------------- metin başlığı denetimi
# hukuk prosu kuralı (2026-11-27): bağlantı yalnız metnin başlığındaki karar numarası künyeyle tutarsa verilir.
#   * başlıkta açık bir karar no var ve künyedeki değil  -> 'olasi', neden metin_numarasi_farkli (tüm mahkemeler)
#   * BAM metninin başlığında karar no yok/karartılmış    -> 'olasi', neden metinde_karar_no_yok
BASLIK_BOY = 1500
_BASLIK_KN = re.compile(r"karar\s*(?:no|n|numarasi|sayisi)\b\s*[:.]?\s*(\d{4})\s*/\s*0*(\d+)(?!\d)")
_BASLIK_EK = re.compile(r"(?<!\d)(\d{4})\s*/\s*(?:\d+\s*-\s*)?0*(\d+)\s*e(?:sas)?\b\s*\.?\s*[,;-]?\s*(\d{4})\s*/\s*0*(\d+)(?!\d)"
                        r"\s*k(?:arar)?\b")
_BASLIK_K = re.compile(r"(?<![\d/])(\d{4})\s*/\s*0*(\d+)(?!\d)\s*k\s*\.")   # '2010/12156 K.' (esas yazımı bozuk olsa da)


def baslik_metni(text):
    """Tam metnin ilk BASLIK_BOY karakteri; etiketsiz, katlanmış, tek boşluklu (örnek kapısıyla aynı bölge)."""
    import html as _html
    duz = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", str(text or ""))).split())
    return " ".join(katla(duz[:BASLIK_BOY]).split())


def baslik_karar_nolari(bas, tur):
    """Başlıkta açıkça yazan karar numaraları {(yıl, no)}. BAM'de 'incelenen karar' bölümünden öncesi."""
    on = bas.split("incelenen")[0] if tur == "bam" else bas
    k = {(int(m[1]), int(m[2])) for m in _BASLIK_KN.finditer(on)}
    k |= {(int(m[3]), int(m[4])) for m in _BASLIK_EK.finditer(on)}
    k |= {(int(m[1]), int(m[2])) for m in _BASLIK_K.finditer(on)}
    return on, k


def baslik_denetle(r, bas):
    """None: başlıktaki karar no künyeyle tutuyor (ya da Yargıtay/Danıştay'da çelişki yok); aksi hâlde neden."""
    kn = karar_no(r.get("karar"))
    if not kn:
        return "metinde_karar_no_yok"
    on, acik = baslik_karar_nolari(bas, r.get("tur"))
    if acik:
        return None if kn in acik else "metin_numarasi_farkli"
    if re.search(rf"(?<!\d){kn[0]}\s*/\s*0*{kn[1]}(?!\d)", on):
        return None
    return "metinde_karar_no_yok" if r.get("tur") == "bam" else None


def daire_basta(r, bas):
    b = birim_derleme(r) or ""
    m = re.fullmatch(r"(?:(.+)-bam-)?(\d+)(hd|cd|d)", b)
    if b == "hgk":
        return "hukuk genel kurulu" in bas
    if b == "cgk":
        return "ceza genel kurulu" in bas
    if b in ("iddk",):
        return "dava daireleri kurulu" in bas and "idar" in bas
    if b == "vddk":
        return "vergi dava daireleri kurulu" in bas
    if not m:
        return False
    sehir, n, t = m[1], int(m[2]), m[3]
    if t == "d":
        return re.search(rf"\b{n}\s*\.\s*daire", bas) is not None or (_SIRA.get(n, "#") + " daire") in bas.replace(" ", " ")
    ad = "hukuk" if t == "hd" else "ceza"
    ok = re.search(rf"\b{n}\s*\.\s*{ad} dairesi", bas) is not None
    if sehir:
        ok = ok and sehir.replace("-", " ") in bas and "bolge adliye" in bas
    return ok


# ----------------------------------------------------------------------------- toplu çalıştırma

DEPO_ALANLARI = ["id", "match_status", "match_confidence", "match_method", "bedesten_document_id", "bedesten_url",
                 "verified_at", "source_dataset", "neden", "bedesten_kontrol"]
YONTEM_MRFG = "mrfg_id"


def depo_satiri(r, o):
    """Yerel sonuç -> depoya yazılacak satır. 'kesin' satırda kimlik veri setinin document_id'sidir
    (Bedesten belge kimliğiyle aynı kimlik uzayı); verified_at yalnız canlı kontrol edilen örneklerde dolar."""
    s = dict.fromkeys(DEPO_ALANLARI)
    s.update(id=r["id"], match_status=o["match_status"], match_confidence=o["match_confidence"],
             source_dataset=o["source_dataset"], neden=o["neden"])
    if o["match_status"] == "kesin":
        s.update(match_method=YONTEM_MRFG, bedesten_document_id=o["bedesten_document_id"],
                 bedesten_url=URL_BICIMI.format(o["bedesten_document_id"]))
    elif o["match_status"] not in ("kapsam_disi", "hatali_kunye"):
        s["match_method"] = YONTEM
    return s


def _git(args, check=True):
    p = subprocess.run(["git", "-C", str(ROOT)] + args, capture_output=True, text=True, encoding="utf-8")
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()[:500]}")
    return p


def _push(durum_yol, ck):
    for deneme in range(5):
        p = _git(["push", "origin", "HEAD:main"], check=False)   # asla --force
        if p.returncode == 0:
            ck["son_push"] = _git(["rev-parse", "--short", "HEAD"]).stdout.strip()
            ck["push_hatasi"] = None
            return True
        ck["push_hatasi"] = p.stderr.strip()[-300:]
        print(f"  push başarısız ({deneme+1}/5): {ck['push_hatasi']}", flush=True)
        time.sleep(min(60 * 2 ** deneme, 1800))
    return False


def ilerleme_yaz(kayitlar, ck):
    """Bütün parti dosyalarından istatistik; PROGRESS.md + ilerleme.json."""
    meta = {r["id"]: (r["tur"], r["kod"]) for r in kayitlar}
    durum = Counter()
    tur = defaultdict(Counter)
    der = defaultdict(Counter)
    for p in sorted((ROOT / BB.ESLESME_DIZIN).glob("parti-*.jsonl")):
        for line in p.open(encoding="utf-8"):
            o = json.loads(line)
            t, kod = meta[o["id"]]
            durum[o["match_status"]] += 1
            if o["neden"]:
                durum["neden:" + o["neden"]] += 1
            if o.get("bedesten_kontrol"):
                durum["kontrol:" + o["bedesten_kontrol"]] += 1
            tur[t][o["match_status"]] += 1
            der[kod][o["match_status"]] += 1
    islenen = sum(v for k, v in durum.items() if ":" not in k)
    toplam = len(kayitlar)
    j = {"toplam_kunye": toplam, "islenen": islenen, "yuzde": round(100 * islenen / toplam, 2),
         "baglanti_mrfg_id": durum["kesin"], "bedesten_kontrol_edilen": sum(v for k, v in durum.items() if k.startswith("kontrol:")),
         "bedesten_kontrol": {k[8:]: v for k, v in sorted(durum.items()) if k.startswith("kontrol:")},
         "olasi": durum["olasi"], "eslesmedi": durum["eslesmedi"], "cok_aday": durum["cok_aday"],
         "hatali_kunye": durum["hatali_kunye"], "kapsam_disi": durum["kapsam_disi"],
         "nedenler": {k[6:]: v for k, v in sorted(durum.items()) if k.startswith("neden:")},
         "tur": {k: dict(v) for k, v in sorted(tur.items())}, "derleme": {k: dict(v) for k, v in sorted(der.items())},
         "son_checkpoint": ck.get("son_checkpoint"), "son_commit": ck.get("son_commit"),
         "son_push": ck.get("son_push"), "kaynak": KAYNAK, "url_bicimi": URL_BICIMI.format("{documentId}")}
    (ROOT / "veri/bedesten/ilerleme.json").write_text(json.dumps(j, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                                     encoding="utf-8")

    def oran(c):
        n = sum(c.values())
        return f"{c['kesin']:,} / {n:,} (%{100 * c['kesin'] / n:.1f})" if n else "-"
    L = ["# Bedesten eşleştirme ilerlemesi", "",
         "Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar "
         "yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, "
         "alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de "
         "kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten "
         "`getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).", "",
         "| | sayı |", "|---|---:|",
         f"| Toplam künye | {toplam:,} |", f"| İşlenen | {islenen:,} (%{j['yuzde']}) |",
         f"| Bağlantılı (mrfg_id) | {j['baglanti_mrfg_id']:,} |",
         f"| Bedesten'de kontrol edilen (örnek) | {j['bedesten_kontrol_edilen']:,} "
         f"({', '.join(f'{k} {v}' for k, v in j['bedesten_kontrol'].items()) or '-'}) |",
         f"| Olası (bağlantı yok) | {j['olasi']:,} |", f"| Eşleşmeyen | {j['eslesmedi']:,} |",
         f"| Birden çok aday | {j['cok_aday']:,} |", f"| Hatalı/eksik künye | {j['hatali_kunye']:,} |",
         f"| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | {j['kapsam_disi']:,} |",
         "", "## Nedenler", "", "| neden | sayı |", "|---|---:|"]
    L += [f"| {k} | {v:,} |" for k, v in j["nedenler"].items()]
    L += ["", "## Mahkeme türüne göre (bağlantılı / işlenen)", "", "| tür | bağlantılı |", "|---|---:|"]
    L += [f"| {k} | {oran(v)} |" for k, v in sorted(tur.items())]
    L += ["", "## Derlemeye göre (bağlantılı / işlenen)", "", "| derleme | bağlantılı |", "|---|---:|"]
    L += [f"| {k} | {oran(v)} |" for k, v in sorted(der.items())]
    L += ["", f"Son checkpoint: {ck.get('son_checkpoint') or '-'}  ", f"Son commit: {ck.get('son_commit') or '-'}  ",
          f"Son push: {ck.get('son_push') or '-'}", ""]
    (ROOT / "veri/bedesten/PROGRESS.md").write_text("\n".join(L), encoding="utf-8")
    return j


def _tarih_bicimleri(iso):
    y, m, d = iso.split("-")
    return {f"{d}.{m}.{y}", f"{d}/{m}/{y}", f"{d}-{m}-{y}", f"{int(d)}.{int(m)}.{y}"}


def ornek_kapisi(no, satirlar, by_id, canli, yerel_bilgi, tohum=None):
    """20 rastgele bağlantının Bedesten'den canlı kontrolü (önbelleksiz). Daire, karar no, esas, tarih
    künyeyle (künyede yoksa yerel aday satırıyla) ve alıntı resmî metinle karşılaştırılır.
    BAM metninde numaralar '...' ile karartılmışsa: alıntı örtüşmesi >= 0.95 ve mahkeme/daire
    çelişmiyorsa geçer, 'numara_karartilmis' olarak işaretlenir. -> (geçti mi, rapor)"""
    import html as _html
    adaylar = [s for s in satirlar if s["match_status"] == "kesin" and s["match_method"] == YONTEM_MRFG]
    secim = sorted(random.Random(1000 + no if tohum is None else tohum).sample(adaylar, min(20, len(adaylar))), key=lambda s: s["id"])
    rapor, gecti = [], True
    for s in secim:
        r = by_id[s["id"]]
        doc = s["bedesten_document_id"]
        while True:
            try:
                t, hata = canli.getir(doc)
                break
            except GunlukTavanDoldu:
                _gece_yarisina_kadar_bekle()
        k = {"id": r["id"], "doc": doc, "kunye": r["kunye"], "zaman": datetime.datetime.now().isoformat(timespec="seconds")}
        if hata:
            k.update(sonuc="UYUSMADI", sorun=[hata], uyari=[], baslik="")
            rapor.append(k)
            gecti = False
            continue
        duz = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", t)).split())
        bas = " ".join(katla(duz[:1500]).split())
        oran, _ = kapsama(r.get("metin") or "", dizi_kumesi(sozcukler(duz)))
        y, n = karar_no(r["karar"])
        sorun, uyari = [], []
        kararti = r["tur"] == "bam" and re.search(r"(karar no|esas-karar no|esas - karar no)\s*:?\s*\.{3,}", bas)
        if not re.search(rf"\b{y}\s*/\s*0*{n}\b", bas):
            (uyari if kararti else sorun).append("karar_no")
        if not daire_basta(r, bas):
            m = re.fullmatch(r"(.+)-bam-\d+[hc]d", birim_derleme(r) or "")
            if kararti and m and m[1].replace("-", " ") in bas and "bolge adliye" in bas:
                uyari.append("daire_no")
            else:
                sorun.append("mahkeme/daire")
        if kararti:
            uyari.append("numara_karartilmis")
            if oran < 0.95:
                sorun.append(f"alinti_{oran:.2f}")
        elif oran < ESIK_KESIN:
            sorun.append(f"alinti_{oran:.2f}")
        yerel = yerel_bilgi(r, doc)
        esas = r.get("esas") or (yerel[0] if yerel else None)
        if esas and not kararti:
            e = karar_no(esas)
            if not e or not re.search(rf"\b{e[0]}\s*/\s*0*{e[1]}\b", bas):
                (sorun if r.get("esas") else uyari).append("esas")
        tarih = r.get("tarih") or (yerel[1] if yerel else None)
        if tarih and re.fullmatch(r"\d{4}-\d{2}-\d{2}", tarih) and not any(b in duz for b in _tarih_bicimleri(tarih)):
            (sorun if r.get("tarih") else uyari).append("tarih_metinde_yok")
        if sorun:
            gecti = False
        k.update(sonuc="UYUSMADI" if sorun else ("TAMAM_ISARETLI" if kararti else "TAMAM"), sorun=sorun,
                 uyari=uyari, kapsama=round(oran, 3), baslik=duz[:150])
        rapor.append(k)
    return gecti, rapor


def ornek_yaz(no, by_id, rapor, gecti):
    L = [f"# Parti {no:02d}: rastgele {len(rapor)} bağlantının Bedesten kontrolü", "",
         "Bağlantıların kimliği veri setinin `document_id` değeridir (mrfg_id). Bu örnekler push'tan önce "
         "Bedesten `getDocumentContent` ile canlı alındı; mahkeme/daire, karar no, esas ve tarih künyeyle "
         "(künyede yoksa yerel aday satırıyla) ve alıntı resmî metinle karşılaştırıldı. `uyarı` push'u durdurmaz; "
         "`sorun` durdurur.", "",
         f"**Kapı sonucu: {'GEÇTİ' if gecti else 'GEÇMEDİ'}** "
         f"({sum(k['sonuc'] != 'UYUSMADI' for k in rapor)}/{len(rapor)}).", ""]
    for i, k in enumerate(rapor, 1):
        r = by_id[k["id"]]
        L += [f"{i}. **{r['kunye']}** — `{r['dosya']}:{r['satir']}` (`{k['id']}`)",
              f"   - Bağlantı: {URL_BICIMI.format(k['doc'])}",
              f"   - Bedesten başlığı: {k.get('baslik', '')[:150]}",
              f"   - Sonuç: {k['sonuc']}; alıntı örtüşmesi {k.get('kapsama', '-')}"
              + (f"; sorun: {', '.join(k['sorun'])}" if k["sorun"] else "")
              + (f"; uyarı: {', '.join(k['uyari'])}" if k["uyari"] else "") + f"; {k['zaman']}", ""]
    yol = ROOT / f"veri/bedesten/ornekler/parti-{no:02d}.md"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("\n".join(L), encoding="utf-8")
    return yol


def _gece_yarisina_kadar_bekle():
    simdi = datetime.datetime.now()
    yarin = (simdi + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    print(f"  günlük tavan doldu; {yarin:%Y-%m-%d %H:%M} saatine kadar bekleniyor", flush=True)
    time.sleep(max(60, (yarin - simdi).total_seconds()))


YB_YOL = "veri/bedesten/yeniden_baglanan.jsonl"


def yeniden_baglananlar():
    """id -> kayıt: metin başlığı künyeyle çelişen eşleşmelerin yerine, başlığı künyeyle tutan TEK mrfg kimliği."""
    p = ROOT / YB_YOL
    d = {}
    if p.exists():
        for line in p.open(encoding="utf-8"):
            x = json.loads(line)
            d[x["id"]] = x
    return d


def _parti_satirlari(m, no, kayitlar, boy):
    yol = ROOT / BB.ESLESME_DIZIN / f"parti-{no:02d}.jsonl"
    if yol.exists():
        return [json.loads(x) for x in yol.open(encoding="utf-8")], True
    parca = kayitlar[(no - 1) * boy: no * boy]
    m.metinleri_yukle(parca)
    return [depo_satiri(r, m.eslestir(r, None)) for r in parca], False


def yeniden_ara(a):
    """metin_numarasi_farkli kayıtları için doğru kararı veri setinde arar. Bağlanma koşulu (hepsi): aynı birimde,
    metin başlığında açık karar no künyedekiyle aynı, daire başlıkta tutuyor, künyedeki esas/tarih metinde geçiyor,
    alıntı örtüşmesi >= ESIK_KESIN ve bu koşulları sağlayan TEK belge var. Sonuç: veri/bedesten/yeniden_baglanan.jsonl"""
    m = Eslestirici(a.db, threads=a.threads, mem=a.bellek)
    kayitlar = list(derleme_kayitlari())
    by_id = {r["id"]: r for r in kayitlar}
    hedef = []
    for no in a.partiler:
        satirlar, _ = _parti_satirlari(m, no, kayitlar, a.parti_boyu)
        for s in satirlar:
            if s["neden"] == "metin_numarasi_farkli" or (s["id"] in yeniden_baglananlar()):
                r = by_id[s["id"]]
                k, _ = kayit_anahtari(r)
                eski = [x[0] for x in m.adaylar(k)]
                hedef.append((r, k, eski, no))
    print(f"aranacak kayıt: {len(hedef)}")
    sonuc, rapor = [], []
    veri = Path(a.veri)
    for src in sorted({k[0] for _, k, _, _ in hedef}):
        hh = [(r["id"], k[1], rf"(^|[^0-9]){k[2][0]}\s*/\s*0*{k[2][1]}([^0-9]|$)") for r, k, _, _ in hedef if k[0] == src]
        m.con.execute("CREATE OR REPLACE TEMP TABLE h(id VARCHAR, birim VARCHAR, pat VARCHAR)")
        m.con.executemany("INSERT INTO h VALUES (?,?,?)", hh)
        files = "[" + ",".join("'" + str(x).replace("\\", "/") + "'" for x in sorted((veri / "data" / src).glob("*.parquet"))) + "]"
        bul = defaultdict(list)
        for hid, doc, text in m.con.execute(f"""
                SELECT h.id, p.document_id, p.text FROM h
                JOIN karar k ON k.source = '{src}' AND k.birim = h.birim
                JOIN read_parquet({files}) p ON p.source = k.source AND p.document_id = k.document_id
                WHERE regexp_matches(substr(p.text, 1, {BASLIK_BOY * 2}), h.pat)""").fetchall():
            bul[hid].append((doc, text))
        for r, k, eski, no in hedef:
            if k[0] != src:
                continue
            uygun = []
            for doc, text in bul.get(r["id"], []):
                if doc in eski:
                    continue
                bas = baslik_metni(text)
                _, acik = baslik_karar_nolari(bas, r.get("tur"))
                duz = " ".join(re.sub(r"<[^>]+>", " ", text).split())
                ok = k[2] in acik and daire_basta(r, bas)
                e = karar_no(r.get("esas"))
                if ok and e:
                    ok = re.search(rf"(?<!\d){e[0]}\s*/\s*0*{e[1]}(?!\d)", bas) is not None
                if ok and r.get("tarih") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["tarih"]):
                    ok = any(b in duz for b in _tarih_bicimleri(r["tarih"]))
                oran, sozcuk = kapsama(r.get("metin") or "", dizi_kumesi(sozcukler(text)))
                if ok and oran >= ESIK_KESIN and sozcuk >= EN_AZ_SOZCUK:
                    uygun.append((doc, round(oran, 3)))
            rapor.append({"id": r["id"], "parti": no, "kunye": r["kunye"], "eski": eski,
                          "metinde_aranan_bulunan": len(bul.get(r["id"], [])), "uygun": uygun})
            if len(uygun) == 1:
                sonuc.append({"id": r["id"], "eski_document_id": eski[0] if len(eski) == 1 else None,
                              "yeni_document_id": uygun[0][0], "kural": "baslik_karar_no+daire+tek_aday+alinti",
                              "source_dataset": KAYNAK})
    (ROOT / YB_YOL).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sonuc), encoding="utf-8")
    Path(a.durum, "yeniden_ara_rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"yeniden bağlanacak: {len(sonuc)} / {len(hedef)}; rapor {Path(a.durum, 'yeniden_ara_rapor.json')}")


def baslik_duzelt(a):
    """Yazılmış partilerde 'kesin' mrfg_id bağlantılarına başlık kuralını uygular, yeniden bağlananları işler,
    md/dizin/veri dosyalarını günceller ve bütünlüğü denetler. Commit/push yapmaz."""
    m = Eslestirici(a.db, threads=a.threads, mem=a.bellek)
    by_id = {r["id"]: r for r in derleme_kayitlari()}
    yb = yeniden_baglananlar()
    say = Counter()
    t0 = time.time()
    iste = set()
    for no in a.partiler:
        for x in (ROOT / BB.ESLESME_DIZIN / f"parti-{no:02d}.jsonl").open(encoding="utf-8"):
            s = json.loads(x)
            if s["match_status"] == "kesin" and s["match_method"] == YONTEM_MRFG:
                k, _ = kayit_anahtari(by_id[s["id"]])
                iste.add((k[0], s["bedesten_document_id"]))
    m.baslik_yukle(iste)
    print(f"başlıklar yüklendi: {len(iste):,} ({time.time() - t0:.0f} sn)", flush=True)
    for no in a.partiler:
        yol = ROOT / BB.ESLESME_DIZIN / f"parti-{no:02d}.jsonl"
        satirlar = [json.loads(x) for x in yol.open(encoding="utf-8")]
        for s in satirlar:
            x = yb.get(s["id"])
            if s["match_status"] == "kesin" and s["match_method"] == YONTEM_MRFG and not (
                    x and s["bedesten_document_id"] == x["yeni_document_id"]):
                r = by_id[s["id"]]
                k, _ = kayit_anahtari(r)
                neden = baslik_denetle(r, m.baslik(k[0], s["bedesten_document_id"]))
                if neden:
                    say[f"{neden}{'_ornek' if s.get('bedesten_kontrol') else ''}"] += 1
                    say[f"parti{no:02d}_{neden}"] += 1
                    s.update(match_status="olasi", match_method=YONTEM, bedesten_document_id=None, bedesten_url=None,
                             verified_at=None, neden=neden, bedesten_kontrol=None)
            if x and s["match_status"] == "olasi" and s["neden"] == "metin_numarasi_farkli":
                s.update(match_status="kesin", match_method=YONTEM_MRFG, bedesten_document_id=x["yeni_document_id"],
                         bedesten_url=URL_BICIMI.format(x["yeni_document_id"]), verified_at=None, neden=None)
                say["yeniden_baglandi"] += 1
                say[f"parti{no:02d}_yeniden_baglandi"] += 1
        yol.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in satirlar), encoding="utf-8")
    print(f"partiler yazıldı ({time.time() - t0:.0f} sn)", flush=True)
    BB.uygula(str(ROOT), sessiz=True)
    print(f"uygulandı ({time.time() - t0:.0f} sn)", flush=True)
    hatalar = BB.denetle(str(ROOT))
    if hatalar:
        raise SystemExit("bütünlük denetimi başarısız: " + "; ".join(hatalar[:5]))
    ck_yol = Path(a.durum) / "checkpoint.json"
    ck = json.loads(ck_yol.read_text())
    for no in a.partiler:
        yol = ROOT / BB.ESLESME_DIZIN / f"parti-{no:02d}.jsonl"
        n = sum(1 for x in yol.open(encoding="utf-8") if json.loads(x)["match_status"] == "kesin")
        if str(no) in ck.get("partiler", {}):
            ck["partiler"][str(no)].update(baglanti=n, baglantisiz=ck["partiler"][str(no)]["islenen"] - n)
    ilerleme_yaz(list(derleme_kayitlari()), ck)
    ck_yol.write_text(json.dumps(ck, ensure_ascii=False, indent=1))
    print(json.dumps(dict(sorted(say.items())), ensure_ascii=False, indent=1))


def calistir(a):
    durum = Path(a.durum)
    durum.mkdir(parents=True, exist_ok=True)
    kilit = durum / "calisiyor.kilit"
    try:
        fd = os.open(str(kilit), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        raise SystemExit(f"başka bir çalıştırma sürüyor ya da yarım kaldı: {kilit} (süreç yoksa silin)")
    import atexit
    atexit.register(lambda: kilit.exists() and kilit.unlink())
    if not _git(["config", "user.email"], check=False).stdout.strip():
        raise SystemExit("git user.email tanımlı değil")
    ck_yol = durum / "checkpoint.json"
    ck = json.loads(ck_yol.read_text()) if ck_yol.exists() else {"tamamlanan": [], "push_bekleyen": []}

    def ck_kaydet():
        tmp = ck_yol.with_suffix(".tmp")
        tmp.write_text(json.dumps(ck, ensure_ascii=False, indent=1))
        os.replace(tmp, ck_yol)

    if ck.get("durduruldu") and not a.parti:
        raise SystemExit("önceki çalıştırma durduruldu: " + ck["durduruldu"])
    kayitlar = list(derleme_kayitlari())
    boy = a.parti_boyu
    parti_sayisi = (len(kayitlar) + boy - 1) // boy
    m = Eslestirici(a.db, threads=a.threads, mem=a.bellek)
    canli = Canli(durum, aralik=a.aralik, gunluk_tavan=a.gunluk_tavan)
    partiler = [a.parti] if a.parti else [b for b in range(1, parti_sayisi + 1) if b not in ck["tamamlanan"]]
    beklet = set(a.push_beklet or []) - set(ck.get("onaylanan", []))
    elle = {}
    ep = ROOT / "veri/bedesten/dogrulanmis.jsonl"
    if ep.exists():
        for line in ep.open(encoding="utf-8"):
            x = json.loads(line)
            if x.get("status") == "official_verified":
                elle[x["id"]] = x
    for no in partiler:
        bas, son = (no - 1) * boy, min(no * boy, len(kayitlar))
        parca = kayitlar[bas:son]
        by_id = {r["id"]: r for r in kayitlar}
        t0 = time.time()
        print(f"== parti {no:02d}/{parti_sayisi}: kayıt {bas + 1:,}-{son:,}", flush=True)
        m.metinleri_yukle(parca)
        yerel = [m.eslestir(r, None) for r in parca]
        satirlar = [depo_satiri(r, o) for r, o in zip(parca, yerel)]
        for s in satirlar:
            x = elle.get(s["id"])
            if x:   # elle resmî kaynaktan doğrulanmış pilot kayıt
                s.update(match_status="kesin", match_confidence=1.0, match_method=x["method"],
                         bedesten_document_id=x["bedesten_document_id"], bedesten_url=x["bedesten_url"],
                         verified_at=x["checked_at"], source_dataset=x["source"], neden=None,
                         bedesten_kontrol="elle")
        yb = yeniden_baglananlar()
        for s in satirlar:
            x = yb.get(s["id"])
            if x and s["match_status"] == "olasi" and s["neden"] == "metin_numarasi_farkli":
                s.update(match_status="kesin", match_method=YONTEM_MRFG, bedesten_document_id=x["yeni_document_id"],
                         bedesten_url=URL_BICIMI.format(x["yeni_document_id"]), verified_at=None, neden=None)
        st = Counter(s["match_status"] for s in satirlar)
        print(f"  yerel: {dict(st)} ({time.time() - t0:.0f} sn)", flush=True)
        # push öncesi canlı örnek kapısı (20 rastgele bağlantı, önbelleksiz, >= 16 sn arayla)
        gecti, rapor = ornek_kapisi(no, satirlar, by_id, canli, m.yerel_bilgi, tohum=a.ornek_tohum)
        (durum / f"kapi-parti-{no:02d}.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
        sonuc = {k["id"]: k for k in rapor}
        for s in satirlar:
            k = sonuc.get(s["id"])
            if k:
                s["bedesten_kontrol"] = {"TAMAM": "tutar", "TAMAM_ISARETLI": "tutar_numara_karartilmis",
                                         "UYUSMADI": "tutmadi"}[k["sonuc"]]
                if k["sonuc"] != "UYUSMADI":
                    s["verified_at"] = k["zaman"][:10]
        print(f"  örnek kapısı: {'GEÇTİ' if gecti else 'GEÇMEDİ'} "
              f"({sum(k['sonuc'] != 'UYUSMADI' for k in rapor)}/{len(rapor)})", flush=True)
        if not gecti:
            # bağlantı eklemeyi durdur: bu partinin sonuçları depoya yazılmaz, yerelde saklanır
            (durum / f"parti-{no:02d}-DURDU.jsonl").write_text(
                "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in satirlar), encoding="utf-8")
            ck["durduruldu"] = f"parti {no:02d} örnek kapısı geçmedi; ayrıntı {durum / f'kapi-parti-{no:02d}.json'}"
            ck_kaydet()
            raise SystemExit(ck["durduruldu"])
        yol = ROOT / BB.ESLESME_DIZIN / f"parti-{no:02d}.jsonl"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in satirlar), encoding="utf-8")
        BB.uygula(str(ROOT), sessiz=True)
        hatalar = BB.denetle(str(ROOT))
        if hatalar:
            raise SystemExit("bütünlük denetimi başarısız, commit yapılmadı: " + "; ".join(hatalar[:5]))
        kayitlar = list(derleme_kayitlari())      # satir değerleri değişmiş olabilir
        by_id = {r["id"]: r for r in kayitlar}
        ornek = ornek_yaz(no, by_id, rapor, gecti)
        bagli = st.get("kesin", 0)
        kontrol = sum(1 for k in rapor if k["sonuc"] != "UYUSMADI")
        ck["son_checkpoint"] = f"parti {no:02d} ({bas + 1}-{son}) {datetime.datetime.now().isoformat(timespec='seconds')}"
        ilerleme_yaz(kayitlar, ck)
        _git(["add", "-A", "md", "dizin", "veri", "araclar/bedesten_eslestir.py", "araclar/bedesten_bagla.py", "yapi.py"])
        if _git(["diff", "--cached", "--quiet"], check=False).returncode:
            nd = Counter(s["neden"] for s in satirlar)
            yeni = sum(1 for s in satirlar if s["id"] in yb and s["match_status"] == "kesin")
            mesaj = (f"Bedesten: batch {no:02d} — {len(parca):,} processed, {bagli:,} linked (mrfg_id), "
                     f"{kontrol} Bedesten-checked\n\n"
                     f"Başlık kuralı: {nd.get('metin_numarasi_farkli', 0)} linksiz (metin_numarasi_farkli), "
                     f"{nd.get('metinde_karar_no_yok', 0)} linksiz (metinde_karar_no_yok, BAM), "
                     f"{yeni} yeniden bağlandı (başlığı künyeyle tutan tek mrfg id).")
            _git(["commit", "-q", "-m", mesaj])
            ck["son_commit"] = _git(["log", "-1", "--format=%h %s"]).stdout.strip()
            print(f"  commit: {ck['son_commit']}", flush=True)
        ck.setdefault("partiler", {})[str(no)] = {"islenen": len(parca), "baglanti": bagli,
                                                  "baglantisiz": len(parca) - bagli, "kontrol": kontrol,
                                                  "commit": ck.get("son_commit")}
        if no not in ck["tamamlanan"]:
            ck["tamamlanan"].append(no)
        if str(ck.get("durduruldu") or "").startswith(f"parti {no:02d} "):
            ck.pop("durduruldu")
        if no in beklet or ck["push_bekleyen"]:
            if no not in ck["push_bekleyen"]:
                ck["push_bekleyen"].append(no)
            print(f"  push bekletiliyor (onay bekleyen partiler: {ck['push_bekleyen']})", flush=True)
        elif not a.push_yok:
            _push(durum, ck)
        ck_kaydet()
        print(f"  parti {no:02d} bitti: {bagli:,} bağlantı; örnekler {ornek.relative_to(ROOT)}; "
              f"{time.time() - t0:.0f} sn", flush=True)
        if a.tek_parti:
            break



def push_onayla(a):
    """Bekletilen partilerin push'unu onaylar: HEAD'i force olmadan iter, bekleme listesini temizler."""
    ck_yol = Path(a.durum) / "checkpoint.json"
    ck = json.loads(ck_yol.read_text())
    if _push(Path(a.durum), ck):
        ck["onaylanan"] = sorted(set(ck.get("onaylanan", [])) | set(ck.get("push_bekleyen", [])))
        ck["push_bekleyen"] = []
        ck["onay_bekleyen_commitler"] = []
        ck_yol.write_text(json.dumps(ck, ensure_ascii=False, indent=1))
        print("push tamam:", ck["son_push"])
    else:
        raise SystemExit("push başarısız: " + str(ck.get("push_hatasi")))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="komut", required=True)

    def ortak(q):
        q.add_argument("--db", required=True, help="DuckDB dizin dosyası (depo dışında)")
        q.add_argument("--threads", type=int, default=4)
        q.add_argument("--bellek", default="6GB")
    q = sub.add_parser("indeks"); ortak(q); q.add_argument("--veri", required=True, help="veri seti kökü (data/<kaynak>/*.parquet)")
    q = sub.add_parser("aday"); ortak(q); q.add_argument("--veri", required=True)
    q = sub.add_parser("calistir"); ortak(q)
    q.add_argument("--durum", required=True, help="checkpoint, canlı önbellek ve istek günlüğü dizini (depo dışında)")
    q.add_argument("--parti-boyu", type=int, default=10000)
    q.add_argument("--parti", type=int, help="yalnız bu partiyi (yeniden) işle")
    q.add_argument("--tek-parti", action="store_true", help="bir parti işleyip dur")
    q.add_argument("--aralik", type=float, default=16.0, help="canlı istekler arası en az saniye (>= 16)")
    q.add_argument("--gunluk-tavan", type=int, default=1000)
    q.add_argument("--tavan-dolunca", choices=["bekle", "olasi"], default="bekle")
    q.add_argument("--push-beklet", type=int, nargs="*", help="bu partilerin push'unu onaya kadar beklet")
    q.add_argument("--push-yok", action="store_true")
    q.add_argument("--ornek-tohum", type=int, help="örnek kapısı için farklı rastgele tohum (yeniden işlemede)")
    q = sub.add_parser("push-onayla"); q.add_argument("--durum", required=True)
    q = sub.add_parser("yeniden-ara"); ortak(q); q.add_argument("--veri", required=True)
    q.add_argument("--durum", required=True); q.add_argument("--partiler", type=int, nargs="+", required=True)
    q.add_argument("--parti-boyu", type=int, default=10000)
    q = sub.add_parser("baslik-duzelt"); ortak(q); q.add_argument("--durum", required=True)
    q.add_argument("--partiler", type=int, nargs="+", required=True)
    a = p.parse_args()
    {"indeks": indeks, "aday": aday, "calistir": calistir, "push-onayla": push_onayla,
     "yeniden-ara": yeniden_ara, "baslik-duzelt": baslik_duzelt}[a.komut](a)


if __name__ == "__main__":
    main()
