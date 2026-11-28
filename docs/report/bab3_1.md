# BAB 3.1 — DESAIN CORE BLOCKCHAIN

> **Penulis bagian ini:** Dzikra
> **Berkas terkait:** `core/block.py`, `core/pow.py`, `core/chain.py`, `tests/test_core.py`

## 3.1.1 Gambaran Umum Modul

Core blockchain dipisahkan menjadi tiga modul dengan tanggung jawab tunggal agar mudah diuji dan dipakai oleh lapisan jaringan:

```
core/
├── block.py   # struktur blok, hashing, serialisasi
├── pow.py     # algoritma mining dan verifikasi Proof of Work
└── chain.py   # genesis, penambahan blok, validasi rantai, longest chain + tie-break
```

Lapisan jaringan (`node/`) hanya berinteraksi melalui antarmuka publik yang ditetapkan pada kontrak proyek. Pemisahan ini memungkinkan core diuji tanpa membuka socket, dan memungkinkan node memakai mock selama core belum tersedia.

## 3.1.2 Struktur Blok dan Hashing

`Block` diimplementasikan sebagai `dataclass` dengan enam field publik sesuai kontrak. Urutan field mengikuti kontrak agar pemakaian posisional tetap konsisten: `index, timestamp, transactions, prev_hash, nonce, hash`.

Hash dihitung dari lima field, **tanpa** menyertakan field `hash` itu sendiri. Payload diserialisasi sebagai JSON kanonik:

```python
payload = {
    "index": self.index,
    "timestamp": self.timestamp,
    "transactions": self.transactions,
    "prev_hash": self.prev_hash,
    "nonce": self.nonce,
}
raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

Tiga keputusan desain penting:

1. **`sort_keys=True`** memastikan urutan kunci tidak memengaruhi hash. Tanpa ini, dua proses yang membangun dict dengan urutan berbeda dapat menghasilkan hash berbeda untuk isi yang sama.
2. **Separator dipadatkan** (`(",", ":")`) menghilangkan spasi yang tidak perlu sehingga representasi byte konsisten dan hash sedikit lebih cepat dihitung.
3. **`timestamp` bertipe float** dan diserialisasi memakai representasi *round-trip* Python. Nilai float yang sama selalu menghasilkan string JSON yang sama pada versi Python yang dipakai proyek.

`to_dict()` menyertakan field `hash`, sedangkan `from_dict()` mengembalikan objek baru dengan tipe yang dinormalisasi (`int`, `float`, `list`, `str`). Sifat bolak-balik diuji secara eksplisit: `Block.from_dict(b.to_dict()).compute_hash() == b.hash`.

Contoh isi blok:

```json
{
  "index": 3,
  "timestamp": 1731000000.123456,
  "transactions": [{"from": "node-1", "to": "node-2", "amount": 5}],
  "prev_hash": "000ab3f1...",
  "nonce": 18234,
  "hash": "000ab9c2..."
}
```

## 3.1.3 Algoritma Proof of Work

Fungsi `mine` menerima blok, difficulty, dan callback `should_stop`. Pseudocode-nya:

```
mine(block, difficulty, should_stop):
    target = "0" * difficulty
    attempts = 0
    loop:
        attempts += 1
        block.hash = sha256(payload(block))
        if block.hash starts with target:
            return block, attempts
        block.nonce += 1
        if should_stop is not None
           and attempts % 1000 == 0
           and should_stop():
            return None, attempts
