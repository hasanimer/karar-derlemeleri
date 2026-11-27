# Bedesten eşleştirme ilerlemesi

Makine okunur hâli: `ilerleme.json`. **Bağlantılı (mrfg_id)**: künyenin mahkemesi, dairesi ve karar yılı/numarası yerel aday dizininde tek bir kararla birebir tuttu, künyede yazıyorsa esas/tarih de tuttu, alıntı tam metinde geçti; bağlantının kimliği veri setinin `document_id` değeridir ve tek tek Bedesten'de kontrol edilmemiştir. **Bağlantılı (bedesten_arama)**: eşleşmeyen künye resmî Bedesten `getEmsalKarar` ucunda tek tek arandı; daire ve karar no (varsa esas/tarih) tek adayla tuttu, metin başlığı kuralından geçti, metin canlı alındı (`verified_at` dolar). **Bedesten'de kontrol edilen**: her partiden rastgele 20 mrfg_id bağlantısının Bedesten `getDocumentContent` ile canlı kontrolü.

| | sayı |
|---|---:|
| Toplam künye | 133,954 |
| İşlenen | 90,000 (%67.19) |
| Bağlantılı (mrfg_id) | 85,230 |
| Bağlantılı (bedesten_arama) | 125 |
| Bedesten'de kontrol edilen (örnek) | 180 (tutar 180) |
| Olası (bağlantı yok) | 868 |
| Eşleşmeyen | 3,454 |
| Birden çok aday | 93 |
| Hatalı/eksik künye | 47 |
| Kapsam dışı (AYM, yabancı, Uyuşmazlık, ilk derece) | 183 |

## Nedenler

| neden | sayı |
|---|---:|
| 2_aday | 93 |
| alinti_kismen_uyuyor | 5 |
| alinti_uyusmuyor | 8 |
| alinti_yok | 74 |
| esas_veya_tarih_uyusmuyor | 265 |
| hatali_kunye | 47 |
| kapsam_disi | 183 |
| kisa_alinti | 3 |
| metin_numarasi_farkli | 36 |
| metinde_karar_no_yok | 750 |
| veri_setinde_anahtar_yok | 3,181 |

## Mahkeme türüne göre (bağlantılı / işlenen)

| tür | bağlantılı |
|---|---:|
| aym | 0 / 95 (%0.0) |
| bam | 6,581 / 8,511 (%77.3) |
| danistay | 1,292 / 1,461 (%88.4) |
| ilk-derece | 0 / 3 (%0.0) |
| yabanci | 0 / 85 (%0.0) |
| yargitay | 77,482 / 79,845 (%97.0) |

## Derlemeye göre (bağlantılı / işlenen)

| derleme | bağlantılı |
|---|---:|
| adi-ortaklik | 2,228 / 2,421 (%92.0) |
| arsa-payi | 7,274 / 7,955 (%91.4) |
| arsa-payi-ilk | 39 / 72 (%54.2) |
| borclar-genel | 3,322 / 3,752 (%88.5) |
| bosanma | 26,574 / 27,137 (%97.9) |
| cisg | 20 / 22 (%90.9) |
| ecrimisil | 3,302 / 3,396 (%97.2) |
| el-atma | 6,038 / 6,290 (%96.0) |
| fidic | 15 / 103 (%14.6) |
| itiraz | 1,574 / 1,709 (%92.1) |
| kadastro | 312 / 389 (%80.2) |
| kamulastirma | 194 / 254 (%76.4) |
| kat-mulkiyeti | 5,617 / 5,711 (%98.4) |
| kira | 13,905 / 14,949 (%93.0) |
| mal-rejimi | 3,694 / 3,757 (%98.3) |
| miras | 7,287 / 7,713 (%94.5) |
| muris-muvazaasi | 45 / 89 (%50.6) |
| ortakligin-giderilmesi | 3,135 / 3,166 (%99.0) |
| tapu-tescil | 352 / 455 (%77.4) |
| temel-ilkeler | 291 / 469 (%62.0) |
| yukleniciden-satin-alan | 137 / 191 (%71.7) |

Son checkpoint: bedesten_arama anlık uygulama 2026-11-27T22:45 (93 bağlantı); arama süreci durmadı  
Son commit: 8fddfa9 Bedesten: resmî arama (anlık) — 311 künye arandı, 93 bağlantı (bedesten_arama)  
Son push: 8fddfa9
