# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 20,000 (%14.93) |
| Bağlantılı (mrfg_id) | 18,623 |
| Bedesten'de kontrol edilen (örnek) | 40 (tutar 40) |
| Olası (bağlantı yok) | 43 |
| Eşleşmeyen | 1,292 |
| Birden çok aday | 13 |
| Hatalı/eksik künye | 27 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 2 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 13 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 37 |
| esas_veya_tarih_uyusmuyor | 57 |
| hatali_kunye | 27 |
| kapsam_disi | 2 |
| kisa_alinti | 1 |
| veri_setinde_anahtar_yok | 1,227 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 2 (%0.0) |
| bam | 3,382 / 4,220 (%80.1) |
| yargitay | 15,241 / 15,778 (%96.6) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 784 / 830 (%94.5) |
| borclar-genel | 3,396 / 3,752 (%90.5) |
| kira | 14,142 / 14,949 (%94.6) |
| temel-ilkeler | 301 / 469 (%64.2) |

Son checkpoint: parti 02 (10001-20000) 2026-11-27T18:08:07  
Son commit: f6c411e Bedesten: batch 01 — 10,000 processed, 9,271 linked (mrfg_id), 20 Bedesten-checked  
Son push: -
