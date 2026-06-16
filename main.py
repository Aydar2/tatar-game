import os
import random
import json
import time
import uuid
import urllib.request
import urllib.parse
import ssl
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 837618188
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "")

QUIZ_SHEET_ID = os.getenv("QUIZ_SHEET_ID", "")
EMOJI_SHEET_ID = os.getenv("EMOJI_SHEET_ID", "")

known_users = set()

# ══════════════════════════════════════════════════════════
# GIGACHAT — ГЕНЕРАЦИЯ ВОПРОСОВ
# ══════════════════════════════════════════════════════════

gigachat_token = None
gigachat_token_expires = 0

def get_gigachat_token():
    """Получает или обновляет Access token"""
    global gigachat_token, gigachat_token_expires
    if gigachat_token and time.time() < gigachat_token_expires:
        return gigachat_token
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        data = urllib.parse.urlencode({"scope": "GIGACHAT_API_PERS"}).encode()
        req = urllib.request.Request(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            result = json.loads(r.read().decode())
        gigachat_token = result["access_token"]
        gigachat_token_expires = time.time() + 1700  # 28 минут
        print("✅ GigaChat токен получен")
        return gigachat_token
    except Exception as e:
        print(f"❌ Ошибка получения токена GigaChat: {e}")
        return None

def generate_questions_gigachat(used_topics=None):
    """Генерирует 10 уникальных вопросов через GigaChat"""
    token = get_gigachat_token()
    if not token:
        return None

    avoid = f"Не повторяй темы: {', '.join(used_topics)}." if used_topics else ""

    prompt = f"""Син — татар теле белгече һәм мәдәният тарихчысы. Татар телен камил беләсең.

Татар мәдәнияте, тарихы, теле, традицияләре буенча 10 викторина соравы төз.
{avoid}

ТЕЛ ТАЛӘПЛӘРЕ (бик мөһим!):
- Саф әдәби татар теле генә кулланыла
- Дөрес формалар: юк (НЕ йок), күп (НЕ коп), белән (НЕ менән), кеше (НЕ кише), нинди (НЕ ниндый)
- Башкорт, казах яки рус сүзләре кушмыйча
- Барлык сүзләр мәгънәле, бер-берсенә туры килергә тиеш

СОРАУ ТАЛӘПЛӘРЕ:
- Сораулар кызыклы, конкрет, бер дөрес җавабы булсын
- Дөрес булмаган вариантлар да ышандырырлык булсын
- explanation: бу темага кагылышлы кызыклы тарихи факт (ни өчен дөрес икәнен кабатламыйча)

Markdown юк. Башка текст юк. Чиста JSON гына:
[{{"q":"сорау?","options":["а","б","в","г"],"answer":0,"explanation":"Кызыклы факт."}}]"""

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        body = json.dumps({
            "model": "GigaChat-Max",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 3000,
        }).encode()

        req = urllib.request.Request(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            result = json.loads(r.read().decode())

        text = result["choices"][0]["message"]["content"]
        print(f"📝 GigaChat ответ: {text[:500]}")
        # Убираем markdown теги
        text = text.replace("```json", "").replace("```", "").strip()
        # Извлекаем JSON массив
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            print("❌ JSON не найден в ответе")
            return None
        text = text[start:end]
        # Чистим кривые кавычки внутри строк
        import re
        text = re.sub(r'«|»', '', text)  # убираем ёлочки
        text = re.sub(r'(?<!")\'(?!")', '', text)  # убираем одиночные кавычки
        # Обрезаем незакрытый JSON — берём только полные объекты
        valid_end = text.rfind("},")
        if valid_end != -1:
            text = text[:valid_end + 1] + "]"
        try:
            questions = json.loads(text)
        except Exception:
            # Последняя попытка — парсим по одному объекту
            questions = []
            for match in re.finditer(r'\{[^{}]+\}', text):
                try:
                    q = json.loads(match.group())
                    if "q" in q and "options" in q and "answer" in q:
                        questions.append(q)
                except Exception:
                    continue
        if not questions:
            print("❌ Ни одного вопроса не распарсилось")
            return None
        print(f"✅ GigaChat сгенерировал {len(questions)} вопросов")
        return questions
    except Exception as e:
        print(f"❌ Ошибка генерации вопросов: {e}")
        return None

# ══════════════════════════════════════════════════════════
# ЗАГРУЗКА ДАННЫХ ИЗ GOOGLE SHEETS
# ══════════════════════════════════════════════════════════

def fetch_sheet(sheet_id):
    """Загружает данные из публичного Google Sheets как CSV"""
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        with urllib.request.urlopen(url, timeout=10) as r:
            lines = r.read().decode("utf-8").strip().splitlines()
        rows = []
        for line in lines[1:]:  # пропускаем заголовок
            parts = line.split(",")
            if len(parts) >= 2:
                rows.append(parts)
        return rows
    except Exception as e:
        print(f"Ошибка загрузки таблицы: {e}")
        return []

def load_quiz_questions():
    """Загружает вопросы викторины из Sheets или fallback"""
    rows = fetch_sheet(QUIZ_SHEET_ID) if QUIZ_SHEET_ID else []
    if rows:
        questions = []
        for row in rows:
            try:
                q = {"q": row[0], "options": [row[1], row[2], row[3], row[4]], "answer": int(row[5]) - 1}
                questions.append(q)
            except Exception:
                continue
        if questions:
            return questions
    return FALLBACK_QUIZ

def load_emoji_songs():
    """Загружает песни из Sheets или fallback"""
    rows = fetch_sheet(EMOJI_SHEET_ID) if EMOJI_SHEET_ID else []
    if rows:
        songs = []
        for row in rows:
            try:
                songs.append({"emoji": row[0], "answer": row[1], "hint": row[2] if len(row) > 2 else ""})
            except Exception:
                continue
        if songs:
            return songs
    return FALLBACK_SONGS

# ══════════════════════════════════════════════════════════
# FALLBACK КОНТЕНТ (если Sheets не подключён)
# ══════════════════════════════════════════════════════════

FALLBACK_QUIZ = [
    {"q": "Татарстанның башкаласы кайсы шәһәр?", "options": ["Казан", "Уфа", "Чаллы", "Әлмәт"], "answer": 0},
    {"q": "Чак-чак нәрсә?", "options": ["Суп", "Бал белән камырдан ясалган татлы", "Татар биюе", "Музыка кораллары"], "answer": 1},
    {"q": "Татарча 'рәхмәт' нәрсәне аңлата?", "options": ["Сәлам", "Хушлашу", "Рәхмәт", "Зинһар"], "answer": 2},
    {"q": "Эчпочмак нәрсә?", "options": ["Ит белән өчпочмак пирог", "Татар бүреге", "Халык бәйрәме", "Музыкант"], "answer": 0},
    {"q": "Сабантуй нәрсә?", "options": ["Татар яңа елы", "Чәчү бәйрәме", "Дини ураза", "Туй йоласы"], "answer": 1},
    {"q": "Габдулла Тукай кем ул?", "options": ["Татар ханы", "Татар шагыйре", "Казан архитекторы", "Спортчы"], "answer": 1},
    {"q": "Татар ирләренең милли баш киеме нәрсә?", "options": ["Папаха", "Түбәтәй", "Феска", "Малахай"], "answer": 1},
    {"q": "Казан Кремле нинди исемлеккә керә?", "options": ["Дөнья могҗизалары", "ЮНЕСКО мирасы", "Миллионлы шәһәрләр", "МДБ башкалалары"], "answer": 1},
    {"q": "Катык нәрсә?", "options": ["Кымыз", "Кисеткән сөт эчемлеге", "Айран", "Тан"], "answer": 1},
    {"q": "Муса Җәлил кем ул?", "options": ["Герой шагыйрь", "Татар ханы", "Архитектор", "Спортчы"], "answer": 0},
    {"q": "Губадия нәрсә?", "options": ["Татар биюе", "Дүгәрәк пирог", "Халык җыры", "Чигү төре"], "answer": 1},
    {"q": "'Казан' сүзе нәрсәне аңлата?", "options": ["Ак шәһәр", "Казан", "Алтын шәһәр", "Елга ярында"], "answer": 1},
    {"q": "Татарстан байрагында нинди төсләр бар?", "options": ["Зәңгәр, ак, кызыл", "Яшел, ак, кызыл", "Сары, яшел, ак", "Яшел, ак, сары"], "answer": 1},
    {"q": "Бәлеш нәрсә?", "options": ["Ит һәм бәрәңге белән зур пирог", "Татар бишек җыры", "Келәм төре", "Баш киеме"], "answer": 0},
    {"q": "Ураза-байрам нинди бәйрәм?", "options": ["Навруз", "Сабантуй", "Рамазан бетү бәйрәме", "Корбан-байрам"], "answer": 2},
    {"q": "Талкыш нәрсә?", "options": ["Татар әкияте", "Бал һәм майдан ясалган татлы", "Халык кораллары", "Чигү төре"], "answer": 1},
    {"q": "Татар теленнән тыш татарлар нинди телдә сөйләшә?", "options": ["Башкорт", "Рус", "Казак", "Төрек"], "answer": 1},
    {"q": "Татарстанда нинди елга ага?", "options": ["Ока", "Идел", "Кама", "Агыйдел"], "answer": 1},
    {"q": "'Шүрәле' поэмасын кем язган?", "options": ["Муса Җәлил", "Габдулла Тукай", "Хади Такташ", "Сәлих Сәйдәшев"], "answer": 1},
    {"q": "Татарстан башкаласында нинди атаклы корылма бар?", "options": ["Кремль", "Эрмитаж", "Большой театр", "Мавзолей"], "answer": 0},
]

FALLBACK_SONGS = [
    {"emoji": "🌙 + 🏠 + ❤️", "answer": "Туган ягым", "hint": "Туган як турында"},
    {"emoji": "🌸 + 💃 + 🎵", "answer": "Апипа", "hint": "Татар халык биюе"},
    {"emoji": "🌊 + 🚣 + 😢", "answer": "Идел буйлап", "hint": "Идел елгасы турында"},
    {"emoji": "❤️ + 👧 + 🌹", "answer": "Гөлҗамал", "hint": "Кыз исеме"},
    {"emoji": "⭐ + 🌙 + 🎶", "answer": "Йолдызлы төн", "hint": "Кичке күк турында"},
    {"emoji": "🏡 + 👴 + 🌿", "answer": "Авылым", "hint": "Татар авылы турында"},
    {"emoji": "🦅 + 🌅 + 🕊️", "answer": "Ирек кошы", "hint": "Иреклек турында"},
    {"emoji": "💐 + 🌞 + 😊", "answer": "Бәхет", "hint": "Шатлык турында"},
    {"emoji": "🎪 + 🤼 + ☀️", "answer": "Сабантуй", "hint": "Татар бәйрәме"},
    {"emoji": "👰 + 💍 + 🎉", "answer": "Туй моңы", "hint": "Туй җыры"},
]

# ══════════════════════════════════════════════════════════
# СОСТОЯНИЕ ИГР
# ══════════════════════════════════════════════════════════

quiz_sessions = {}
emoji_sessions = {}

# ══════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ══════════════════════════════════════════════════════════

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Викторина", callback_data="start_quiz"),
         InlineKeyboardButton("🎵 Җырны тап", callback_data="start_emoji")],
        [InlineKeyboardButton("🏆 Нәтиҗәләр", callback_data="scores"),
         InlineKeyboardButton("ℹ️ Ничек уйнарга", callback_data="howto")],
    ])

