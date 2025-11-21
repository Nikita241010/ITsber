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
        question = "выдай будущие IT события в спб по типу конференций в которых можно быть как слушателем так и выступать в вузах и колледжах, узнать про их характеристику по пунктам : количество спикеров, количество участников , количество обсуждаемых тем , заинтересованность аудитории, формат проведения, дата проведения, онлайн или офлайн и обязательно разделять события на те в которых ты можешь быть слушателем и на те в которых можно зарегистрироваться на спикера"
        
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
