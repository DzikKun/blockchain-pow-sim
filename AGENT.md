# AGENT.md — Proyek UAS KPT: Simulasi Blockchain Terdistribusi

> **Satu file untuk semua.** Berisi konteks proyek, kontrak teknis, alur Git, dan instruksi tugas masing-masing anggota.
>
> **Cara pakai (untuk AI agent):**
> 1. Baca seluruh Bagian 1-8 (konteks dan aturan bersama).
> 2. Tanyakan atau deteksi siapa penggunanya. Jika pengguna bilang "saya Dzikra" → kerjakan **hanya Bagian 9**. Jika "saya Kibar" → kerjakan **hanya Bagian 10**.
> 3. Jangan mengerjakan tugas atau mengedit folder milik anggota lain.
>
> **Pembaruan 26 November 2026 — pengalihan tugas:** karena `node/` belum selesai dan data benchmark dibutuhkan lebih dulu, **`bench/` dan `README.md` dialihkan dari Kibar ke Dzikra**. Kibar fokus menyelesaikan `node/` dan `tests/test_node.py`. Rincian baru ada di Bagian 4, 5, 9, dan 10.

---

## 1. Konteks Proyek

- **Mata kuliah:** KPT (UAS), **Tema 4: Distributed Blockchain Simulation**
- **Judul:** Analisis Pengaruh Jumlah Node dan Tingkat Kesulitan Mining terhadap Throughput Blockchain Terdistribusi
- **Tujuan:** Membuat simulasi blockchain Proof of Work dengan beberapa node (tiap node = 1 proses OS) di satu laptop, lalu mengukur pengaruh **jumlah node** dan **difficulty** terhadap throughput, waktu blok, latensi sinkronisasi, dan jumlah fork.
- **Mengapa judul ini:** paling ringan dan gratis, bisa dijalankan di laptop biasa, hasilnya mudah dijadikan tabel dan grafik, dan bisa membahas isu konsumsi energi PoW (makin tinggi difficulty → makin besar waktu dan CPU)...

## 2. Anggota dan Spesifikasi Laptop

| Anggota | CPU | RAM | OS | Catatan |
|---|---|---|---|---|
| **Kibar** | Intel i5-6200U @2.3GHz (2C/4T, 2016) | 8 GB | Windows 10 Pro 22H2 | Storage ~51 GB bebas. **Patokan terendah** |
| **Dzikra** | Intel i3-N305 @1.8GHz (8C) | 8 GB | Windows 11 25H2 | Storage ~100 GB bebas. Laptop utama demo dan uji skala besar |

Tanpa GPU. Perbedaan hardware ini sengaja dijadikan **bahan analisis tambahan** di laporan.

## 3. Batasan Teknis (WAJIB dipatuhi)

- Python **3.10+** di kedua laptop.
- Library inti hanya standar: `hashlib`, `multiprocessing`, `socket`, `threading`, `json`, `subprocess`.
- Library tambahan hanya untuk analisis dan test: `pandas`, `matplotlib`, `psutil`, `pytest`.
- **Difficulty maksimal 5. Node maksimal 8.** Tanpa cloud berbayar, tanpa koin asli.
- Semua skenario di grid umum harus bisa jalan di laptop Kibar.
- Mining memakai proses node itu sendiri (**1 node = 1 proses, mining single-process**). Jangan `threading` untuk hashing berat (kena GIL) dan jangan spawn proses mining tambahan.
- Semua socket hanya ke `127.0.0.1`.

## 4. Pembagian Kerja (ringkas)

| | **Dzikra** | **Kibar** |
|---|---|---|
| Fokus | Core blockchain + benchmark + analisis data | Jaringan antar-node + demo |
| Folder | `core/`, `bench/`, `analysis/`, `tests/test_core.py`, `tests/test_bench.py`, `tests/test_analysis.py`, `results/figures/`, `README.md`, `requirements.txt` | `node/`, `tests/test_node.py` |
| Laporan | Bab 1, 2, 3.1, 5 | Bab 3.2, 4, 6 |
| Eksperimen | Grid umum + grid tambahan (8 node, difficulty 5) | Grid umum saja (memakai runner dari Dzikra) |

