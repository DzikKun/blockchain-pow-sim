# BAB 1 — PENDAHULUAN

> **Proyek:** Simulasi Blockchain Terdistribusi (Tema 4)
> **Mata kuliah:** Komputasi Pararel dan Terdistribusi
> **Judul:** Analisis Pengaruh Jumlah Node dan Tingkat Kesulitan Mining terhadap Throughput Blockchain Terdistribusi
>
> **Penulis bagian ini:** Dzikra

## 1.1 Latar Belakang

Blockchain adalah struktur data terdistribusi yang menyimpan riwayat transaksi dalam blok-blok yang saling terhubung melalui hash kriptografis. Setiap blok memuat hash blok sebelumnya, sehingga perubahan satu blok akan merusak seluruh rantai setelahnya. Sifat ini yang disebut *immutability* membuat blockchain dipakai pada sistem pembayaran, pencatatan aset, dan aplikasi lain yang membutuhkan integritas data tanpa otoritas pusat.

Agar blok baru dapat diterima secara kolektif, jaringan blockchain membutuhkan mekanisme konsensus. Salah satu mekanisme paling sederhana dan paling banyak dipelajari adalah *Proof of Work* (PoW). Pada PoW, sebuah node harus menemukan nilai `nonce` sedemikian rupa sehingga hash blok memenuhi target tertentu, umumnya sejumlah karakter nol di awal hash. Pencarian ini dilakukan dengan coba-coba (brute force) sehingga biayanya dapat diukur secara objektif: semakin banyak nol yang diminta, semakin banyak percobaan hash yang dibutuhkan.

Dalam praktiknya, penambahan node dan kenaikan difficulty memiliki dua efek yang berlawanan. Menambah node berarti menambah total hash power, sehingga blok dapat ditemukan lebih cepat. Namun, node yang lebih banyak juga memperbesar peluang dua node menemukan blok berbeda pada waktu hampir bersamaan. Peristiwa ini menghasilkan *fork*, yaitu percabangan rantai, yang pada akhirnya harus diselesaikan dengan aturan *longest chain*. Di sisi lain, kenaikan difficulty memperpanjang interval blok, menurunkan laju produksi blok, tetapi juga menekan jumlah fork karena peluang tabrakan antar-node mengecil. Dengan demikian, jumlah node dan difficulty membentuk ruang kompromi antara throughput, latensi sinkronisasi, dan stabilitas rantai.

PoW juga identik dengan konsumsi energi. Setiap percobaan hash memakai CPU, dan difficulty yang lebih tinggi menuntut lebih banyak percobaan untuk hasil yang sama. Pada skala simulasi di satu laptop, konsumsi energi tidak menjadi masalah biaya nyata, tetapi pola penggunaan CPU tetap dapat dijadikan proksi untuk membahas hubungan antara difficulty, waktu komputasi, dan energi. Aspek ini relevan sebagai bahan analisis tambahan pada laporan.

Karena itu, proyek ini membangun simulasi blockchain PoW yang berjalan sepenuhnya di satu laptop dengan beberapa proses node pada `127.0.0.1`. Setiap node adalah satu proses sistem operasi, mining dilakukan secara *single-process* di dalam node tersebut, dan komunikasi antar-node memakai socket TCP. Dengan cara ini, pengaruh jumlah node dan difficulty dapat diukur secara terkontrol tanpa membutuhkan cloud berbayar, GPU, atau koin asli. Dua laptop dengan spesifikasi berbeda—Kibar (Intel i5-6200U, 2 core/4 thread) dan Dzikra (Intel i3-N305, 8 core)—dipakai untuk melihat sejauh mana perbedaan perangkat keras memengaruhi hasil.

## 1.2 Rumusan Masalah

Berdasarkan latar belakang di atas, rumusan masalah penelitian ini adalah:

1. Bagaimana pengaruh **tingkat difficulty** terhadap waktu per blok dan throughput blockchain pada simulasi PoW multi-node?
2. Bagaimana pengaruh **jumlah node** terhadap throughput, latensi sinkronisasi, serta jumlah fork dan blok orphan?
3. Bagaimana kombinasi jumlah node dan difficulty memengaruhi **efisiensi** sistem, yaitu perbandingan antara tambahan throughput dan biaya sinkronisasi/fork yang muncul?
4. Seberapa besar perbedaan hasil antara laptop Kibar dan laptop Dzikra pada grid eksperimen yang sama, dan bagaimana kaitannya dengan jumlah core serta frekuensi CPU?
5. Bagaimana pola penggunaan CPU berubah terhadap difficulty dan jumlah node, dan apa implikasinya terhadap konsumsi energi PoW?

