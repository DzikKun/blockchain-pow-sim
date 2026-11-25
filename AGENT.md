# AGENT.md — Proyek UAS KPT: Simulasi Blockchain Terdistribusi

> **Satu file untuk semua.** Berisi konteks proyek, kontrak teknis, alur Git, dan instruksi tugas masing-masing anggota.
>
> **Cara pakai (untuk AI agent):**
> 1. Baca seluruh Bagian 1-8 (konteks dan aturan bersama).
> 2. Tanyakan atau deteksi siapa penggunanya. Jika pengguna bilang "saya Dzikra" → kerjakan **hanya Bagian 9**. Jika "saya Kibar" → kerjakan **hanya Bagian 10**.
> 3. Jangan mengerjakan tugas atau mengedit folder milik anggota lain.

---

## 1. Konteks Proyek

- **Mata kuliah:** KPT (UAS), **Tema 4: Distributed Blockchain Simulation**
- **Judul:** Analisis Pengaruh Jumlah Node dan Tingkat Kesulitan Mining terhadap Throughput Blockchain Terdistribusi
- **Tujuan:** Membuat simulasi blockchain Proof of Work dengan beberapa node (tiap node = 1 proses OS) di satu laptop, lalu mengukur pengaruh **jumlah node** dan **difficulty** terhadap throughput, waktu blok, latensi sinkronisasi, dan jumlah fork.
- **Mengapa judul ini:** paling ringan dan gratis, bisa dijalankan di laptop biasa, hasilnya mudah dijadikan tabel dan grafik, dan bisa membahas isu konsumsi energi PoW (makin tinggi difficulty → makin besar waktu dan CPU).

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
| Fokus | Core blockchain + analisis data | Jaringan antar-node + benchmark |
| Folder | `core/`, `analysis/`, `tests/test_core.py`, `results/figures/`, `requirements.txt` | `node/`, `bench/`, `tests/test_node.py`, `README.md` |
| Laporan | Bab 1, 2, 3.1, 5 | Bab 3.2, 4, 6 |
| Eksperimen | Grid umum + grid tambahan (8 node, difficulty 5) | Grid umum saja |

**Aturan emas:** jangan edit folder milik orang lain. Butuh perubahan di sana → buka Issue GitHub atau minta orangnya. Perubahan kontrak → lewat PR ke file ini dan kabari yang lain.

Supaya bisa paralel: Dzikra membuat core dengan signature sesuai kontrak (Bagian 5), Kibar memakai **mock lokal** sampai core asli ter-merge, dan Dzikra memakai **CSV dummy** sampai data benchmark asli ada.

## 5. Struktur Repo

```
blockchain-sim/
├── AGENT.md               # file ini
├── README.md              # Kibar
├── requirements.txt       # Dzikra
├── .gitignore
├── core/                  # DZIKRA: block.py, pow.py, chain.py
├── analysis/              # DZIKRA: make_dummy.py, analyze.py
├── node/                  # KIBAR: network.py, node.py, run.py
├── bench/                 # KIBAR: run_experiments.py
├── tests/
│   ├── test_core.py       # DZIKRA
│   └── test_node.py       # KIBAR
├── results/
│   ├── raw/               # CSV: <machine>_<timestamp>.csv (dua-duanya commit)
│   └── figures/           # DZIKRA: PNG grafik
└── docs/report/           # bab1.md, bab2.md, bab3_1.md, bab3_2.md, bab4.md, bab5.md, bab6.md
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
    def replace_chain(self, new_chain: list[Block]) -> bool: ...   # hanya jika lebih panjang DAN valid
    def to_list(self) -> list[dict]: ...
```

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
- Dihasilkan oleh `bench/run_experiments.py` (Kibar), dibaca oleh `analysis/analyze.py` (Dzikra).

## 7. Matriks Eksperimen

Semua run: **3 ulangan**, charger tercolok, Windows power mode "Best performance", tutup aplikasi berat.

| Grid | Node | Difficulty | Blok | Laptop |
|---|---|---|---|---|
| **Umum (dibandingkan antar-laptop)** | 2, 4 | 1, 2, 3, 4 | 10 | Kibar + Dzikra |
| Tambahan | 8 | 1, 2, 3, 4 | 10 | Dzikra |
| Tambahan | 2, 4, 8 | 5 | 10 | Dzikra |

