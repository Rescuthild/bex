# BEX Coffee v2 — Backend + Rol Ayrimi Tasarim Belgesi

## Ozet

BEX Coffee alan temizlik kontrol uygulamasini tek HTML dosyasindan, FastAPI backend + SQLite veritabanli, mudur/calisan rol ayrimli bir web uygulamasina donusturme tasarimi.

**Faz A:** Backend, kalici veri, rol ayrimi, loglama
**Faz B:** Gercek zamanli izleme (WebSocket) — ayri spec ile ele alinacak

## Kararlar

| Karar | Secim | Neden |
|-------|-------|-------|
| Kimlik dogrulama | URL ayrimi (`/admin/{token}`) | Basit, kafede pratik |
| Alarm onay kimligi | Atanan personel otomatik | Rotasyon zaten atama yapiyor |
| Admin korumasi | Gizli URL token (env var) | Sifresiz, link bilen girer |
| Veritabani | SQLite | Tek dosya, bu olcek icin yeterli |
| Backend | FastAPI (Python) | Hafif, WebSocket destegi, taninir |

## Mimari

### URL Yapisi

```
/                    -> Calisan ekrani (sayaclar + alarm)
/admin/{token}       -> Mudur paneli (tam yonetim + loglar)
/api/*               -> REST API
```

### Teknik Yigin

- **Backend:** FastAPI + uvicorn
- **Veritabani:** SQLite (tek dosya, volume mount ile kalici)
- **Frontend:** Vanilla HTML/CSS/JS (mevcut tasarim korunur)
- **Deploy:** Tek Docker container, Coolify uzerinde

### Proje Yapisi

```
bex/
  main.py              # FastAPI uygulama, API endpointleri
  database.py          # SQLite baglanti, tablo olusturma, CRUD
  models.py            # Pydantic modelleri (request/response)
  static/
    index.html         # Calisan ekrani
    admin.html          # Mudur paneli
    manifest.json       # PWA manifest
  Dockerfile
  requirements.txt
```

## Veritabani Semasi

### areas
| Sutun | Tip | Aciklama |
|-------|-----|----------|
| id | INTEGER PK | Otomatik artan |
| name | TEXT NOT NULL | Alan adi (orn: "Bar Tezgahi") |
| interval_min | INTEGER NOT NULL | Kontrol sikligi (dakika) |
| created_at | TEXT | ISO 8601 timestamp |

### staff
| Sutun | Tip | Aciklama |
|-------|-----|----------|
| id | INTEGER PK | Otomatik artan |
| name | TEXT NOT NULL | Personel adi |
| created_at | TEXT | ISO 8601 timestamp |

### shifts
| Sutun | Tip | Aciklama |
|-------|-----|----------|
| id | INTEGER PK | Otomatik artan |
| staff_id | INTEGER FK | staff.id referansi |
| day_of_week | INTEGER | 0=Pazar, 6=Cumartesi |
| shift_start | TEXT | "HH:MM" formati |
| shift_end | TEXT | "HH:MM" formati |

### logs
| Sutun | Tip | Aciklama |
|-------|-----|----------|
| id | INTEGER PK | Otomatik artan |
| area_id | INTEGER FK | areas.id referansi |
| staff_id | INTEGER FK NULL | staff.id (null = kimse yoktu) |
| action | TEXT | "checked" veya "missed" |
| alarm_time | TEXT | Alarmin caldigi zaman (ISO 8601) |
| confirmed_at | TEXT NULL | Onay zamani (ISO 8601, missed icin null) |

## API Endpointleri

### Public (calisan ekrani)

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/api/areas` | Tum alanlari ve surelerini dondurur |
| GET | `/api/staff/active` | Su an vardiyada olan personeli dondurur |
| GET | `/api/shifts/today` | Bugunun vardiya programi |
| POST | `/api/logs` | Kontrol yapildi kaydı. Body: `{area_id, staff_id}` |

### Admin (token ile korunan)

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/api/admin/{token}/areas` | Alan listesi |
| POST | `/api/admin/{token}/areas` | Yeni alan ekle |
| PATCH | `/api/admin/{token}/areas/{id}` | Alan guncelle (ad, sure) |
| DELETE | `/api/admin/{token}/areas/{id}` | Alan sil |
| GET | `/api/admin/{token}/staff` | Personel listesi |
| POST | `/api/admin/{token}/staff` | Yeni personel ekle |
| DELETE | `/api/admin/{token}/staff/{id}` | Personel sil |
| GET | `/api/admin/{token}/shifts` | Haftalik vardiya programi |
| POST | `/api/admin/{token}/shifts` | Vardiya ekle |
| DELETE | `/api/admin/{token}/shifts/{id}` | Vardiya sil |
| GET | `/api/admin/{token}/logs` | Log sorgusu. Query: `?date=2026-03-18&area_id=1` |

### Admin Token Dogrulamasi

- Token, `ADMIN_TOKEN` environment variable'indan okunur
- URL'deki `{token}` ile karsilastirilir
- Eslesmezse 404 doner (varligini bile belli etme)

## Frontend Tasarimi

### Calisan Ekrani (`index.html`)

Mevcut kontrol panelinin sadeletirilmis hali:
- Sayfa acilisinda `GET /api/areas` ve `GET /api/staff/active` cagirilir
- Timer mantigi ayni kalir (deadline tabanlı, localStorage'da deadline'lar)
- Alarm popup'inda atanan personelin adi gosterilir
- "Kontrol Yapildi" butonuna basilinca `POST /api/logs` cagirilir
- Alan/personel/vardiya duzenleme sekmeleri YOKTUR
- Sag panelde "Bugun Vardiyada" listesi (API'den)

### Mudur Paneli (`admin.html`)

Mevcut tam arayuz + yeni Loglar sekmesi:
- **Kontrol Paneli:** Sayaclar + alarm (calisan ekraniyla ayni)
- **Haftalik Vardiya:** CRUD islemleri API uzerinden
- **Alanlar:** CRUD islemleri API uzerinden
- **Personel:** CRUD islemleri API uzerinden
- **Loglar (YENi):** Tablo gorunumu, tarih filtresi, alan filtresi

### Loglar Sekmesi Detay

- Tarih secici (varsayilan: bugun)
- Alan filtresi (dropdown, "Tumu" secenegi)
- Tablo: Saat | Alan | Personel | Durum (Yapildi/Kacirildi) | Onay Suresi
- Ozet satirlari: toplam kontrol, kacirilma orani
- CSV export butonu

## Deploy Yapisi

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Coolify Ayarlari

- **Build pack:** Dockerfile
- **Port:** 8000
- **Volume:** `/app/data` (SQLite dosyasi icin)
- **Env vars:** `ADMIN_TOKEN=<gizli-token>`
- **Domain:** `https://bex.saviordigital.com`

### Volume Mount

SQLite dosyasi `/app/data/bex.db` konumunda olusturulur. Coolify'da volume mount ile container yeniden olusturulsa bile veri korunur.

## Faz B Hazirlik Notlari

Bu tasarim Faz B'ye (gercek zamanli izleme) gecisi kolaylastirir:
- FastAPI WebSocket destegi built-in → `/ws` endpoint eklenir
- `logs` tablosu zaten var → yeni kayit aninda WebSocket event yayini
- Mudur paneline canli dashboard sekmesi eklenir
- Gecikme uyarilari: alarm_time ile confirmed_at farki hesaplanir

Faz B ayri bir spec belgesiyle ele alinacak.
