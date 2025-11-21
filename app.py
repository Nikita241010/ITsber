from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
import requests
import json
import os
import re
import csv
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.secret_key = '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'
CORS(app)

# Файл для хранения пользователей
USERS_FILE = 'users.json'
LAST_UPDATE_FILE = 'last_update.txt'

def load_users():
    """Загрузка пользователей из файла"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки пользователей: {e}")
            return {}
    return {}

def save_users(users):
    """Сохранение пользователей в файл"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пользователей: {e}")
        return False

def init_default_users():
    """Инициализация пользователей по умолчанию"""
    users = load_users()
    
    default_users = {
        'admin': {'password': 'admin123', 'role': 'admin'},
        'worker': {'password': 'worker123', 'role': 'worker'}
    }
    
    for username, user_data in default_users.items():
        if username not in users:
            users[username] = user_data
    
    save_users(users)
    return users

def get_last_update_time():
    """Получаем время последнего обновления"""
    try:
        if os.path.exists(LAST_UPDATE_FILE):
            with open(LAST_UPDATE_FILE, 'r') as f:
                return datetime.fromisoformat(f.read().strip())
    except Exception as e:
        print(f"Ошибка чтения времени обновления: {e}")
    return None

def save_last_update_time():
    """Сохраняем время обновления"""
    try:
        with open(LAST_UPDATE_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        return True
    except Exception as e:
        print(f"Ошибка сохранения времени обновления: {e}")
        return False

def should_update_events():
    """Проверяем, нужно ли обновлять события (раз в 3 дня)"""
    last_update = get_last_update_time()
    if not last_update:
        return True
    
    time_diff = datetime.now() - last_update
    return time_diff.days >= 3

def ai_ask():
    """Функция для получения данных от AI с обработкой ошибок"""
    qwestion = "выдай будущие 20 самых известных IT событий в спб(или близких городах) " \
              "по типу конференций в которых можно быть"\
              "как слушателем так и спикером, рассказывай только о тех событиях о которых " \
              "знаешь хотя бы 6 из 9 фактов(шаблон ниже), говори сухо, только числа, факты," \
              "я хочу использовать твой ответ автоматически его парсит и заносить в базу так что" \
              " всё должно быть строго по шаблону, начинай каждую строку как в шаблоне, никаких лишних символов или пробелов, учти что мне нужны будущие события а не прошедшие, но только те где указана точная дата и до года вперёд но желательно в ближайшие 3 месяца"\
              "Формат ответа:"\
              "порядковый номер"\
              "Название:"\
              "Дата проведения:(Обязательно нужна точная дата)"\
              "Место проведения:(Должно быть в России обязательно)"\
              "Краткое описание: А вот его сухо не надо, заинтерисуй но не придумывай"\
              "Формат: Онлайн\офлайн"\
              "Количество участников: (если нет информации предположи основываясь на известности мероприятия или истории, никаких плюсов, либо цифра либо диопазон)"\
              "Количество спикеров: (если нет информации предположи основываясь на известности мероприятия или истории, никаких плюсов, либо цифра либо диопазон)"\
              "Участие: как спикер\слушатель"

    try:
        print("🔄 Отправка запроса к AI...")
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer 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",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "IT Events Parser",
            },
            data=json.dumps({
                "model": "openai/gpt-4o-mini-search-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": qwestion
                    }
                ],
                "max_tokens": 10000,
                "temperature": 0.8
            }),
            timeout=60
        )
        
        if response.status_code == 200:
            response_data = response.json()
            message_content = response_data['choices'][0]['message']['content']
            print("✅ Данные успешно получены от AI")
            return message_content
        else:
            print(f'❌ Ошибка API: {response.status_code} - {response.text}')
            return None
            
    except requests.exceptions.Timeout:
        print('❌ Таймаут при запросе к AI')
        return None
    except requests.exceptions.ConnectionError:
        print('❌ Ошибка подключения к AI')
        return None
    except requests.exceptions.RequestException as e:
        print(f'❌ Ошибка сети при запросе к AI: {e}')
        return None
    except Exception as e:
        print(f'❌ Неожиданная ошибка в ai_ask: {e}')
        return None

