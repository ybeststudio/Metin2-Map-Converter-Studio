# Metin2 Map Converter Studio

Metin2 client map klasörlerinden server tarafında kullanılabilir map dosyaları üreten Windows aracı.

Program; `setting.txt`, area klasörleri ve `attr.atr` dosyalarını okuyarak server tarafındaki temel map paketini oluşturur. `_pass` veya parent map kullanan haritalarda, kaynak mapte attr yoksa `ParentMapName` üzerinden gerçek attr kaynağı bulunur.

## Özellikler

- Gerçek LZO sıkıştırmalı `server_attr` üretimi
- `Setting.txt`, `Town.txt`, `boss.txt`, `npc.txt`, `regen.txt`, `stone.txt` çıktıları
- Varsa `sungma_attr.txt` taşıma desteği
- `ParentMapName` ve `_pass` fallback desteği
- Toplu map üretimi
- Modern Türkçe masaüstü arayüzü
- Tek dosya Windows exe build desteği

## Temiz Klasör Yapısı

```txt
MapConverter/
  assets/                 # ikon ve statik uygulama varlıkları
  bin/                    # hazır Windows exe
  GeneratedMaps/          # üretilen map çıktıları
  scripts/                # build scriptleri
  src/                    # uygulama kaynak kodu
  tests/                  # otomatik testler
  README.md
  requirements.txt
```

`GeneratedMaps` klasörü çıktı alanıdır. GitHub'a üretilmiş mapler eklenmez; klasör sadece `.gitkeep` ile boş tutulur.

## Çıktı Formatı

Her üretilen map klasörü sade server map yapısındadır:

```txt
GeneratedMaps/<map_adi>/
  boss.txt
  npc.txt
  regen.txt
  server_attr
  Setting.txt
  stone.txt
  Town.txt
  sungma_attr.txt   # sadece kaynak mapte varsa
```

Teknik raporlar kullanıcıyı karıştırmamak için map klasörünün içine yazılmaz. Gerekirse `GeneratedMaps/_reports` altında tutulur.

## Kullanım

Hazır exe:

```txt
bin/MapConverterGui.exe
```

Varsayılan ayarlar:

- Kaynak map dizini: `D:\ymir work`
- Çıktı dizini: `MapConverter\GeneratedMaps`
- Rapor dizini: `MapConverter\GeneratedMaps\_reports`

## Kaynaktan Çalıştırma

```powershell
python -m pip install -r requirements.txt
python -m app.main launch-gui
```

## Komut Satırı ile Üretim

Tek map:

```powershell
python -m app.main generate-maps `
  --source-root "D:\ymir work" `
  --output-root ".\GeneratedMaps" `
  --report-file ".\GeneratedMaps\_reports\generation_summary.json" `
  --map-name "metin2_map_smhgate_threeway"
```

Birden fazla map:

```powershell
python -m app.main generate-maps `
  --source-root "D:\ymir work" `
  --output-root ".\GeneratedMaps" `
  --report-file ".\GeneratedMaps\_reports\generation_summary.json" `
  --map-name "metin2_map_smhgate_a1" `
  --map-name "metin2_map_guild_whitedragon_boss_pass"
```

## Exe Build

```powershell
python -m pip install -r requirements.txt
python scripts\build_windows_exe.py
```

Build sonrası tek dosya exe otomatik olarak buraya kopyalanır:

```txt
bin/MapConverterGui.exe
```

## Test

```powershell
python -m pytest -q
```

## Notlar

- `server_attr` üretimi için `python-lzo` gereklidir.
- Program kaynak mapte attr bulamazsa `ParentMapName` alanını kullanır.
- `_pass` ile biten maplerde base map üzerinden attr mirası desteklenir.
- Üretilen mapler GitHub'a eklenmemelidir; sadece kaynak kod ve exe paylaşılmalıdır.