**Aturan emas:** jangan edit folder milik orang lain. Butuh perubahan di sana → buka Issue GitHub atau minta orangnya. Perubahan kontrak → lewat PR ke file ini dan kabari yang lain.

**Alasan pengalihan (26 November 2026):** `node/` belum tersedia di remote, sedangkan analisis dan laporan Dzikra membutuhkan CSV benchmark. Agar tidak saling menunggu, Dzikra mengambil `bench/` dan `README.md`; Kibar berkonsentrasi pada `node/` yang menjadi prasyarat demo dan benchmark asli.

Supaya bisa paralel: Dzikra membuat core dengan signature sesuai kontrak (Bagian 5), Kibar memakai **mock lokal** sampai core asli ter-merge, dan Dzikra menguji runner benchmark dengan **node palsu** (`tests/fake_node.py`) sampai `node/run.py` tersedia.

## 5. Struktur Repo

```
blockchain-sim/
├── AGENT.md               # file ini
├── README.md              # DZIKRA: instalasi, demo, benchmark
├── requirements.txt       # Dzikra
├── .gitignore
├── core/                  # DZIKRA: block.py, pow.py, chain.py
├── analysis/              # DZIKRA: make_dummy.py, analyze.py, make_tables.py, microbench_core.py
├── node/                  # KIBAR: network.py, node.py, run.py
├── bench/                 # DZIKRA: run_experiments.py
├── tests/
│   ├── test_core.py       # DZIKRA
│   ├── test_analysis.py   # DZIKRA
│   ├── test_bench.py      # DZIKRA
│   ├── fake_node.py       # DZIKRA: mock node untuk menguji bench tanpa node/
│   └── test_node.py       # KIBAR
├── results/
│   ├── raw/               # CSV: <machine>_<timestamp>.csv (dua-duanya commit)
│   ├── raw/logs/          # log JSONL per node saat benchmark (di-ignore)
│   ├── dummy/             # CSV simulasi awal (di-ignore)
│   ├── microbench/        # DZIKRA: hasil microbenchmark core
│   ├── figures/           # DZIKRA: PNG grafik
│   ├── summary.csv        # DZIKRA: agregasi hasil analyze.py
│   └── tables.md          # DZIKRA: tabel Markdown Bab 5
└── docs/
    ├── INTEGRASI_CORE.md  # DZIKRA: panduan core/ untuk node/
    └── report/            # bab1.md, bab2.md, bab3_1.md, bab3_2.md, bab4.md, bab5.md, bab6.md
```

## 6. KONTRAK ANTARMUKA (jangan diubah sepihak)

### 6.1 `core/block.py`
```python
class Block:
    index: int
    timestamp: float
    transactions: list[dict]
    prev_hash: str
    nonce: int
    hash: str

    def compute_hash(self) -> str: ...      # sha256 dari field tanpa 'hash', deterministik
    def to_dict(self) -> dict: ...
    @staticmethod
    def from_dict(d: dict) -> "Block": ...
```

### 6.2 `core/pow.py`
```python
def mine(block: Block, difficulty: int, should_stop=None) -> tuple[Block | None, int]:
    """
    Cari nonce sehingga hash diawali `difficulty` karakter '0'.
    should_stop: callable() -> bool, dicek tiap 1000 iterasi.
                 True -> berhenti, return (None, attempts).
    return: (block_berhasil_atau_None, jumlah_attempts)
    """

def is_valid_pow(block: Block, difficulty: int) -> bool: ...
```

