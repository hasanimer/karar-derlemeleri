---
name: karar-derlemeleri
description: Av. Hakan Dimdik'in hasanimer/karar-derlemeleri arşivinde Türk hukukuna ilişkin emsal kararları konu veya künye üzerinden bulur ve doğrulanabilir kaynak gösterir. Kullanıcı bu derlemelerde Yargıtay, BAM, Danıştay veya başka bir merciin kararını aradığında, bir künyeyi kontrol etmek ya da bir karar alıntısını kaynaklandırmak istediğinde kullan.
---

# Karar Derlemeleri

[hasanimer/karar-derlemeleri](https://github.com/hasanimer/karar-derlemeleri), Av. Hakan Dimdik’in seçtiği karar alıntılarının Markdown arşividir. Arama sonucunu ilgili Markdown dosyasında, `##` ile başlayan künye başlığından bir sonraki künye başlığına kadar olan bölümde kontrol et. Konu başlıkları derleyenin tasnifidir. Dış aramada kişisel bilgilerden arındırılmış hukuki kavramları ve kamuya açık künyeleri kullan.

## Derlemede ara

- Konuya göre [derleme dizininden](https://github.com/hasanimer/karar-derlemeleri/blob/main/dizin/derlemeler.md) ilgili `md/<kod>/00-icindekiler.md` dosyasını, oradan konu bağlantısını aç. Kira derlemesinde gerektiğinde `00-icindekiler-<NN>.md` alt dizinini izle. Kullanıcı tarihsel karşılaştırma istemedikçe `eski-surum` işaretli derlemeleri ele. Dosya başındaki `derleme`, `surum` ve `konu` alanlarını atıf için kullan.
- Depo yerelde varsa mevcut kopyasının kökünde `araclar/ara.py` ile ara. Birden çok terim aynı alıntıda aranır. Bir öbeği birlikte aramak için tırnak kullan. `-b` başlık ve künye araması, `-m` merci, `-y` yıl ve `-n` gösterilecek sonuç sınırıdır. `-d` derleme kodunu kısmi eşler. Örneğin `-d arsa-payi` sonucunda `md/arsa-payi-ilk/` yollarını ayrıca ele.

  ```bash
  python3 araclar/ara.py -d kira -n 8 -- 'tahliye taahhüdü' 'teslim'
  rg -wF -- 'yargitay|3hd|k2018/6854' dizin/kararlar/
  ```

  Merci bilinmiyorsa künye dizininde `k2018/6854` gibi karar numarasını ara ve adayları merciye göre ayır. `dosya` ve `satir` alanlarını kullanarak eşleşen künyeyi aç. Konu başlıklarının Türkçe karakterleri sadeleştirilmiş biçimi `dizin/konular.tsv` dosyasındaki `ara` sütunundadır.
- Yerel kopya yoksa GitHub bağlayıcısında `hasanimer/karar-derlemeleri` ile sınırlandırarak karar numarasını veya konu terimlerini ara. `md/` altındaki karar dosyasını `fetch_file` ile aç ve arama sonucunda revizyon verildiyse onu kullan. Arama kullanılamıyorsa GitHub’daki derleme dizininden konuya ilerle. GitHub araması veya dizinden örnekleme yaptıysan taramanın kapsamını belirt.

## Künye ve atıf

- Künyeyi kaynakta yazıldığı gibi aktar. Esas numarası, tarih, daire veya karar sonucu kaynakta belirsizse bunu açık bırak. Aynı karar numarası birden fazla mercide geçiyorsa adayları merci ve mevcut künye alanlarıyla ayır.
- Başlığın altında karar metni yoksa “derlemede yalnız künye var” de. Alıntıyı yalnız ait olduğu künye altında kullan. Tırnak içindeki pasajı kaynakla karşılaştır ve özetleri özet olarak belirt. `…` satırını ve anonimleştirmeyi koru. Aynı pasajın farklı künyelerde tekrarlanmasını bağımsız gerekçeler olarak sayma. Konuyla ilgili farklı yönde kararlar bulursan bunları merci ve mevcut tarih bilgileriyle birlikte göster.
- Her karar için künye, ilgili gerekçenin kısa özeti, **Av. Hakan Dimdik**, derlemenin adı ve varsa sürümü, konu başlığı ve Markdown bağlantısı ver. Erişilen GitHub revizyonu ve satır numaraları belliyse bağlantıya ekle. Derlemenin özgün PDF bağlantısı gerektiğinde üstverideki `kaynak_pdf` alanından alınabilir.
- Markdown’daki UYAP tam metin bağlantısı alıntının dışındaki kaynak bilgisidir. Bağlantı varsa açıp künye ile metni karşılaştır. Tam metne veya güncel hukuki duruma dayanılacaksa kararı ve ilgili mevzuatı resmî kaynaktan doğrula. Resmî metne erişemezsen derlemedeki bulguyu kendi kapsamıyla aktar ve tam metni doğrulayamadığını belirt. Derlemede eşleşmeye ulaşamadıysan “derlemelerde bulamadım” de ve aranan kapsamı belirt.

Resmî doğrulama için merciye göre [Yargıtay Karar Arama](https://karararama.yargitay.gov.tr/), [UYAP Emsal](https://emsal.uyap.gov.tr/), [Danıştay Karar Arama](https://karararama.danistay.gov.tr/) veya [AYM Kararlar Bilgi Bankası](https://kararlarbilgibankasi.anayasa.gov.tr/) kullanılabilir. Mevzuat için [Mevzuat Bilgi Sistemi](https://www.mevzuat.gov.tr/) üzerinden yürürlük durumunu kontrol et.
