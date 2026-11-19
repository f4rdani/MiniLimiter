# Daftar screenshot yang perlu diambil manual

Ambil screenshot aplikasi **MiniLimiter (Administrator)** lalu simpan di folder ini dengan **nama file persis** di bawah. Format **PNG**. Disarankan ukuran jendela minimal `1280×760` dan crop hanya jendela aplikasi (atau Task Manager untuk item 8).

> Pastikan aplikasi dijalankan dari `MiniLimiter.exe` dan prompt UAC diklik **Yes**, agar status bar menampilkan **Administrator** dan **Shaper active**.

| # | Nama file | Tampilan yang harus terlihat |
|---|---|---|
| 1 | `01-activity.png` | Tab **Activity**: process tree, kolom **DL Rate / UL Rate / Rule Status**, baris **This PC** dengan limit `4,00 MB/s`, **Microsoft Edge** dengan `2,00 MB/s`, status bar **Administrator · Shaper active**. |
| 2 | `02-info-limit-chart.png` | Masih di Activity, klik **Microsoft Edge** → panel kanan **Info View** menampilkan aturan **Limit In = 2 MB/s**, dan **Traffic Chart** dengan garis batas `2 MB/s`. |
| 3 | `03-rules-all.png` | Tab **Rules**, filter **All**: terlihat baris **Limit** dan **Blocker** sekaligus (mis. `msedge.exe 2 MB/s`, `spotify.exe 512 KB/s`, `demo-blocker.exe`). |
| 4 | `04-rules-blocker.png` | Tab **Rules**, filter **Blocker** aktif — hanya menampilkan aturan blocker. |
| 5 | `05-applications.png` | Tab **Application List**: daftar semua proses berjalan dengan kolom **Status** (Online/Offline) dan path. |
| 6 | `06-network.png` | Tab **Network**: adapter jaringan (Wi-Fi/Ethernet), alamat IP, gateway, dan status koneksi. |
| 7 | `07-device-limit.png` | Tab Activity dengan baris **This PC** dipilih → Info View menampilkan **device-level limit 4 MB/s** + total DL/UL. |
| 8 | `08-taskmanager.png` | **Task Manager → Details → MiniLimiter.exe**, kolom **CPU** dan **Memory** terlihat (ini dipakai di section “Light on resources”). |
| 9 | `09-tray.png` *(opsional)* | Ikon tray MiniLimiter dengan tooltip hover yang menampilkan DL/UL live. |

## Tips

- Tekan **Win + Shift + S** untuk crop cepat, lalu simpan ke folder ini.
- Tutup tab/browser lain yang tidak perlu agar fokus bersih.
- Jika ingin menyembunyikan data pribadi (SSID/IP), blur sebelum menyimpan.
- Setelah semua file ada, halaman `docs/index.html` otomatis menampilkan gambar tersebut — placeholder akan hilang dengan sendirinya.

## Angka CPU / RAM

Catat angka dari screenshot Task Manager dan beri tahu saya, saya akan isi ke section **Light on resources** di `docs/index.html`.
