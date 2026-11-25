# BAB 2 — LANDASAN TEORI

> **Penulis bagian ini:** Dzikra

## 2.1 Blockchain

Blockchain adalah log transaksi terdistribusi yang tersusun sebagai rantai blok. Setiap blok memiliki daftar transaksi, stempel waktu, dan hash blok sebelumnya. Karena hash blok sebelumnya ikut di-hash, perubahan pada satu blok mengubah hash blok tersebut, memutus tautan ke blok berikutnya, dan membuat rantai tidak valid. Sifat ini memberikan integritas data tanpa memerlukan otoritas pusat, selama mayoritas peserta sepakat pada rantai yang sama.

Pada sistem nyata, blockchain juga melibatkan tanda tangan digital, aturan validasi transaksi, dan insentif ekonomi. Simulasi pada proyek ini menyederhanakan aspek-aspek tersebut dan berfokus pada bagian yang relevan untuk analisis kinerja: struktur blok, Proof of Work, aturan longest chain, dan sinkronisasi antar-node.

## 2.2 Hash Kriptografis dan Integritas Data

Fungsi hash kriptografis menerima masukan dengan panjang berapa pun dan menghasilkan keluaran berukuran tetap. SHA-256 menghasilkan 256 bit atau 64 karakter heksadesimal. Tiga sifat yang dimanfaatkan pada blockchain adalah:

1. **Deterministik** — masukan yang sama selalu menghasilkan hash yang sama.
2. **Sensitif terhadap perubahan** — perubahan satu bit pada masukan menghasilkan hash yang sangat berbeda (*avalanche effect*).
3. **Satu arah** — sulit menemukan masukan yang menghasilkan hash tertentu (*preimage resistance*).

Pada simulasi ini, hash blok dihitung dari representasi JSON kanonik atas `index`, `timestamp`, `transactions`, `prev_hash`, dan `nonce`. Kunci JSON diurutkan (`sort_keys=True`) dan separator dipadatkan agar dua proses yang menghasilkan isi blok sama juga menghasilkan hash yang sama, terlepas dari urutan penulisan field.

## 2.3 Struktur Blok dan Genesis

Blok pada simulasi memiliki field berikut.

| Field | Tipe | Keterangan |
|---|---|---|
| `index` | int | Posisi blok pada rantai; genesis bernilai 0 |
| `timestamp` | float | Waktu pembuatan blok (epoch detik) |
| `transactions` | list[dict] | Daftar transaksi (boleh kosong) |
| `prev_hash` | str | Hash blok sebelumnya |
| `nonce` | int | Nilai yang diubah selama mining |
| `hash` | str | SHA-256 dari lima field di atas |

Blok pertama disebut **genesis**. Genesis tidak memiliki pendahulu sehingga `prev_hash` diisi 64 karakter nol. Agar semua node memulai dari kondisi yang sama, genesis harus **deterministik**: nilai `timestamp`, `transactions`, `nonce`, dan `hash`-nya identik di semua node. Tanpa determinisme ini, dua node tidak akan pernah sepakat apakah rantai lawan valid, karena genesis mereka berbeda.

## 2.4 Proof of Work

Proof of Work adalah mekanisme untuk membuktikan bahwa sejumlah kerja komputasi telah dilakukan. Pada blockchain, pekerjaan tersebut berupa pencarian `nonce` sehingga:

```
SHA256(index || timestamp || transactions || prev_hash || nonce)
    diawali dengan `difficulty` karakter '0'
```

Karena SHA-256 bersifat acak semu, setiap nilai `nonce` memberi peluang keberhasilan yang sama. Proses mining karenanya bersifat *trial and error*: node menghitung hash, memeriksa apakah prefix nol terpenuhi, lalu menaikkan `nonce` dan mengulang. Tidak ada cara yang lebih efisien daripada mencoba sebanyak mungkin nilai.

Setelah blok ditemukan, node lain dapat memverifikasi pekerjaan tersebut hanya dengan satu kali perhitungan hash. Inilah asimetri penting PoW: mahal untuk membuat, murah untuk memverifikasi.

## 2.5 Difficulty dan Ekspektasi Waktu Mining

Satu karakter heksadesimal mewakili 4 bit. Peluang satu hash memenuhi target dengan `d` karakter nol adalah:

```
p = 16^(-d)
```

Jumlah percobaan sampai berhasil mengikuti distribusi geometrik dengan nilai harapan:

```
E[percobaan] = 1/p = 16^d
```