## 8. Alur Git, Timeline, dan Definition of Done

### Alur Git
1. Dzikra membuat repo dan push skeleton (Fase 0), mengundang Kibar sebagai collaborator. Kibar clone.
2. Branch per fitur: `feat/dzikra-core`, `feat/dzikra-analysis`, `feat/kibar-node`, `feat/kibar-bench`.
3. Commit kecil dan sering. Format pesan: `core: tambah validasi PoW`, `node: implement broadcast`, `bench: tambah skenario 4 node`.
4. Merge ke `main` lewat Pull Request, yang lain melihat sekilas sebelum merge.
5. Sebelum mulai kerja: `git pull --rebase origin main`.
6. CSV hasil dari masing-masing laptop di-commit ke `results/raw/` dengan nama file berisi `machine` (tidak bentrok).

### Timeline (tambahkan tanggal sesuai deadline)
| Fase | Isi | Siapa |
|---|---|---|
| 0 | Repo, skeleton, file ini disepakati | Dzikra (Kibar review) |
| 1 | Paralel: Dzikra `core/` minimal dulu lalu analisis, Kibar `node/` dengan mock | keduanya |
| 2 | Integrasi: node memakai core asli, demo 4 node, 10 blok. Kibar lanjut `bench/` | keduanya |
| 3 | Benchmark di masing-masing laptop | keduanya |
| 4 | Analisis, grafik, laporan, README, demo | keduanya |

**Titik sinkron kritis:** begitu `core/` versi minimal jalan, Dzikra **segera merge dan kabari Kibar**. Begitu runner `bench/` jalan, Kibar **kabari Dzikra**.

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

## 9. INSTRUKSI DZIKRA — Core Blockchain + Analisis Data

**Folder milikmu:** `core/`, `analysis/`, `tests/test_core.py`, `results/figures/`, `requirements.txt`
**Jangan sentuh:** `node/`, `bench/`

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
- [ ] `is_valid_chain`, `replace_chain` (ganti hanya jika lebih panjang DAN valid), `to_list()`
- *Selesai jika:* chain yang dimanipulasi (ubah 1 transaksi) ditolak oleh `is_valid_chain`

**D4. `tests/test_core.py`**
- [ ] Test: hash deterministik, mining valid, tampering terdeteksi, `replace_chain` hanya menerima yang lebih panjang dan valid, serialisasi bolak-balik
- [ ] `pytest tests/test_core.py` hijau

> **Begitu D1-D3 jalan minimal: PR, merge ke `main`, kabari Kibar.** Jangan tunggu sempurna. Rapikan di PR berikutnya.

### Fase 1b — Analisis (paralel selagi menunggu data Kibar)
**D5. `analysis/make_dummy.py`**
- [ ] Hasilkan CSV palsu sesuai kontrak 6.6 agar grafik bisa dikembangkan tanpa menunggu benchmark asli

**D6. `analysis/analyze.py`**
- [ ] Baca semua `results/raw/*.csv`, gabungkan dengan `pandas`
- [ ] Hitung rata-rata dan standar deviasi per `(machine, nodes, difficulty)`, simpan ke `results/summary.csv` dan print ke terminal
- [ ] Grafik PNG di `results/figures/` (judul dan label sumbu Bahasa Indonesia):
  1. Waktu per blok vs difficulty (garis per jumlah node)
  2. Throughput vs jumlah node (garis per difficulty)
  3. Latensi sinkronisasi vs jumlah node
  4. Fork/orphan vs jumlah node
  5. Perbandingan Kibar vs Dzikra pada grid umum (bar chart)
  6. CPU rata-rata vs difficulty (bahas aspek energi)

### Fase 3 — Eksperimen di laptopmu
- [ ] `python -m bench.run_experiments --machine dzikra` (dibuat Kibar) untuk **grid umum dan grid tambahan** (Bagian 7)
- [ ] Commit CSV ke `results/raw/` (nama berisi `dzikra`)
- [ ] Catat kondisi: charger, power mode, tanda throttling/panas