# ══════════════════════════════════════════════════════════
# СТАРТ
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name

    if user.id not in known_users:
        known_users.add(user.id)
        username = f"@{user.username}" if user.username else "username юк"
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"👤 Яңа кулланучы!\n\n"
                     f"Исем: {user.first_name} {user.last_name or ''}\n"
                     f"Username: {username}\n"
                     f"ID: {user.id}\n\n"
                     f"Барлыгы: {len(known_users)} кулланучы"
            )
        except Exception:
            pass

    text = (
        f"Сәлам, {name}! 🌙\n\n"
        "*Татар Уены* — дуслар өчен уен ботына хуш килдегез!\n\n"
        "🧠 *Викторина* — татар мәдәнияте буенча сораулар. Беренче дөрес җавап биргән — җиңүче!\n\n"
        "🎵 *Җырны тап* — эмодзи буенча татар җырын таб. Кем тизрәк?\n\n"
        "Дусларыңны чакыр һәм уйный башла 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════
# ВИКТОРИНА
# ══════════════════════════════════════════════════════════

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    await query.message.reply_text("⏳ Сораулар әзерләнә...")

    prev_scores = quiz_sessions.get(chat_id, {}).get("scores", {})
    # Берём темы использованных вопросов внутри этого чата
    used_topics = quiz_sessions.get(chat_id, {}).get("used_topics", [])
    # Если накопилось много тем — оставляем только последние 30 чтобы промпт не разбухал
    if len(used_topics) > 30:
        used_topics = used_topics[-30:]

    if GIGACHAT_AUTH_KEY:
        questions = generate_questions_gigachat(used_topics)
        if not questions:
            await query.message.reply_text("⚠️ GigaChat җавап бирмәде, кабат яза башла...")
            questions = FALLBACK_QUIZ
    else:
        questions = load_quiz_questions()

    # Добавляем новые темы в историю чата
    new_topics = used_topics + [q["q"][:30] for q in questions]

    quiz_sessions[chat_id] = {
        "scores": prev_scores,
        "used": [],
        "questions": questions,
        "used_topics": new_topics
    }

    await send_quiz_question(context, chat_id, query.message)

async def send_quiz_question(context, chat_id, message=None):
    session = quiz_sessions.get(chat_id, {"scores": {}, "used": [], "questions": FALLBACK_QUIZ})
    questions = session.get("questions", FALLBACK_QUIZ)
    available = [i for i in range(len(questions)) if i not in session["used"]]

    if not available:
        scores = session["scores"]
        if scores:
            ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            result = "🏆 *Уен бетте! Нәтиҗәләр:*\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, score) in enumerate(ranking):
                medal = medals[i] if i < 3 else f"{i+1}."
                result += f"{medal} {name} — {score} балл\n"
        else:
            result = "Беркем дә дөрес җавап бирмәде 😅"

        # Сохраняем счёт и историю тем, сбрасываем только вопросы
        used_topics = session.get("used_topics", [])
        quiz_sessions[chat_id] = {
            "scores": scores,
            "used": [],
            "questions": [],
            "used_topics": used_topics
        }
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Яңадан уйна", callback_data="start_quiz"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu")
        ]])
        if message:
            await message.reply_text(result, parse_mode="Markdown", reply_markup=kb)
        return

    idx = random.choice(available)
    q = questions[idx]
    session["used"].append(idx)
    session["current"] = idx
    session["answered"] = False
    quiz_sessions[chat_id] = session

    buttons = []
    for i, opt in enumerate(q["options"]):
        buttons.append([InlineKeyboardButton(opt, callback_data=f"quiz_answer_{i}")])
    buttons.append([InlineKeyboardButton("⏭ Киләсе сорау", callback_data="quiz_next")])

    text = f"❓ *Сорау {len(session['used'])}/{len(questions)}*\n\n{q['q']}"
    if message:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user
    answer_idx = int(query.data.split("_")[-1])

    session = quiz_sessions.get(chat_id)
    if not session or session.get("answered"):
        await query.answer("Бу сорауга инде җавап бирделәр!", show_alert=True)
        return

    questions = session.get("questions", FALLBACK_QUIZ)
    q = questions[session["current"]]
    name = user.first_name

    if answer_idx == q["answer"]:
        session["answered"] = True
        session["scores"][name] = session["scores"].get(name, 0) + 1
        quiz_sessions[chat_id] = session
        await query.answer(f"✅ Дөрес! +1 балл, {name}!", show_alert=True)
        explanation = q.get("explanation", "")
        expl_text = f"\n\n📖 _{explanation}_" if explanation else ""
        buttons = [[
            InlineKeyboardButton("⏭ Киләсе сорау", callback_data="quiz_next"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu")
        ]]
        await query.edit_message_text(
            f"✅ *{name}* дөрес җавап бирде!\n\n"
            f"❓ {q['q']}\n\n"
            f"💡 Җавап: *{q['options'][q['answer']]}*"
            f"{expl_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await query.answer("❌ Дөрес түгел, тагын уйла!", show_alert=True)

async def quiz_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await send_quiz_question(context, chat_id, query.message)

# ══════════════════════════════════════════════════════════
# УГАДАЙ ПЕСНЮ ПО ЭМОДЗИ
# ══════════════════════════════════════════════════════════

async def start_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    songs = load_emoji_songs()
    shuffled = random.sample(songs, len(songs))
    emoji_sessions[chat_id] = {"songs": shuffled, "index": 0, "scores": {}}

    await send_emoji_song(query.message, chat_id)

async def send_emoji_song(message, chat_id):
    session = emoji_sessions.get(chat_id)
    if not session:
        return

    idx = session["index"]
    songs = session["songs"]

    if idx >= len(songs):
        scores = session["scores"]
        if scores:
            ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            result = "🏆 *Уен бетте! Нәтиҗәләр:*\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, score) in enumerate(ranking):
                medal = medals[i] if i < 3 else f"{i+1}."
                result += f"{medal} {name} — {score} балл\n"
        else:
            result = "Беркем дә таба алмады 😅"

        emoji_sessions.pop(chat_id, None)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Яңадан", callback_data="start_emoji"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu")
        ]])
        await message.reply_text(result, parse_mode="Markdown", reply_markup=kb)
        return

    song = songs[idx]
    session["answered"] = False
    session["current_answer"] = song["answer"].lower().strip()
    emoji_sessions[chat_id] = session

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Ым", callback_data="emoji_hint"),
         InlineKeyboardButton("⏭ Киләсе", callback_data="emoji_next")]
    ])

    await message.reply_text(
        f"🎵 *Җырны тап! ({idx+1}/{len(songs)})*\n\n"
        f"*{song['emoji']}*\n\n"
        f"_Татарча яз_ 👇",
        parse_mode="Markdown",
        reply_markup=kb
    )