### 6.3 `core/chain.py`
```python
class Blockchain:
    def __init__(self, difficulty: int): ...   # otomatis buat genesis DETERMINISTIK (sama di semua node)
    chain: list[Block]
    difficulty: int
    @property
    def last_block(self) -> Block: ...
    def new_block(self, transactions: list[dict]) -> Block: ...   # belum di-mine, prev_hash = last_block.hash
    def add_block(self, block: Block) -> bool: ...                 # cek index, prev_hash, hash, PoW -> append
    def is_valid_chain(self, chain: list[Block]) -> bool: ...
    def replace_chain(self, new_chain: list[Block]) -> bool: ...   # lebih panjang, atau sama panjang dengan hash terakhir lebih kecil; DAN valid
    def to_list(self) -> list[dict]: ...
```

**Aturan tie-break (PC-001).** `replace_chain` menerima rantai yang lebih panjang;
jika panjangnya sama, rantai dengan **hash blok terakhir lebih kecil secara
leksikografis** yang menang. Aturan ini deterministik sehingga dua node yang
menambang blok berbeda pada ketinggian sama tetap memilih rantai yang sama.
Perubahan ini tercatat di `docs/CONTRACT_CHANGES.md`.

### 6.4 Protokol jaringan
Transport TCP localhost. 1 pesan = 1 baris JSON diakhiri `\n`. Node ke-`i` listen di port `5000 + i`.

| type | payload | arti |
|---|---|---|
| `NEW_BLOCK` | `{"block": {...}, "sender": int, "sent_at": float}` | broadcast blok hasil mining |
| `GET_CHAIN` | `{"sender": int}` | minta chain lengkap |
| `CHAIN` | `{"chain": [...], "sender": int}` | balasan chain lengkap |
| `TX` | `{"tx": {...}}` | transaksi baru (opsional) |

### 6.5 Entry point node dan log event
```
python -m node.run --id 0 --port 5000 --peers 5001,5002,5003 --difficulty 3 --blocks 10 --log results/raw/events_<run>.jsonl
```
Satu baris JSON per event:
```json
{"t": 1731000000.123, "node": 0, "event": "block_mined", "index": 3, "hash": "000ab..", "attempts": 18234}
{"t": 1731000000.456, "node": 1, "event": "block_received", "index": 3, "sender": 0, "sent_at": 1731000000.130}
{"t": 1731000000.500, "node": 2, "event": "fork_detected", "index": 3}
{"t": 1731000000.600, "node": 2, "event": "chain_replaced", "old_len": 3, "new_len": 4}
```

### 6.6 Format CSV hasil: `results/raw/<machine>_<timestamp>.csv`
Satu baris = satu run. `machine` ∈ {`kibar`, `dzikra`}.
```
machine,run_id,nodes,difficulty,blocks_target,blocks_confirmed,total_time_s,throughput_bps,avg_block_time_s,avg_sync_latency_ms,forks_detected,orphan_blocks,cpu_avg_pct
```
- `throughput_bps` = `blocks_confirmed / total_time_s`
- `avg_sync_latency_ms` = rata-rata `(t_received - sent_at) × 1000`
- `orphan_blocks` = blok yang di-mine tapi tidak masuk chain final
- Dihasilkan oleh `bench/run_experiments.py` (**Dzikra**), dibaca oleh `analysis/analyze.py` (Dzikra).
- Kolom tambahan `status` (`ok` / `timeout` / `error`) boleh ditulis **di akhir** baris untuk menandai run yang gagal. `analysis/analyze.py` mengabaikan kolom tambahan ini dan mendeteksi timeout dari `blocks_confirmed < blocks_target`.

## 7. Matriks Eksperimen

Semua run: **3 ulangan**, charger tercolok, Windows power mode "Best performance", tutup aplikasi berat.

| Grid | Node | Difficulty | Blok | Laptop |
|---|---|---|---|---|
| **Umum (dibandingkan antar-laptop)** | 2, 4 | 1, 2, 3, 4 | 10 | Kibar + Dzikra |
| Tambahan | 8 | 1, 2, 3, 4 | 10 | Dzikra |
| Tambahan | 2, 4, 8 | 5 | 10 | Dzikra |

**Catatan d5:** gunakan timeout minimal **180 detik** (disarankan 240) dan jeda pendinginan **5–10 detik** antar-run. Jalankan d5 paling akhir. Dasar angkanya ada di Catatan teknis Dzikra (Bagian 9).

