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

QUIZ_QUESTION_COUNT = 10

# Частые ошибки GigaChat: башкорт/рус → татар
TATAR_SPELLING_FIXES = [
    (r"\bйок\b", "юк"), (r"\bЙок\b", "Юк"),
    (r"\bкоп\b", "күп"), (r"\bКоп\b", "Күп"),
    (r"\bменән\b", "белән"), (r"\bМенән\b", "Белән"),
    (r"\bкише\b", "кеше"), (r"\bКише\b", "Кеше"),
    (r"\bниндый\b", "нинди"), (r"\bНиндый\b", "Нинди"),
    (r"\bнинде\b", "нинди"), (r"\bНинде\b", "Нинди"),
    (r"\bук\b", "юк"), (r"\bУк\b", "Юк"),
    (r"\bшəhәр\b", "шәһәр"), (r"\bШəhәр\b", "Шәһәр"),
    (r"\bшәhәр\b", "шәһәр"), (r"\bШәhәр\b", "Шәһәр"),
    (r"\bһәhәр\b", "шәһәр"),
    (r"\bбашkорт\b", "башкорт"), (r"\bБашkорт\b", "Башкорт"),
    (r"\bбашkортча\b", "башкортча"),
    (r"\bтатарский\b", "татар"), (r"\bТатарский\b", "Татар"),
    (r"\bгород\b", "шәһәр"), (r"\bГород\b", "Шәһәр"),
    (r"\bчеловек\b", "кеше"), (r"\bЧеловек\b", "Кеше"),
    (r"\bязык\b", "тел"), (r"\bЯзык\b", "Тел"),
    (r"\bистория\b", "тарих"), (r"\bИстория\b", "Тарих"),
    (r"\bкультура\b", "мадәният"), (r"\bКультура\b", "Мәдәният"),
    (r"\bответ\b", "җавап"), (r"\bОтвет\b", "Җавап"),
    (r"\bвопрос\b", "сорау"), (r"\bВопрос\b", "Сорау"),
    (r"\bправильный\b", "дөрес"), (r"\bПравильный\b", "Дөрес"),
    (r"\bнарод\b", "халык"), (r"\bНарод\b", "Халык"),
    (r"\bпесня\b", "җыр"), (r"\bПесня\b", "Җыр"),
    (r"\bпраздник\b", "бәйрәм"), (r"\bПраздник\b", "Бәйрәм"),
    (r"\bрека\b", "елга"), (r"\bРека\b", "Елга"),
    (r"\bстолица\b", "башкала"), (r"\bСтолица\b", "Башкала"),
    (r"\bфлаг\b", "байрак"), (r"\bФлаг\b", "Байрак"),
    (r"\bэлект\b", "элек"), (r"\bЭлект\b", "Элек"),
    (r"\bбармын\b", "юк"), (r"\bБармын\b", "Юк"),
    (r"\bбарды\b", "булды"),
    (r"\bкайдадыр\b", "кайда"),
    (r"\bничего\b", "бернәрсә"),
]

# Русские/башкортские слова — если остались после правки, вопрос отбрасываем
FORBIDDEN_WORDS = {
    "город", "человек", "язык", "история", "культура", "ответ", "вопрос",
    "правильный", "правильно", "народ", "песня", "праздник", "река", "столица",
    "флаг", "который", "которая", "которое", "почему", "потому", "через",
    "между", "только", "можно", "нужно", "очень", "самый", "самая",
    "йок", "менән", "ниндый", "башҡорт", "башҡортча", "башkорт",
    "зәркүе", "зәркүрә", "урал-батыр",
}

TATAR_LANGUAGE_PROMPT = """
ДӨРЕС ТАТАР ТЕЛЕ (бик мөһим — här sözne tikşer):
- Саф татар теле: рус, башkорт, казах sözläre yok
- юk (NE йok), küp (NE kop), belän (NE menän), keşe (NE kişe), nindi (NE nindiy, NE ninde)
- şähär (NE gorod), tel (NE yazyk), tarix (NE istoriya), cawap (NE otvet), sorau (NE vopros), bayräm (NE prazdnik)
- Rus -ый/-ая/-ое sozle yok
- Variantlar bir-bersenä oxşamasın, ber genä dörüs cawap bulsin
- answer indeksı dörüs variantka turı kilsin
- explanation — qızıq fakt, dörüs tatarça, soravnı takrarlamasin
"""


