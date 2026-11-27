# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 10,000 (%7.47) |
| Bağlantılı (mrfg_id) | 9,271 |
| Bedesten'de kontrol edilen (örnek) | 20 (tutar 20) |
| Olası (bağlantı yok) | 10 |
| Eşleşmeyen | 703 |
| Birden çok aday | 9 |
| Hatalı/eksik künye | 7 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 0 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 9 |
| alinti_uyusmuyor | 1 |
| alinti_yok | 10 |
| esas_veya_tarih_uyusmuyor | 57 |
| hatali_kunye | 7 |
| veri_setinde_anahtar_yok | 645 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| bam | 1,015 / 1,370 (%74.1) |
| yargitay | 8,256 / 8,630 (%95.7) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| borclar-genel | 3,396 / 3,752 (%90.5) |
| kira | 5,574 / 5,779 (%96.5) |
| temel-ilkeler | 301 / 469 (%64.2) |

Son checkpoint: parti 01 (1-10000) 2026-11-27T18:01:36  
Son commit: -  
Son push: -