## 8. Alur Git, Timeline, dan Definition of Done

### Alur Git
1. Dzikra membuat repo dan push skeleton (Fase 0), mengundang Kibar sebagai collaborator. Kibar clone.
2. Branch per fitur: `feat/dzikra-core`, `feat/dzikra-analysis`, `feat/dzikra-bench`, `feat/kibar-node`.
3. Commit kecil dan sering. Format pesan: `core: tambah validasi PoW`, `node: implement broadcast`, `bench: tambah timeout d5`.
4. Merge ke `main` lewat Pull Request, yang lain melihat sekilas sebelum merge.
5. Sebelum mulai kerja: `git pull --rebase origin main`.
6. CSV hasil dari masing-masing laptop di-commit ke `results/raw/` dengan nama file berisi `machine` (tidak bentrok). Log mentah `results/raw/logs/` tidak di-commit.

### Timeline (tambahkan tanggal sesuai deadline)
| Fase | Isi | Siapa |
|---|---|---|
| 0 | Repo, skeleton, file ini disepakati | Dzikra (Kibar review) |
| 1 | Paralel: Dzikra `core/` minimal lalu analisis; Kibar `node/` dengan mock | keduanya |
| 2 | Integrasi: node memakai core asli, demo 4 node, 10 blok. Dzikra mengerjakan `bench/` paralel | keduanya |
| 3 | Benchmark di masing-masing laptop memakai runner Dzikra | keduanya |
| 4 | Analisis, grafik, laporan, README, demo | keduanya |

**Titik sinkron kritis:**
- Begitu `core/` versi minimal jalan, Dzikra **segera merge dan kabari Kibar**.
- Begitu `node/run.py` bisa dijalankan, Kibar **kabari Dzikra** agar benchmark asli bisa dimulai.
- Runner `bench/` sudah tersedia di branch `feat/dzikra-core` dan diuji dengan node palsu; Dzikra **kabari Kibar** setelah CSV-nya terbaca `analysis/analyze.py`.

### Definition of Done
- [ ] `pytest` hijau di kedua laptop
- [ ] Demo: 4 node, difficulty 3, 10 blok, semua chain akhir identik
- [ ] Minimal 1 skenario fork terdeteksi dan terselesaikan (longest chain)
- [ ] CSV dari kedua laptop ada di `results/raw/`
- [ ] Grafik di `results/figures/`
- [ ] Laporan lengkap di `docs/report/`
- [ ] README berisi cara install dan cara menjalankan

### Aturan untuk AI Agent
- Kerjakan hanya bagianmu dan hanya di foldermu.
- Patuhi kontrak Bagian 6. Jika harus mengubah, jangan diam-diam: tulis usulan di `docs/CONTRACT_CHANGES.md` dan minta konfirmasi manusia.
- Jangan tambah dependency di luar yang diizinkan tanpa izin.
- Jangan naikkan difficulty di atas 5 atau node di atas 8.
- Setiap fungsi baru harus punya test atau contoh pemakaian minimal.
- Jika terblokir menunggu pekerjaan anggota lain, buat stub/mock lokal (jangan commit ke folder orang lain) dan lanjutkan.

---

## 9. INSTRUKSI DZIKRA — Core Blockchain, Benchmark, dan Analisis Data

**Folder milikmu:** `core/`, `bench/`, `analysis/`, `tests/test_core.py`, `tests/test_bench.py`, `tests/test_analysis.py`, `tests/fake_node.py`, `results/figures/`, `README.md`, `requirements.txt`
**Jangan sentuh:** `node/`, `tests/test_node.py`, `docs/report/bab3_2.md`, `bab4.md`, `bab6.md`
**Catatan:** `bench/` dan `README.md` dialihkan dari Kibar ke kamu sejak 26 November 2026. `node/` tetap milik Kibar.

