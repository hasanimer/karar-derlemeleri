# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 50,000 (%37.33) |
| Bağlantılı (mrfg_id) | 47,129 |
| Bedesten'de kontrol edilen (örnek) | 100 (tutar 100) |
| Olası (bağlantı yok) | 81 |
| Eşleşmeyen | 2,552 |
| Birden çok aday | 26 |
| Hatalı/eksik künye | 29 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 183 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 26 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 74 |
| esas_veya_tarih_uyusmuyor | 245 |
| hatali_kunye | 29 |
| kapsam_disi | 183 |
| kisa_alinti | 2 |
| veri_setinde_anahtar_yok | 2,299 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 95 (%0.0) |
| bam | 5,832 / 6,932 (%84.1) |
| danistay | 1,292 / 1,461 (%88.4) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 40,005 / 41,424 (%96.6) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,305 / 2,421 (%95.2) |
| arsa-payi | 7,413 / 7,955 (%93.2) |
| arsa-payi-ilk | 40 / 72 (%55.6) |
| borclar-genel | 3,396 / 3,752 (%90.5) |
| bosanma | 306 / 316 (%96.8) |
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

Son checkpoint: parti 05 (40001-50000) 2026-11-27T18:33:48  
Son commit: ac0e437 Bedesten: batch 04 — 10,000 processed, 9,539 linked (mrfg_id), 20 Bedesten-checked  
Son push: ac0e437
