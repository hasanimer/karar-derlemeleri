# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 40,000 (%29.86) |
| Bağlantılı (mrfg_id) | 37,363 |
| Bedesten'de kontrol edilen (örnek) | 80 (tutar 80) |
| Olası (bağlantı yok) | 81 |
| Eşleşmeyen | 2,324 |
| Birden çok aday | 23 |
| Hatalı/eksik künye | 27 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 182 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 23 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 74 |
| esas_veya_tarih_uyusmuyor | 245 |
| hatali_kunye | 27 |
| kapsam_disi | 182 |
| kisa_alinti | 2 |
| veri_setinde_anahtar_yok | 2,071 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 94 (%0.0) |
| bam | 5,653 / 6,724 (%84.1) |
| danistay | 1,290 / 1,459 (%88.4) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 30,420 / 31,635 (%96.2) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,305 / 2,421 (%95.2) |
| arsa-payi | 7,413 / 7,955 (%93.2) |
| arsa-payi-ilk | 40 / 72 (%55.6) |
| borclar-genel | 3,396 / 3,752 (%90.5) |
| cisg | 21 / 22 (%95.5) |
| el-atma | 3,033 / 3,168 (%95.7) |
| fidic | 15 / 103 (%14.6) |
| kadastro | 312 / 389 (%80.2) |
| kamulastirma | 194 / 254 (%76.4) |
| kat-mulkiyeti | 5,645 / 5,711 (%98.8) |
| kira | 14,142 / 14,949 (%94.6) |
| muris-muvazaasi | 45 / 89 (%50.6) |
| tapu-tescil | 359 / 455 (%78.9) |
| temel-ilkeler | 301 / 469 (%64.2) |
| yukleniciden-satin-alan | 142 / 191 (%74.3) |

Son checkpoint: parti 04 (30001-40000) 2026-11-27T18:27:14  
Son commit: 6bfe427 Bedesten: batch 03 — 10,000 processed, 9,201 linked (mrfg_id), 20 Bedesten-checked  
Son push: 6bfe427