### Fase 0 — Setup repo (duluan, selesaikan cepat)
- [ ] Buat repo GitHub `blockchain-sim`, undang Kibar
- [ ] Push struktur folder (Bagian 5) dan file `AGENT.md` ini
- [ ] Buat `requirements.txt` (`pandas`, `matplotlib`, `psutil`, `pytest`) dan `.gitignore` (`__pycache__/`, `.venv/`, `*.pyc`)
- [ ] Push **skeleton `core/`** dengan signature persis sesuai kontrak (boleh `raise NotImplementedError`) agar Kibar bisa mulai import

### Fase 1 — Core (prioritas utama)
**D1. `core/block.py`**
- [ ] Class `Block` sesuai kontrak 6.1
- [ ] `compute_hash()`: SHA-256 dari JSON dengan `sort_keys=True` atas `index, timestamp, transactions, prev_hash, nonce` (tanpa field `hash`)
- [ ] `to_dict()` / `from_dict()` bolak-balik tanpa kehilangan data
- *Selesai jika:* `Block.from_dict(b.to_dict()).compute_hash() == b.hash`

**D2. `core/pow.py`**
- [ ] `mine(...)` sesuai kontrak 6.2, cek `should_stop()` tiap 1000 iterasi (bukan tiap iterasi)
- [ ] Kembalikan `attempts`; tambahkan `assert difficulty <= 5`
- [ ] `is_valid_pow(block, difficulty)`
- *Selesai jika:* difficulty 3 selesai < 2 detik di laptopmu; `should_stop` yang return True menghentikan mining dengan `(None, attempts)`

**D3. `core/chain.py`**
- [ ] Genesis block **deterministik** (misal `timestamp=0`, nonce tetap) agar identik di semua node
- [ ] `new_block`, `add_block` (cek index berurutan, `prev_hash`, hash benar, PoW valid)
- [ ] `is_valid_chain`, `replace_chain` (ganti jika lebih panjang DAN valid; jika sama panjang, hash terakhir lebih kecil menang), `to_list()`
- *Selesai jika:* chain yang dimanipulasi (ubah 1 transaksi) ditolak oleh `is_valid_chain`

**D4. `tests/test_core.py`**
- [ ] Test: hash deterministik, mining valid, tampering terdeteksi, `replace_chain` menerima rantai lebih panjang dan tie-break hash terkecil, serialisasi bolak-balik
- [ ] `pytest tests/test_core.py` hijau

> **Begitu D1-D3 jalan minimal: PR, merge ke `main`, kabari Kibar.** Jangan tunggu sempurna. Rapikan di PR berikutnya.

### Fase 1b — Analisis (paralel selagi menunggu `node/`)
**D5. `analysis/make_dummy.py`**
- [ ] Hasilkan CSV palsu sesuai kontrak 6.6 agar grafik bisa dikembangkan tanpa menunggu benchmark asli
- [ ] Tulis ke `results/dummy/` (di-ignore Git), bukan ke `results/raw/`

**D6. `analysis/analyze.py`**
- [ ] Baca semua `results/raw/*.csv`, gabungkan dengan `pandas`
- [ ] Hitung rata-rata dan standar deviasi per `(machine, nodes, difficulty)`, simpan ke `results/summary.csv` dan print ke terminal
- [ ] Deteksi run timeout (`blocks_confirmed < blocks_target`), sediakan opsi `--exclude-timeouts`
- [ ] Lewati file yang kolomnya tidak lengkap dengan peringatan, jangan crash
- [ ] Grafik PNG di `results/figures/` (judul dan label sumbu Bahasa Indonesia):
  1. Waktu per blok vs difficulty (garis per jumlah node)
  2. Throughput vs jumlah node (garis per difficulty)
  3. Latensi sinkronisasi vs jumlah node
  4. Fork/orphan vs jumlah node
  5. Perbandingan Kibar vs Dzikra pada grid umum (bar chart)
  6. CPU rata-rata vs difficulty (bahas aspek energi)

**D7. `analysis/make_tables.py`**
- [ ] Hasilkan tabel Markdown Bab 5 dari `results/summary.csv` (grid umum, grid tambahan, rasio Kibar/Dzikra, CPU & proksi energi)
- [ ] Format desimal koma agar konsisten dengan laporan berbahasa Indonesia

