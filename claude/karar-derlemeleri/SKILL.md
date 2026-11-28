---
name: karar-derlemeleri
description: Av. Hakan Dimdik'in emsal karar derlemelerinde konuya veya künyeye göre karar bulur; künyeyi ve alıntıyı kaynaktaki gibi verir, resmî kaynaktan doğrulamaya yönlendirir.
---

# Karar Derlemeleri (Claude.ai sürümü)

Kaynak: herkese açık GitHub deposu **hasanimer/karar-derlemeleri**. Av. Hakan Dimdik'in hazırlayıp paylaştığı 35 emsal karar derlemesinin Markdown çevirisidir (yaklaşık 134 bin karar alıntısı). Metinler derleyenin seçtiği **alıntılardır**, kararın tamamı değildir. Kullanıcı bu derlemelerde karar aradığında, bir künyeyi kontrol etmek ya da bir alıntıyı kaynaklandırmak istediğinde bu beceriyi kullan.

Ham dosya kökü: `https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/main/`
Bağlantı vermek için sayfa kökü: `https://github.com/hasanimer/karar-derlemeleri/blob/main/`

## Depoya erişim (sırayla dene)

1. **Kod çalıştırma ortamı ağa çıkabiliyorsa** ham dosyaları oradan indir (ör. `curl -sL <ham-kök>dizin/derlemeler.md`). Büyük dizin dosyalarını (künye dizini) yalnız bu yolla indir ve içinde ara; tamamını sohbete yazma.
2. Olmazsa **web'den getirme (web fetch)** ile ham adresleri tek tek aç. Başlangıç noktası: `https://raw.githubusercontent.com/hasanimer/karar-derlemeleri/main/llms.txt`.
3. İkisi de olmuyorsa kullanıcıdan ilgili dosyayı eklemesini iste ("+" → "GitHub'dan ekle" ile `hasanimer/karar-derlemeleri` deposundan ya da dosya yükleyerek). Erişemediğin dosyanın içeriğini tahmin etme.

## Konuya göre bulma

1. `dizin/derlemeler.md`: 35 derleme, hukuk alanına göre; her derlemenin kodu (`md/<kod>/`) ve ana bölümleri.
2. `md/<kod>/00-icindekiler.md`: o derlemenin konu başlıkları ve dosya bağlantıları (bağlantılar bu dosyaya göredir). **Kira** derlemesi iki düzeylidir: bir bölümün tüm alt başlıkları `md/kira/00-icindekiler-<NN>.md` dosyasındadır (ör. tahliye için `00-icindekiler-04.md`).
3. Konu dosyası: `md/<kod>/<bölüm>/<konu>/<kod>.<no>.<NNN>.md`. Bir konu birkaç parçaya bölünmüş olabilir (`.001`, `.002` …); dosya başındaki `sonraki` alanı bir sonraki parçayı gösterir. Aradığını ilk parçada bulamazsan sonraki parçalara geç ve kaç parçaya baktığını söyle.
4. Dosyada `#` konu başlığı, `##` karar künyesidir; künyenin altındaki paragraflar o karardan alıntıdır. Dosya başındaki `derleme`, `surum`, `konu` alanlarını atıfta kullan.

## Künyeye göre bulma

`dizin/kararlar/<kod>.tsv` her künye için bir satırdır (sütunlar: `kunye`, `anahtar`, `dosya`, `satir` …). `anahtar` biçimi `<tür>|<birim>|k<karar no>` (ör. `yargitay|3hd|k2019/2024`). Karar numarasını bu dosyada ara, `dosya` ve `satir` ile yalnız o kararın bulunduğu Markdown dosyasını aç. Merci bilinmiyorsa aynı numaradaki adayları merciye göre ayır.

## Yanıt kuralları (zorunlu)

- **Künyeyi dosyada yazdığı gibi** aktar. Olmayan esas numarasını, tarihi, daireyi ekleme; künyeyi düzeltme. Künyelerin çoğunda esas numarası ve tarih yoktur.
- **Alıntıyı tırnak içinde, kelimesi kelimesine** ver ve yalnız ait olduğu künyenin altındaki metinden al. Özetliyorsan özet olduğunu söyle. Tek başına `…` satırı atlanmış metni, metin içindeki `...` gizlenmiş adı gösterir.
- Altında metin olmayan künyeye ("derlemede yalnız künye var") önceki ya da sonraki alıntıyı mal etme. Aynı paragraf birçok künyenin altında tekrar edebilir; bunları bağımsız gerekçe sayma.
- Alıntıdan kararın sonucu (onama/bozma) çıkmıyorsa bilmediğini söyle. Merciin düzeyini belirt (İBK, HGK, daire, BAM, ilk derece).
- Her karar için ver: künye · kısa alıntı · **Av. Hakan Dimdik**, derlemenin adı ve sürümü · konu başlığı · Markdown sayfa bağlantısı (`https://github.com/hasanimer/karar-derlemeleri/blob/main/<dosya>`).
- Künyenin altında "UYAP – Kararın tam metni" bağlantısı varsa onu da ver; açabiliyorsan künyeyi ve alıntıyı tam metinle karşılaştır, açamıyorsan doğrulayamadığını söyle.
- Bulamazsan "derlemelerde bulamadım" de ve hangi dosyalara baktığını belirt; genel bilgiyle doldurma.
- Her hukuki yanıtın sonuna ekle: "Bu metinler Av. Hakan Dimdik'in derlemelerinden seçme alıntılardır; kararın tam metnini ve güncelliğini resmî kaynaktan doğrulayın (karararama.yargitay.gov.tr, emsal.uyap.gov.tr, karararama.danistay.gov.tr, kararlarbilgibankasi.anayasa.gov.tr, mevzuat.gov.tr). Hukuki görüş değildir."