def apply_tatar_corrections(text):
    """Автозамена типичных ошибок ИИ в татарском тексте."""
    import re
    if not text:
        return text
    result = text
    for pattern, replacement in TATAR_SPELLING_FIXES:
        result = re.sub(pattern, replacement, result)
    return result


def normalize_question(q):
    """Нормализует орфографию во всех полях вопроса."""
    normalized = dict(q)
    normalized["q"] = apply_tatar_corrections(q.get("q", ""))
    normalized["options"] = [apply_tatar_corrections(o) for o in q.get("options", [])]
    if q.get("explanation"):
        normalized["explanation"] = apply_tatar_corrections(q["explanation"])
    return normalized


def question_has_language_issues(q):
    """True если в вопросе остались явные языковые проблемы."""
    import re
    parts = [q.get("q", "")] + list(q.get("options", []))
    if q.get("explanation"):
        parts.append(q["explanation"])
    text = " ".join(parts).lower()

    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            return True

    # Русские прилагательные на -ый/-ая/-ое/-ие
    if re.search(r"\b\w+(ый|ая|ое|ые|ий|ая)\b", text):
        return True

    # Латинская h вместо татарской һ
    if re.search(r"[a-zA-Z]", text.replace("GigaChat", "")):
        if re.search(r"\bh[a-zа-яё]", text, re.IGNORECASE):
            return True

    return False


def gigachat_chat(token, messages, temperature=0.4, max_tokens=4000):
    """Общий запрос к GigaChat API."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    body = json.dumps({
        "model": "GigaChat-Max",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
        result = json.loads(r.read().decode())
    return result["choices"][0]["message"]["content"]


def proofread_questions_gigachat(token, questions):
    """Второй проход: GigaChat вычитывает и исправляет татарский."""
    if not questions:
        return questions

    payload = json.dumps(questions, ensure_ascii=False, indent=2)
    prompt = f"""Ты редактор татарского языка. Ниже JSON с вопросами викторины.

{payload}

Задача:
1. Исправь ВСЕ орфографические ошибки — только правильный татарский (кириллица)
2. Замени русизмы и башкортизмы: юк (НЕ йок), күп (НЕ коп), белән (НЕ менән), кеше (НЕ кише), нинди (НЕ ниндый)
3. Проверь что answer указывает на верный вариант в options — исправь если нет
4. Варианты не должны быть похожи, только один правильный ответ
5. explanation — интересный факт на правильном татарском