```

Beberapa detail yang disengaja:

- **`attempts` menghitung jumlah hash yang benar-benar dihitung**, termasuk hash yang berhasil. Nilai ini dipakai untuk menganalisis efisiensi mining dan untuk log event `block_mined`.
- **`should_stop` dicek setiap 1000 percobaan**, bukan setiap iterasi. Pemeriksaan tiap iterasi menambah biaya dan memperlambat loop; interval 1000 percobaan menjaga respons tetap cepat pada difficulty tinggi tanpa mengorbankan kecepatan.
- **Difficulty divalidasi `0..5`** dengan `assert` sesuai batasan proyek. Nilai di luar rentang langsung ditolak agar eksperimen tidak keluar dari matriks yang disepakati.
- **Blok dimutasi di tempat.** `nonce` dan `hash` diperbarui selama pencarian. Jika mining dihentikan, blok yang dikembalikan adalah `None`, tetapi objek blok masih menyimpan nonce terakhir. Pemanggil tidak boleh memakai blok tersebut sebagai blok valid.
- **Mining berjalan di thread pemanggil**, tanpa thread atau proses tambahan, sesuai batasan satu node satu proses.

`is_valid_pow(block, difficulty)` memeriksa tiga hal: panjang hash 64 karakter, hash yang tersimpan sama dengan hasil perhitungan ulang, dan prefix nol terpenuhi. Pemeriksaan konsistensi hash membuat fungsi ini juga menangkap blok yang hash-nya dipalsukan.

## 3.1.4 Genesis Deterministik

Genesis dibuat oleh `create_genesis_block()` dengan nilai tetap:

| Field | Nilai |
|---|---|
| `index` | `0` |
| `timestamp` | `0.0` |
| `transactions` | `[]` |
| `prev_hash` | `"0" * 64` |
| `nonce` | `0` |
| `hash` | hasil `compute_hash()` dari nilai di atas |

Genesis **tidak ditambang** dan tidak diwajibkan memenuhi target difficulty. Keputusan ini diambil karena dua alasan:

1. **Konsistensi lintas difficulty.** Jika genesis ditambang dengan difficulty tertentu, hash genesis akan berbeda untuk setiap difficulty. Node dengan difficulty berbeda tidak akan pernah sepakat pada genesis yang sama. Dengan genesis tanpa PoW, genesis identik untuk difficulty 1 sampai 5.
2. **Titik awal yang murah dan pasti.** Genesis tidak membawa nilai ekonomi dan tidak perlu membuktikan kerja. Validasi genesis cukup membandingkan seluruh isinya dengan template, sehingga tidak ada peluang dua node memakai genesis berbeda.

Validasi genesis dilakukan di `is_valid_chain` dengan membandingkan `to_dict()` blok pertama terhadap template. Perbandingan penuh ini menangkap perubahan sekecil apa pun, termasuk perubahan `timestamp` atau `transactions`.

Konsekuensi desain: rantai yang diterima dari peer harus memakai genesis yang sama. Ini bukan masalah pada simulasi karena semua node menjalankan kode yang sama, tetapi perlu dicatat sebagai asumsi.

## 3.1.5 Penambahan Blok

`new_block(transactions)` membuat blok baru yang belum ditambang:

- `index = last_block.index + 1`
- `timestamp = time.time()`
- `prev_hash = last_block.hash`
- `nonce = 0`, `hash = ""`

`add_block(block)` menerima blok hanya jika seluruh kondisi berikut terpenuhi:

1. Objek bertipe `Block`.
2. `block.index == last_block.index + 1` (tidak boleh melompat atau mundur).
3. `block.prev_hash == last_block.hash` (tautan benar).
4. `block.compute_hash() == block.hash` (hash konsisten dengan isi).
5. `is_valid_pow(block, difficulty)` (pekerjaan memenuhi target).

Jika salah satu gagal, method mengembalikan `False` dan rantai tidak berubah. Pemeriksaan dilakukan sebelum `append`, sehingga tidak ada keadaan parsial. Pendekatan ini penting untuk node: blok dari peer tidak pernah dipercaya sebelum divalidasi.

## 3.1.6 Validasi Rantai dan Longest Chain

`is_valid_chain(chain)` melakukan validasi menyeluruh:

1. Rantai tidak kosong.
2. Blok pertama identik dengan genesis deterministik.
3. Untuk setiap blok setelah genesis:
   - `index` berurutan,
   - `prev_hash` menunjuk ke hash blok sebelumnya,
   - hash konsisten dengan isi,
   - PoW valid pada difficulty rantai.

`replace_chain(new_chain)` mengganti rantai jika rantai baru valid dan **lebih panjang**, atau **sama panjang dengan hash blok terakhir lebih kecil**:

```python
if len(new_chain) < len(self.chain):
    return False
if len(new_chain) == len(self.chain) and (
    new_chain[-1].hash >= self.chain[-1].hash
):
    return False
if not self.is_valid_chain(new_chain):
    return False
