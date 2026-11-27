# Bedesten eşleştirme

Derleme künyelerini UYAP Bedesten'deki özgün kararlarla eşleştirir ve doğrulanan kararın altına resmî tam metin bağlantısı ekler. Bağlantılar kaynak metinden ayrı metadata'dır; künye, alıntı, `id` ve `es` değişmez.

## Dosyalar

- `eslesmeler/parti-NN.jsonl`: 10.000'lik partilerin sonucu, kayıt başına bir satır (`id` ile derleme kaydına bağlanır). Alanlar: `id`, `match_status` (`kesin`, `olasi`, `eslesmedi`, `cok_aday`, `hatali_kunye`, `kapsam_disi`), `match_confidence` (alıntının 5'li sözcük dizilerinin tam metinde bulunma oranı), `match_method` (`mrfg_id` = bağlantı kimliği veri setinin `document_id` değeri), `bedesten_document_id`, `bedesten_url`, `verified_at` (yalnız Bedesten'de canlı kontrol edilen kayıtlarda dolu), `source_dataset`, `neden`, `bedesten_kontrol` (`tutar`, `tutar_numara_karartilmis`, `elle`). Belge kimliği ve adres yalnız `kesin` satırlarda bulunur.
- `dogrulanmis.jsonl`: elle resmî kaynaktan doğrulanmış kayıtlar (pilot). Parti sonuçlarından önceliklidir.
- `ornekler/parti-NN.md`: her partiden rastgele 20 bağlantının Bedesten'de canlı kontrol sonucu (hukuki kontrol için).
- `PROGRESS.md`, `ilerleme.json`: ilerleme istatistikleri; "bağlantılı (mrfg_id)" ile "Bedesten'de kontrol edilen" ayrı sayılır.

## Kesin eşleşme (bağlantı eklenir)

Hepsi birlikte aranır: (1) künyede mahkeme türü, daire ve karar yılı/numarası yazılıdır ve yerel aday dizininde tek bir kararla birebir tutar (birden çok aday varsa bağlantı eklenmez); (2) künyede esas numarası ya da tarih yazıyorsa onlar da tutar; (3) alıntının en az %80'i (5'li sözcük dizileri; en az 12 sözcük) tam metinde geçer. Yargıtay aynı gerekçe paragraflarını yüzlerce kararda tekrarladığından alıntı benzerliği tek başına hiçbir zaman yetmez; daire ya da karar numarası olmayan künye bağlantı almaz. Yalnız karar numarası da yetmez. Hiçbir kimlik ya da adres üretilmez.

Aday kimlikler yerel bir veri setinden (Hugging Face `mrfg/turkish-court-decisions`, sabit revizyon) bulunur. Veri setinin `document_id` değeri Bedesten belge kimliğiyle aynıdır (Yargıtay, BAM ve Danıştay örnekleriyle sınandı); bağlantılar bu kimlikle eklenir ve tek tek Bedesten'de kontrol edilmez. Veri setinin metni depoya yazılmaz. Her partide push'tan önce rastgele 20 bağlantı Bedesten `getDocumentContent` ile canlı alınır; mahkeme/daire, karar no, esas, tarih ve alıntı karşılaştırılır. Biri bile tutmazsa parti depoya yazılmaz, push edilmez ve bağlantı ekleme durur. BAM metinlerinde numaralar `...` ile karartılmışsa örnek, alıntı örtüşmesi en az 0,95 ve mahkeme çelişmiyorsa geçer ve işaretlenir. Alıntısız künye (`olasi`, `alinti_yok`), veri setinde bulunmayan karar (`eslesmedi`) ve AYM, yabancı, Uyuşmazlık Mahkemesi kararları (`kapsam_disi`) bağlantı almaz.

## Metin başlığı kuralı (hukuk prosu, 27.11.2026)

Bağlantı yalnız eşleşen belgenin metin başlığındaki karar numarası künyeyle tutarsa verilir:

* Başlıkta açıkça yazan karar no künyedekinden farklıysa (tüm mahkemeler) kayıt `olasi`, `neden: metin_numarasi_farkli`; bağlantı yok.
* BAM metninin başlığında (incelenen karar bölümünden önce) karar no yoksa ya da karartılmışsa kayıt `olasi`, `neden: metinde_karar_no_yok`; bağlantı yok.
* Çelişkili kayıt için doğru karar veri setinde başka bir kimlikte bulunur, o belgenin başlığındaki daire ve karar no künyeyle birebir tutar, künyedeki esas/tarih metinde geçer, alıntı örtüşür ve bu koşulları sağlayan TEK belge varsa o kimliğe bağlanır (`yeniden_baglanan.jsonl`, `match_method: mrfg_id`, `verified_at: null`).
* Sınamalar: `python3 test_bedesten.py`.

## Bağlantı biçimi

`https://mevzuat.adalet.gov.tr/ictihat/{documentId}` UYAP Mevzuat ve İçtihat Programı'nın karar görüntüleme sayfasıdır; sayfa, aynı kimlikle Bedesten `emsal-karar/getDocumentContent` çağırır. Markdown'da künyenin altına `[UYAP – Kararın tam metni](...)` satırı eklenir. Bu satırlar yüzünden `satir` değerleri (sürüme özgüdür) ve parça dosyası boyutları yeniden hesaplanır; parça sınırları değişmez. `yapi.py` bağlantıları bu dizinden okur, yeniden üretimde korur; `--dogrula` gidiş-dönüş karşılaştırmasında bağlantı satırlarını yok sayar, boyut sınırını bağlantısız ölçer.

## Çalıştırma

```sh
python -m pip install duckdb
python araclar/bedesten_eslestir.py indeks --veri <veri seti kökü> --db <depo dışı>/indeks.duckdb
python araclar/bedesten_eslestir.py aday   --veri <veri seti kökü> --db <depo dışı>/indeks.duckdb
python araclar/bedesten_eslestir.py calistir --db <...>/indeks.duckdb --durum <depo dışı durum dizini> \
    --aralik 16 --gunluk-tavan 1000 --push-beklet 1
python araclar/bedesten_bagla.py --denetle
```

Canlı istekler (yalnız örnek kapısı) tek iş parçacıklıdır: en az 16 saniye arayla, 429/5xx'te üstel geri çekilme ve kalıcı yavaşlama, günlük tavan. Her istek durum dizinindeki günlüğe yazılır; Yargıtay karar arama portalı kullanılmaz. Çalıştırma kesilirse son checkpoint'ten sürer.
