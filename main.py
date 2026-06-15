import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ══════════════════════════════════════════════════════════
# КОНТЕНТ
# ══════════════════════════════════════════════════════════

QUIZ_QUESTIONS = [
    {"q": "Как называется столица Татарстана?", "options": ["Казань", "Уфа", "Набережные Челны", "Альметьевск"], "answer": 0},
    {"q": "Что такое чак-чак?", "options": ["Суп", "Сладкое блюдо из теста с мёдом", "Татарский танец", "Музыкальный инструмент"], "answer": 1},
    {"q": "Как будет 'спасибо' на татарском?", "options": ["Сәлам", "Рәхмәт", "Зинһар", "Әйе"], "answer": 1},
    {"q": "Какая река протекает через Казань?", "options": ["Ока", "Волга", "Кама", "Белая"], "answer": 1},
    {"q": "Что такое эчпочмак?", "options": ["Треугольный пирожок с мясом", "Татарская шапка", "Народный праздник", "Музыкант"], "answer": 0},
    {"q": "Как переводится слово 'Татарстан'?", "options": ["Земля гор", "Страна татар", "Великая степь", "Земля у реки"], "answer": 1},
    {"q": "Какой праздник татары отмечают после Рамадана?", "options": ["Навруз", "Сабантуй", "Ураза-байрам", "Курбан-байрам"], "answer": 2},
    {"q": "Что такое Сабантуй?", "options": ["Татарский новый год", "Праздник плуга после посева", "Религиозный пост", "Свадебный обряд"], "answer": 1},
    {"q": "Как называется татарский национальный головной убор мужчин?", "options": ["Папаха", "Тюбетейка", "Феска", "Малахай"], "answer": 1},
    {"q": "Кто написал поэму 'Шурале'?", "options": ["Муса Джалиль", "Габдулла Тукай", "Хади Такташ", "Салих Сайдашев"], "answer": 1},
    {"q": "Что такое губадия?", "options": ["Татарский танец", "Круглый пирог с рисом и сухофруктами", "Народная песня", "Вид вышивки"], "answer": 1},
    {"q": "На каком языке говорят татары помимо татарского?", "options": ["Башкирский", "Русский", "Казахский", "Турецкий"], "answer": 1},
    {"q": "Как будет 'привет' на татарском?", "options": ["Рәхмәт", "Хуш", "Сәлам", "Бәхет"], "answer": 2},
    {"q": "Казанский Кремль входит в список...", "options": ["Чудес света", "Наследия ЮНЕСКО", "Городов-миллионников", "Столиц СНГ"], "answer": 1},
    {"q": "Что такое бэлеш?", "options": ["Большой пирог с мясом и картофелем", "Татарская колыбельная", "Вид ковра", "Головной убор"], "answer": 0},
    {"q": "Муса Джалиль — это...", "options": ["Татарский поэт-герой", "Татарский хан", "Архитектор Казани", "Спортсмен"], "answer": 0},
    {"q": "Как называется татарский кисломолочный напиток?", "options": ["Кумыс", "Катык", "Айран", "Тан"], "answer": 1},
    {"q": "Что означает слово 'Казань'?", "options": ["Белый город", "Котёл", "Золотой город", "Речной берег"], "answer": 1},
    {"q": "Какой цвет присутствует на флаге Татарстана?", "options": ["Синий, белый, красный", "Зелёный, белый, красный", "Жёлтый, зелёный, белый", "Зелёный, белый, жёлтый"], "answer": 1},
    {"q": "Что такое талкыш?", "options": ["Татарская сказка", "Сладкое блюдо из мёда и масла", "Народный инструмент", "Вид вышивки"], "answer": 1},
]

