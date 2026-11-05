# Tarik Manga Deposu

İki depoyu (Keiyoushi ve cuong-tran/manga-repo) tek `index.pb` içinde birleştirir ve kendi
GitHub hesabında yayınlar. Anime İzle'de "Depo ekle" ile bu tek adres yeterlidir.

Birleştirme kuralları: aynı paket iki depoda varsa sürümü (versionCode) yüksek olan alınır;
APK/JAR/ikon adresleri mutlak hale getirilir, yani dosyalar özgün depodan inmeye devam eder.

## Kurulum
1. GitHub'da boş bir depo aç (ör. `manga-repo`, herkese açık).
2. Bu klasörün içeriğini o depoya `main` dalına yükle:
   ```
   cd MangaRepo
   git init -b main && git add . && git commit -m "ilk sürüm"
   git remote add origin https://github.com/<kullanici>/manga-repo.git
   git push -u origin main
   ```
3. Depoda **Settings → Actions → General → Workflow permissions → Read and write** seç.
4. **Actions → Depoyu güncelle → Run workflow** ile bir kez çalıştır (sonra her gün kendiliğinden güncellenir).
5. Adresin: `https://raw.githubusercontent.com/<kullanici>/manga-repo/repo/index.pb`

Kaynak eklemek/çıkarmak için `sources.json` dosyasını düzenleyip push et.
Yerelde denemek: `python3 test_merge.py` ve `python3 merge_repos.py`.
