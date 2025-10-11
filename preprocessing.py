import re
import string
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
import nltk

# Download resource NLTK jika belum ada
nltk.download('punkt')
nltk.download('stopwords')

stop_words = set(stopwords.words('indonesian'))

# Inisialisasi stemmer Sastrawi
factory = StemmerFactory()
stemmer = factory.create_stemmer()

def preprocess(text):
    # Case folding
    text = text.lower()
    
    # Hapus tanda baca
    text = re.sub(r'['+string.punctuation+']', ' ', text)
    
    # Tokenizing
    tokens = word_tokenize(text)
    
    # Stopword removal
    tokens = [word for word in tokens if word not in stop_words]
    
    # Stemming menggunakan Sastrawi
    tokens = [stemmer.stem(word) for word in tokens]
    
    return ' '.join(tokens)
