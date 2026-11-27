# Karar Derlemeleri: kayıt veri kümesi

**English abstract.** 133,954 records from 35 Turkish case-law compilations prepared and shared by attorney Hakan Dimdik (x.com/hakandimdik): one JSON object per cited decision (court heading as written, parsed court / chamber / decision number where present, topic path, and the excerpt chosen by the compiler). The texts are selected excerpts, not full decisions; most headings carry no docket number or date. Rights in the compilations belong to the compiler; attribution is required. Verify every decision in the official sources before relying on it.

## Toplamlar

Sürüm `2026.11.27`, şema `1`. 35 derleme · 133.954 kayıt (133.954 karar künyesi, 0 konu notu) · metinli 132.689 · farklı metin 104.792 · metinsiz künye 1.265. Sıkıştırılmış toplam 63,7 MB. Dosya başına sayılar ve SHA-256 özetleri `manifest.json` içindedir; `ornek.jsonl` biçimi görmek için küçük bir örnektir.

## Yükleme

Etiketli (değişmeyen) taban adres: `https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/v2026.11.27/veri/`

```python
import pandas as pd
taban = "https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/v2026.11.27/veri/"
# dtype verilmezse bir dosyada hep null olan metin sütunu ve null içeren yil sütunu float64 olur
tur = {"surum": "string", "kunye": "string", "mahkeme": "string", "daire": "string", "esas": "string", "karar": "string", "basvuru": "string", "tarih": "string", "yil": "Int64", "not": "string", "anahtar": "string"}
df = pd.read_json(taban + "kararlar/kira.jsonl.gz", lines=True, compression="gzip", dtype=tur)
```

```python
import json, urllib.request
from datasets import Features, List, Value, load_dataset   # datasets >= 4; eskisinde List yerine Sequence
taban = "https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/v2026.11.27/veri/"
m = json.load(urllib.request.urlopen(taban + "manifest.json"))
# Şema açık verilmelidir: ilk satırlarda null olan sütunun türü kendiliğinden çıkarılamaz.
S, I, B, L = Value("string"), Value("int64"), Value("bool"), List(Value("string"))
features = Features({
    "id": S, "kod": S, "derleme": S, "surum": S, "alan": S, "bolum": S, "konu": L, "konu_yolu": S,
    "sira": I, "tur": S, "kunye": S, "mahkeme": S, "daire": S, "esas": S, "karar": S,
    "kararlar": L, "basvuru": S, "tarih": S, "yil": I, "not": S, "anahtar": S, "bayrak": L,
    "metin": S, "metin_var": B, "kisaltma_var": B, "es": S, "tekrar_sira": I, "tekrar_sayisi": I,
    "tekrar_konular": L, "dosya": S, "satir": I, "atif": S, "paylasim": S,
})
ds = load_dataset("json", data_files=[taban + x["dosya"] for x in m["derlemeler"]], features=features,
                  split="train")
```

```sql
-- duckdb
INSTALL httpfs; LOAD httpfs;
SELECT kunye, konu_yolu FROM read_json_auto('https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/v2026.11.27/veri/kararlar/kira.jsonl.gz') WHERE yil >= 2024 LIMIT 10;
```

## Alanlar

Her satır bir JSON nesnesidir; anahtarlar bu sıradadır. Bir anahtarın adı ya da türü değişirse `sema` artar.