Konsekuensinya, setiap kenaikan difficulty sebesar 1 meningkatkan ekspektasi pekerjaan **16 kali lipat**. Nilai ini yang membuat difficulty menjadi tuas yang sangat kuat: perbedaan satu tingkat dapat mengubah waktu blok dari sepersekian detik menjadi puluhan detik.

Karena distribusi geometrik bersifat *memoryless*, waktu mining tidak bisa diprediksi secara tepat untuk satu blok. Yang dapat diprediksi adalah nilai rata-ratanya. Oleh karena itu, pengukuran memakai beberapa blok per run dan beberapa ulangan, lalu melaporkan rata-rata dan standar deviasi.

Pada implementasi simulasi, `should_stop` dicek setiap 1000 percobaan. Pemeriksaan yang terlalu sering akan memperlambat loop, sedangkan pemeriksaan yang terlalu jarang membuat node lambat bereaksi ketika blok valid dari node lain tiba. Interval 1000 percobaan dipilih sebagai kompromi: pada difficulty rendah mining selesai sebelum pemeriksaan pertama, sedangkan pada difficulty tinggi respons masih dalam skala milidetik hingga puluhan milidetik.

## 2.6 Konsensus Longest Chain, Fork, dan Blok Orphan

Ketika beberapa node mining secara bersamaan, dua node dapat menemukan blok berbeda pada ketinggian yang sama. Jaringan kemudian memiliki dua versi rantai. Aturan konsensus yang dipakai adalah **longest chain**: rantai dengan jumlah blok terbanyak dan valid dianggap pemenang. Node yang menerima rantai lebih panjang akan mengganti rantainya.

Blok yang pernah ditambang tetapi tidak masuk ke rantai final disebut **blok orphan**. Fork dan orphan adalah biaya alami dari desentralisasi: semakin banyak penambang yang bersaing dan semakin pendek interval blok, semakin besar peluang dua blok lahir hampir bersamaan. Sebaliknya, difficulty tinggi memperpanjang interval blok sehingga peluang tabrakan mengecil.

Pada simulasi ini, fork dideteksi ketika node menerima `NEW_BLOCK` yang tidak menyambung ke rantai lokal (index melompat atau `prev_hash` berbeda). Node lalu mengirim `GET_CHAIN` ke pengirim dan mencoba mengganti rantainya dengan rantai yang lebih panjang. Peristiwa ini dicatat sebagai `fork_detected` dan `chain_replaced` pada log JSONL.

Perlu dicatat bahwa aturan longest chain sederhana memiliki kelemahan: dua rantai dengan panjang sama tidak memiliki tie-breaker eksplisit. Pada simulasi, rantai yang datang lebih dulu dipertahankan sampai ada rantai yang benar-benar lebih panjang. Untuk skala eksperimen ini, pendekatan tersebut cukup karena tujuannya adalah mengamati penyelesaian fork, bukan membangun konsensus produksi.

## 2.7 Jaringan, Broadcast, dan Latensi Sinkronisasi

Setiap node berjalan sebagai proses terpisah dan mendengarkan koneksi TCP pada port `5000 + id`. Ketika sebuah blok berhasil ditambang, node mengirim pesan `NEW_BLOCK` ke semua peer. Pesan berupa satu baris JSON yang diakhiri newline. Pendekatan *newline-delimited JSON* dipilih karena sederhana, mudah di-debug, dan tidak membutuhkan pustaka tambahan.

Latensi sinkronisasi didefinisikan sebagai selisih waktu antara saat blok diterima dan saat blok dikirim:

```
latensi = t_diterima - sent_at
```

Karena pengirim menyertakan `sent_at` dalam pesan, latensi ini tidak terpengaruh perbedaan jam antar-mesin. Pada simulasi satu laptop, latensi mencerminkan waktu antrean socket, penanganan thread, parsing JSON, validasi blok, dan penulisan log. Latensi tidak mengukur propagasi jaringan geografis.

## 2.8 Throughput dan Waktu per Blok

**Throughput** adalah jumlah blok yang berhasil dikonfirmasi per satuan waktu:

```
throughput = blocks_confirmed / total_time
```

**Waktu per blok** adalah kebalikan dari laju tersebut pada tingkat run:

```
avg_block_time = total_time / blocks_confirmed
```

Keduanya saling terkait, tetapi tidak identik dengan interval mining murni karena `total_time` mencakup waktu mulai proses, sinkronisasi awal, dan penyelesaian. Pada difficulty rendah, komponen overhead dapat mendominasi sehingga throughput tidak lagi naik meskipun hash power bertambah. Fenomena ini penting untuk dibahas: penambahan node hanya bermanfaat bila waktu mining menjadi bagian dominan dari total waktu.

## 2.9 Sistem Terdistribusi dan Pemrosesan Paralel

