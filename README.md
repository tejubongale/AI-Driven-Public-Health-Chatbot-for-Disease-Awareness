# AI-Driven Public Health Chatbot

A multilingual, hybrid AI chatbot designed for disease awareness and prevention. It combines semantic symptom matching with a health-focused dataset and provides an LLM-based fallback for general advice.

## 🚀 Features

- **Multilingual Support**: Supports English, Hindi, Kannada, and Telugu for both input and responses.
- **Hybrid Intelligence**:
  - **Dataset Mode**: Precise symptom-to-disease matching using `SentenceTransformers`.
  - **LLM Fallback**: Uses `distilgpt2` for general preventive health advice when no direct match is found in the dataset.
- **Rate Limiting**: Integrated safety measures with `Flask-Limiter`.
- **Modern UI**: Clean, responsive web interface with voice input support.

## 🛠️ Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd health-chatbot-demo
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   FLASK_SECRET_KEY=your_secret_key_here
   PORT=5000
   ```

## 💻 Usage

1. **Run the Flask Application**
   ```bash
   python flask_app.py
   ```
2. **Access the Web Interface**
   Open your browser and navigate to `http://127.0.0.1:5000`.

## 📂 Project Structure

- `flask_app.py`: Main backend logic and API routes.
- `templates/index.html`: Main frontend template.
- `static/`: Contains `style.css` and `script.js`.
- `diseases_dataset.csv`: Multilingual disease and symptom data.
- `requirements.txt`: Python dependencies.

## ⚠️ Disclaimer

**This chatbot is for educational and awareness purposes only.** It is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