| Alan | Tür | Açıklama |
|---|---|---|
| `id` | str | `<kod>:<16 hex>`; kod + künye + metnin özeti. Künye ve metin değişmedikçe sürümler arasında sabittir. Aynı (künye, metin) çifti yinelenirse `-2`, `-3` eklenir. |
| `kod` | str | Derlemenin sürümsüz kısa kodu (`kira`, `itiraz`). |
| `derleme` | str | Derlemenin tam adı. |
| `surum` | str|null | Derleyenin sürüm adı (`V7`, `Cilt 2`) ya da null. |
| `alan` | str | Hukuk alanı (7 gruptan biri). |
| `bolum` | str | Konu ağacındaki yer (`01-03`). Sürüme özgüdür. |
| `konu` | [str] | Kökten yaprağa konu başlıkları, derleyenin yazdığı gibi. |
| `konu_yolu` | str | `konu` alanının ` > ` ile birleştirilmişi. |
| `sira` | int | Derleme içinde 1'den başlayan karar sırası (belge sırası). `konu-notu` kaydı karar değildir, sırası 0'dır. Sürüme özgüdür. |
| `tur` | str | `yargitay`, `bam`, `danistay`, `aym`, `uyusmazlik`, `ilk-derece`, `yabanci`, `konu-notu`. |
| `kunye` | str|null | Başlık, kaynakta yazdığı gibi. Hiç değiştirilmez. Konu notunda null. |
| `mahkeme` | str|null | `Yargıtay`, `<Şehir> BAM`, `Danıştay`, `AYM`, `Uyuşmazlık Mahkemesi`, ilk derece mahkemesinin adı; yabancı kararlarda parantez dışındaki ilk virgüle kadarki metin. |
| `daire` | str|null | `3. HD`, `HGK`, `İBK`, `13. D.`, `İDDK`, `Birinci Bölüm` vb.; künyede yoksa null. |
| `esas` | str|null | Künyede yazıyorsa esas numarası. |
| `karar` | str|null | İlk karar numarası. Yılı yazılmamışsa `?/N`. |
| `kararlar` | [str] | Künyedeki bütün karar numaraları. |
| `basvuru` | str|null | AYM bireysel başvuru numarası. |
| `tarih` | str|null | Künyede yazıyorsa karar tarihi (ISO). |
| `yil` | int|null | Tarihin, yoksa karar, başvuru ya da esas numarasının yılı. Yaklaşıktır. 1900'den küçük ya da sürüm yılından büyük çıkarsa (yazım hatası) null olur ve `yil_supheli` bayrağı konur. |
| `not` | str|null | Künyenin sonundaki parantez içi derleyen notu. |
| `anahtar` | str|null | ASCII arama anahtarı: `<tur>|<birim>|<no>`, ör. `yargitay|3hd|k2018/6854`. |
| `bayrak` | [str] | Ayrıştırma uyarıları: `cok_karar`, `k_eki_yok`, `yil_yok`, `karar_no_yok`, `dipnot`, `yazim`, `mahkeme_cikarim`, `yil_supheli`. |
| `metin` | str | Alıntı. Paragraflar `\n\n` ile ayrılır; Markdown işaretleri (`**kalın**`) korunur; `### …` ile başlayan paragraf FIDIC'teki özgün metin/çeviri ara başlığıdır. Metinsiz künyede boş dizgi. |
| `metin_var` | bool | Metin boş değilse true. |
| `kisaltma_var` | bool | Yalnız `…` olan bir paragraf (atlanmış metin) varsa true. |
| `es` | str | Metnin özeti (boşlukları sadeleştirilmiş metnin SHA-1'inin ilk 16 hanesi); metinsizde boş. |
| `tekrar_sira` | int | Aynı `es` değerini taşıyan kayıtlar içinde 0'dan başlayan sıra (derleme sırası, sonra karar sırası). |
| `tekrar_sayisi` | int | Aynı metni taşıyan kayıt sayısı; metinsizde 0. |
| `tekrar_konular` | [str] | Aynı metnin geçtiği `<kod>/<bolum>` değerleri. |
| `dosya` | str | Depodaki parça dosyasının yolu. Sürüme özgüdür. |
| `satir` | int | O dosyada `## künye` satırının numarası. Sürüme özgüdür. |
| `atif` | str | Önerilen atıf metni. |
| `paylasim` | str | Derlemenin paylaşıldığı gönderi. |

## Önerilen süzgeç

`tur != 'konu-notu' and metin_var and tekrar_sira == 0` → 104.792 satır: her farklı alıntı bir kez. Aynı metin başka künyelerin ya da konuların altında da geçiyorsa `tekrar_sayisi` ve `tekrar_konular` bunu gösterir; hiçbir kayıt silinmemiştir.

## Gömme (embedding) önerisi

- Gömülecek metin: `derleme + ' — ' + konu_yolu + '\n' + kunye + '\n' + metin`.
- Kayıtlar doğal parçalardır: metin ortancası 1,3 KB, %99'u 5,8 KB'ın altındadır, en büyüğü 26,8 KB'tır.
- 512 belirteçlik modellerde `\n\n` üzerinden bölün ve bağlam satırını (derleme, konu yolu, künye) her parçada yineleyin.
- Yalnız `…` olan paragrafları atmayın; derleyenin metin atladığını gösterir.

## Bilinen sınırlar

- Metinler seçme alıntıdır; kararın sonucu (onama, bozma) çoğu zaman alıntıdan anlaşılmaz.
- Esas numarası yazan künye oranı %2,5, tarih yazan künye oranı %0,6; çoğunda ikisi de yoktur. `yil` çoğunlukla karar numarasından türetilir, yaklaşıktır.
- `mahkeme`, `daire`, `karar` gibi alanlar künyeden düzenli ifadeyle çıkarılmıştır; eksik olan tahmin edilmez, şüpheli durumlar `bayrak` alanındadır. Asıl olan `kunye` alanıdır.
- 1.265 künyenin altında metin yoktur (`metin_var` false); kaynak o künyenin altına metin koymamıştır. En çok *Dava Şartı Arabuluculuk Cilt 2* derlemesindedir (1.105 künye); orada bunların 992 tanesi, art arda gelen 2 ile 46 künyelik 157 dizi hâlindedir (seri kararlar), yalnız 113 tanesi tek başınadır. Dizideki kararların hangi komşu alıntıyı paylaştığını kaynak söylemez; bu yüzden hiçbir metin kopyalanmamış, hiçbir grup çıkarılmamıştır. Önceki ya da sonraki kaydın metnini onlara mal etmeyin.
- `konu-notu` türündeki kayıt karar değildir: bir konu başlığı ile ilk künye arasındaki metindir, `sira` değeri 0'dır, `kunye` null'dır. Bu sürümde 0 tane vardır.
- Sıra: bir derlemenin belge sırası `sira` alanıdır (JSONL satırları da bu sıradadır). Dosya yolundan sıralarken bir başlığın kendi dosyaları alt dizinlerinden önce gelir; düz alfabetik yol sıralaması bu sırayı vermez.
- Metin Unicode NFC biçimine getirilmiştir (dönüştürücü çıktısındaki birkaç ayrık harf+işaret çifti birleşik harfe çevrilir); bunun dışında künye ve metin kaynaktaki gibidir. Tek istisna: dönüştürücünün düz satır olarak çıkardığı 3 başlık satırı elle düzeltilmiştir (`- Yargıtay 8. HD 2017/15084 K.:` → `#### Yargıtay 8. HD 2017/15084 K.`; `A. ARABULUCULUK ŞARTI SAĞLANMIŞ OLMAZ` → `### A. ARABULUCULUK ŞARTI SAĞLANMIŞ OLMAZ`; `B. ARABULUCULUK ŞARTI SAĞLANMIŞ OLUR` → `### B. ARABULUCULUK ŞARTI SAĞLANMIŞ OLUR`).
- Kayıtların yaklaşık %21'i başka bir kayıtla aynı metni taşır; künye sayısı bağımsız karar sayısı değildir.
- Paragraf sınırları PDF dönüştürmesinden gelir, sezgiseldir. PDF sayfa numarası tutulmaz.
- `ESKİ SÜRÜM` durumundaki derleme (`arsa-payi-ilk`) güncel hâliyle (`arsa-payi`) örtüşür.

## Hukuki doğruluk (sistem istemine yapıştırmak için)

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

Bu derlemelerden yararlanırken kaynak olarak Av. Hakan Dimdik'i gösterin. Derlemeler üzerindeki haklar derleyene aittir; bu depo içerik üzerinde hak iddia etmez. Derleyenin talebi hâlinde içerik kaldırılır. Önerilen atıf biçimi her kaydın `atif` alanındadır: *Av. Hakan Dimdik, "<derlemenin adı>", X (@hakandimdik), 2026.*

## Sürüm ve etiket

Her yeniden üretim `vYYYY.AA.GG` biçiminde etiketlenir; etiket `manifest.json` içindeki `surum` ile aynıdır. Yukarıdaki adresler etikete sabitlenmiştir. `id`, künye ve metin değişmedikçe sürümler arasında aynı kalır (kod sürüm numarası taşımaz). `sira`, `bolum`, `dosya` ve `satir` sürüme özgüdür; kalıcı kimlik olarak kullanmayın.
