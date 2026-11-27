#!/usr/bin/env python3
"""Bedesten metin başlığı kuralı (hukuk prosu, 2026-11-27) için sınamalar.

Çalıştırma: python3 test_bedesten.py
Kural: başlıkta açık karar no var ve künyedeki değilse bağlantı yok (metin_numarasi_farkli, tüm mahkemeler);
BAM başlığında karar no yok/karartılmışsa bağlantı yok (metinde_karar_no_yok).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "araclar"))
from bedesten_eslestir import baslik_denetle, baslik_metni  # noqa: E402

BAM_FARKLI = ("T.C.\nİZMİR\nBÖLGE ADLİYE MAHKEMESİ\n6. HUKUK DAİRESİ\n\nT Ü R K M İ L L E T İ A D I N A\n"
              "İ S T İ N A F K A R A R I\n\nDOSYA NO : 2022/1385\nKARAR NO : 2022/2065\n\nİNCELENEN KARARIN\n"
              "MAHKEMESİ : İZMİR 3. ASLİYE TİCARET MAHKEMESİ\nTARİHİ : 08/02/2022\nESAS NO : 2021/958\nKARAR NO : 2022/106\n")
BAM_KARARTILMIS = ("T.C. KONYA BAM .. HUKUK DAİRESİ\nT.C.\nKONYA\nBÖLGE ADLİYE MAHKEMESİ\n.. HUKUK DAİRESİ\n\n"
                   "DOSYA NO :\nKARAR NO :\n\nT Ü R K M İ L L E T İ A D I N A\nİNCELENEN KARARIN\n"
                   "MAHKEMESİ : KONYA .. ASLİYE TİCARET MAHKEMESİ\nTARİHİ : 04/07/2019\nNUMARASI : .... Esas .... Karar\n")
BAM_NOKTALI = "T.C. ANKARA BÖLGE ADLİYE MAHKEMESİ 21.HUKUK DAİRESİ .... TÜRK MİLLETİ ADINA KARAR ... İNCELENEN DOSYANIN"
BAM_ESAS_KARAR = ("ANKARA BAM 26. HUKUK DAİRESİ 2021/1021 Esas - 2024/165 Karar T.C. ANKARA BÖLGE ADLİYE MAHKEMESİ "
                  "26. HUKUK DAİRESİ ESAS NO : 2021/1021 KARAR NO : 2024/165 İNCELENEN KARARIN MAHKEMESİ : ANKARA")
BAM_YALNIZ_ALT = ("T.C. İSTANBUL BÖLGE ADLİYE MAHKEMESİ 35. HUKUK DAİRESİ DOSYA NO: 2018/3484 İNCELENEN KARARIN "
                  "MAHKEMESİ: İSTANBUL 5. ASLİYE TİCARET MAHKEMESİ KARAR NO : 2018/1939")
BAM_YAZIM = "T.C. İSTANBUL BÖLGE ADLİYE MAHKEMESİ 44. HUKUK DAİRESİ DOSYA NO: 2022/664 KARAR NO: 2024/1835984) İNCELENEN"
YARGITAY = ("Hukuk Genel Kurulu 2017/1281 E. , 2018/35 K. \"İçtihat Metni\" MAHKEMESİ :Asliye Hukuk Mahkemesi "
            "... (Yargıtay HGK 2010/1 E., 2010/5 K. sayılı kararı)")
YARGITAY_FARKLI = "3. Hukuk Dairesi 2019/100 E. , 2019/200 K. \"İçtihat Metni\""
DANISTAY = "Danıştay 6. Daire Başkanlığı 2019/123 E. , 2020/45 K. \"İçtihat Metni\""


def kayit(tur, karar):
    return {"tur": tur, "karar": karar}


DURUMLAR = [
    ("BAM başlıkta başka karar no (İzmir 2069 -> 2065)", kayit("bam", "2022/2069"), BAM_FARKLI, "metin_numarasi_farkli"),
    ("BAM başlık künyeyle tutuyor", kayit("bam", "2022/2065"), BAM_FARKLI, None),
    ("BAM alt mahkeme karar no'su sayılmaz", kayit("bam", "2022/106"), BAM_FARKLI, "metin_numarasi_farkli"),
    ("BAM karartılmış boş alanlar (Konya)", kayit("bam", "2022/608"), BAM_KARARTILMIS, "metinde_karar_no_yok"),
    ("BAM noktalı karartma", kayit("bam", "2022/201"), BAM_NOKTALI, "metinde_karar_no_yok"),
    ("BAM 'esas - karar' biçimi", kayit("bam", "2024/165"), BAM_ESAS_KARAR, None),
    ("BAM 'esas - karar' biçimi, farklı", kayit("bam", "2024/169"), BAM_ESAS_KARAR, "metin_numarasi_farkli"),
    ("BAM kendi karar no yok, yalnız alt mahkemede geçiyor", kayit("bam", "2018/1939"), BAM_YALNIZ_ALT, "metinde_karar_no_yok"),
    ("BAM resmî metinde bitişik rakam (1835 != 1835984)", kayit("bam", "2024/1835"), BAM_YAZIM, "metin_numarasi_farkli"),
    ("Yargıtay HGK tutuyor (atıf yapılan karar engel değil)", kayit("yargitay", "2018/35"), YARGITAY, None),
    ("Yargıtay başlıkta farklı karar no", kayit("yargitay", "2019/201"), YARGITAY_FARKLI, "metin_numarasi_farkli"),
    ("Yargıtay başlıkta numara yok -> BAM kuralı uygulanmaz", kayit("yargitay", "2019/201"), "Hukuk Dairesi İçtihat Metni", None),
    ("Danıştay tutuyor", kayit("danistay", "2020/45"), DANISTAY, None),
    ("Danıştay farklı", kayit("danistay", "2020/46"), DANISTAY, "metin_numarasi_farkli"),
    ("Yargıtay HGK daireli esas (2012/7-1092 E.), alt mahkeme numaraları engel değil", kayit("yargitay", "2013/758"),
     "Hukuk Genel Kurulu 2012/7-1092 E. , 2013/758 K. MAHKEMESİ : Hatay NUMARASI : 2004/2299 E- 2005/272 K.", None),
    ("Yargıtay HGK daireli esas, farklı karar no", kayit("yargitay", "2013/759"),
     "Hukuk Genel Kurulu 2012/7-1092 E. , 2013/758 K.", "metin_numarasi_farkli"),
    ("Yargıtay esas yılı resmî metinde bozuk (209/11154 E.)", kayit("yargitay", "2010/12156"),
     "2. Hukuk Dairesi 209/11154 E. , 2010/12156 K. MAHKEMESİ : Silifke NUMARASI : Esas no: 2006/391 Karar no:2009/88", None),
    ("BAM 'karar n:' kısaltması; 'dosya no 2020/457 karar' karar sayılmaz", kayit("bam", "2021/1193"),
     "T.C. İSTANBUL BÖLGE ADLİYE MAHKEMESİ 43. HUKUK DAİRESİ DOSYA N: 2020/457 KARAR N: 2021/1193 TÜRK MİLLETİ ADINA", None),
    ("BAM 'karar n:' kısaltması, farklı", kayit("bam", "2021/1194"),
     "T.C. İSTANBUL BÖLGE ADLİYE MAHKEMESİ 43. HUKUK DAİRESİ DOSYA N: 2020/457 KARAR N: 2021/1193 TÜRK MİLLETİ ADINA",
     "metin_numarasi_farkli"),
    ("Baştaki sıfır", kayit("yargitay", "2018/35"), "Hukuk Genel Kurulu 2017/1281 E. , 2018/0035 K.", None),
]


def main():
    hata = 0
    for ad, r, metin, bek in DURUMLAR:
        gel = baslik_denetle(r, baslik_metni(metin))
        if gel != bek:
            hata += 1
            print(f"HATA: {ad}: beklenen {bek!r}, gelen {gel!r}")
    if hata:
        sys.exit(f"test_bedesten.py: {hata} hata")
    print(f"test_bedesten.py: {len(DURUMLAR)} denetim geçti")


if __name__ == "__main__":
    main()
