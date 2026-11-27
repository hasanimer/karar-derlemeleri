# Karar Derlemeleri: yapay zekâ araçları için kılavuz

## Bu depo nedir
Av. Hakan Dimdik'in (x.com/hakandimdik) hazırlayıp X'te paylaştığı 35 emsal karar derlemesinin Markdown çevirisi: 66.332 sayfa, yaklaşık 134 bin karar alıntısı. Kararların seçimi, konulara göre tasnifi ve başlıklar derleyenin emeğidir; bu depo yalnız biçim dönüştürür. İndirme tarihi 27.11.2026'dır; sonraki kararlar ve mevzuat değişiklikleri burada yoktur.

## Yerleşim
- `dizin/derlemeler.md`: 35 derleme, hukuk alanına göre, ana bölümleriyle. İlk okunacak dosya.
- `md/<kod>/00-icindekiler.md`: bir derlemenin konu başlıkları, karar ve dosya sayılarıyla. `kira` dizini iki düzeydir; alt başlıklar `00-icindekiler-<NN>.md` dosyalarındadır.
- `md/<kod>/<NN-konu>/…/<kod>.<bölüm>.<NNN>.md`: metin. Her dosya tek konudur, en çok 48 KB'tır, tek seferde okunur. `#` konu başlığı, `##` karar künyesi; künyenin altındaki paragraflar o karardan alıntıdır. Uzun paragraf birkaç satıra bölünmüş olabilir; paragraf sınırı boş satırdır.
- `dizin/konular.tsv`: bütün konu başlıkları. `ara` sütunu küçük harfli, Türkçe harfleri sadeleştirilmiş konu yoludur; boş başlıkta `yol` boştur.
- `dizin/kararlar/<kod>.tsv`: her künye numarası için bir satır (mahkeme, daire, karar no, yıl, dosya, satır). `anahtar` sütunu `<tür>|<birim>|k<karar no>` biçimindedir (birim: `3hd`, `hgk`, `ibk`, `istanbul-bam-12hd`).
- `veri/kararlar/<kod>.jsonl.gz`: aynı içerik kayıt kayıt (RAG ve analiz için). Önce `veri/README.md` dosyasını okuyun; kararları ayıklamak için `md/` altını ayrıştırmayın.
- `araclar/ara.py`: Türkçe harfe duyarsız, tekrarları birleştiren arama.