Simulasi ini menggabungkan dua bentuk paralelisme:

1. **Paralelisme antar-node** — beberapa proses OS berjalan bersamaan, masing-masing dengan ruang memori terpisah.
2. **Konkurensi di dalam node** — thread dipakai untuk menangani koneksi socket yang bersifat I/O-bound, sedangkan mining tetap di thread utama.

Python memiliki *Global Interpreter Lock* (GIL) yang membatasi eksekusi bytecode Python menjadi satu thread pada satu waktu. Untuk pekerjaan CPU-bound seperti hashing, GIL membuat thread tidak memberi percepatan. Karena itu, mining dilakukan di proses node itu sendiri dan paralelisme sejati diperoleh dari beberapa proses node, bukan dari thread tambahan. Batasan ini sengaja dipatuhi agar hasil eksperimen mencerminkan perilaku nyata Python dan agar tidak terjadi oversubscription core.

Ketika jumlah proses mining melebihi jumlah core fisik, terjadi perebutan CPU. Setiap proses mendapat jatah waktu yang lebih kecil, sehingga penambahan node tidak lagi memberi percepatan linear. Secara umum, percepatan dibatasi oleh hukum Amdahl: bagian serial (startup, sinkronisasi, penulisan log) membatasi manfaat paralelisasi. Selain itu, biaya komunikasi dan validasi meningkat seiring jumlah node.

## 2.10 Konsumsi Energi

Konsumsi energi PoW berkaitan langsung dengan jumlah hash yang dihitung. Secara kasar, energi sebanding dengan:

```
energi ~ jumlah_hash x energi_per_hash
```

Untuk target blok yang sama, difficulty yang lebih tinggi menuntut lebih banyak hash, sehingga energi per blok meningkat. Namun, wall-clock time dapat turun ketika lebih banyak node bekerja paralel. Karena itu, waktu penyelesaian yang singkat tidak otomatis berarti energi yang lebih kecil: daya total yang ditarik bisa lebih besar karena banyak core aktif bersamaan.

Pada eksperimen ini, energi tidak diukur dengan wattmeter. Sebagai proksi dipakai **CPU-detik**, yaitu persentase CPU sistem rata-rata dikalikan durasi run:

```
cpu_seconds_proxy = (cpu_avg_pct / 100) x total_time_s
```

Proksi ini bukan pengukuran energi absolut, tetapi cukup untuk membandingkan pola relatif antar-konfigurasi. Pembahasan energi harus disampaikan dengan keterbatasan ini secara eksplisit.

## 2.11 Definisi Metrik

| Metrik | Definisi | Satuan |
|---|---|---|
| `throughput_bps` | `blocks_confirmed / total_time_s` | blok/detik |
| `avg_block_time_s` | `total_time_s / blocks_confirmed` | detik |
| `avg_sync_latency_ms` | rata-rata `(t_received - sent_at) x 1000` | milidetik |
| `forks_detected` | jumlah event `fork_detected` | kejadian/run |
| `orphan_blocks` | blok yang ditambang tetapi tidak masuk rantai final | blok/run |
| `cpu_avg_pct` | rata-rata penggunaan CPU sistem, sampling 0,5 detik | persen |
| `cpu_seconds_proxy` | `cpu_avg_pct/100 x total_time_s` (turunan) | CPU-detik |

## 2.12 Pustaka dan Alat

- **Python 3.10+** sebagai bahasa implementasi.
- **`hashlib`** untuk SHA-256.
- **`socket` dan `threading`** untuk server TCP dan penanganan koneksi.
- **`multiprocessing`/`subprocess`** untuk menjalankan node sebagai proses terpisah.
- **`json`** untuk serialisasi pesan dan log.
- **`pandas`** untuk penggabungan CSV dan agregasi statistik.
- **`matplotlib`** untuk grafik PNG.
- **`psutil`** untuk sampling penggunaan CPU pada benchmark.
- **`pytest`** untuk pengujian unit.

## 2.13 Rujukan

1. S. Nakamoto, *Bitcoin: A Peer-to-Peer Electronic Cash System*, 2008.
2. L. Lamport, R. Shostak, dan M. Pease, "The Byzantine Generals Problem," *ACM Transactions on Programming Languages and Systems*, 1982.
3. G. M. Amdahl, "Validity of the Single Processor Approach to Achieving Large Scale Computing Capabilities," *AFIPS Spring Joint Computer Conference*, 1967.
4. Dokumentasi resmi Python: `hashlib`, `socket`, `threading`, dan `multiprocessing`.
5. Dokumentasi resmi pandas dan matplotlib.