**D8. `analysis/microbench_core.py`**
- [ ] Ukur hash rate mentah, hash rate berkelanjutan (deteksi throttling), waktu mining d1–d5, dan waktu verifikasi
- [ ] Simpan CSV ke `results/microbench/` (bukan `results/raw/`)

**D9. Test analisis**
- [ ] `tests/test_analysis.py`: dummy deterministik, agregasi mean/std, deteksi timeout, file rusak, CLI, 6 grafik, microbenchmark
- [ ] `pytest tests/test_analysis.py` hijau

### Fase 2 — Benchmark runner (dialihkan dari Kibar)

**D10. `bench/run_experiments.py`**
- [ ] Argumen: `--machine {kibar,dzikra}`, `--nodes 2,4`, `--difficulty 1,2,3,4`, `--blocks 10`, `--runs 3`
- [ ] Opsi tambahan: `--timeout 180`, `--pause 2`, `--out-dir results/raw`, `--node-module node.run`
- [ ] Tiap kombinasi dan ulangan: spawn N proses node via `subprocess`, tunggu selesai, kumpulkan event JSONL
- [ ] Log per node ke file terpisah di `results/raw/logs/` (folder di-ignore Git)
- [ ] Hitung metrik: `total_time_s`, `blocks_confirmed`, `throughput_bps`, `avg_block_time_s`, `avg_sync_latency_ms`, `forks_detected`, `orphan_blocks`
- [ ] Ukur `cpu_avg_pct` dengan `psutil` (sampling 0,2 detik)
- [ ] Tulis CSV sesuai **kontrak 6.6** ke `results/raw/<machine>_<timestamp>.csv`, plus kolom `status` di akhir
- [ ] **Timeout per run** (default 180 detik), tandai `status=timeout` di CSV lalu lanjut
- [ ] Jeda 2-3 detik antar-run; khusus d5 gunakan jeda 5-10 detik
- [ ] Validasi batas proyek: node ≤ 8, difficulty ≤ 5
- [ ] `--node-module tests.fake_node` agar runner bisa diuji tanpa `node/`
- *Selesai jika:* `python -m bench.run_experiments --machine dzikra --nodes 2 --difficulty 1 --blocks 5 --runs 1` menghasilkan CSV valid yang terbaca `pandas` dan `analysis/analyze.py`

**D11. Test benchmark**
- [ ] `tests/fake_node.py`: node palsu yang menerima argumen kontrak 6.5, bisa disuruh tidur (uji timeout) atau gagal (uji error)
- [ ] `tests/test_bench.py`: metrik, pembacaan JSONL rusak, validasi argumen, end-to-end, timeout, node gagal
- [ ] `pytest tests/test_bench.py` hijau

> Setelah runner selesai dan CSV terbaca, **kabari Kibar**. Jangan menjalankan benchmark asli sebelum `node/run.py` tersedia.

### Fase 3 — Eksperimen di laptopmu
- [ ] `python -m bench.run_experiments --machine dzikra` (runner milikmu) untuk **grid umum dan grid tambahan** (Bagian 7)
- [ ] Commit CSV ke `results/raw/` (nama berisi `dzikra`)
- [ ] Jalankan d5 paling akhir dengan `--timeout 240 --pause 8`
- [ ] Catat kondisi: charger, power mode, tanda throttling/panas

### Fase 4 — Laporan (`docs/report/`, format Markdown)
- [ ] `bab1.md` Pendahuluan (latar belakang, rumusan masalah, tujuan, batasan)
- [ ] `bab2.md` Landasan Teori (blockchain, PoW, difficulty, konsensus, longest chain, throughput, sistem terdistribusi)
- [ ] `bab3_1.md` Desain Core (struktur block, algoritma PoW, validasi)
- [ ] `bab5.md` Hasil dan Analisis (tabel dan grafik, bandingkan dua laptop, bahas energi dan keterbatasan core)
- [ ] `README.md` (dipindahkan dari Kibar): instalasi, demo 4 node, benchmark, analisis, struktur repo

