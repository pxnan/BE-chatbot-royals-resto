import pickle
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score
import seaborn as sns
import matplotlib.pyplot as plt
from preprocessing import preprocess
import numpy as np

# ===== Load QA Model Tunggal =====
with open('model/model_qa.pkl', 'rb') as f:
    qa_data = pickle.load(f)

model_qa = qa_data['model']
vectorizer_qa = qa_data['vectorizer']
categories = qa_data['categories']  # kategori setiap pertanyaan

# ===== Load Dataset Testing =====
df_test = pd.DataFrame({
    'pertanyaan': [
        # Introduction (40 pertanyaan)
        "hai", "halo", "selamat pagi", "assalamualaikum", "selamat siang", 
        "selamat sore", "selamat malam", "hi", "hey", "p", 
        "oi", "good morning", "hello", "apa kabar?", "permisi", 
        "hai kak", "halo semua", "selamat pagi semua", "assalamualaikum wr wb", "selamat siang pak", 
        "selamat sore bu", "selamat malam kak", "hey there", "hello there", "good morning sir", 
        "good afternoon", "good evening", "apa kabar hari ini?", "permisi kak", "halo admin", 
        "hi there", "hey admin", "p!", "oi bro", "morning", 
        "evening", "night", "hai selamat pagi", "halo selamat siang", "assalamualaikum pak",
        
        # Menu (80 pertanyaan)
        "daftar menu", "ada menu apa saja disini?", "menu apa saja disini?", "menu apa saja yang tersedia?", "jual apa saja di resto ini?", 
        "bisa lihat menu?", "tolong tunjukkan menu", "apa saja yang dijual?", "mau lihat daftar makanan", "resto ini jual apa?", 
        "bisa minta menunya?", "punya menu apa saja?", "tampilkan menu resto", "mau pesan, ada menu apa?", "bisa lihat daftar menu?", 
        "menu hari ini apa?", "makanan pembuka ada menu apa saja?", "apa saja makanan pembuka?", "menu makanan pembuka", "appetizer apa yang ada?", 
        "salad apa saja yang tersedia?", "sup ada menu apa saja?", "menu sup apa yang ada?", "apa saja pilihan sup?", "list menu sup", 
        "soup apa yang tersedia?", "jenis sup apa saja?", "kuah ada menu apa saja?", "menu kuah apa yang ada?", "apa saja pilihan kuah?", 
        "list menu berkuah", "makanan berkuah apa saja?", "jenis kuah apa yang tersedia?", "sapi ada menu apa saja?", "menu sapi apa yang ada?",
        "daging sapi ada apa saja?", "beef menu apa yang tersedia?", "masakan sapi apa saja?", "olahan daging sapi apa yang ada?", "daging ada menu apa saja?", 
        "menu daging apa yang ada?", "olahan daging apa saja?", "masakan daging apa yang tersedia?", "iga dan dendeng ada apa saja?", "sate dan dendeng menu apa?", 
        "ayam ada menu apa saja?", "menu ayam apa yang ada?", "chicken menu apa saja?", "olahan ayam apa yang tersedia?", "sate ayam dan ayam goreng ada apa?",
        "bebek ada menu apa saja?", "menu bebek apa yang ada?", "duck menu apa saja?", "olahan bebek apa yang tersedia?", "bebek goreng ada varian apa?", 
        "jenis masakan bebek apa?", "burung dara ada menu apa saja?", "menu burung dara apa yang ada?", "pigeon menu apa saja?", "olahan burung dara apa?", 
        "burung dara goreng ada varian apa?", "jenis masakan burung dara?", "ada menu burung dara apa?", "squab menu apa yang tersedia?", "nasi ada menu apa saja?", 
        "menu nasi apa yang ada?", "fried rice menu apa saja?", "nasi goreng ada varian apa?", "rice dishes apa yang tersedia?", "jenis nasi goreng apa saja?",
        "telur ada menu apa saja?", "menu telur apa yang ada?", "egg menu apa saja?", "olahan telur apa yang tersedia?", "bubur ada menu apa saja?", 
        "menu bubur apa yang ada?", "porridge menu apa saja?", "olahan bubur apa yang tersedia?", "mie ada menu apa saja?", "menu mie apa yang ada?", 
        
        # Harga (60 pertanyaan)
        "harga salad udang?", "berapa harga salad udang?", "salad udang harganya berapa?", "price salad udang", "harga salad udang goreng?", 
        "berapa harga salad udang goreng?", "salad udang goreng harganya?", "harga salad fillet ikan krispi keju?", "berapa harga salad ikan krispi keju?", "salad ikan krispi keju harganya?",
        "harga salad lobster?", "salad lobster berapa harganya?", "berapa harga salad lobster?", "harga salad lobster per ons?", "harga salad cumi goreng?", 
        "salad cumi goreng berapa?", "berapa harga salad cumi?", "harga salad buah?", "salad buah harganya berapa?", "berapa harga salad buah?", 
        "harga salad ayam?", "salad ayam berapa harganya?", "berapa harga salad ayam?", "daftar harga makanan pembuka", "harga semua makanan pembuka", 
        "price list appetizer", "harga Sup Asparagus Jagung Kepiting?", "berapa harga sup asparagus jagung kepiting?", "sup asparagus jagung kepiting harganya?", "price sup asparagus jagung kepiting", 
        "harga setengah porsi sup asparagus jagung kepiting?", "harga Sup Asparagus Jagung Ayam?", "sup asparagus jagung ayam berapa?", "berapa harga sup asparagus ayam?", "harga 1/2 porsi sup asparagus jagung ayam?",
        "harga Sup Jagung Kepiting?", "sup jagung kepiting harganya berapa?", "price sup jagung kepiting", "harga Sup Jagung Ayam?", "sup jagung ayam berapa harganya?", 
        "harga setengah porsi sup jagung ayam?", "harga Sup Asam Pedas / Sze Cuan?", "sup asam pedas harganya?", "sup sze cuan berapa?", "harga sup sze cuan?",
        "harga Sup Tahu Aneka Seafood?", "sup tahu seafood harganya berapa?", "berapa harga sup tahu aneka seafood?", "harga Sup Bibir Ikan?", "sup bibir ikan berapa?",
        "harga sup bibir ikan?", "harga Sup Tahu dan Sapi Cincang?", "sup tahu sapi cincang harganya?", "berapa harga sup tahu sapi?", "harga Sup Tom Yam?",
        "sup tom yam berapa harganya?", "harga tom yam soup?", "daftar harga semua sup", "harga semua menu sup", "price list soup",
        
        # Fasilitas (40 pertanyaan)
        "apakah tersedia area parkir?", "ada parkiran?", "parkir mobil ada?", "parkir motor dimana?", "kapasitas parkir berapa?",
        "apakah ada toilet?", "toilet dimana?", "wc ada berapa?", "toilet pria wanita?", "apakah ada mushola?",
        "tempat sholat ada?", "ruang ibadah?", "sholat dimana?", "apakah ada ruangan vip?", "private room ada?",
        "ruangan tertutup?", "kapasitas ruang vip?", "apakah ada ruangan meeting?", "ruang rapat?", "tempat meeting?",
        "bisa untuk seminar?", "apakah ada ruangan untuk merokok atau smoking area?", "smoking area dimana?", "boleh merokok?", "tempat merokok?", 
        "apakah ada live music?", "hiburan musik?", "ada band?", "jam berapa ada musik?", "apakah ada wifi?",
        "internet gratis?", "password wifi?", "koneksi internet?", "apakah ada colokan listrik untuk cas hp atau laptop?", "stop kontak ada?", 
        "bisa charge hp?", "colokan laptop dimana?", "apakah ada tempat bermain anak anak?", "playground ada?", "area anak-anak?",
        
        # Alamat (30 pertanyaan)
        "dimana alamat royal's resto?", "alamat lengkap dimana?", "lokasi royal's resto?", "dimana lokasinya?", "tempatnya di mana?",
        "bisa kasih alamat lengkap?", "di jalan apa?", "apakah dekat dengan pusat kota?", "lokasi di pusat kota?", "dekat kota ternate?",
        "di daerah mana?", "apakah Royal's Resto terdapat cabang lain?", "ada cabang di luar ternate?", "branch lain dimana?", "cabang jakarta ada?", 
        "apakah ada di kota lain?", "apakah royal's resto dekat dengan jalan utama?", "dekat jalan raya?", "jarak ke jalan utama?", "akses dari jalan besar?", 
        "apakah royal's resto terdapat di google maps?", "bisa dicari di google maps?", "ada di maps?", "bisa pakai gps?", "koordinat gps?", 
        "apakah royal's resto mudah dijangkau dengan kendaraan umum?", "akses angkutan umum?", "bisa naik bus?", "transportasi umum ke resto?", "apakah dekat dengan hotel?",
        
        # Reservasi (40 pertanyaan)
        "bagaimana cara reservasi di Royal's Resto?", "cara booking meja?", "gimana pesan tempat?", "proses reservasi bagaimana?", "mau booking gimana?", 
        "apa nomor telepon Royal's Resto?", "nomor hp royal's resto?", "kontak resto?", "telepon royal's resto?", "whatsapp royal's resto?", "apakah bisa reservasi untuk rombongan?", 
        "booking untuk grup besar?", "bisa untuk acara kantor?", "reservasi banyak orang?", "apakah bisa reservasi untuk acara?", "bisa untuk pernikahan?", 
        "acara keluarga?", "reservasi untuk ulang tahun?", "apakah perlu dp untuk reservasi?", "down payment untuk booking?", "uang muka reservasi?", 
        "berapa dp untuk reservasi?", "apakah bisa membatalkan reservasi?", "cancel reservasi boleh?", "batalkan booking?", "syarat pembatalan?",
        "apakah ada biaya pembatalan reservasi?", "denda cancel reservasi?", "uang dp bisa kembali?", "refund dp?", "apakah bisa mengganti hari reservasi?", 
        "reschedule booking?", "ubah jadwal reservasi?", "pindah tanggal booking?", "apakah ada maksimal orang untuk reservasi?", "kapasitas maksimal reservasi?", 
        "berapa orang bisa booking?", "maksimal berapa orang?", "apakah bisa untuk acara?", "bisa menghubungi kemana?", "bisa membatalkan reservasi atau tidak?",
        
        # Pembayaran (40 pertanyaan)
        "apakah bisa bayar tunai?", "bisa bayar cash?", "pembayaran tunai diterima?", "menerima uang cash?", "apakah bisa bayar dengan kartu debit?", 
        "kartu debit bca diterima?", "debit card bisa?", "bisa gesek kartu debit?", "apakah bisa bayar dengan kartu kredit?", "kartu kredit visa/mastercard?", 
        "credit card diterima?", "bisa bayar pakai kredit?", "apakah bisa bayar dengan qris?", "pembayaran qr code?", "bisa scan qris?", 
        "pembayaran digital?", "apakah bisa bayar dengan transfer bank?", "transfer bca boleh?", "bayar via bank transfer?", "bri transfer diterima?",
        "apakah ada biaya tambahan untuk pembayaran non tunai?", "admin kartu kredit?", "charge untuk debit card?", "biaya tambahan qris?", "apakah bisa bayar dengan e-wallet?", 
        "gopay bisa?", "ovo diterima?", "dana bisa bayar?", "link aja?", "apakah ada minimal pembayaran kartu?", 
        "minimal transaksi kartu kredit?", "minimal gesek kartu?", "apakah bisa bayar dengan cicilan?", "kartu kredit cicilan?", "installment?", 
        "apakah bisa split bill?", "pembayaran dipisah?", "bayar sendiri-sendiri?", "ada biaya tambahan non tunai?", "qris bisa atau tidak?"
        
        # Jam Operasional (30 pertanyaan)
        "royal's resto buka jam berapa?", "jam buka sampai kapan?", "buka jam berapa?", "operational hours?", "buka dari jam berapa?",
        "tutup jam berapa?", "jam operasional resto", "kapan buka?", "apakah buka setiap hari?", "buka hari minggu?",
        "buka hari libur?", "buka sabtu minggu?", "setiap hari buka?", "apakah tutup hari tertentu?", "apakah buka saat libur nasional?",
        "buka saat natal?", "buka tahun baru?", "buka hari kemerdekaan?", "libur nasional buka?", "apakah buka saat bulan puasa?",
        "jam buka ramadhan?", "buka saat puasa?", "operasional bulan puasa", "jam buka saat ramadhan", "apakah ada perbedaan jam buka saat weekday dan weekend?",
        "beda jam buka weekdays weekends?", "jam buka sabtu berbeda?", "weekend jam berapa buka?", "apakah bisa reservasi di luar jam buka?", "bisa pesan sebelum buka?",
        
        # Promo (40 pertanyaan)
        "apakah ada promo?", "ada diskon hari ini?", "apakah ada potongan harga?", "ada promo khusus?", "apakah ada paket hemat?",
        "ada menu paket?", "apakah ada buy 1 get 1?", "ada voucher diskon?", "apakah ada cashback?", "ada promo weekend?",
        "apakah ada promo bulan ini?", "ada special offer?", "apakah ada harga khusus member?", "ada diskon untuk siswa?", "apakah ada promo mahasiswa?", 
        "ada diskon karyawan?", "apakah ada harga promo?", "ada paket keluarga?", "apakah ada combo meal?", "ada menu bundling?", 
        "apakah ada happy hour?", "ada diskon early bird?", "apakah ada promo pembukaan?", "ada celebration package?", "apakah ada birthday promo?", 
        "ada anniversary discount?", "apakah ada corporate discount?", "ada group discount?", "apakah ada bulk order promo?", "ada loyalty program?", 
        "apakah ada points reward?", "ada referral bonus?", "apakah ada seasonal promotion?", "ada festival promo?", "apakah ada holiday special?", 
        "ada new year promo?", "apakah ada christmas discount?", "ada ramadhan promo?", "apakah ada lebaran discount?", "ada valentine promo?"
    ],
    'kategori': [
        # Introduction (40)
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        "introduction", "introduction", "introduction", "introduction", "introduction", 
        
        # Menu (80)
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        "menu", "menu", "menu", "menu", "menu",
        
        # Harga (60)
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        "harga", "harga", "harga", "harga", "harga",
        
        # Fasilitas (40)
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        "fasilitas", "fasilitas", "fasilitas", "fasilitas", "fasilitas",
        
        # Alamat (30)
        "alamat", "alamat", "alamat", "alamat", "alamat",
        "alamat", "alamat", "alamat", "alamat", "alamat",
        "alamat", "alamat", "alamat", "alamat", "alamat",
        "alamat", "alamat", "alamat", "alamat", "alamat",
        "alamat", "alamat", "alamat", "alamat", "alamat",
        "alamat", "alamat", "alamat", "alamat", "alamat",
        
        # Reservasi (40)
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        "reservasi", "reservasi", "reservasi", "reservasi", "reservasi",
        
        # Pembayaran (40)
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        "pembayaran", "pembayaran", "pembayaran", "pembayaran", "pembayaran",
        
        # Jam Operasional (30)
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional", "jam_operasional",
        
        # Promo (40)
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
        "promo", "promo", "promo", "promo", "promo",
    ]
})

