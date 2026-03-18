# BEX Coffee

Kafe ve restoran icin alan temizlik takip sistemi. Alanlari, personeli ve vardiyalari yonetir, temizlik kontrollerini zamanlar ve gecikmeleri takip eder.

## Ozellikler

- **Alan Yonetimi**: Temizlik yapilacak alanlari tanimla (mutfak, salon, tuvalet vb.)
- **Personel & Vardiya**: Calisan ve vardiya yonetimi, gun bazli program
- **Temizlik Loglari**: Her temizlik kontrolu kaydedilir, gecikme suresi hesaplanir
- **Canli Bildirimler**: WebSocket ile anlik guncellemeler
- **Admin Paneli**: Personel, alan ve vardiya yonetimi icin ayri arayuz
- **PWA Destegi**: Mobil cihazlarda uygulama olarak kurulabilir
- **Otomatik Zamanlama**: Alan bazli temizlik araligi ve gecikme esigi

## Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python, FastAPI |
| Veritabani | SQLite |
| Frontend | Vanilla HTML/CSS/JS |
| Canli Bildirim | WebSocket |
| Deploy | Docker, Docker Compose |

## Kurulum

```bash
# Gelistirme
pip install -r requirements.txt
python main.py

# Docker
docker compose up -d
```

## Ortam Degiskenleri

| Degisken | Varsayilan | Aciklama |
|----------|-----------|----------|
| `ADMIN_TOKEN` | `dev-token-change-me` | Admin API erisim tokeni |
| `DB_PATH` | `/app/data/bex.db` | SQLite veritabani yolu |
| `PORT` | `8000` | Sunucu portu |

## API Endpointleri

| Method | Yol | Aciklama |
|--------|-----|----------|
| GET | `/` | Ana sayfa (temizlik takip) |
| GET | `/admin` | Admin paneli |
| WS | `/ws` | WebSocket canli bildirim |
| GET/POST | `/api/areas` | Alan CRUD |
| GET/POST | `/api/staff` | Personel CRUD |
| GET/POST | `/api/shifts` | Vardiya CRUD |
| GET/POST | `/api/logs` | Temizlik log CRUD |

## Lisans

MIT
