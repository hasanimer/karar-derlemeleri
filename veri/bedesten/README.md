# Bedesten eşleştirme (deneysel)

`araclar/bedesten_eslestir.py`, yerel Parquet dosyalarından Yargıtay künyelerine aday Bedesten belge kimliği üretir. Kaynak dosyaların gerçekten Bedesten kimliği içerdiğini, yalnız Yargıtay kararlarını kapsadığını ve veri kullanım koşullarını kullanıcı doğrulamalıdır.

```sh
python -m pip install pyarrow
python araclar/bedesten_eslestir.py /path/to/yargitay/*.parquet --source 'veri seti ve sabit revizyon'
```

Sütun isimleri `--court`, `--decision`, `--esas`, `--text`, `--id` ile uyarlanabilir. Çıktı `veri/bedesten/eslesmeler.jsonl` dosyasındadır. `unique_in_input` yalnız taranan girdide tek aday bulunduğunu ifade eder; resmî kaynaktan doğrulama değildir. `ambiguous` ve `unmatched` için belge kimliği atanmaz. 50 kelimelik örtüşme tek başına karar kimliğini kanıtlamaz. Veri setinin eksiksizliği, kimliklerin doğruluğu ve resmî belge içeriği ayrıca kontrol edilmelidir.

Resmî karar sayfası biçimi `https://mevzuat.adalet.gov.tr/ictihat/{documentId}` olarak doğrulandı. Otomatik aday çıktısında `bedesten_url` yine null bırakılır; resmî başlık ve metin doğrulaması yapılan kayıtlar `dogrulanmis.jsonl` dosyasında saklanır. İlk kayıt HGK 2025/502 E., 2026/15 K. (1225412500). Bu aşamada mevcut Markdown ve JSONL karar dosyalarına bağlantı eklenmemiştir. Toplu eşleştirme gerçek veri üzerinde henüz çalıştırılmamıştır.

Bedesten kimliği içeren aday kaynak: https://huggingface.co/datasets/muhammedturan/turk-ictihat-kararlari-fulltext (daire sütunu için `--court daire`). İndirme bu çalışma ortamında DNS erişimi bulunmadığından gerçekleştirilemedi.
