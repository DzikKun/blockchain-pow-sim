# Panduan Integrasi `core/` untuk Lapisan Node

> **Untuk:** Kibar
> **Dari:** Dzikra
> **Status:** `core/` sudah lengkap dan teruji (29 test). Dokumen ini menjelaskan cara memakainya dari `node/` tanpa perlu membaca seluruh implementasi.

## 1. Ringkasan API

```python
from core import Block, Blockchain, mine, is_valid_pow, create_genesis_block
```

| Kebutuhan node | Pemakaian |
|---|---|
| Membuat rantai saat start | `chain = Blockchain(difficulty)` |
| Membuat kandidat blok | `block = chain.new_block(transactions)` |
| Menambang blok | `mined, attempts = mine(block, difficulty, should_stop)` |
| Menambahkan blok lokal / dari peer | `chain.add_block(block) -> bool` |
| Mengubah dict jaringan menjadi blok | `Block.from_dict(data)` |
| Mengubah rantai menjadi list dict | `chain.to_list()` |
| Mengganti rantai dengan yang lebih panjang (atau tie-break hash terkecil) | `chain.replace_chain(list_of_blocks) -> bool` |
| Menvalidasi PoW blok | `is_valid_pow(block, difficulty)` |

## 2. Alur Mining di Node

```python
from core import Blockchain, mine

class Node:
    def __init__(self, node_id, difficulty, ...):
        self.id = node_id
        self.chain = Blockchain(difficulty)
        self.stop_mining = False

    def mine_next_block(self, transactions):
        self.stop_mining = False
        block = self.chain.new_block(transactions)

        mined, attempts = mine(
            block,
            self.chain.difficulty,
            should_stop=lambda: self.stop_mining,
        )

        if mined is None:
            return None  # dihentikan karena ada blok dari peer

        if not self.chain.add_block(mined):
            return None  # seharusnya tidak terjadi; jangan broadcast

        return mined
```

Catatan penting:

- **`mine` memutasi `block`** (`nonce` dan `hash`). Jika hasilnya `None`, buang blok itu dan buat blok baru lewat `new_block`.
- **`should_stop` dicek tiap 1000 percobaan.** Pada difficulty 1–2, mining bisa selesai sebelum flag sempat dibaca. Itu normal: setelah blok peer diterima, gunakan `add_block`/`replace_chain` untuk menyelaraskan rantai.
- Set flag `stop_mining = True` saat ada blok valid dari peer, lalu reset ke `False` sebelum mulai menambang blok berikutnya.
- `attempts` dari `mine` dipakai untuk log `block_mined`.

## 3. Menerima `NEW_BLOCK`

```python
block = Block.from_dict(message["block"])

if self.chain.add_block(block):
    self.stop_mining = True
    log({
        "event": "block_received",
        "index": block.index,
        "sender": message["sender"],
        "sent_at": message["sent_at"],
    })
else:
    # Blok tidak menyambung -> minta rantai lengkap ke pengirim.
    self.send(
        message["sender"],
        {"type": "GET_CHAIN", "sender": self.id},
    )
    log({"event": "fork_detected", "index": block.index})
```

`add_block` sudah memeriksa: index berurutan, `prev_hash`, hash konsisten, dan PoW sesuai `chain.difficulty`. Tidak perlu validasi tambahan.

## 4. Menerima `CHAIN`

```python
new_chain = [Block.from_dict(item) for item in message["chain"]]

old_len = len(self.chain.chain)
if self.chain.replace_chain(new_chain):
    self.stop_mining = True
    log({
        "event": "chain_replaced",
        "old_len": old_len,
        "new_len": len(self.chain.chain),
    })
```

Syarat `replace_chain`: rantai baru harus valid secara penuh (genesis + tautan + hash + PoW) dan **lebih panjang** dari rantai lokal. Jika panjangnya **sama**, rantai dengan hash blok terakhir **lebih kecil secara leksikografis** yang diterima (tie-break PC-001); rantai sama panjang dengan hash lebih besar ditolak.

## 5. Invarian Genesis

Semua node **wajib** memakai genesis yang sama:

```python
# BENAR
chain = Blockchain(difficulty)

# SALAH: jangan membuat genesis manual dengan timestamp sekarang
genesis = Block(index=0, timestamp=time.time(), transactions=[], prev_hash="0" * 64)
```

Genesis dibuat otomatis oleh `Blockchain.__init__`, dengan `timestamp=0`, `nonce=0`, dan `prev_hash` 64 nol. Genesis sengaja tidak ditambang agar hash-nya sama untuk difficulty 1–5. Jangan mengganti atau menambang ulang genesis.

## 6. Jebakan yang Sering Terjadi

1. **Mengirim objek `Block` mentah ke `json.dumps`** → gunakan `block.to_dict()`.
2. **Menerima `chain` lalu langsung menganggapnya list `Block`** → konversi dulu dengan `Block.from_dict`.
3. **Memakai `is_valid_pow` tanpa mencocokkan difficulty** → selalu pakai `chain.difficulty` yang sama antar-node.
4. **Menambang blok baru saat rantai lokal belum sinkron** → setelah `chain_replaced`, mulai lagi dari `chain.new_block`.
5. **Transaksi berisi tipe non-JSON** (misalnya `set`, `datetime`) → hash akan gagal. Gunakan dict/list/str/int/float/bool/None.
6. **Mengharapkan `mine` berhenti seketika** → callback hanya dicek tiap 1000 percobaan.
7. **Mengabaikan tie-break rantai sama panjang** → aturan proyek: rantai lebih panjang menang; jika sama panjang, hash blok terakhir lebih kecil yang menang (PC-001). Tanpa tie-break, dua node dapat saling bertukar rantai atau berhenti pada rantai berbeda.

## 7. Kontrak Pesan yang Sudah Disepakati

```json
{"type": "NEW_BLOCK", "block": {...}, "sender": 0, "sent_at": 1731000000.123}
{"type": "GET_CHAIN", "sender": 1}
{"type": "CHAIN", "chain": [...], "sender": 1}
{"type": "TX", "tx": {...}}
```

`block` adalah hasil `Block.to_dict()`, `chain` adalah hasil `chain.to_list()` (atau list dict yang ekuivalen).

## 8. Cek Cepat Sebelum Menjalankan Node

```powershell
python -m pytest tests/test_core.py -q
```

Jika ada bug atau perilaku yang tidak sesuai, buka Issue di GitHub dan jangan edit `core/` langsung. Perubahan kontrak harus dibahas bersama dan dicatat di `docs/CONTRACT_CHANGES.md`.
