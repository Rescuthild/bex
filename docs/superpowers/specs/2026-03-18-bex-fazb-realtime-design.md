# BEX Coffee Faz B — Gercek Zamanli Izleme Tasarim Belgesi

## Ozet

Faz A'da kurulan FastAPI + SQLite altyapisina WebSocket katmani ekleyerek mudur icin canli izleme dashboard'u ve cift yonlu gercek zamanli guncelleme ozelligini kazandirma.

## Kararlar

| Karar | Secim | Neden |
|-------|-------|-------|
| Dashboard stili | Harita tarzi (alan kartlari, renk durumu) | Tek bakista tum kafenin durumu |
| Gecikme esigi | Alan bazinda ayarlanabilir | Her alanin onceligi farkli |
| Gercek zamanli kapsam | Cift yonlu (mudur→calisan + calisan→mudur) | Config degisiklikleri aninda yansisin |

## WebSocket Mimarisi

### Endpoint

`/ws` — tek WebSocket endpoint'i. Baglanan client ilk mesajda rolunu bildirir:

```json
{"type": "register", "role": "admin"}
{"type": "register", "role": "worker"}
```

### ConnectionManager

Sunucu tarafinda `ConnectionManager` sinifi:
- `admin_connections: list[WebSocket]` — bagli mudur client'lari
- `worker_connections: list[WebSocket]` — bagli calisan client'lari
- `broadcast_admins(data)` — tum admin'lere mesaj gonderir
- `broadcast_workers(data)` — tum calisan'lara mesaj gonderir
- `disconnect(ws)` — baglanti kopma yonetimi

### Olaylar

| Olay | Yön | Tetikleyen | Icerik |
|------|-----|------------|--------|
| `alarm_confirmed` | sunucu → admin | `POST /api/logs` basarili olduğunda | `{type, area_id, area_name, staff_id, staff_name, confirmed_at}` |
| `alarm_triggered` | worker → sunucu → admin | Calisan ekraninda alarm calindiginda | `{type, area_id, area_name, staff_id, staff_name, alarm_time}` |
| `config_changed` | sunucu → worker | Admin CRUD endpoint'i basarili olduğunda | `{type, change: "areas"|"staff"|"shifts"}` |

## Veritabani Degisiklikleri

### areas tablosu — yeni sutun

| Sutun | Tip | Varsayilan | Aciklama |
|-------|-----|-----------|----------|
| delay_threshold_min | INTEGER | 5 | Gecikme uyari esigi (dakika) |

Migration: `ALTER TABLE areas ADD COLUMN delay_threshold_min INTEGER NOT NULL DEFAULT 5`

## API Degisiklikleri

### Mevcut endpoint'lere eklenenler

- `POST /api/logs`: Basarili kayit sonrasi admin'lere `alarm_confirmed` broadcast
- Admin CRUD endpoint'leri (areas, staff, shifts): Basarili islem sonrasi worker'lara `config_changed` broadcast
- `PATCH /api/admin/{token}/areas/{id}`: `delay_threshold_min` alanini da gunceller

### Yeni endpoint

- `GET /ws`: WebSocket baglanti endpoint'i

### Model degisiklikleri

- `AreaCreate`: `delay_threshold_min: int = 5` eklenir
- `AreaUpdate`: `delay_threshold_min: Optional[int] = None` eklenir
- `AreaOut`: `delay_threshold_min: int` eklenir

## Mudur Dashboard — Canli Izleme Sekmesi

### Alan Kartlari

Her alan icin bir kart. Renk kodlamasi:

| Renk | Durum | Kosul |
|------|-------|-------|
| **Gri** | Normal | Sayac calisiyor, alarm yok |
| **Turuncu** | Alarm aktif | Alarm tetiklendi, henuz onaylanmadi |
| **Kirmizi** | Gecikme | Alarm onaylanmadan `delay_threshold_min` gecti |
| **Yesil** | Temiz | Son kontrol suresi icinde yapilmis |

### Kart icerigi

- Alan adi + ikon
- Durum rengi (kart border + arka plan)
- Kalan sure (sayac) veya "Alarm aktif — X dk Y sn" veya "Son kontrol: HH:MM (Personel Adi)"
- Gecikme durumunda: titresim animasyonu + gecikme suresi

### WebSocket Entegrasyonu

Admin paneli `/ws`'e baglanir, `role: "admin"` olarak kaydolur. Gelen mesajlara gore kartlari gunceller:

- `alarm_confirmed`: ilgili alan kartini yesile cevirir, son kontrol bilgisini gunceller
- `alarm_triggered`: ilgili alan kartini turuncuya cevirir, gecikme sayacini baslatir

### Gecikme Ayarlari

"Alanlar" sekmesindeki tabloya yeni sutun: "Gecikme Esigi (dk)". Varsayilan 5dk. Mudur her alan icin ayri deger girebilir.

## Calisan Ekrani — WebSocket Entegrasyonu

### Baglanti

Sayfa acildiginda `/ws`'e baglanir, `role: "worker"` olarak kaydolur.

### config_changed handler

```
config_changed mesaji geldiginde → loadState() cagir → timer'lar ve personel listesi guncellenir
```

### Fallback

- 5 dakikalik polling kaldirilmaz — WebSocket koptuğunda fallback olarak calisir
- WebSocket kopma durumunda otomatik yeniden baglanti (exponential backoff)

### alarm_triggered

Calisan ekraninda alarm tetiklendiginde sunucuya WebSocket uzerinden bildirir:

```json
{"type": "alarm_triggered", "area_id": 1, "staff_id": 2}
```

## Dosya Degisiklikleri

| Dosya | Degisiklik |
|-------|-----------|
| `main.py` | `ConnectionManager` sinifi, `/ws` endpoint, CRUD endpoint'lerine broadcast ekleme |
| `database.py` | `init_db()`'de `delay_threshold_min` migration |
| `models.py` | Area modellerine `delay_threshold_min` ekleme |
| `static/admin.html` | "Canli Izleme" sekmesi, WebSocket baglantisi, alan kartlari, gecikme ayari |
| `static/index.html` | WebSocket baglantisi, `config_changed` handler, `alarm_triggered` gonderimi |

## Teknik Notlar

- FastAPI WebSocket destegi built-in (ek paket gerekmez)
- WebSocket baglantilari Cloudflare proxy uzerinden calisir (WebSocket upgrade destekleniyor)
- SQLite WAL mode concurrent read'leri destekler — WebSocket broadcast sirasinda okuma sorunu olmaz
- Reconnection: client tarafinda 1s, 2s, 4s, 8s, max 30s exponential backoff