async def emoji_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    session = emoji_sessions.get(chat_id)
    if not session:
        return
    song = session["songs"][session["index"]]
    hint = song.get("hint", "Ым юк")
    await query.message.reply_text(f"💡 Ым: _{hint}_", parse_mode="Markdown")

async def emoji_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    session = emoji_sessions.get(chat_id)
    if session:
        song = session["songs"][session["index"]]
        session["index"] += 1
        emoji_sessions[chat_id] = session
        await query.message.reply_text(f"⏭ Дөрес җавап: *{song['answer']}*", parse_mode="Markdown")
    await send_emoji_song(query.message, chat_id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет ответы на угадай песню"""
    chat_id = update.effective_chat.id
    session = emoji_sessions.get(chat_id)

    if not session or session.get("answered"):
        return

    user_answer = update.message.text.lower().strip()
    correct = session.get("current_answer", "")
    user = update.effective_user
    name = user.first_name

    if user_answer == correct or correct in user_answer or user_answer in correct:
        session["answered"] = True
        session["scores"][name] = session["scores"].get(name, 0) + 1
        session["index"] += 1
        emoji_sessions[chat_id] = session

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Киләсе", callback_data="emoji_next_after"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu")
        ]])
        await update.message.reply_text(
            f"✅ *{name}* тапты! +1 балл 🎉\n\n"
            f"Дөрес: *{session['songs'][session['index']-1]['answer']}*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await update.message.reply_text("❌ Дөрес түгел, тагын уйла!")

async def emoji_next_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await send_emoji_song(query.message, chat_id)

# ══════════════════════════════════════════════════════════
# ПРОЧЕЕ
# ══════════════════════════════════════════════════════════

async def show_scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    quiz_scores = quiz_sessions.get(chat_id, {}).get("scores", {})
    emoji_scores = emoji_sessions.get(chat_id, {}).get("scores", {})

    all_scores = {}
    for name, score in {**quiz_scores, **emoji_scores}.items():
        all_scores[name] = all_scores.get(name, 0) + score

    if not all_scores:
        await query.message.reply_text("Әле баллар юк! Уен башла 🎮", reply_markup=main_keyboard())
        return

    ranking = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Хәзерге хисап:*\n\n"
    for i, (name, score) in enumerate(ranking):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {name} — {score} балл\n"

    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def howto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ *Ничек уйнарга:*\n\n"
        "1️⃣ Ботны дуслар белән группага өсти\n"
        "2️⃣ /start яз\n\n"
        "🧠 *Викторина:*\n"
        "Бот сорау бирә — беренче дөрес басканга балл!\n\n"
        "🎵 *Җырны тап:*\n"
        "Эмодзи буенча татар җырын тап — татарча яз!\n\n"
        "Барысын чакыр! 🎉"
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"📊 *Статистика:*\n\n"
        f"👥 Кулланучылар саны: {len(known_users)}",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Баш меню 👇", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^start_quiz$"))
    app.add_handler(CallbackQueryHandler(start_emoji, pattern="^start_emoji$"))
    app.add_handler(CallbackQueryHandler(quiz_answer, pattern="^quiz_answer_"))
    app.add_handler(CallbackQueryHandler(quiz_next, pattern="^quiz_next$"))
    app.add_handler(CallbackQueryHandler(emoji_hint, pattern="^emoji_hint$"))
    app.add_handler(CallbackQueryHandler(emoji_next, pattern="^emoji_next$"))
    app.add_handler(CallbackQueryHandler(emoji_next_after, pattern="^emoji_next_after$"))
    app.add_handler(CallbackQueryHandler(show_scores, pattern="^scores$"))
    app.add_handler(CallbackQueryHandler(howto, pattern="^howto$"))
    app.add_handler(CallbackQueryHandler(menu, pattern="^menu$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🎮 Татар Уены запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
