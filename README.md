# Simulasi Blockchain Proof-of-Work Multi-Node

Simulasi blockchain sederhana berbahasa Python untuk tugas **Komputasi Paralel dan Terdistribusi**. Setiap node berjalan sebagai proses terpisah di localhost, menyambung lewat TCP, menambang blok dengan SHA-256, lalu menyinkronkan rantai terpanjang.

Proyek ini mengukur **throughput, waktu per blok, latensi sinkronisasi, fork/orphan, dan penggunaan CPU** pada berbagai kombinasi jumlah node dan difficulty.

## Tim dan Pembagian Tugas

| Anggota | Fokus | Folder |
|---|---|---|
| **Kibar** | Jaringan antar-node dan demo | `node/`, `tests/test_node.py`, `docs/report/bab3_2.md`, `bab4.md`, `bab6.md` |
| **Dzikra** | Core blockchain, benchmark, analisis | `core/`, `bench/`, `analysis/`, `tests/`, `README.md`, `docs/report/bab1.md`, `bab2.md`, `bab3_1.md`, `bab5.md` |

> Catatan status: sejak 26 November 2026, `bench/` dan `README.md` dialihkan dari Kibar ke Dzikra agar Kibar fokus menyelesaikan `node/`. Rincian pembagian tugas ada di `AGENT.md` Bagian 4.

## Kebutuhan

- **Python 3.10+** (diuji pada 3.15.2)
- Windows, Linux, atau macOS
- Dependency: `pandas`, `matplotlib`, `psutil`, `pytest` (lihat `requirements.txt`)

## Instalasi

```powershell
git clone https://github.com/DzikKun/blockchain-pow-sim.git
cd blockchain-pow-sim

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Di Linux/macOS, aktifkan venv dengan `source .venv/bin/activate`.

## Struktur Repo

```
blockchain-pow-sim/
├── core/                  # Block, PoW, Blockchain (Dzikra)
├── node/                  # Server TCP + logika node (Kibar)
├── bench/                 # Runner benchmark (Dzikra)
├── analysis/              # Analisis, grafik, tabel, microbenchmark
├── tests/                 # test_core, test_node, test_bench, test_analysis
├── results/
│   ├── raw/               # CSV benchmark asli + logs/ (log di-ignore)
│   ├── dummy/             # CSV simulasi awal (di-ignore)
│   ├── figures/           # grafik PNG
│   ├── microbench/        # hasil microbenchmark core
│   ├── summary.csv        # agregasi hasil analyze.py
│   └── tables.md          # tabel Markdown Bab 5
└── docs/
    ├── INTEGRASI_CORE.md  # panduan core/ untuk node/
    └── report/            # bab1 .. bab6
```

## Menjalankan Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test tidak membutuhkan jaringan atau `node/` asli. Runner benchmark diuji memakai `tests/fake_node.py`.

## Demo 4 Node (Difficulty 3, 10 Blok)

Buka **empat terminal** di root repo, aktifkan venv di masing-masing, lalu jalankan satu perintah per terminal. Node ke-`i` memakai port `5000 + i` dan mendaftarkan port node lain sebagai peer.

```powershell
# Terminal 1 — node 0
python -m node.run --id 0 --port 5000 --peers 5001,5002,5003 --difficulty 3 --blocks 10 --log results/raw/events_demo_node0.jsonl

# Terminal 2 — node 1
python -m node.run --id 1 --port 5001 --peers 5000,5002,5003 --difficulty 3 --blocks 10 --log results/raw/events_demo_node1.jsonl

# Terminal 3 — node 2
python -m node.run --id 2 --port 5002 --peers 5000,5001,5003 --difficulty 3 --blocks 10 --log results/raw/events_demo_node2.jsonl

# Terminal 4 — node 3
python -m node.run --id 3 --port 5003 --peers 5000,5001,5002 --difficulty 3 --blocks 10 --log results/raw/events_demo_node3.jsonl
```

Yang perlu ditunjukkan saat demo:

1. Setiap node menulis event JSONL: `block_mined`, `block_received`, `fork_detected`, `chain_replaced`.
2. Setelah 10 blok, **semua node memiliki rantai akhir yang identik** (index dan hash blok terakhir sama).
3. Jika ada fork, tunjukkan event `fork_detected` diikuti `chain_replaced` (aturan *longest chain*).

> Catatan: perintah di atas memerlukan `node/run.py` dari Kibar. Selama `node/` belum tersedia, bagian benchmark di bawah tetap bisa dijalankan memakai node palsu.

## Menjalankan Benchmark

Runner men-spawn N proses node untuk setiap kombinasi, menyimpan log per node di `results/raw/logs/`, lalu menulis satu baris CSV per run sesuai kontrak.

### Grid umum (2 dan 4 node, difficulty 1–4)

```powershell
python -m bench.run_experiments --machine dzikra --nodes 2,4 --difficulty 1,2,3,4 --blocks 10 --runs 3
```

Ganti `--machine dzikra` menjadi `--machine kibar` di laptop Kibar.

### Grid tambahan (8 node, difficulty 1–4)

```powershell
python -m bench.run_experiments --machine dzikra --nodes 8 --difficulty 1,2,3,4 --blocks 10 --runs 3
```

### Difficulty 5 (timeout dan pendinginan khusus)

Difficulty 5 adalah bottleneck utama. Pada laptop Dzikra, satu blok d5 memerlukan sekitar **17,7 detik** per proses setelah CPU throttled. Untuk 2 node dan 10 blok, totalnya mendekati **100 detik**, dengan variansi yang besar.

```powershell
python -m bench.run_experiments --machine dzikra --nodes 2,4,8 --difficulty 5 --blocks 10 --runs 3 --timeout 240 --pause 8
```

Aturan untuk d5:

- Jalankan **paling akhir**, jangan dicampur dengan difficulty rendah.
- Gunakan `--timeout` **minimal 180 detik**; contoh di atas memakai 240 detik.
- Beri jeda pendinginan **5–10 detik** antar-run (`--pause 8`).
- Pastikan charger tercolok dan power mode "Best performance".
- Run yang melewati timeout tetap ditulis ke CSV dengan kolom `status=timeout`, sehingga tidak hilang.

### Menguji runner tanpa `node/`

```powershell
python -m bench.run_experiments --machine dzikra --nodes 2 --difficulty 1 --blocks 3 --runs 1 --pause 0 --node-module tests.fake_node --out-dir results/smoke
```

### Opsi penting

| Opsi | Default | Keterangan |
|---|---|---|
| `--machine` | `dzikra` | Label mesin (`kibar`/`dzikra`), dipakai di nama CSV |
| `--nodes` | `2,4` | Daftar jumlah node, dipisah koma (maks. 8) |
| `--difficulty` | `1,2,3,4` | Daftar difficulty, dipisah koma (maks. 5) |
| `--blocks` | `10` | Target blok per run |
| `--runs` | `3` | Ulangan per kombinasi |
| `--timeout` | `180` | Batas waktu per run (detik) |
| `--pause` | `2` | Jeda antar-run (detik) |
| `--out-dir` | `results/raw` | Folder CSV keluaran |
| `--node-module` | `node.run` | Modul node; ganti untuk mock/test |

CSV ditulis inkremental, jadi data run yang sudah selesai tidak hilang bila proses dihentikan.

## Analisis dan Grafik

```powershell
# 1. Agregasi CSV asli -> results/summary.csv + 6 grafik
python -m analysis.analyze

