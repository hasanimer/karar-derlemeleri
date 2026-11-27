# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 70,000 (%52.26) |
| Bağlantılı (mrfg_id) | 66,776 |
| Bedesten'de kontrol edilen (örnek) | 140 (tutar 140) |
| Olası (bağlantı yok) | 81 |
| Eşleşmeyen | 2,858 |
| Birden çok aday | 62 |
| Hatalı/eksik künye | 40 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 183 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 62 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 74 |
| esas_veya_tarih_uyusmuyor | 249 |
| hatali_kunye | 40 |
| kapsam_disi | 183 |
| kisa_alinti | 2 |
| veri_setinde_anahtar_yok | 2,601 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 95 (%0.0) |
| bam | 5,864 / 6,970 (%84.1) |
| danistay | 1,292 / 1,461 (%88.4) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 59,620 / 61,386 (%97.1) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,305 / 2,421 (%95.2) |
| arsa-payi | 7,413 / 7,955 (%93.2) |
| arsa-payi-ilk | 40 / 72 (%55.6) |
| borclar-genel | 3,396 / 3,752 (%90.5) |
| bosanma | 19,953 / 20,316 (%98.2) |
| cisg | 21 / 22 (%95.5) |
| ecrimisil | 3,309 / 3,396 (%97.4) |
| el-atma | 6,049 / 6,290 (%96.2) |
| fidic | 15 / 103 (%14.6) |
| kadastro | 312 / 389 (%80.2) |
| kamulastirma | 194 / 254 (%76.4) |
| kat-mulkiyeti | 5,645 / 5,711 (%98.8) |
| kira | 14,142 / 14,949 (%94.6) |
| muris-muvazaasi | 45 / 89 (%50.6) |
| ortakligin-giderilmesi | 3,135 / 3,166 (%99.0) |
| tapu-tescil | 359 / 455 (%78.9) |
| temel-ilkeler | 301 / 469 (%64.2) |
| yukleniciden-satin-alan | 142 / 191 (%74.3) |

Son checkpoint: parti 07 (60001-70000) 2026-11-27T18:46:34  
Son commit: 94e56ce Bedesten: batch 06 — 10,000 processed, 9,805 linked (mrfg_id), 20 Bedesten-checked  
Son push: 94e56ce