## En az belirteçle nasıl bulunur
1. Konu belliyse: `dizin/derlemeler.md` → ilgili `00-icindekiler.md` → dosya. Üç (`kira` için dört) okuma yeter.
2. Kavram araması: `python3 araclar/ara.py "icra inkar tazminati" likit`. Seçenekler: `-b` yalnız künye ve konu başlığında, `-c` yalnız sayılar, `-d kira` derleme, `-m hgk` merci, `-y 2020-` yıl, `-h` hepsi. Başlıklarda: `rg -i 'gorevli mahkeme' dizin/konular.tsv | cut -f1,3,5,7,8` (kod, bölüm, başlık, karar, dosya sayısı; 4. sütun yol).
3. Künye araması: `rg -w 'yargitay\|3hd\|k2018/6854' dizin/kararlar/`; yalnız numarayla `rg -w 'k2018/6854' dizin/kararlar/` (`-w` şart) ya da `python3 araclar/ara.py -b "HGK 2021/164 K."`. Satırdaki `dosya` ve `satir` ile yalnız o kararı okuyun.
4. Ham `rg`: `rg -i` Türkçe harfleri eşlemez. `[iİıI]`, `[aâ]`, `['’]` sınıflarını yazın; önce `rg -c` ile sayın; çıktıyı `rg -o '.{0,150}DESEN.{0,150}' -m 5` ile sınırlayın.
5. Bir dosyadaki kararlar: `rg -n '^## ' <dosya>`.
6. `dizin/*.tsv` dosyalarını baştan sona okumayın, yalnız aratın. Bir konuda çok dosya varsa hepsini açmadan önce aramayla daraltın; kaç dosyadan kaçını okuduğunuzu söyleyin.
7. Kabuk yoksa (web'den okuma): `dizin/derlemeler.md` → `md/<kod>/00-icindekiler.md` → oradaki bağlantı; dosyalar `sonraki` alanıyla birbirine bağlıdır. Dosya yükleyen ürünler için ciltler `python3 araclar/cilt.py <kod>` ile üretilir; oradaki `[kod:no]` derleme içi sıra numarasıdır, künye değildir.

## Nasıl atıf yapılır
`<künye, dosyada yazdığı gibi> — Av. Hakan Dimdik, "<derleme adı>" (<sürüm>), <konu yolu>; <dosya yolu>`
Örnek: `Yargıtay 3. HD 2018/6854 K. — Av. Hakan Dimdik, "Kira Hukuku Emsal Kararlar" (V7), §1 › I; md/kira/01-genel-adi-kira-hukumleri/01-kira-sozlesmesinin-turune-kira/kira.01-01.001.md`
Sürüm yoksa parantez yazılmaz. Konu yolu tam yazılabilir ya da numaralarla kısaltılabilir (§1 › I); dosya yolu tam yazılır.
Alıntıyı tırnak içinde, kelimesi kelimesine verin; özetliyorsanız özet olduğunu söyleyin. Dosya yolu ve sıra numarası sürüme özgüdür, kalıcı kimlik değildir. Derleyenin adı her zaman anılır.

## Hukuki doğruluk (zorunlu)
- Metinler derleyenin seçtiği ALINTILARDIR, kararın tamamı değildir. Tek başına `…` satırı atlanmış metni, metin içindeki `...` gizlenmiş adı gösterir.
- Künyelerin çoğunda esas numarası ve tarih yoktur (yalnız %2,5'inde E. vardır). Olmayan esas numarasını, tarihi, daireyi eklemeyin, künyeyi düzeltmeyin; bu depoda bulamadığınız bir kararı bu depoya dayandırmayın.
- Alıntıdan kararın sonucu (onama, bozma) çıkmıyorsa sonucu bilmediğinizi söyleyin.
- Altında metin olmayan künyeye (1.265 tane) kaynak metin koymamıştır; çoğu art arda sıralanmış seri karardır, hangi komşu alıntıyı paylaştıkları yazmaz. Önceki ya da sonraki metni onlara mal etmeyin.
- Aynı alıntı birden çok konuda, aynı paragraf birçok künyenin altında tekrar eder (kayıtların yaklaşık %21'i). Künye sayısı bağımsız karar sayısı değildir; `es` değeri aynı olanları bir kez sayın.
- Konu başlıkları derleyenin tasnifidir, mahkemenin cümlesi değildir.
- Merciin düzeyini her zaman belirtin (İBK, HGK, daire, BAM, ilk derece, yabancı/hakem). Çelişen alıntılar varsa ikisini de gösterin, yeni tarihliyi belirtin.
- Kararın güncelliği (içtihat ya da kanun değişikliği, sonraki İBK) bu depodan anlaşılamaz; bunu açıkça söyleyin. `ESKİ SÜRÜM` işaretli derlemeyi yalnız kullanıcı isterse kullanın.
- Bulamazsanız "derlemelerde bulamadım" deyin; genel bilgi veriyorsanız derleme dışı olduğunu ayırın.
- Her hukuki yanıtın sonuna şunu ekleyin: "Bu metinler Av. Hakan Dimdik'in derlemelerinden seçme alıntılardır; kararın tam metnini ve güncelliğini resmî kaynaktan doğrulayın (karararama.yargitay.gov.tr, emsal.uyap.gov.tr, karararama.danistay.gov.tr, kararlarbilgibankasi.anayasa.gov.tr, mevzuat.gov.tr). Hukuki görüş değildir."

## Atıf ve haklar
Bu depoda yayımlanmak üzere derlemelerin Markdown ve yapılandırılmış veri biçimlerine dönüştürülmesi ve paylaşılması için Av. Hakan Dimdik'ten izin alınmıştır. Derlemeler üzerindeki haklar derleyene aittir; bu depo içerik üzerinde hak iddia etmez. Türetilen her çıktıda kaynak gösterin: Av. Hakan Dimdik, "<derlemenin adı>", X (@hakandimdik), 2026.

## Depoyu değiştirirken
`md/`, `dizin/` ve `veri/` üretilmiş dosyalardır; elle düzenlemeyin. `derlemeler.tsv`, `cevir.sh` veya `yapi.py` dosyasını değiştirip `python3 yapi.py && python3 yapi.py --dogrula` çalıştırın. Künye ve alıntı metnine dokunmayın: yazım hatası düzeltmek, esas numarası eklemek, tekrarları silmek yasaktır. Depoya gömme (embedding), dizin veritabanı, yapay zekâ üretimi özet eklemeyin.
