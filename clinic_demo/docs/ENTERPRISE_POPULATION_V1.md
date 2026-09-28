# Enterprise Population Expansion v1 — 19.0.1.0.65

## Upgrade dan eksekusi

Paket repair berisi full replacement clinic_billing 19.0.3.0.7 dan clinic_demo 19.0.1.0.65. Companion clinic_membership 19.0.3.0.8 tetap diwajibkan dan tidak berubah. Baseline: clinic19a(20260922-062015).md. Governing prompt tersimpan dalam GOVERNING_MODEL_BY_MODEL.md.

1. Backup database dan filestore, hentikan Odoo, replace penuh ketiga folder addon dari ZIP.
2. Restart; Update Apps List; upgrade clinic_billing, lalu clinic_demo.
3. Pada Demo Run yang sama (Full Enterprise, Safe Mode aktif), Refresh Compatibility lalu Reconcile Existing Dataset. Jangan Reset Dataset atau mengganti anchor date.
4. Journey Progress kini memuat 137 journey: 40 sebelumnya dan 97 baru. Journey consumer menunggu perluasan sumber; ini bukan kehilangan data lama.
5. Execute Next / Resume menyelesaikan satu batch, maksimal 56 transaksi utama. Ulangi jika notifikasi menunjukkan kemajuan/READY; berhenti bila FAILED/BLOCKED, simpan detail journey dan log. Tidak perlu memilih checkbox baris.
6. Setelah seluruh batch, lanjutkan Reports → Dashboard → Analytics dan acceptance journeys. Terakhir Validate. Pastikan Journey Progress, Acceptance Results, dan Reporting Sufficiency semuanya lulus dengan evidence baru.

Generate Full juga berhenti setelah satu batch populasi baru untuk membatasi transaksi HTTP; tidak ada background job atau commit manual.

## Populasi yang direncanakan

| Domain | Tambahan | Status owner |
| --- | ---: | --- |
| Booking | 536 | done / cancelled |
| Procedure | 536 | done / cancelled |
| Billing | 536 | posted / cancelled |
| Insurance authorization | 120 | prepared / cancelled |
| Membership enrollment | 120 | draft / cancelled |
| Inventory usage | 536 | done / cancel |
| Wallet top-up | 536 | posted / canceled |
| Incident | 24 | triage |
| Total transaksi utama | 2.944 | |

Jumlah ini tidak memasukkan encounter, policy, stock move, accounting move, execution log, dan integration event pendukung. 536 adalah jumlah semua status, bukan 536 posting. Batch per domain/periode mempunyai business key tetap, waktu relatif anchor, variasi jumlah bulanan, empat persona historis, tiga unit persediaan dan empat wallet. Booking → Encounter → Procedure → Billing memiliki relasi sumber eksplisit. Ini populasi sintetis untuk demo, bukan transaksi pasien nyata.

Inventory memakai produk sumber donasi zero-value; bukan demonstrasi kompleksitas valuasi persediaan. Insurance prepared tidak menyatakan approval payer. Membership draft bukan anggota aktif. Incident triage bukan kasus resolved. Pembatasan tersebut sengaja dipertahankan sesuai workflow owner, tanpa memalsukan status.

## Kontrak keamanan dan determinisme

Satu setup dan 96 batch domain/bulan, dengan dependencies eksplisit. Identitas accounting, procedure event, billing event dan membership event diberikan sebelum workflow terkait; generator tidak memanggil production sequence atau UUID. Owner billing/membership kini menerima kontrak nama event opsional; caller produksi tanpa kontrak mempertahankan perilaku sebelumnya. Collision lintas sumber ditolak. Event baru diabaikan melalui action_ignore; tidak ada dispatch eksternal dari adapter.

Preflight mencakup field, method, role, akses actor, prerequisite dan company. Owner tetap memeriksa business constraint saat eksekusi; kegagalan membatalkan batch melalui savepoint. Record terikat provenance run; record asing tidak diadopsi. Posting yang selesai tidak diputar ulang atau dikembalikan ke draft. Reset data finansial tetap konservatif.

## Batas acceptance dan validasi paket

Reporting Sufficiency meminta minimal 500 observasi domain rutin dan 120 authorization/enrollment, minimal tiga dimensi, dua status, 12 bulan dan lima exception. Recipe batch dan owner validation tetap wajib; jumlah saja tidak membuktikan kesiapan enterprise penuh. V1 menggunakan 12 periode dalam jendela historis 365 hari master, bukan klaim target preferensi 18–24 bulan atau keseluruhan 15–50 ribu record telah tercapai.

252 source/behavioral tests PASS; guardrail clinic_demo, clinic_billing dan clinic_membership PASS; parse composite 939 Python + 517 XML tanpa error. Test memakai analisis sumber dan record doubles. Database Odoo native tidak tersedia dalam lingkungan build: instalasi, ACL record aktual, lock accounting, konflik jadwal dan seluruh lifecycle belum diuji runtime di sini. Jangan menafsirkan hasil ini sebagai runtime PASS.