def parse_events_universal(text: str):
    """УНИВЕРСАЛЬНЫЙ ПАРСЕР для любого формата"""
    events = {}
    
    if not text or not text.strip():
        print("❌ Получен пустой текст для парсинга")
        return []
    
    print(f"🔍 Начинаем парсинг текста длиной {len(text)} символов...")
    
    try:
        # Нормализация текста
        normalized_text = text.strip()
        normalized_text = re.sub(r'(\d+)\*\*Название:\*\*', r'\1\n**Название:**', normalized_text)
        normalized_text = re.sub(r'(\d+)\.\s*\*\*Название:\*\*', r'\1\n**Название:**', normalized_text)
        normalized_text = re.sub(r'(\d+)\.\s*Название:', r'\1\n**Название:**', normalized_text)
        
        # Разбиваем на блоки мероприятий
        blocks = []
        blocks1 = re.split(r'\n(?=\d+\n\*\*Название:\*\*)', normalized_text)
        if len(blocks1) > 1:
            blocks = blocks1
            print(f"📦 Стратегия 1: найдено {len(blocks)} блоков")
        else:
            blocks2 = re.split(r'\n(?=\d+\.?\s*\n?Название:)', normalized_text)
            if len(blocks2) > 1:
                blocks = blocks2
                print(f"📦 Стратегия 2: найдено {len(blocks)} блоков")
            else:
                blocks3 = re.split(r'\n(?=\d+\.?)', normalized_text)
                blocks = blocks3
                print(f"📦 Стратегия 3: найдено {len(blocks)} блоков")
        
        for i, block in enumerate(blocks):
            if not block.strip():
                continue
                
            # Извлекаем номер мероприятия
            event_num = None
            num_patterns = [
                r'^(\d+)\n\*\*Название:\*\*',
                r'^(\d+)\.\n\*\*Название:\*\*',
                r'^(\d+)\*\*Название:\*\*',
                r'^(\d+)\.\s*Название:',
                r'^(\d+)\s+Название:',
                r'^(\d+)\.'
            ]
            
            for pattern in num_patterns:
                match = re.search(pattern, block)
                if match:
                    event_num = match.group(1)
                    break
            
            if not event_num:
                continue
                
            # Создаем/обновляем мероприятие
            if event_num in events:
                current_event = events[event_num]
            else:
                current_event = {
                    'номер': event_num,
                    'название': '',
                    'дата_проведения': '',
                    'место_проведения': '',
                    'краткое_описание': '',
                    'формат': '',
                    'количество_участников': '',
                    'количество_спикеров': '',
                    'участие': ''
                }
                events[event_num] = current_event
            
            # Парсинг полей
            field_patterns = {
                'название': [
                    r'Название:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Название:\s*([^\n]+)',
                    r'\*\*Название:\*\*([^\n]+)'
                ],
                'дата_проведения': [
                    r'Дата проведения:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Дата проведения:\s*([^\n]+)',
                    r'\*\*Дата проведения:\*\*([^\n]+)'
                ],
                'место_проведения': [
                    r'Место проведения:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Место проведения:\s*([^\n]+)',
                    r'\*\*Место проведения:\*\*([^\n]+)'
                ],
                'краткое_описание': [
                    r'Краткое описание:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Краткое описание:\s*([^\n]+)',
                    r'\*\*Краткое описание:\*\*([^\n]+)'
                ],
                'формат': [
                    r'Формат:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Формат:\s*([^\n]+)',
                    r'\*\*Формат:\*\*([^\n]+)'
                ],
                'количество_участников': [
                    r'Количество участников:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Количество участников:\s*([^\n]+)',
                    r'\*\*Количество участников:\*\*([^\n]+)'
                ],
                'количество_спикеров': [
                    r'Количество спикеров:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Количество спикеров:\s*([^\n]+)',
                    r'\*\*Количество спикеров:\*\*([^\n]+)'
                ],
                'участие': [
                    r'Участие:\*\*\s*([^\n*]+)(?=\*\*|$)',
                    r'Участие:\s*([^\n]+)',
                    r'\*\*Участие:\*\*([^\n]+)'
                ]
            }
            
            for field_name, patterns in field_patterns.items():
                if current_event[field_name]:
                    continue
                    
                for pattern in patterns:
                    match = re.search(pattern, block)
                    if match:
                        value = match.group(1).strip()
                        value = re.sub(r'\s+', ' ', value)
                        value = value.strip('*').strip()
                        
                        if value:
                            current_event[field_name] = value
                            break
        
        # Фильтруем пустые мероприятия
        valid_events = [event for event in events.values() if event['название']]
        
        print(f"🎯 Успешно обработано {len(valid_events)} мероприятий")
        return sorted(valid_events, key=lambda x: int(x['номер']))
    
    except Exception as e:
        print(f"❌ Ошибка при парсинге данных: {e}")
        return []