Не меняй структуру и количество ({len(questions)}). Верни ТОЛЬКО исправленный JSON-массив, без markdown."""

    try:
        text = gigachat_chat(token, [{"role": "user", "content": prompt}], temperature=0.2)
        print(f"📝 GigaChat вычитка: {text[:300]}...")
        fixed = parse_gigachat_questions(text)
        if len(fixed) >= len(questions) // 2:
            return fixed
    except Exception as e:
        print(f"⚠️ Ошибка вычитки: {e}")
    return questions


def parse_gigachat_questions(raw_text):
    """Парсит JSON-массив вопросов из ответа GigaChat."""
    import re

    text = raw_text.replace("```json", "").replace("```", "").strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    text = text[start:end]
    text = re.sub(r'«|»', '', text)

    try:
        questions = json.loads(text)
        if isinstance(questions, list):
            return [q for q in questions if _is_valid_question(q)]
    except json.JSONDecodeError:
        pass

    questions = []
    depth = 0
    obj_start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                try:
                    q = json.loads(text[obj_start:i + 1])
                    if _is_valid_question(q):
                        questions.append(q)
                except json.JSONDecodeError:
                    pass
                obj_start = None
    return questions


def _is_valid_question(q):
    return (
        isinstance(q, dict)
        and q.get("q")
        and isinstance(q.get("options"), list)
        and len(q["options"]) >= 2
        and isinstance(q.get("answer"), int)
        and 0 <= q["answer"] < len(q["options"])
    )


def pick_quiz_questions(questions):
    """Возвращает ровно QUIZ_QUESTION_COUNT валидных вопросов."""
    valid = [q for q in questions if _is_valid_question(q)]
    if len(valid) <= QUIZ_QUESTION_COUNT:
        return valid[:QUIZ_QUESTION_COUNT]
    return random.sample(valid, QUIZ_QUESTION_COUNT)


def polish_questions(token, questions):
    """Нормализация, вычитка и фильтрация по языку."""
    questions = [normalize_question(q) for q in questions]
    questions = proofread_questions_gigachat(token, questions)
    questions = [normalize_question(q) for q in questions]

    clean = [
        q for q in questions
        if _is_valid_question(q) and not question_has_language_issues(q)
    ]
    dropped = len(questions) - len(clean)
    if dropped:
        print(f"⚠️ Отфильтровано {dropped} вопросов с языковыми ошибками")
    return clean


def pad_questions_to_count(questions):
    """Добирает до QUIZ_QUESTION_COUNT из FALLBACK_QUIZ."""
    if len(questions) > QUIZ_QUESTION_COUNT:
        return questions[:QUIZ_QUESTION_COUNT]
    if len(questions) < QUIZ_QUESTION_COUNT:
        print(f"⚠️ Добираем до {QUIZ_QUESTION_COUNT} (сейчас {len(questions)})")
        existing = {q["q"] for q in questions}
        extras = [q for q in FALLBACK_QUIZ if q["q"] not in existing]
        random.shuffle(extras)
        for q in extras:
            if len(questions) >= QUIZ_QUESTION_COUNT:
                break
            questions.append(q)
    return questions[:QUIZ_QUESTION_COUNT]


def generate_questions_gigachat(used_topics=None):
    """Генерирует 10 уникальных вопросов через GigaChat"""
    token = get_gigachat_token()
    if not token:
        return None

    avoid = f"Не повторяй темы: {', '.join(used_topics)}." if used_topics else ""

    prompt = f"""Син — татар теле белгече һәм татар мәдәнияте тарихчысы. Татар телен камил беләсең.

Татар мәдәнияте, тарихы, теле, традицияләре буенча ТАМ ТУЛЫ {QUIZ_QUESTION_COUNT} викторина соравы төз.
{avoid}

КАТГЫЙ ТЫЮЛАР:
- Башкорт, чуваш, казах яки башка халыкларның мәдәниятен татар дип күрсәтмәскә
- Башкорт мифологиясе персонажлары (Зәркүрә, Урал-батыр һ.б.) кертмәскә
- Башкорт, казах яки рус сүзләре кушмыйча — саф татар теле генә
- Дөрес булмаган яки шөбһәле фактлар кертмәскә

{TATAR_LANGUAGE_PROMPT}
СОРАУ ТАЛӘПЛӘРЕ:
- Нәкъ {QUIZ_QUESTION_COUNT} сорау — азрак түгел, күпрәк түгел!
- Сораулар конкрет, бер генә дөрес җавабы булсын
- explanation: бу шәхес/вакыйга/күренеш турында кызыклы тарихи факт (ни өчен дөрес икәнен кабатламый)

Markdown юк. Башка текст юк. Чиста JSON гына, массив из ровно {QUIZ_QUESTION_COUNT} объектов:
[{{"q":"сорау?","options":["а","б","в","г"],"answer":0,"explanation":"Кызыклы факт."}}]"""

    try:
        text = gigachat_chat(token, [{"role": "user", "content": prompt}], temperature=0.4)
        print(f"📝 GigaChat ответ: {text[:500]}")
        questions = parse_gigachat_questions(text)
        if not questions:
            print("❌ Ни одного вопроса не распарсилось")
            return None

        questions = polish_questions(token, questions)
        questions = pad_questions_to_count(questions)
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
            questions = pick_quiz_questions(FALLBACK_QUIZ)
    else:
        questions = pick_quiz_questions(load_quiz_questions())

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