print(f"Total testing samples: {len(df_test)}")
print(f"Kategori distribution:")
print(df_test['kategori'].value_counts())

# === Preprocess pertanyaan ===
df_test['processed'] = df_test['pertanyaan'].apply(preprocess)

# Transform testing
X_test_tfidf = vectorizer_qa.transform(df_test['processed'])

# Prediksi indeks jawaban
y_pred_indices = model_qa.predict(X_test_tfidf)

# Konversi indeks → kategori
y_pred_categories = [categories[i] for i in y_pred_indices]
y_true_categories = df_test['kategori'].tolist()

# ===== Akurasi =====
accuracy = accuracy_score(y_true_categories, y_pred_categories) * 100
print(f"Accuracy Kategori: {accuracy:.2f}%\n")

# ===== Confusion Matrix =====
unique_categories = sorted(list(set(categories)))
cm = confusion_matrix(y_true_categories, y_pred_categories, labels=unique_categories)

plt.figure(figsize=(12, 10))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=unique_categories,
            yticklabels=unique_categories)
plt.xlabel("Predicted Category")
plt.ylabel("True Category")
plt.title("Confusion Matrix Kategori (Model QA)")
plt.tight_layout()
plt.show()

# ===== Classification Report =====
print("\n=== Classification Report ===")
print(classification_report(y_true_categories, y_pred_categories))

# ===== Detail Accuracy per Category =====
print("\n=== Accuracy per Category ===")
category_accuracy = {}
for category in unique_categories:
    mask = np.array(y_true_categories) == category
    if sum(mask) > 0:
        cat_accuracy = accuracy_score(np.array(y_true_categories)[mask], np.array(y_pred_categories)[mask]) * 100
        category_accuracy[category] = cat_accuracy
        print(f"{category}: {cat_accuracy:.2f}%")

# ===== Sample Predictions =====
print("\n=== Sample Predictions ===")
sample_indices = [0, 50, 100, 150, 200, 250, 300, 350]
for idx in sample_indices:
    print(f"Pertanyaan: {df_test.iloc[idx]['pertanyaan']}")
    print(f"True: {y_true_categories[idx]}, Predicted: {y_pred_categories[idx]}")
    print(f"Match: {y_true_categories[idx] == y_pred_categories[idx]}\n")