## 1.3 Tujuan Penelitian

1. Membangun core blockchain PoW yang deterministik, tervalidasi, dan dapat dipakai bersama oleh semua node.
2. Mengukur throughput, waktu per blok, latensi sinkronisasi, jumlah fork, jumlah blok orphan, dan penggunaan CPU pada berbagai kombinasi jumlah node dan difficulty.
3. Menganalisis hubungan antara parameter eksperimen dan metrik kinerja, termasuk titik ketika penambahan node tidak lagi memberi manfaat sebanding.
4. Membandingkan hasil pada dua laptop dengan spesifikasi berbeda sebagai bahan analisis pengaruh perangkat keras.
5. Menyajikan hasil dalam bentuk tabel dan grafik yang dapat dipakai untuk membahas trade-off PoW, termasuk aspek konsumsi energi.

## 1.4 Manfaat Penelitian

**Manfaat teoretis.** Penelitian ini memberi gambaran kuantitatif tentang hubungan antara hash power, difficulty, laju blok, dan fork pada blockchain PoW sederhana. Hasilnya dapat dipakai sebagai ilustrasi konsep longest chain, probabilitas fork, dan batas skalabilitas horizontal pada sistem konsensus berbasis komputasi.

**Manfaat praktis.** Simulasi ini menyediakan kerangka kerja yang ringan dan gratis untuk eksperimen blockchain di laptop biasa. Kode core, protokol jaringan, dan runner benchmark dapat dipakai ulang untuk demonstrasi kelas, tugas lanjutan, atau eksperimen parameter lain tanpa ketergantungan layanan eksternal.

## 1.5 Batasan Masalah

Agar eksperimen dapat diselesaikan dalam waktu dan sumber daya yang tersedia, penelitian dibatasi sebagai berikut.

1. Simulasi dijalankan di **satu laptop** dengan semua node berkomunikasi melalui `127.0.0.1`; tidak ada jaringan fisik antar-laptop.
2. Setiap node adalah **satu proses OS** dan mining dilakukan **single-process** di dalam node tersebut. Tidak ada proses mining tambahan dan tidak memakai thread untuk hashing berat.
3. Jumlah node maksimum **8** dan difficulty maksimum **5**.
4. Setiap run menargetkan **10 blok** (di luar genesis) dengan **3 ulangan** per kombinasi.
5. Implementasi memakai **Python 3.10+** dan pustaka standar (`hashlib`, `multiprocessing`, `socket`, `threading`, `json`, `subprocess`). Pustaka tambahan hanya untuk analisis dan pengujian: `pandas`, `matplotlib`, `psutil`, dan `pytest`.
6. Tidak memakai GPU, cloud berbayar, koin asli, tanda tangan digital, mempool transaksi kompleks, maupun mekanisme konsensus selain longest chain.
7. Waktu sistem dianggap cukup akurat karena seluruh node berjalan di satu mesin; latensi yang diukur adalah latensi pengiriman pesan di localhost, bukan latensi jaringan geografis.
8. Hasil benchmark bergantung pada kondisi laptop (charger, power mode, suhu, aplikasi latar belakang). Kondisi ini dicatat dan dijaga semirip mungkin antar-run.

## 1.6 Sistematika Penulisan

- **Bab 1** memuat latar belakang, rumusan masalah, tujuan, manfaat, dan batasan.
- **Bab 2** membahas landasan teori blockchain, Proof of Work, konsensus longest chain, fork, throughput, latensi, pemrosesan paralel, dan konsumsi energi.
- **Bab 3.1** menjelaskan desain core blockchain: struktur blok, algoritma mining, validasi rantai, dan pengujian unit.
- **Bab 3.2** (Kibar) menjelaskan desain jaringan antar-node, protokol pesan, dan arsitektur node.
- **Bab 4** (Kibar) menjelaskan metodologi pengujian dan konfigurasi eksperimen.
- **Bab 5** menyajikan hasil, tabel, grafik, dan analisis, termasuk perbandingan dua laptop serta pembahasan energi.
- **Bab 6** (Kibar) memuat kesimpulan dan saran.