NEVER_HAVE_I_EVER = [
    "Я никогда не ел чак-чак прямо руками с блюда на чужой свадьбе 🍯",
    "Я никогда не притворялся что понимаю татарский, когда бабушка что-то говорила 👂",
    "Я никогда не засыпал на Сабантуе от жары ☀️",
    "Я никогда не говорил 'рәхмәт' вместо спасибо в русской компании и не смущался 😄",
    "Я никогда не называл эчпочмак просто 'треугольником' 🔺",
    "Я никогда не брал добавку губадии три раза подряд 🥧",
    "Я никогда не пел татарскую песню не зная слов но делая вид что знаю 🎵",
    "Я никогда не путал катык со сметаной и не признавался в этом 🥛",
    "Я никогда не говорил маме что уже поел чтобы не есть суп 🍲",
    "Я никогда не фотографировал еду у бабушки для инстаграма 📸",
    "Я никогда не танцевал татарский танец на свадьбе не зная движений 💃",
    "Я никогда не объяснял иностранцу что такое Татарстан больше 10 минут 🗺️",
    "Я никогда не выигрывал в борьбе на Сабантуе даже у младшего родственника 💪",
    "Я никогда не притворялся что мне не жарко в тюбетейке летом 🧢",
    "Я никогда не пробовал говорить на татарском и переходил на русский через два слова 😅",
    "Я никогда не называл Казань лучшим городом России в споре с москвичом 🏙️",
    "Я никогда не ел бэлеш на завтрак, обед и ужин в один день 🥧",
    "Я никогда не делал вид что знаю все правила курэша (татарской борьбы) 🤼",
    "Я никогда не говорил гостям что сам приготовил, хотя готовила мама 👩‍🍳",
    "Я никогда не гордился Казанью как будто сам её построил 🕌",
]

# ══════════════════════════════════════════════════════════
# СОСТОЯНИЕ ИГР
# ══════════════════════════════════════════════════════════

quiz_sessions = {}   # chat_id -> {question, scores, used_questions, msg_id}
never_sessions = {}  # chat_id -> {statements, current_index, players}

# ══════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ══════════════════════════════════════════════════════════

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Викторина", callback_data="start_quiz"),
         InlineKeyboardButton("😄 Я никогда не...", callback_data="start_never")],
        [InlineKeyboardButton("🏆 Счёт", callback_data="scores"),
         InlineKeyboardButton("ℹ️ Как играть", callback_data="howto")],
    ])

# ══════════════════════════════════════════════════════════
# СТАРТ
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    name = update.effective_user.first_name
    text = (
        f"Сәлам, {name}! 🌙\n\n"
        "Добро пожаловать в *Татар Уены* — татарскую игру для компании!\n\n"
        "🧠 *Викторина* — вопросы про татарскую культуру. Кто первый ответит — получает очко!\n\n"
        "😄 *Я никогда не...* — классическая игра с татарским колоритом. Узнай кто из друзей самый настоящий татарин!\n\n"
        "Позови друзей в чат и начинайте 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════
# ВИКТОРИНА
# ══════════════════════════════════════════════════════════

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    if chat_id not in quiz_sessions:
        quiz_sessions[chat_id] = {"scores": {}, "used": []}

    await send_quiz_question(context, chat_id, query.message)

async def send_quiz_question(context, chat_id, message=None):
    session = quiz_sessions.get(chat_id, {"scores": {}, "used": []})
    available = [i for i in range(len(QUIZ_QUESTIONS)) if i not in session["used"]]

    if not available:
        # Все вопросы использованы — показываем итог
        scores = session["scores"]
        if scores:
            ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            result = "🏆 *Игра окончена! Результаты:*\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, score) in enumerate(ranking):
                medal = medals[i] if i < 3 else f"{i+1}."
                result += f"{medal} {name} — {score} очков\n"
        else:
            result = "Никто не ответил правильно 😅"

        quiz_sessions[chat_id] = {"scores": {}, "used": []}
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Играть снова", callback_data="start_quiz"),
                                    InlineKeyboardButton("🏠 Меню", callback_data="menu")]])
        if message:
            await message.reply_text(result, parse_mode="Markdown", reply_markup=kb)
        return

    idx = random.choice(available)
    q = QUIZ_QUESTIONS[idx]
    session["used"].append(idx)
    session["current"] = idx
    session["answered"] = False
    quiz_sessions[chat_id] = session

    buttons = []
    for i, opt in enumerate(q["options"]):
        buttons.append([InlineKeyboardButton(opt, callback_data=f"quiz_answer_{i}")])
    buttons.append([InlineKeyboardButton("⏭ Следующий вопрос", callback_data="quiz_next")])

    text = f"❓ *Вопрос {len(session['used'])}/{len(QUIZ_QUESTIONS)}*\n\n{q['q']}"
    if message:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user
    answer_idx = int(query.data.split("_")[-1])

    session = quiz_sessions.get(chat_id)
    if not session or session.get("answered"):
        await query.answer("Уже ответили на этот вопрос!", show_alert=True)
        return

    q = QUIZ_QUESTIONS[session["current"]]
    name = user.first_name

    if answer_idx == q["answer"]:
        session["answered"] = True
        session["scores"][name] = session["scores"].get(name, 0) + 1
        quiz_sessions[chat_id] = session
        await query.answer(f"✅ Правильно! +1 очко, {name}!", show_alert=True)

        buttons = [[InlineKeyboardButton("⏭ Следующий вопрос", callback_data="quiz_next"),
                    InlineKeyboardButton("🏠 Меню", callback_data="menu")]]
        await query.edit_message_text(
            f"✅ *{name}* ответил правильно!\n\n"
            f"❓ {q['q']}\n\n"
            f"💡 Ответ: *{q['options'][q['answer']]}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await query.answer("❌ Неправильно, попробуй ещё!", show_alert=True)

async def quiz_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await send_quiz_question(context, chat_id, query.message)

# ══════════════════════════════════════════════════════════
# Я НИКОГДА НЕ
# ══════════════════════════════════════════════════════════

async def start_never(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    statements = random.sample(NEVER_HAVE_I_EVER, len(NEVER_HAVE_I_EVER))
    never_sessions[chat_id] = {"statements": statements, "index": 0}

    await send_never_statement(query.message, chat_id)

async def send_never_statement(message, chat_id):
    session = never_sessions.get(chat_id)
    if not session:
        return

    idx = session["index"]
    statements = session["statements"]

    if idx >= len(statements):
        never_sessions.pop(chat_id, None)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Играть снова", callback_data="start_never"),
                                    InlineKeyboardButton("🏠 Меню", callback_data="menu")]])
        await message.reply_text("😄 *Вот и всё! Надеемся было весело!*\n\nТеперь вы знаете друг друга лучше 😏",
                                  parse_mode="Markdown", reply_markup=kb)
        return

    stmt = statements[idx]
    num = idx + 1
    total = len(statements)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✋ Делал!", callback_data="never_did"),
         InlineKeyboardButton("😇 Не делал", callback_data="never_nodid")],
        [InlineKeyboardButton("⏭ Следующее", callback_data="never_next")],
    ])

    await message.reply_text(
        f"😄 *Я никогда не... ({num}/{total})*\n\n{stmt}\n\n_Нажмите ✋ если делали!_",
        parse_mode="Markdown", reply_markup=kb
    )

