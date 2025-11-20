# app.py
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

def call_openrouter_api():
    """Функция для запроса к OpenRouter API с вопросом про IT конкурсы"""
    try:
        # Новый вопрос про IT конкурсы
        question = "Какие есть IT конкурсы в ближайшее время на которые я смогу сходить, расскажи о 10 самых известных. В каждом укажи: где он проходит, когда он проходит, стоимость участия"
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer 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",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "IT Competitions Finder",
            },
            json={
                "model": "openai/gpt-4o-mini-search-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "max_tokens": 2000,  # Увеличил лимит для более подробного ответа
                "temperature": 0.7
            },
            timeout=45  # Увеличил таймаут для более сложного запроса
        )
        
        if response.status_code == 200:
            response_data = response.json()
            return {
                'question': question,
                'answer': response_data['choices'][0]['message']['content'],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {
                'error': f"Ошибка API: {response.status_code}",
                'details': response.text
            }
            
    except Exception as e:
        return {
            'error': f"Ошибка: {str(e)}"
        }

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/get-competitions', methods=['POST'])
def get_competitions():
    """Эндпоинт для получения информации о IT конкурсах"""
    try:
        # Вызываем API с вопросом про IT конкурсы
        result = call_openrouter_api()
        
        if 'error' in result:
            return jsonify({
                'status': 'error',
                'message': result['error'],
                'details': result.get('details', '')
            }), 500
        
        # Возвращаем результат
        return jsonify({
            'status': 'success',
            'message': 'Информация о конкурсах успешно получена',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
