#!/usr/bin/env python3
"""Künye ayrıştırıcısı, başlık sınıflayıcısı ve yardımcılar için sınamalar.

Çalıştırma: python3 test_kunye.py
Başlıkların hepsi derlemelerden alınmıştır; ara/ varsa her birinin kaynakta gerçekten geçtiği de denetlenir.
"""
import glob
import os
import sys

import yapi
from yapi import F, TRUPPER, kunye_coz, norm, sar, siniflandir, slug

KOK = os.path.dirname(os.path.abspath(__file__))

# (künye, beklenen alanlar). Yazılmayan alan denetlenmez.
ORNEKLER = [
    # olağan biçim
    ("Yargıtay 3. HD 2018/6854 K.",
     dict(tur="yargitay", mahkeme="Yargıtay", daire="3. HD", esas="", karar="2018/6854", kararlar=["2018/6854"],
          tarih="", yil=2018, bayrak=[], anahtarlar=["yargitay|3hd|k2018/6854"])),
    ("Yargıtay HGK 2021/164 K.",
     dict(tur="yargitay", daire="HGK", karar="2021/164", anahtarlar=["yargitay|hgk|k2021/164"])),
    ("İstanbul BAM 15. HD, 2018/1827 E., 2018/1351 K., 23.10.2018",
     dict(tur="bam", mahkeme="İstanbul BAM", daire="15. HD", esas="2018/1827", karar="2018/1351",
          tarih="2018-10-23", yil=2018, anahtarlar=["bam|istanbul-bam-15hd|k2018/1351"])),
    # birden çok karar numarası
    ("Yargıtay 3. HD 2025/4234 K., 2022/1103 K. ve 2018/2937 K.",
     dict(daire="3. HD", karar="2025/4234", kararlar=["2025/4234", "2022/1103", "2018/2937"], yil=2025,
          bayrak=["cok_karar"],
          anahtarlar=["yargitay|3hd|k2025/4234", "yargitay|3hd|k2022/1103", "yargitay|3hd|k2018/2937"])),
    # esas var, karar numarası yazılmamış
    ("Danıştay 15. D. 2018/3372 E., K.",
     dict(tur="danistay", mahkeme="Danıştay", daire="15. D.", esas="2018/3372", karar="", kararlar=[], yil=2018,
          bayrak=["karar_no_yok"], anahtarlar=["danistay|15d|e2018/3372"])),
    # yılı olmayan karar numarası
    ("Yargıtay 3. HD 4831 K.",
     dict(daire="3. HD", karar="?/4831", kararlar=["?/4831"], yil=None, bayrak=["yil_yok"],
          anahtarlar=["yargitay|3hd|k?/4831"])),
    # dipnot rakamı
    ("Yargıtay 3. HD 2025/3047 K.2", dict(karar="2025/3047", bayrak=["dipnot"], yil=2025)),
    ("İzmir BAM 23. HD 2025/1268 K.1",
     dict(tur="bam", mahkeme="İzmir BAM", daire="23. HD", karar="2025/1268", bayrak=["dipnot"])),
    # daireden sonra virgül, mahkemeden sonra virgül ya da nokta
    ("Yargıtay 20. HD, 2015/10565 K.", dict(daire="20. HD", karar="2015/10565", bayrak=[])),
    ("Yargıtay, 4. HD 2022/17299 K.", dict(daire="4. HD", karar="2022/17299", bayrak=[])),
    ("Yargıtay. 3. HD 2026/3231 K", dict(daire="3. HD", karar="2026/3231", bayrak=["yazim"])),
    ("Yargıtay 6. HD 2014/9709 E. , 2014/11464 K.", dict(esas="2014/9709", karar="2014/11464")),
    # K eki ya da karar numarası yok
    ("Yargıtay 3. HD 2025/3048", dict(karar="2025/3048", bayrak=["k_eki_yok"])),
    ("Yargıtay 3. HD 2021/2236 K", dict(karar="2021/2236", bayrak=[])),
    ("Yargıtay 2. HD K.", dict(daire="2. HD", karar="", kararlar=[], yil=None, bayrak=["karar_no_yok"],
                               anahtarlar=["yargitay|2hd|"])),
    ("Yargıtay HGK K.", dict(daire="HGK", karar="", bayrak=["karar_no_yok"])),
    # yazım hataları (başlık değişmez, yalnız ayrıştırma düzeltir)
    ("Yargtay 3. HD 2017/17713 K.", dict(tur="yargitay", mahkeme="Yargıtay", daire="3. HD", bayrak=["yazim"])),
    ("İstambul BAM 63. HD 2025/461 K.", dict(tur="bam", mahkeme="İstanbul BAM", daire="63. HD", bayrak=["yazim"])),
    ("İstanbul 36 HD 2024/2529 K.",
     dict(tur="bam", mahkeme="İstanbul BAM", daire="36. HD", karar="2024/2529", bayrak=["yazim"])),
    # mahkeme adı yazılmamış
    ("3. HD 2018/11915 K.", dict(tur="yargitay", mahkeme="Yargıtay", daire="3. HD", bayrak=["mahkeme_cikarim"])),
    ("HGK 2021/267 K.", dict(tur="yargitay", daire="HGK", bayrak=["mahkeme_cikarim"])),
    ("İBK 1979/3 K.", dict(tur="yargitay", daire="İBK", karar="1979/3", bayrak=["mahkeme_cikarim"])),
    ("YİBK 2021/1 E., 2022/3 K.",
     dict(tur="yargitay", mahkeme="Yargıtay", daire="İBK", esas="2021/1", karar="2022/3",
          bayrak=["mahkeme_cikarim"], anahtarlar=["yargitay|ibk|k2022/3"])),
    ("Hukuk Bölümü 2014/318 K.",
     dict(tur="uyusmazlik", mahkeme="Uyuşmazlık Mahkemesi", daire="Hukuk Bölümü", bayrak=["mahkeme_cikarim"])),
    # kurullar
    ("Yargıtay İBK 03.06.2022 tarihli, 2021/1 E., 2022/3 K.",
     dict(daire="İBK", esas="2021/1", karar="2022/3", tarih="2022-06-03", yil=2022)),
    ("Yargıtay Büyük Genel Kurulu 2016/6 K.", dict(daire="Büyük Genel Kurul", karar="2016/6")),
    ("Danıştay İdare Dava Daireleri Kurulu 2025/2480 E., 2025/2339 K.",
     dict(daire="İDDK", esas="2025/2480", karar="2025/2339", anahtarlar=["danistay|iddk|k2025/2339"])),
    ("Danıştay İçtihatları Birleştirme Kurulu 1968/8 E., 1973/14 K.", dict(daire="İBK", yil=1973)),
    ("Danıştay 10. Daire 2025/677 K.", dict(daire="10. D.", karar="2025/677")),
    ("Uyuşmazlık Mahkemesi Hukuk Bölümü 2023/485 E., 2023/714 K.",
     dict(tur="uyusmazlik", daire="Hukuk Bölümü", anahtarlar=["uyusmazlik|hukukbolumu|k2023/714"])),
    # AYM biçimleri
    ("AYM 01.02.2023 tarihli, 2019/22587 Başvuru No.",
     dict(tur="aym", mahkeme="AYM", daire="", basvuru="2019/22587", karar="", tarih="2023-02-01", yil=2023,
          bayrak=[], anahtarlar=["aym||b2019/22587"])),
    ("AYM 05.06.2024 tarihli, B. No: 2020/36152", dict(basvuru="2020/36152", karar="", bayrak=[], yil=2024)),
    ("AYM Birinci Bölüm, B. No: 2019/19839, 15.03.2023",
     dict(daire="Birinci Bölüm", basvuru="2019/19839", tarih="2023-03-15",
          anahtarlar=["aym|birincibolum|b2019/19839"])),
    ("Anayasa Mahkemesi (Genel Kurul) B. No: 2020/21347",
     dict(tur="aym", mahkeme="AYM", daire="Genel Kurul", basvuru="2020/21347", tarih="", yil=2020)),
    ("AYM 2012/94 E., 2013/89 K., 10.07.2013",
     dict(esas="2012/94", karar="2013/89", basvuru="", tarih="2013-07-10", anahtarlar=["aym||k2013/89"])),
    # not: parantez içindeki RG tarihi karar tarihi sanılmaz
    ("Anayasa Mahkemesi 16.07.2026 tarihli, 2026/23 E., 2026/162 K. (RG 06.11.2026, 33422)",
     dict(tur="aym", esas="2026/23", karar="2026/162", tarih="2026-07-16", **{"not": "RG 06.11.2026, 33422"})),
    ("Yargıtay 3. HD 2025/3540 K. (oy çokluğu)", dict(karar="2025/3540", **{"not": "oy çokluğu"})),
    # 200 karakterlik İBK notu: içinde ikinci bir E./K. çifti ve iç içe parantez var
    ("Yargıtay İBK 25.01.1984 tarihli, 1983/3 E., 1984/1 K. (İBK metni veritabanında ve Bedesten’de "
     "bulunmadığından içeriği, YİBK 16.05.2025 tarihli 2024/1 E., 2025/2 K. kararının (RG 18.07.2025, S. 32959) "
     "gerekçesindeki özetten aktarılmıştır)",
     dict(daire="İBK", esas="1983/3", karar="1984/1", kararlar=["1984/1"], tarih="1984-01-25", yil=1984,
          bayrak=[], anahtarlar=["yargitay|ibk|k1984/1"])),
    # nottaki "Asliye Hukuk" mahkemeyi değiştirmez
    ("İzmir BAM 1. HD 2024/1759 K. (şirket hisse devrinin muris muvazaası nedeniyle iptali; görevli mahkeme "
     "Asliye Hukuk)", dict(tur="bam", mahkeme="İzmir BAM", daire="1. HD", karar="2024/1759")),
    # FIDIC'teki Türk kararları (virgüllü, esaslı, tarihli)
    ("Danıştay 13. D., 2022/2378 E., 2022/3794 K., 24.10.2022",
     dict(tur="danistay", daire="13. D.", esas="2022/2378", karar="2022/3794", tarih="2022-10-24", yil=2022,
          bayrak=[], anahtarlar=["danistay|13d|k2022/3794"])),
    ("Ankara 10. Asliye Ticaret Mahkemesi, 2022/135 E., 2023/805 K., 01.11.2023",
     dict(tur="ilk-derece", mahkeme="Ankara 10. Asliye Ticaret Mahkemesi", daire="", esas="2022/135",
          karar="2023/805", tarih="2023-11-01",
          anahtarlar=["ilk-derece|ankara-10-asliye-ticaret-mahkemesi|k2023/805"])),
    ("İstanbul Anadolu 3. Sulh Hukuk Mahkemesi 2024/137 E.",
     dict(tur="ilk-derece", mahkeme="İstanbul Anadolu 3. Sulh Hukuk Mahkemesi", esas="2024/137", karar="",
          yil=2024, bayrak=["karar_no_yok"])),
]