self.chain = list(new_chain)
return True
```

Aturan *longest chain* saja tidak cukup pada simulasi paralel: dua node dapat menambang blok berbeda pada ketinggian yang sama, sehingga rantai tetap sama panjang. Tanpa tie-break, kedua node mempertahankan rantai masing-masing dan demo tidak pernah konvergen. Karena itu ditambahkan tie-break deterministik **PC-001**: jika panjangnya sama, rantai dengan hash blok terakhir lebih kecil secara leksikografis yang dipilih. Perbandingan string hex 64 karakter identik dengan perbandingan numerik dan hasilnya sama di semua node. Detail usulan ada di `docs/CONTRACT_CHANGES.md`.

## 3.1.7 Kompleksitas

| Operasi | Kompleksitas waktu | Catatan |
|---|---|---|
| `compute_hash` | O(ukuran payload) | SHA-256 atas JSON blok |
| `mine` | O(16^d) ekspektasi | Distribusi geometrik, tanpa batas atas |
| `is_valid_pow` | O(ukuran payload) | Satu hash + pemeriksaan prefix |
| `add_block` | O(1) + hashing | Validasi lokal terhadap blok terakhir |
| `is_valid_chain` | O(n) hash | n = jumlah blok |
| `replace_chain` | O(n) hash | Validasi penuh sebelum mengganti |
| `to_list` | O(n) | Serialisasi seluruh rantai |

Biaya dominant saat runtime adalah mining, sedangkan validasi rantai penuh hanya dilakukan saat menerima `CHAIN` dari peer. Untuk 10 blok dan difficulty maksimum 5, validasi penuh tetap murah dibanding satu kali mining.

## 3.1.8 Antarmuka untuk Lapisan Node

Core mengekspos fungsi dan class melalui `core/__init__.py`:

```python
from core import Block, Blockchain, mine, is_valid_pow, create_genesis_block
```

Alur yang dipakai node:

1. `chain = Blockchain(difficulty)` saat start.
2. `block = chain.new_block(txs)` untuk kandidat blok.
3. `mined, attempts = mine(block, difficulty, should_stop)`.
4. Jika `mined is not None`, panggil `chain.add_block(mined)` lalu broadcast.
5. Saat menerima `CHAIN`, ubah list of dict menjadi `Block` dengan `Block.from_dict`, lalu panggil `chain.replace_chain(blocks)`.
6. Saat menerima `NEW_BLOCK`, validasi dengan `add_block`; jika gagal karena tidak menyambung, minta chain lengkap.

Serialisasi untuk jaringan memakai `to_dict()`/`from_dict()` sehingga format pesan tetap sesuai kontrak `{"block": {...}}` dan `{"chain": [...]}`.

## 3.1.9 Pengujian Unit

Pengujian memakai `pytest` dan mencakup kontrak, determinisme, keamanan validasi, serta perilaku berhenti. Hasil eksekusi:

```
$ python -m pytest tests/test_core.py -q
30 passed in 0.82s
```

Kelompok pengujian:

| Kelompok | Contoh kasus | Tujuan |
|---|---|---|
| Hashing | hash deterministik, perubahan konten mengubah hash, field `hash` tidak ikut di-hash | Memastikan determinisme |
| Serialisasi | `to_dict`/`from_dict` bolak-balik, nilai JSON-like | Memastikan tidak ada data hilang |
| Mining | hash valid, difficulty 3 selesai cepat, `should_stop` menghentikan, difficulty > 5 ditolak | Memastikan PoW benar dan terkendali |
| Verifikasi | difficulty lebih tinggi ditolak, hash palsu ditolak | Memastikan validasi ketat |
| Genesis | identik untuk difficulty 1, 3, 5 | Memastikan konsensus titik awal |
| Penambahan blok | index salah, `prev_hash` salah, PoW invalid, objek bukan `Block` | Memastikan rantai tidak bisa dirusak |
| Validasi rantai | transaksi diubah, genesis diubah, tautan diputus | Memastikan tampering terdeteksi |
| Longest chain + tie-break | lebih panjang valid diterima; sama panjang dengan hash terakhir lebih kecil diterima; lebih pendek, sama panjang dengan hash lebih besar, atau lebih panjang invalid ditolak | Memastikan konsensus deterministik |

Pengujian juga mengukur waktu mining difficulty 3 dan memberi batas longgar 5 detik agar tidak flaky pada laptop lambat. Pada laptop Dzikra, mining difficulty 3 selesai sekitar **0,03 detik** pada kondisi burst dan **0,07 detik** pada kondisi CPU yang sudah throttled—jauh di bawah 2 detik. Pengukuran lengkap ada di Bagian 5.9.

## 3.1.10 Keterbatasan Desain Core

1. **Difficulty bersifat tetap per instance `Blockchain`.** Tidak ada penyesuaian difficulty otomatis seperti pada Bitcoin. Ini disengaja agar variabel eksperimen terkontrol.
2. **Tidak ada tanda tangan digital.** Validitas transaksi tidak diperiksa; fokus penelitian adalah PoW dan sinkronisasi.
3. **Tidak ada mempool dan aturan biaya.** Transaksi hanya daftar dict yang ditempelkan ke blok.
4. **Longest chain dengan tie-break hash.** Rantai sama panjang diselesaikan dengan memilih hash blok terakhir yang lebih kecil. Aturan ini deterministik, tetapi bukan aturan Bitcoin (Bitcoin memakai akumulasi kerja, bukan panjang saja).
5. **Timestamp memakai jam node.** Pada simulasi satu mesin, seluruh node berbagi jam yang sama. Pada jaringan nyata, skew jam perlu ditangani.
6. **Genesis tidak memakai PoW.** Keputusan ini memudahkan konsensus lintas difficulty, tetapi berarti genesis tidak memiliki bukti kerja.

Keterbatasan ini dicatat agar pembahasan di Bab 5 tidak melebih-lebihkan cakupan hasil. Untuk tujuan membandingkan pengaruh jumlah node dan difficulty, penyederhanaan tersebut tidak mengubah mekanisme inti yang ingin diamati.