def save_events_to_csv(events, filename: str = "events_database.csv"):
    """Сохраняет события в CSV файл"""
    if not events:
        print("❌ Нет данных для сохранения.")
        return False
    
    fieldnames = [
        'номер', 'название', 'дата_проведения', 'место_проведения', 
        'краткое_описание', 'формат', 'количество_участников', 
        'количество_спикеров', 'участие'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for event in events:
                writer.writerow(event)
        
        print(f"💾 Данные успешно сохранены в файл: {filename}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении в CSV: {e}")
        return False

def update_events_automatically():
    """Автоматическое обновление событий с обработкой ошибок"""
    if should_update_events():
        print("🔄 Запуск автоматического обновления событий...")
        
        try:
            ai_response = ai_ask()
            if ai_response:
                events = parse_events_universal(ai_response)
                if events:
                    if save_events_to_csv(events):
                        save_last_update_time()
                        print("✅ Автоматическое обновление завершено успешно")
                        return True
                    else:
                        print("❌ Не удалось сохранить данные в CSV")
                else:
                    print("❌ Не удалось распарсить данные от AI")
            else:
                print("❌ Не удалось получить данные от AI")
            
            print("⚠️ Автоматическое обновление не удалось, но система продолжает работать")
            return False
            
        except Exception as e:
            print(f"❌ Критическая ошибка при автоматическом обновлении: {e}")
            print("⚠️ Система продолжает работать со старыми данными")
            return False
    else:
        last_update = get_last_update_time()
        next_update = last_update + timedelta(days=3) if last_update else None
        print(f"⏰ Следующее обновление: {next_update}")
        return True

def background_updater():
    """Фоновая задача для проверки обновлений"""
    while True:
        try:
            success = update_events_automatically()
            if not success:
                print("⚠️ Фоновое обновление не удалось, продолжаем работу")
            # Проверяем каждые 6 часов
            time.sleep(6 * 60 * 60)
        except Exception as e:
            print(f"❌ Критическая ошибка в фоновом обновлении: {e}")
            print("⚠️ Перезапуск фонового обновления через 1 час")
            time.sleep(60 * 60)  # Ждем час при ошибке

# Запускаем фоновое обновление
updater_thread = threading.Thread(target=background_updater, daemon=True)
updater_thread.start()

# Инициализируем пользователей
users = init_default_users()

@app.route('/')
def index():
    """Главная страница"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>База данных событий</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>
        <h1>База данных IT событий</h1>
        <p>Система запущена и работает!</p>
        <p><a href="/main">Перейти к приложению</a></p>
    </body>
    </html>
    """

@app.route('/main')
def main_app():
    """Основное приложение"""
    return send_file('index.html')

@app.route('/login', methods=['POST'])
def login():
    """Эндпоинт для аутентификации"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Отсутствуют данные'
            }), 400
            
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        
        if not username or not password or not role:
            return jsonify({
                'status': 'error',
                'message': 'Все поля обязательны для заполнения'
            }), 400
        
        users = load_users()
        
        if (username in users and 
            users[username]['password'] == password and 
            users[username]['role'] == role):
            
            session['user'] = {
                'username': username,
                'role': role
            }
            return jsonify({
                'status': 'success',
                'message': 'Успешный вход в систему',
                'user': {
                    'username': username,
                    'role': role
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Неверный логин, пароль или роль'
            }), 401
            
    except Exception as e:
        print(f"❌ Ошибка в login: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера'
        }), 500

@app.route('/register', methods=['POST'])
def register():
    """Эндпоинт для регистрации"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Отсутствуют данные'
            }), 400
            
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        
        if not username or not password or not role:
            return jsonify({
                'status': 'error',
                'message': 'Все поля обязательны для заполнения'
            }), 400
        
        users = load_users()
        
        if username in users:
            return jsonify({
                'status': 'error',
                'message': 'Пользователь с таким логином уже существует'
            }), 400
        
        if len(username) < 3:
            return jsonify({
                'status': 'error',
                'message': 'Логин должен содержать минимум 3 символа'
            }), 400
            
        if len(password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Пароль должен содержать минимум 6 символов'
            }), 400
        
        users[username] = {
            'password': password,
            'role': role
        }
        
        if save_users(users):
            return jsonify({
                'status': 'success',
                'message': 'Регистрация успешна'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Ошибка сохранения пользователя'
            }), 500
            
    except Exception as e:
        print(f"❌ Ошибка в register: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера'
        }), 500

