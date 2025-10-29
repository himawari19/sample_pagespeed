# PageSpeed Monitor (Nutriclub)

A lightweight monitor yang secara otomatis mengambil skor Google PageSpeed Insights (PSI) dari daftar URL, menyimpan hasil historis, dan mem-publish dashboard statis lewat GitHub Pages.

---

## 🔧 Fitur

- Ambil skor PSI (mobile / desktop) untuk URL yang ditentukan  
- Simpan data historis harian (JSON / CSV)  
- Generate dashboard HTML statis (grafik, tabel)  
- Deploy otomatis ke GitHub Pages lewat GitHub Actions  
- Triggerable secara manual / jadwal (cron)  
- Dukungan notifikasi ke Telegram (opsional)  

---

## 📂 Struktur Direktori & File Penting

```
.
├── .github/
│   └── workflows/           # Workflow GitHub Actions
├── dashboard/                # Hasil output HTML / JSON historis
├── example.env                # Contoh variabel environment
├── notify_telegram.py         # Modul notifikasi Telegram
├── psi_csv_dashboard.py       # Script utama dashboard / fetching
├── urls.csv                   # Daftar URL + strategi (mobile / desktop)
├── utils_history.py           # Utilitas pengolahan data historis
├── requirements.txt           # Dependencies Python
├── README.md                  # (Dokumen ini)
└── …
```

---

## 🛠 Setup & Instalasi

1. Clone repositori  
   ```bash
   git clone https://github.com/maazway/pagespeed-monitor-nr.git
   cd pagespeed-monitor-nr
   ```

2. Instal dependensi  
   ```bash
   pip install -r requirements.txt
   ```

3. Salin `example.env` ke `.env`, lalu isi variabel:  
   ```
   PSI_API_KEY=<key kamu>
   TELEGRAM_BOT_TOKEN=<token bot telegram opsional>
   TELEGRAM_CHAT_ID=<chat_id opsional>
   ```

4. Atur daftar target URL di `urls.csv` dengan format:
   ```
   url,strategy
   https://example.com,desktop
   https://example.com,mobile
   ```

---

## ▶️ Menjalankan Secara Lokal

```bash
python psi_csv_dashboard.py --csv urls.csv
```

Kemudian buka hasilnya di:  
```
dashboard/dashboard.html
```

---

## 🤖 Integrasi dengan GitHub Actions / CI

- Workflow dijadwalkan untuk berjalan setiap hari (jam 06:00 WIB)  
- Output: `dashboard/dashboard.html`, `dashboard/history.json`, `dashboard/history/YYYY-MM.json`  
- Setelah selesai, workflow akan commit & push ke branch `main` dan melakukan deploy ke GitHub Pages  

Kamu bisa modifikasi jadwal cron-nya di file workflow di `.github/workflows/…`

---

## 🔔 Notifikasi Telegram (Opsional)

Jika kamu ingin menerima notifikasi setiap kali ada pembaruan atau skor baru:

- Isi `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di `.env`  
- Module `notify_telegram.py` akan mengirim pesan berdasarkan template yang sudah ada  
- Notifikasi bisa di-trigger setelah proses fetch / dashboard selesai  

---

## 📋 Tips & Best Practices

- Pastikan key PSI masih valid dan memiliki kuota yang cukup  
- Caching atau rate limit mungkin diperlukan kalau target URL banyak  
- Jika endpoint gagal, tambahkan retry atau handling error (timeout, status code ≠ 200)  
- Untuk tampilan dashboard, kamu bisa modifikasi template HTML di folder `dashboard`  

---

## 🧮 Contoh Cron untuk WIB

| Waktu WIB | Cron (UTC) | Cron Expression |
|-----------|-------------|------------------|
| 05:00 WIB | 22:00 UTC (hari sebelumnya) | `0 22 * * *` |
| 06:00 WIB | 23:00 UTC (hari sebelumnya) | `0 23 * * *` |
| 07:00 WIB | 00:00 UTC | `0 0 * * *` |

---

## 📜 Lisensi & Kontribusi

- Kontribusi: welcome! Silakan ajukan issue atau pull request  
- Harap sertakan deskripsi perubahan dan test case kalau memungkinkan  