### Fase 4 — Laporan (`docs/report/`, format Markdown)
- [ ] `bab1.md` Pendahuluan (latar belakang, rumusan masalah, tujuan, batasan)
- [ ] `bab2.md` Landasan Teori (blockchain, PoW, difficulty, konsensus, longest chain, throughput, sistem terdistribusi)
- [ ] `bab3_1.md` Desain Core (struktur block, algoritma PoW, validasi)
- [ ] `bab5.md` Hasil dan Analisis (tabel dan grafik, bandingkan dua laptop, bahas energi dan keterbatasan core)

---

## 10. INSTRUKSI KIBAR — Jaringan Antar-Node + Benchmark

**Folder milikmu:** `node/`, `bench/`, `tests/test_node.py`, `README.md`
**Jangan sentuh:** `core/`, `analysis/`
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

**K3. Sinkronisasi dan Fork**
- [ ] `NEW_BLOCK` yang tidak menyambung (index lompat atau `prev_hash` beda) → kirim `GET_CHAIN` ke pengirim
- [ ] Terima `CHAIN` → `replace_chain` (longest valid chain)
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
- [ ] Node tertinggal bisa sync via `GET_CHAIN`
- [ ] Blok invalid (hash dirusak) ditolak

### Fase 2 — Integrasi (setelah `core/` Dzikra ter-merge)
- [ ] `git pull --rebase origin main`, ganti mock dengan `core.*`
- [ ] Demo: 4 node, difficulty 3, 10 blok → semua chain identik
- [ ] Buat skenario fork sengaja (difficulty 1 dengan banyak node) dan pastikan terselesaikan
- [ ] Bug di `core/` → laporkan lewat Issue GitHub, jangan edit sendiri

### Fase 2b — Benchmark runner
**K7. `bench/run_experiments.py`**
- [ ] Argumen: `--machine {kibar,dzikra}`, `--nodes 2,4`, `--difficulty 1,2,3,4`, `--blocks 10`, `--runs 3`
- [ ] Tiap kombinasi dan ulangan: spawn N proses node via `subprocess`, tunggu selesai, kumpulkan event JSONL
- [ ] Hitung metrik: `total_time_s`, `blocks_confirmed`, `throughput_bps`, `avg_block_time_s`, `avg_sync_latency_ms`, `forks_detected`, `orphan_blocks`
- [ ] Ukur `cpu_avg_pct` dengan `psutil` (rata-rata CPU sistem selama run, sampling 0.5 detik)
- [ ] Tulis CSV sesuai **kontrak 6.6** ke `results/raw/<machine>_<timestamp>.csv`
- [ ] **Timeout per run** (misal 120 detik), tandai di CSV dan lanjut jika macet
- [ ] Jeda 2-3 detik antar-run (pelepasan port dan pendinginan CPU)
- *Selesai jika:* `python -m bench.run_experiments --machine kibar --nodes 2 --difficulty 1 --blocks 5 --runs 1` menghasilkan CSV valid yang terbaca `pandas`

> Setelah K7 selesai, **kabari Dzikra** agar bisa dicoba di laptopnya.

### Fase 3 — Eksperimen di laptopmu
- [ ] Charger tercolok, power mode "Best performance", tutup Chrome dan aplikasi berat
- [ ] Jalankan **hanya grid umum**: node 2, 4 × difficulty 1-4 × 10 blok × 3 ulangan
- [ ] Commit CSV ke `results/raw/` (nama berisi `kibar`)
- [ ] Catat throttling atau run yang timeout

### Fase 4 — Laporan dan README
- [ ] `docs/report/bab3_2.md` Desain Jaringan dan Arsitektur Node (diagram, protokol pesan, broadcast, sinkronisasi, resolusi fork)
- [ ] `docs/report/bab4.md` Metodologi Pengujian (spesifikasi laptop, parameter, matriks eksperimen, metrik, cara ambil data)
- [ ] `docs/report/bab6.md` Kesimpulan dan Saran
- [ ] `README.md`: instalasi, cara run demo, cara run benchmark, struktur repo
- [ ] Skrip/langkah demo presentasi (4 node, difficulty 3, tunjukkan log fork jika ada)

### Catatan teknis Kibar
- 1 node = 1 proses; dengan 4 thread logis, 4 node sudah memenuhi laptopmu.
- Handler koneksi pakai thread (I/O-bound, aman dengan GIL). Mining tetap di thread utama node.
- Windows Firewall mungkin meminta izin Python saat pertama kali: pilih "Allow" (hanya private network).
