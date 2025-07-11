# youtube-ai-backend/app.py

from flask import Flask, request, jsonify
import logging
from flask_cors import CORS
import requests # HTTP istekleri için

# Loglama ayarları
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Gemini API Anahtarınızı buraya ekleyin.
# Canvas ortamında bu otomatik olarak sağlanacaktır, bu yüzden şimdilik boş bırakın.
GEMINI_API_KEY = "AIzaSyCYXSTuCW1Wcg5Gb6m40oF12cBlke3a8i8" # Buraya API anahtarınızı yapıştırmayın! Canvas otomatik sağlar.
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ... (mevcut import'lar ve global değişkenler) ...
from markdown import markdown # Markdown'ı HTML'e çevirmek için

# ... (app, CORS, GEMINI_API_KEY, GEMINI_API_URL tanımları) ...

# Modeli yükleme kısmı kaldırılmıştı, API kullanıldığı için.

@app.route('/')
def home():
    log.debug("Root path isteği alındı.")
    return "YouTube Yorum Asistanı Backend'i çalışıyor!"

@app.route('/summarize', methods=['POST'])
def summarize_comments():
    log.info("'/summarize' endpoint'ine POST isteği geldi.")

    try:
        data = request.json
        if data is None:
            log.warning("İstek gövdesi boş veya geçerli JSON değil.")
            return jsonify({"error": "Geçerli bir JSON isteği gövdesi bekleniyor."}), 400

        comments_data = data.get('comments', [])
        comments_text_only = [c['text'] for c in comments_data if 'text' in c]
        
        log.debug(f"Gelen özetlenecek yorum sayısı: {len(comments_text_only)}")

        if not comments_text_only:
            log.warning("Özetleme isteğinde yorum bulunamadı (400 Bad Request).")
            return jsonify({"error": "Özetlenecek yorum bulunamadı."}), 400

        combined_text = ""
        max_comments_to_combine = 200 
        max_chars_for_gemini = 20000 

        for i, comment_text in enumerate(comments_text_only):
            if i >= max_comments_to_combine:
                break
            if len(combined_text) + len(comment_text) + 1 > max_chars_for_gemini:
                break
            combined_text += comment_text + "\n" 

        if not combined_text.strip():
            log.warning("Birleştirilmiş metin boş, özetleme yapılamaz (400 Bad Request).")
            return jsonify({"error": "Özetlenecek yeterli metin bulunamadı."}), 400

        # Gemini API'ye gönderilecek prompt'u oluştur
        # Modelden Markdown formatında çıktı istemek için prompt'u güncelliyoruz
        prompt = f"Aşağıdaki YouTube yorumlarını özetle. Yorumlardaki ana temaları, yaygın görüşleri ve önemli noktaları madde işaretleri ve başlıklar kullanarak Markdown formatında kısa ve öz bir şekilde belirt:\n\n{combined_text}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7, 
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 500 
            }
        }

        headers = {
            "Content-Type": "application/json"
        }
        api_url_with_key = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

        log.info(f"Gemini API'ye özetleme isteği gönderiliyor. Giriş metin uzunluğu: {len(combined_text)} karakter.")
        
        response = requests.post(api_url_with_key, headers=headers, json=payload)
        response.raise_for_status() 

        gemini_result = response.json()
        
        summary_markdown_text = "Özet alınamadı."
        if gemini_result and gemini_result.get('candidates'):
            first_candidate = gemini_result['candidates'][0]
            if first_candidate.get('content') and first_candidate['content'].get('parts'):
                summary_markdown_text = first_candidate['content']['parts'][0].get('text', "Özet metni boş geldi.")
        
        # Markdown metnini HTML'e dönüştür
        # `output_format='html'` ile düz HTML çıktısı alıyoruz.
        summary_html_text = markdown(summary_markdown_text, extensions=['fenced_code', 'nl2br']) 
        
        log.info("Özet başarıyla Gemini API'den alındı ve HTML olarak gönderiliyor.")
        return jsonify({"summary": summary_html_text}) # HTML olarak gönder

    except requests.exceptions.RequestException as req_err:
        log.critical(f"Gemini API isteği sırasında ağ/HTTP hatası oluştu: {req_err}", exc_info=True)
        return jsonify({"error": f"Yapay zeka servisine bağlanırken hata oluştu: {req_err}"}), 500
    except Exception as e:
        log.critical(f"Yorum özetlenirken kritik bir hata oluştu: {e}", exc_info=True)
        return jsonify({"error": f"Yorumları özetlerken bir hata oluştu: {e}"}), 500

@app.route('/filter', methods=['POST'])
def filter_comments_backend():
    log.info("'/filter' endpoint'ine POST isteği geldi.")
    try:
        data = request.json
        if data is None:
            log.warning("Filtreleme isteğinde gövde boş veya geçerli JSON değil.")
            return jsonify({"error": "Geçerli bir JSON isteği gövdesi bekleniyor."}), 400

        comments_data = data.get('comments', []) # Artık [{text:..., author:...}, ...] şeklinde
        keyword = data.get('keyword', '')

        log.debug(f"Gelen yorum objesi sayısı: {len(comments_data)}, Anahtar kelime: '{keyword}'")

        if not comments_data or not keyword:
            log.warning("Filtreleme isteğinde yorum veya anahtar kelime eksik (400 Bad Request).")
            return jsonify({"error": "Yorumlar veya anahtar kelime eksik."}), 400

        log.info(f"Filtreleniyor: {len(comments_data)} yorum, anahtar kelime: '{keyword}'")
        
        filtered_comments = []
        for comment_obj in comments_data:
            comment_text = comment_obj.get('text', '')
            author_name = comment_obj.get('author', '')
            
            # Hem yorum metninde hem de yazar adında arama yap
            if keyword.lower() in comment_text.lower() or keyword.lower() in author_name.lower():
                filtered_comments.append(comment_obj) # Eşleşen tüm objeyi ekle
        
        log.info(f"{len(filtered_comments)} yorum bulundu.")
        return jsonify({"filtered_comments": filtered_comments})
    except Exception as e:
        log.critical(f"Yorum filtrelenirken kritik bir hata oluştu: {e}", exc_info=True)
        return jsonify({"error": f"Yorumları filtrelerken bir hata oluştu: {e}"}), 500

if __name__ == '__main__':
    log.info("Flask uygulaması başlatılıyor...")
    app.run(debug=True, host='0.0.0.0', port=5001)