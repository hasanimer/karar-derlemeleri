# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bedesten'de kontrol edilen**: her partiden rastgele 20 bağlantının Bedesten `getDocumentContent` ile canlı kontrolü (`verified_at` yalnız bunlarda doludur).

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 30,000 (%22.4) |
| Bağlantılı (mrfg_id) | 27,824 |
| Bedesten'de kontrol edilen (örnek) | 60 (tutar 60) |
| Olası (bağlantı yok) | 43 |
| Eşleşmeyen | 1,921 |
| Birden çok aday | 17 |
| Hatalı/eksik künye | 27 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 168 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 17 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 37 |
| esas_veya_tarih_uyusmuyor | 225 |
| hatali_kunye | 27 |
| kapsam_disi | 168 |
| kisa_alinti | 1 |
| veri_setinde_anahtar_yok | 1,688 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 80 (%0.0) |
| bam | 5,303 / 6,340 (%83.6) |
| danistay | 1,254 / 1,407 (%89.1) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 21,267 / 22,085 (%96.3) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,305 / 2,421 (%95.2) |
| arsa-payi | 7,413 / 7,955 (%93.2) |
| arsa-payi-ilk | 40 / 72 (%55.6) |
| borclar-genel | 3,396 / 3,752 (%90.5) |
| cisg | 21 / 22 (%95.5) |
| fidic | 15 / 103 (%14.6) |
| kira | 14,142 / 14,949 (%94.6) |
| tapu-tescil | 49 / 66 (%74.2) |
| temel-ilkeler | 301 / 469 (%64.2) |
| yukleniciden-satin-alan | 142 / 191 (%74.3) |

Son checkpoint: parti 03 (20001-30000) 2026-11-27T18:15:39  
Son commit: 6dee6ce Bedesten: batch 02 — 10,000 processed, 9,352 linked (mrfg_id), 20 Bedesten-checked  
Son push: -