# yabancı mahkeme / hakem kararları (FIDIC; sınıflayıcının 7. kuralı)
YABANCI = [
    ("ICC, Micheletti Company Limited v Ministry of Youth and Sports of Ghana, ICC Dava No. 27732/CPB, kısmi hakem "
     "kararı, 08.03.2024",
     dict(tur="yabanci", mahkeme="ICC", daire="", esas="", karar="", kararlar=[], tarih="2024-03-08", yil=2024,
          bayrak=[], anahtarlar=["yabanci|icc|"])),
    ("Braşov İstinaf Mahkemesi, 6/Ap sayılı karar, 04.02.2015",
     dict(tur="yabanci", mahkeme="Braşov İstinaf Mahkemesi", tarih="2015-02-04", **{"not": ""})),
]


def kaynak_basliklari():
    b = set()
    for yol in glob.glob(os.path.join(KOK, "ara", "*", "*.md")):
        with open(yol, encoding="utf-8") as f:
            for s in f:
                if s[:1] == "#":
                    m = yapi.BASLIK.match(s.rstrip("\n"))
                    if m:
                        b.add(m.group(2))
    return b


def main():
    n = 0
    for kume, yabanci in ((ORNEKLER, False), (YABANCI, True)):
        for kunye, beklenen in kume:
            r = kunye_coz(kunye, yabanci=yabanci)
            for alan, deger in beklenen.items():
                assert r[alan] == deger, f"{kunye!r}: {alan} = {r[alan]!r}, beklenen {deger!r}"
                n += 1
    # yabanci_kunye derlemesinde tanınmayan mahkeme (5. kuralla künye sayılan başlık) -> yabancı
    r = kunye_coz("Romanya Yüksek Kasasyon ve Adalet Divanı, 2. Hukuk Dairesi, 3155/2014 sayılı karar, 21.10.2014",
                  yabanci_olabilir=True)
    assert r["tur"] == "yabanci" and r["karar"] == "" and r["tarih"] == "2014-10-21" and r["bayrak"] == []
    # yabancı künyesi olmayan derlemede tanınmayan mahkeme üretimi durdurur
    try:
        kunye_coz("Bilinmeyen Kurum 2020/1 E.")
        raise AssertionError("tanınmayan mahkeme hata vermedi")
    except yapi.YapiHatasi:
        pass
    n += 2

    # akla yatmayan yıl (yazım hatası): yil boş, bayrak var; künye, karar no ve anahtar yazıldığı gibi
    r = kunye_coz("Konya BAM 4. HD 1202/3128 K.")
    assert r["yil"] is None and r["bayrak"] == ["yil_supheli"], r
    assert r["karar"] == "1202/3128" and r["anahtarlar"] == ["bam|konya-bam-4hd|k1202/3128"], r
    r = kunye_coz("Yargıtay 3. HD 2027/15 K.")              # sürüm yılından büyük (uydurma örnek)
    assert r["yil"] is None and "yil_supheli" in r["bayrak"] and r["karar"] == "2027/15", r
    r = kunye_coz("Yargıtay İBK 1899/1 K.")                 # 1900'den küçük (uydurma örnek)
    assert r["yil"] is None and "yil_supheli" in r["bayrak"], r
    assert kunye_coz("Yargıtay HGK 1900/1 K.")["yil"] == 1900
    assert kunye_coz("Yargıtay 3. HD 2026/3231 K")["yil"] == 2026 and "yil_supheli" not in \
        kunye_coz("Yargıtay 3. HD 2026/3231 K")["bayrak"]
    # yabancı mahkeme adı: parantez dışındaki ilk virgülde biter
    r = kunye_coz("Güney Afrika Yüksek Mahkemesi (Gauteng Dairesi, Pretoria), Lonerock Construction v South African "
                  "National Roads Agency SOC Ltd \\[2023] ZAGPPHC 2245, Dava No. 89831/2018, 27.06.2023", yabanci=True)
    assert r["mahkeme"] == "Güney Afrika Yüksek Mahkemesi (Gauteng Dairesi, Pretoria)", r
    assert r["tarih"] == "2023-06-27" and r["yil"] == 2023 and r["karar"] == "" and r["bayrak"] == [], r
    assert kunye_coz("Tek parça (virgül, yalnız parantezde)", yabanci=True)["mahkeme"] == \
        "Tek parça (virgül, yalnız parantezde)"
    n += 12
    if os.path.isdir(os.path.join(KOK, "ara")):
        var = kaynak_basliklari()
        assert "Konya BAM 4. HD 1202/3128 K." in var
        assert any(x.startswith("Güney Afrika Yüksek Mahkemesi (Gauteng Dairesi, Pretoria), Lonerock") for x in var)
        n += 2

    # sınıflayıcı
    S = lambda L, t, acik=False, yab=False: siniflandir(L, t, acik, yab)
    assert S(1, "§1. GENEL (ADÎ) KİRA HÜKÜMLERİ") == ("KONU", 1)
    assert S(3, "3. HD 2018/11915 K.") == ("KUNYE", 2)          # COURT, STRUCT'tan önce
    assert S(3, "Yargıtay 3. HD 2018/6854 K.") == ("KUNYE", 2)
    assert S(3, "A. ADÎ KİRA-KONUT VE ÇATILI İŞYERİ KİRASI AYRIMI") == ("KONU", 4)
    assert S(3, "Türkçe çevirisi", acik=True, yab=True) == ("ALT", 3)
    assert S(3, "İngilizce çevirisi (kararın aslı İspanyolca)", acik=True, yab=True) == ("ALT", 3)
    assert S(3, "Romanya Yüksek Kasasyon ve Adalet Divanı, 2. Hukuk Dairesi, 3155/2014 sayılı karar, 21.10.2014",
             yab=True) == ("KUNYE", 5)
    assert S(3, "DİĞER KARARLAR") == ("KONU", 6)
    assert S(3, "Braşov İstinaf Mahkemesi, 6/Ap sayılı karar, 04.02.2015", yab=True) == ("KUNYE", 7)
    assert S(4, "Çünkü taraflar anlaşırlarsa mahkeme kararına gerek kalmadan hukuki sonuç doğar.") == ("GOVDE", 7)
    assert siniflandir(4, "DİĞER KARARLAR", False, False, {"DİĞER KARARLAR": "GOVDE"}) == ("GOVDE", 0)
    n += 11

    # yardımcılar
    assert F("İİK’nın  ŞİKÂYET Usulü") == "iik'nin sikayet usulu"
    assert slug("TAKİBE İTİRAZ (İİK m. 62 vd.)") == "takibe-itiraz-iik-m-62-vd"
    assert slug("…") == "bolum"
    assert len(slug("KİRA SÖZLEŞMESİNİN TÜRÜNE, KİRA SÖZLEŞMESİNİN TİCARÎ İŞ VE HATTA TİCARÎ DAVA OLUP")) <= 40
    assert yapi.NUMARALAYICI.sub("", "§1. TAKİBE İTİRAZ") == "TAKİBE İTİRAZ"
    assert yapi.NUMARALAYICI.sub("", "KISIM I – TÜRK MAHKEME KARARLARI") == "TÜRK MAHKEME KARARLARI"
    assert norm("  ä  b\n c ") == "ä b c"
    assert TRUPPER("diğer kararlar") == "DİĞER KARARLAR"
    n += 8

    # yumuşak satır kırma: boşluk dışında hiçbir şey değişmez, satırlar sınırı aşmaz, ** içinde kırılmaz
    cumle = "Mahkemece **işin esası incelenerek** karar verilmesi gerekirken yazılı şekilde hüküm kurulmuştur. "
    uzun = (cumle * 40).strip()
    sarili = sar(uzun)
    assert sarili.replace("\n", " ") == uzun
    assert all(len(x) <= yapi.SAR_SINIR for x in sarili.split("\n")) and "\n" in sarili
    assert all(x.count("**") % 2 == 0 for x in sarili.split("\n"))
    assert sar("kısa satır") == "kısa satır"
    assert not any(x[:3] in ("1. ", "2. ") for x in sar(("Bu husus 6100 sayılı Kanun. 1. maddeye göre. " * 60).strip())
                   .split("\n")[1:])
    n += 5

    # başlıklar gerçekten derlemelerde geçiyor mu
    if os.path.isdir(os.path.join(KOK, "ara")):
        var = kaynak_basliklari()
        eksik = [k for k, _ in ORNEKLER + YABANCI if k not in var]
        assert not eksik, f"kaynakta bulunmayan sınama başlıkları: {eksik}"
        n += len(ORNEKLER) + len(YABANCI)
    print(f"test_kunye.py: {n} denetim geçti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
