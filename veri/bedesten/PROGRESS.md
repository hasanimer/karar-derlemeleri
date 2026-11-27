# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 80,000 (%59.72) |
| Bağlantılı (mrfg_id) | 75,914 |
| Bedesten'de kontrol edilen (örnek) | 160 (tutar 160) |
| Olası (bağlantı yok) | 711 |
| Eşleşmeyen | 3,062 |
| Birden çok aday | 86 |
| Hatalı/eksik künye | 44 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 183 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 86 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 74 |
| esas_veya_tarih_uyusmuyor | 252 |
| hatali_kunye | 44 |
| kapsam_disi | 183 |
| kisa_alinti | 2 |
| metin_numarasi_farkli | 27 |
| metinde_karar_no_yok | 603 |
| veri_setinde_anahtar_yok | 2,802 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 95 (%0.0) |
| bam | 5,280 / 7,020 (%75.2) |
| danistay | 1,292 / 1,461 (%88.4) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 69,342 / 71,336 (%97.2) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,228 / 2,421 (%92.0) |
| arsa-payi | 7,274 / 7,955 (%91.4) |
| arsa-payi-ilk | 39 / 72 (%54.2) |
| borclar-genel | 3,320 / 3,752 (%88.5) |
| bosanma | 26,574 / 27,137 (%97.9) |
| cisg | 20 / 22 (%90.9) |
| ecrimisil | 3,302 / 3,396 (%97.2) |
| el-atma | 6,038 / 6,290 (%96.0) |
| fidic | 15 / 103 (%14.6) |
| kadastro | 312 / 389 (%80.2) |
| kamulastirma | 194 / 254 (%76.4) |
| kat-mulkiyeti | 5,617 / 5,711 (%98.4) |
| kira | 13,905 / 14,949 (%93.0) |
| mal-rejimi | 3,119 / 3,179 (%98.1) |
| muris-muvazaasi | 45 / 89 (%50.6) |
| ortakligin-giderilmesi | 3,135 / 3,166 (%99.0) |
| tapu-tescil | 352 / 455 (%77.4) |
| temel-ilkeler | 288 / 469 (%61.4) |
| yukleniciden-satin-alan | 137 / 191 (%71.7) |

Son checkpoint: parti 08 (70001-80000) 2026-11-27T18:52:52  
Son commit: 97e3d3d Bedesten: batch 08 — 10,000 processed, 9,768 linked (mrfg_id), 20 Bedesten-checked  
Son push: 97e3d3d