### Catatan teknis Dzikra
- Hash rate laptop ini sekitar **121.000 H/s** saat burst, turun ke **~52.000 H/s** setelah beban penuh (throttling). Jangan memakai angka burst untuk memperkirakan durasi benchmark.
- Waktu mining per blok (1 proses, kondisi throttled): d3 ≈ 0,07 s, d4 ≈ 0,94 s, d5 ≈ **17,7 s**.
- Estimasi d5 2 node 10 blok ≈ **100 detik** → gunakan `--timeout 240 --pause 8`; timeout 120 detik terlalu mepet.
- Verifikasi PoW hanya sekitar **20 µs**, jadi mining yang mendominasi, bukan validasi.
- Genesis wajib deterministik (`timestamp=0`, `nonce=0`) agar hash sama untuk semua difficulty.
- Panduan integrasi `core/` untuk Kibar ada di `docs/INTEGRASI_CORE.md`.

---

## 10. INSTRUKSI KIBAR — Jaringan Antar-Node

**Folder milikmu:** `node/`, `tests/test_node.py`
**Jangan sentuh:** `core/`, `analysis/`, `bench/`, `README.md`, `tests/test_bench.py`, `tests/test_analysis.py`
**Catatan:** `bench/` dan `README.md` dialihkan ke Dzikra sejak 26 November 2026. Fokusmu: menyelesaikan `node/` secepat mungkin agar demo dan benchmark asli bisa dijalankan.
**Ingat:** laptopmu patokan terendah. Jangan menjalankan 8 node di laptopmu (itu bagian Dzikra).

### Fase 0 — Setup
- [ ] Terima undangan repo dari Dzikra, `git clone`, buat venv, `pip install -r requirements.txt`
- [ ] Pahami Bagian 6 (kontrak) sampai jelas
- [ ] Buat branch `feat/kibar-node`

### Fase 1 — Node dan Jaringan (jangan menunggu `core/` asli)
> Sambil menunggu core asli, buat **mock lokal** (`node/_mock_core.py`, jangan di-commit ke `core/`) yang meniru `Block`, `mine`, `Blockchain` secara sederhana. Begitu core asli ter-merge, ganti import-nya.

**K1. `node/network.py`**
- [ ] Server TCP (`socket` + `threading`) di port `5000 + id`, terima pesan JSON per baris
- [ ] `send(port, message_dict)` dengan timeout 1-2 detik, tangani koneksi gagal tanpa crash
- [ ] `broadcast(peers, message_dict)`; format pesan sesuai 6.4
- [ ] Set `SO_REUSEADDR` agar port bisa dipakai ulang antar-run
- *Selesai jika:* 2 proses bisa saling kirim dan terima di localhost

**K2. `node/node.py`**
- [ ] Class `Node(id, port, peers, difficulty, blocks_target, log_path)`
- [ ] Loop mining: `Blockchain.new_block(...)` → `mine(block, difficulty, should_stop)`, dengan `should_stop` membaca flag yang di-set saat ada blok valid dari peer
- [ ] Blok berhasil → `add_block` lokal → broadcast `NEW_BLOCK` (isi `sent_at = time.time()`)
- [ ] Terima `NEW_BLOCK` valid dan menyambung → `add_block`, hentikan mining sekarang, mulai blok berikutnya
- [ ] Berhenti saat chain lokal mencapai `blocks_target` blok (di luar genesis)
- [ ] **Wajib:** setelah target tercapai, beri **grace period 1 detik** sambil terus mengirim `GET_CHAIN` tiap ±0,2 detik. Tanpa ini, blok saingan di ketinggian yang sama tidak pernah dipertukarkan dan rantai akhir 4 node berbeda. Prototipe dengan jeda 1 detik menghasilkan rantai identik 3/3 run.

