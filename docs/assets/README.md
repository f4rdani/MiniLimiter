# Daftar screenshot untuk website

Semua file diletakkan di folder ini dengan **nama persis** seperti di bawah (format PNG). Halaman `docs/index.html` otomatis menampil gambar yang sudah ada; untuk yang belum ada, placeholder akan tetap terlihat.

## Sudah tersedia ✅

| File | Tampilan | Catatan |
|---|---|---|
| `01-activity.png` | Activity — process tree, DL/UL, rule status, status bar **Administrator · Shaper active** | Dari `activity.png` |
| `02-info-limit-chart.png` | Info View dengan **Limit In = 2 MB/s** + Traffic Chart dengan garis `limit 2,00 MB/s` | Dari `info view dan limit 2mb.png` |
| `03-rules-all.png` | Tab Rules, filter **All**, baris `Limit · In · msedge.exe · 2,00 MB/s · Active` | Dari `rules tab.png` |
| `04-blocker.png` | Activity filter **Limited**: Microsoft Edge berstatus **Blocked**, Info View mencentang **Block In + Block Out** | Dari `blocked.png` |
| `05-applications.png` | Tab **Application List** — daftar proses + Status + Executable path | Dari screenshot Applications |
| `06-network.png` | Tab Network — adapter, tipe, status | **IP sudah disensor** (ditutup `* * * *`) |
| `07-device-limit.png` | This PC — limit `4,00 MB/s` IN + OUT, badge ↓↑, dua garis di chart | Dari `pc limit.png` |
| `08-taskmanager.png` | Task Manager → Details → `MiniLimiter.exe` | **CPU 0,4% · Memory 33,1 MB** |
| `09-tray.png` | Ikon tray + tooltip **DL: 1,23 KB/s · UL: 2,56 KB/s · Limiter: On** | Dari `tray.png` |

> Penyensoran IP dilakukan dengan menimpa kolom IP pada gambar menggunakan Pillow. Alamat asli tidak tersimpan di file mana pun di repo.

## Masih dibutuhkan ⬜

Tidak ada — semua screenshot yang dipakai website sudah tersedia.

## Angka CPU / RAM

Sudah diisi di `docs/index.html`: **CPU 0,4%** dan **Memory 33,1 MB** (working set), diambil dari `08-taskmanager.png`.

## Catatan istilah

**This PC / Entire-PC cap** = batas kecepatan **total untuk seluruh komputer**, diatur dari baris paling atas di tab Activity. Beda dengan aturan per-aplikasi yang hanya membatasi satu program.

## Tips screenshot berikutnya

- Minimal ukuran jendela `1280×760`, crop hanya jendela aplikasi.
- Jalankan EXE dengan UAC disetujui agar status bar bertuliskan **Administrator**.
- Blur data pribadi lain (SSID, path user) kalau diperlukan sebelum menyimpan.
- Setelah file ditambahkan, cukup `git push` — GitHub Pages deploy otomatis.