# 2. Abaikan run timeout dari agregasi
python -m analysis.analyze --exclude-timeouts

# 3. Tabel Markdown untuk Bab 5
python -m analysis.make_tables --out results/tables.md

# 4. Microbenchmark core (hash rate + waktu mining d1–d5)
python -m analysis.microbench_core

# 5. Data dummy untuk mengembangkan pipeline tanpa benchmark asli
python -m analysis.make_dummy
python -m analysis.analyze --raw-dir results/dummy
```

Grafik yang dihasilkan:

1. Waktu blok vs difficulty
2. Throughput vs jumlah node
3. Latensi sinkronisasi vs jumlah node
4. Fork dan orphan vs jumlah node
5. Perbandingan Kibar vs Dzikra
6. Penggunaan CPU vs difficulty

> `analysis/analyze.py` membaca semua `*.csv` di folder `--raw-dir`. File yang kolomnya tidak lengkap dilewati dengan peringatan.

## Format CSV (Kontrak)

Satu baris = satu run:

```
machine,run_id,nodes,difficulty,blocks_target,blocks_confirmed,total_time_s,
throughput_bps,avg_block_time_s,avg_sync_latency_ms,forks_detected,
orphan_blocks,cpu_avg_pct,status
```

Kolom `status` ditambahkan di akhir untuk menandai `ok`, `timeout`, atau `error`. Pipeline analisis mengabaikan kolom tambahan ini, dan menganggap run sebagai timeout bila `blocks_confirmed < blocks_target`.

Definisi metrik:

- `throughput_bps = blocks_confirmed / total_time_s`
- `avg_block_time_s = total_time_s / blocks_confirmed`
- `avg_sync_latency_ms = rata-rata (t_diterima - sent_at) × 1000`
- `orphan_blocks = jumlah block_mined − blocks_confirmed`
- `forks_detected = jumlah event fork_detected`
- `cpu_avg_pct = rata-rata sampling psutil selama run`

## Status Data

| Data | Sumber | Status |
|---|---|---|
| Tabel grid Bab 5 | `results/raw/*.csv` | **Menunggu benchmark asli**; sementara memakai dummy |
| Hash rate & throttling | `results/microbench/*.csv` | **Asli**, laptop Dzikra |
| Grafik | `results/figures/` | Dibuat dari data yang tersedia |

Hasil microbenchmark penting: hash rate turun dari sekitar **121.000** menjadi **52.000 hash/detik** setelah beban penuh berkelanjutan. Karena itu, timeout kecil berisiko mencatat run d5 sebagai gagal padahal hanya lambat.

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `Modul node 'node.run' tidak ditemukan` | `node/` belum tersedia | Pakai `--node-module tests.fake_node` untuk uji runner |
| `Address already in use` | Port 5000–5007 masih dipakai run sebelumnya | Tunggu jeda `--pause`, atau hentikan proses Python yang tersisa |
| Banyak `status=timeout` di d5 | Timeout terlalu pendek / CPU throttled | Naikkan `--timeout` ke 240, beri jeda 5–10 detik |
| Grafik kosong | Folder `results/raw` kosong | Jalankan benchmark atau `analysis.make_dummy` lebih dulu |
| `ImportError` pandas di Windows | Kebijakan Application Control memblokir DLL pandas 3.1 | Gunakan versi yang sudah dipatok di `requirements.txt` (`<3.1`) |

## Referensi Internal

- [`AGENT.md`](AGENT.md) — kontrak proyek, matriks eksperimen, pembagian tugas
- [`docs/INTEGRASI_CORE.md`](docs/INTEGRASI_CORE.md) — cara memakai `core/` dari `node/`
- [`docs/report/`](docs/report/) — draf laporan Bab 1–6
