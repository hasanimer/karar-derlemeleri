# Claude.ai için beceri (skill)

Bu klasördeki **karar-derlemeleri** becerisi, Claude'a bu arşivde nasıl arama yapacağını ve künyeyi nasıl aktaracağını öğretir. Arşivin kendisi içinde değildir. Claude, gerekli dosyaları herkese açık GitHub adreslerinden kendisi okur.

## Kurulum (bir kez)

1. **[karar-derlemeleri.zip](https://github.com/hasanimer/karar-derlemeleri/raw/main/claude/karar-derlemeleri.zip)** dosyasını indirin. Açmayın, olduğu gibi kullanın.
2. claude.ai'de sol menüden **Özelleştir (Customize) → Skills** bölümüne gidin, **+ → Upload a skill** ile dosyayı seçin.
3. Listede **karar-derlemeleri** açık görünüyorsa kurulum tamam.

Skills bölümü görünmüyorsa **Ayarlar → Capabilities** altında dosya oluşturma ve kod çalıştırma (Code execution and file creation) seçeneğini açın. Skill yükleme ücretli planlarda (Pro, Max, Team, Enterprise) vardır. Ayrıntılar: [Claude'da skill kullanımı](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

## Kullanım

Yeni bir sohbette sorunuzu düz Türkçe yazın. Örnek:

> Kiralananın yeniden inşası veya imarı nedeniyle tahliye davasında onaylı projenin dava açılırken sunulması şart mı? Av. Hakan Dimdik'in emsal karar derlemelerinden bir Yargıtay kararı bul; künyeyi derlemede yazdığı gibi, kısa alıntıyla ve kaynak bağlantısıyla ver.

Claude künyeyi derlemede yazdığı gibi, alıntıyı kelimesi kelimesine ve derleme sayfası ile varsa UYAP tam metin bağlantısıyla verir. Dilekçeye almadan önce kararın tam metnini ve güncelliğini resmî kaynaktan doğrulayın.

## Dosyalar

- `karar-derlemeleri.zip`: claude.ai'ye yüklenecek dosya (içinde yalnız `karar-derlemeleri/SKILL.md`).
- `karar-derlemeleri/SKILL.md`: aynı becerinin okunabilir kaynağı. Değiştirirseniz ZIP'i yeniden oluşturun: `karar-derlemeleri/` klasörü ZIP'in kökünde olmalı, açıklama (description) en çok 200 karakter.

Codex ve benzeri araçlar için becerinin özgün sürümü `.agents/skills/karar-derlemeleri/SKILL.md` dosyasındadır.

Derlemeler: Av. Hakan Dimdik ([@hakandimdik](https://x.com/hakandimdik)).
