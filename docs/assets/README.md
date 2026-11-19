# Daftar screenshot untuk website

Semua file diletakkan di folder ini dengan **nama persis** seperti di bawah (format PNG). Halaman `docs/index.html` otomatis menampil gambar yang sudah ada; untuk yang belum ada, placeholder akan tetap terlihat.

## Sudah tersedia ✅

| File | Tampilan | Catatan |
|---|---|---|
| `01-activity.png` | Activity — process tree, DL/UL, rule status, status bar **Administrator · Shaper active** | Dari `activity.png` |
| `02-info-limit-chart.png` | Info View dengan **Limit In = 2 MB/s** + Traffic Chart dengan garis `limit 2,00 MB/s` | Dari `info view dan limit 2mb.png` |
| `03-rules-all.png` | Tab Rules, filter **All**, baris `Limit · In · msedge.exe · 2,00 MB/s · Active` | Dari `rules tab.png` |
| `05-applications.png` | Tab **Application List** — daftar proses + Status + Executable path | Dari `Screenshot 2026-11-19 112010.png` |
| `06-network.png` | Tab Network — adapter, tipe, status | **IP sudah disensor** (ditutup kotak `* * * *`) dari `network.png` |

> Penyensoran IP dilakukan dengan menimpa kolom IP pada gambar menggunakan Pillow. Alamat asli tidak tersimpan di file mana pun di repo.

## Masih dibutuhkan ⬜

| File | Tampilan yang harus terlihat |
|---|---|
| `04-rules-blocker.png` | Tab **Rules**, klik filter **Blocker** — hanya menampilkan aturan blocker. |
| `07-device-limit.png` | Tab Activity dengan baris **This PC** dipilih → device-level limit + total DL/UL. |
| `08-taskmanager.png` | **Task Manager → Details → MiniLimiter.exe**, kolom **CPU** dan **Memory** terlihat. Dipakai di section *Light on resources*. |
| `09-tray.png` *(opsional)* | Ikon tray MiniLimiter + tooltip DL/UL saat di-hover. |

## Angka CPU / RAM

Section *Light on resources* di `docs/index.html` masih menampilkan `—` untuk CPU dan RAM. Sebutkan angka dari Task Manager, saya akan mengisinya.

## Tips screenshot berikutnya

- Minimal ukuran jendela `1280×760`, crop hanya jendela aplikasi.
- Jalankan EXE dengan UAC disetujui agar status bar bertuliskan **Administrator**.
- Blur data pribadi lain (SSID, path user) kalau diperlukan sebelum menyimpan.
- Setelah file ditambahkan, cukup `git push` — GitHub Pages deploy otomatis.
