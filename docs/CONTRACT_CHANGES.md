# Usulan Perubahan Kontrak

> Setiap perubahan pada `AGENT.md` Bagian 6 harus dicatat di sini dan disetujui
> kedua anggota sebelum diimplementasikan.

## PC-001 — Tie-break untuk rantai sama panjang

- **Tanggal:** 28 November 2026
- **Diusulkan oleh:** Dzikra
- **Status:** Diimplementasikan di `core/chain.py` + `tests/test_core.py`; menunggu persetujuan Kibar
- **Menyentuh:** `AGENT.md` 6.3, `core/chain.py`, `node/node.py`, `tests/test_core.py`, `tests/test_node.py`

### Masalah

Pada demo 4 node, difficulty 3, 10 blok, rantai akhir tidak identik. Dua node
dapat menambang blok ke-10 yang berbeda. Karena `replace_chain` hanya menerima
rantai yang lebih panjang, dua rantai sama panjang tidak pernah diselesaikan.
Node juga langsung keluar saat `index >= blocks_target` sehingga tidak ada
kesempatan bertukar rantai.

### Usulan aturan

`replace_chain(new_chain)` menerima rantai baru bila:

1. rantai valid penuh; dan
2. lebih panjang dari rantai lokal; atau
3. sama panjang dan hash blok terakhir baru **lebih kecil secara
   leksikografis** daripada hash blok terakhir lokal.

Rantai sama panjang dengan hash terakhir lebih besar tetap ditolak. Perbandingan
memakai string hex 64 karakter, sehingga deterministik di semua node.

### Perubahan perilaku

- Validasi blok, PoW, genesis, dan aturan rantai terpanjang tidak berubah.
- Hanya pemilihan rantai saat seri yang berubah.
- Tidak ada perubahan format pesan, CSV, atau metrik.

### Pembagian implementasi

- **Dzikra (selesai):**
  - `core/chain.py::replace_chain` menerima rantai sama panjang bila hash
    blok terakhir baru lebih kecil.
  - Test `tests/test_core.py`: rantai lebih panjang tetap menang; rantai sama
    panjang dengan hash lebih kecil diterima; rantai sama panjang dengan hash
    lebih besar ditolak.
- **Kibar (belum):**
  - Grace period 1–2 detik setelah target tercapai, tetap melayani `GET_CHAIN`
    dan meminta chain secara periodik sebelum keluar.
  - Test 4 node, difficulty 3, 10 blok, 3 ulangan; seluruh `chain.to_list()`
    harus identik.
- **Dzikra (selesai):** memperbarui `AGENT.md` 6.3, `docs/INTEGRASI_CORE.md`,
  `docs/report/bab2.md`, dan `docs/report/bab3_1.md`.

### Alternatif yang ditolak

- **Menambang satu blok ekstra:** masih probabilistik dan mengubah arti
  `blocks_target` serta metrik.
- **Hanya satu node menambang blok terakhir:** menghilangkan perilaku paralel
  yang justru ingin diukur.
- **Tie-break berdasarkan jumlah transaksi atau timestamp:** tidak deterministik
  lintas node karena timestamp memakai jam masing-masing node.

### Dampak laporan

Bab 3.1/3.2 dan Bab 5 menjelaskan aturan: rantai terpanjang menang; jika sama
panjang, hash blok terakhir terkecil yang dipilih. Tidak ada angka benchmark
yang berubah selain konsistensi rantai akhir.

### Rencana pengujian

- Unit test `core/chain.py` untuk ketiga kasus di atas.
- Integration test 4 node, difficulty 3, 10 blok, 3 ulangan → semua rantai identik.
- Demo manual 4 node difficulty 3 10 blok → hash blok ke-10 sama di semua node.

### Bukti validasi (28 November 2026)

Prototipe grace period 1 detik dijalankan di salinan terpisah (bukan `node/`
repo) dengan `core/` yang sudah memakai PC-001:

| Skenario | Hasil |
|---|---|
| Tie-break saja, 4 node d3 10 blok, 3 ulangan | ❌ 0/3 identik (node terbelah dua kubu) |
| Tie-break + grace period 1 detik, 4 node d3 10 blok, 3 ulangan | ✅ 3/3 identik |
| `pytest -q` dengan grace period | ✅ 74 passed |
| `pytest tests/test_node.py` 3× berturut-turut | ✅ 5 passed setiap run |

Kesimpulan: tie-break saja tidak cukup. Grace period wajib masuk bersama
PC-001, jika tidak node keluar sebelum sempat bertukar rantai.

### Catatan `fork_detected` (bukan bug)

Pada 3 run di atas: 21–22 blok ditambang per run, 10 masuk rantai akhir,
11–12 menjadi orphan, dan `fork_detected` 34–36. Angka itu setara
**3 × jumlah orphan** karena setiap blok orphan dikirim ke tiga peer dan
setiap penolakan dicatat. Jadi `fork_detected` menghitung *kejadian* blok
saingan yang diterima, bukan jumlah orphan unik. Tidak perlu dedupe; cukup
jelaskan definisinya di laporan.