**K3. Sinkronisasi dan Fork**
- [ ] `NEW_BLOCK` yang tidak menyambung (index lompat atau `prev_hash` beda) → kirim `GET_CHAIN` ke pengirim
- [ ] Terima `CHAIN` → `replace_chain` (rantai lebih panjang menang; jika sama panjang, hash blok terakhir lebih kecil menang — PC-001)
- [ ] Catat event `fork_detected` dan `chain_replaced`
- [ ] Node yang tertinggal bisa sync lewat `GET_CHAIN` saat start

**K4. Logging event**
- [ ] Tulis JSONL sesuai 6.5: `block_mined`, `block_received` (sertakan `sent_at`), `fork_detected`, `chain_replaced`
- [ ] Gunakan `time.time()` (satu mesin, latensi valid) dan lock agar tulis log antar-thread tidak bercampur

**K5. `node/run.py`**
- [ ] CLI sesuai 6.5 (`--id --port --peers --difficulty --blocks --log`)
- [ ] Pakai `if __name__ == "__main__":` (wajib di Windows)

**K6. `tests/test_node.py`**
- [ ] 2 node, difficulty 1, 3 blok → chain akhir identik
- [ ] **4 node, difficulty 3, 10 blok, 3 ulangan → semua `chain.to_list()` identik** (jalankan lewat subprocess agar race tertangkap)
- [ ] Node tertinggal bisa sync via `GET_CHAIN`
- [ ] Blok invalid (hash dirusak) ditolak

### Fase 2 — Integrasi (setelah `core/` Dzikra ter-merge)
- [ ] `git pull --rebase origin main`, ganti mock dengan `core.*`
- [ ] Demo: 4 node, difficulty 3, 10 blok → semua chain identik
- [ ] Buat skenario fork sengaja (difficulty 1 dengan banyak node) dan pastikan terselesaikan
- [ ] Bug di `core/` → laporkan lewat Issue GitHub, jangan edit sendiri

### Fase 2b — Serah terima benchmark
- [ ] **Tidak perlu membuat `bench/`.** Runner sudah dikerjakan Dzikra (`bench/run_experiments.py`) dan diuji dengan node palsu.
- [ ] Pastikan `node/run.py` menerima argumen persis kontrak 6.5: `--id --port --peers --difficulty --blocks --log`.
- [ ] Setelah `node/run.py` bisa dijalankan, **kabari Dzikra** agar benchmark asli dimulai.
- [ ] Baca `README.md` untuk cara menjalankan benchmark di laptopmu.

### Fase 3 — Eksperimen di laptopmu
- [ ] Charger tercolok, power mode "Best performance", tutup Chrome dan aplikasi berat
- [ ] Jalankan **hanya grid umum**: node 2, 4 × difficulty 1-4 × 10 blok × 3 ulangan
  ```powershell
  python -m bench.run_experiments --machine kibar --nodes 2,4 --difficulty 1,2,3,4 --blocks 10 --runs 3
  ```
- [ ] Commit CSV ke `results/raw/` (nama berisi `kibar`)
- [ ] Catat throttling atau run yang timeout

### Fase 4 — Laporan
- [ ] `docs/report/bab3_2.md` Desain Jaringan dan Arsitektur Node (diagram, protokol pesan, broadcast, sinkronisasi, resolusi fork)
- [ ] `docs/report/bab4.md` Metodologi Pengujian (spesifikasi laptop, parameter, matriks eksperimen, metrik, cara ambil data)
- [ ] `docs/report/bab6.md` Kesimpulan dan Saran
- [ ] Skrip/langkah demo presentasi (4 node, difficulty 3, tunjukkan log fork jika ada)
- [ ] Serahkan log/dokumentasi demo ke Dzikra untuk bahan Bab 5

### Catatan teknis Kibar
- 1 node = 1 proses; dengan 4 thread logis, 4 node sudah memenuhi laptopmu.
- Handler koneksi pakai thread (I/O-bound, aman dengan GIL). Mining tetap di thread utama node.
- Windows Firewall mungkin meminta izin Python saat pertama kali: pilih "Allow" (hanya private network).