@app.route('/logout', methods=['POST'])
def logout():
    """Эндпоинт для выхода из системы"""
    session.pop('user', None)
    return jsonify({
        'status': 'success',
        'message': 'Успешный выход из системы'
    })

@app.route('/check-auth')
def check_auth():
    """Проверка авторизации"""
    user = session.get('user')
    if user:
        return jsonify({
            'status': 'success',
            'user': user
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Не авторизован'
        }), 401

@app.route('/get-events', methods=['POST'])
def get_events():
    """Эндпоинт для получения событий от AI и сохранения в CSV"""
    user = session.get('user')
    if not user:
        return jsonify({
            'status': 'error',
            'message': 'Требуется авторизация'
        }), 401
    
    try:
        print("🔄 Запуск получения событий от AI...")
        
        ai_response = ai_ask()
        
        if not ai_response:
            return jsonify({
                'status': 'error',
                'message': 'Не удалось получить данные от AI. Проверьте подключение к интернету и API ключ.'
            }), 500
        
        events = parse_events_universal(ai_response)
        
        if not events:
            return jsonify({
                'status': 'error',
                'message': 'Не удалось распарсить данные от AI. Формат ответа не соответствует ожидаемому.'
            }), 500
        
        if save_events_to_csv(events):
            save_last_update_time()
            return jsonify({
                'status': 'success',
                'message': f'Успешно получено и сохранено {len(events)} событий',
                'data': {
                    'events_count': len(events),
                    'filename': 'events_database.csv'
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Ошибка при сохранении данных в файл'
            }), 500
        
    except Exception as e:
        print(f"❌ Ошибка в get-events: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Внутренняя ошибка сервера: {str(e)}'
        }), 500

@app.route('/api/events/csv')
def get_events_csv():
    """Отдает CSV файл с событиями"""
    try:
        return send_file('events_database.csv', as_attachment=False, mimetype='text/csv')
    except FileNotFoundError:
        return jsonify({
            'status': 'error',
            'message': 'Файл с событиями не найден'
        }), 404

@app.route('/api/update-status')
def get_update_status():
    """Возвращает статус последнего обновления"""
    try:
        last_update = get_last_update_time()
        next_update = last_update + timedelta(days=3) if last_update else None
        needs_update = should_update_events()
        
        return jsonify({
            'last_update': last_update.isoformat() if last_update else None,
            'next_update': next_update.isoformat() if next_update else None,
            'needs_update': needs_update
        })
    except Exception as e:
        print(f"❌ Ошибка в get_update_status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Ошибка получения статуса обновления'
        }), 500

@app.route('/events-database.csv')
def get_events_database():
    """Альтернативный путь к CSV файлу"""
    try:
        return send_file('events_database.csv', as_attachment=False, mimetype='text/csv')
    except FileNotFoundError:
        return jsonify({
            'status': 'error',
            'message': 'Файл с событиями не найден'
        }), 404

if __name__ == '__main__':
    # Создаем пустой CSV файл если его нет
    if not os.path.exists('events_database.csv'):
        try:
            with open('events_database.csv', 'w', encoding='utf-8-sig') as f:
                f.write('номер,название,дата_проведения,место_проведения,краткое_описание,формат,количество_участников,количество_спикеров,участие\n')
            print("✅ Создан пустой CSV файл для событий")
        except Exception as e:
            print(f"❌ Ошибка создания CSV файла: {e}")
    
    # Запускаем автоматическое обновление при старте
    print("🚀 Запуск автоматического обновления событий...")
    try:
        update_events_automatically()
    except Exception as e:
        print(f"❌ Ошибка при запуске автоматического обновления: {e}")
        print("⚠️ Система запускается со старыми данными")
    
    print("✅ Сервер запущен и готов к работе")
    app.run(debug=True, port=5000, host='0.0.0.0')