async def never_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    did = query.data == "never_did"

    if did:
        await query.answer(f"😂 {user.first_name} делал это!", show_alert=True)
    else:
        await query.answer(f"😇 {user.first_name} не делал!", show_alert=True)

async def never_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    session = never_sessions.get(chat_id)
    if session:
        session["index"] += 1
        never_sessions[chat_id] = session

    await send_never_statement(query.message, chat_id)

# ══════════════════════════════════════════════════════════
# ПРОЧЕЕ
# ══════════════════════════════════════════════════════════

async def show_scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    session = quiz_sessions.get(chat_id)
    if not session or not session.get("scores"):
        await query.message.reply_text("Пока нет очков! Начните викторину 🧠", reply_markup=main_keyboard())
        return

    scores = session["scores"]
    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Текущий счёт:*\n\n"
    for i, (name, score) in enumerate(ranking):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {name} — {score} очков\n"

    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def howto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ *Как играть:*\n\n"
        "1️⃣ Добавь бота в групповой чат с друзьями\n"
        "2️⃣ Нажми /start\n\n"
        "🧠 *Викторина:*\n"
        "Бот задаёт вопрос — кто первый нажмёт правильный ответ, получает очко. Побеждает тот, у кого больше очков!\n\n"
        "😄 *Я никогда не...:*\n"
        "Бот читает фразу — нажимайте ✋ если делали это. Смейтесь над друзьями!\n\n"
        "Зовите всех и начинайте! 🎉"
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Главное меню 👇", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^start_quiz$"))
    app.add_handler(CallbackQueryHandler(start_never, pattern="^start_never$"))
    app.add_handler(CallbackQueryHandler(quiz_answer, pattern="^quiz_answer_"))
    app.add_handler(CallbackQueryHandler(quiz_next, pattern="^quiz_next$"))
    app.add_handler(CallbackQueryHandler(never_reaction, pattern="^never_(did|nodid)$"))
    app.add_handler(CallbackQueryHandler(never_next, pattern="^never_next$"))
    app.add_handler(CallbackQueryHandler(show_scores, pattern="^scores$"))
    app.add_handler(CallbackQueryHandler(howto, pattern="^howto$"))
    app.add_handler(CallbackQueryHandler(menu, pattern="^menu$"))

    print("🎮 Татар Уены бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
