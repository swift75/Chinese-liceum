from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from base import database, User, ChineseWord
from consts import WORDS, CARDS, SENTENCES, LESSONS
import random
import os

app = Flask(__name__)
app.secret_key = "super-secret-key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "chinese.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
database.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return database.session.get(User, int(user_id))

def sync_words_from_consts():
    added_count = 0
    for item in WORDS:
        word_text = item.get("word", "").strip()
        pinyin = item.get("pinyin", "").strip()
        translation = item.get("translation_ru", "").strip()
        if not word_text:
            continue
        existing_word = ChineseWord.query.filter_by(chinese_text=word_text).first()
        if existing_word:
            continue
        new_word = ChineseWord(chinese_text=word_text, pinyin=pinyin, translation=translation)
        database.session.add(new_word)
        added_count += 1
    database.session.commit()
    print(f"Loaded {added_count} words")

def normalize_text(text):
    return " ".join((text or "").strip().lower().split())

def add_points_to_user(user, add_rating=False):
    user.points = (getattr(user, "points", 0) or 0) + 1
    if add_rating:
        user.rating = (getattr(user, "rating", 0) or 0) + 1
    database.session.commit()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            return render_template("register.html", message="Заполни логин и пароль", message_type="danger")
        if len(password) < 5:
            return render_template("register.html", message="Пароль должен быть не короче 5 символов", message_type="danger")
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", message="Такой логин уже занят", message_type="danger")
        new_user = User(username=username, password_hash=generate_password_hash(password))
        database.session.add(new_user)
        database.session.commit()
        return redirect(url_for("login", message="Аккаунт создан. Теперь можно войти.", message_type="success"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            return render_template("login.html", message="Введите логин и пароль", message_type="danger")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("vocabulary"))
        return render_template("login.html", message="Неверный логин или пароль", message_type="danger")
    message = request.args.get("message")
    message_type = request.args.get("message_type")
    return render_template("login.html", message=message, message_type=message_type)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/vocabulary")
@login_required
def vocabulary():
    sorted_users = User.query.order_by(User.points.desc(), User.rating.desc(), User.id.asc()).all()
    user_rank = 0
    for index, user in enumerate(sorted_users, start=1):
        if user.id == current_user.id:
            user_rank = index
            break
    return render_template("vocabulary.html", lessons=LESSONS, user_rank=user_rank)

@app.route("/words")
@login_required
def words():
    words_list = ChineseWord.query.order_by(ChineseWord.id.asc()).all()
    return render_template("words.html", words=words_list)

@app.route("/download-hsk")
@login_required
def download_hsk():
    return send_file(os.path.join(BASE_DIR, "HSK.pdf"), as_attachment=True)

@app.route("/practice")
@login_required
def practice():
    return render_template("practice.html")

@app.route("/practice/words", methods=["GET", "POST"])
@login_required
def practice_words():
    words_list = ChineseWord.query.all()
    if not words_list:
        return render_template("practice.html", message="Добавьте слова", message_type="warning")

    def init_word():
        word = random.choice(words_list)
        correct_answer = word.translation

        wrong_answers = list(dict.fromkeys(
            item.translation for item in words_list if item.translation != correct_answer
        ))
        random.shuffle(wrong_answers)

        options = [correct_answer] + wrong_answers[:3]
        random.shuffle(options)

        session["practice_word_id"] = word.id
        session["practice_word_attempts"] = 2
        session["practice_word_finished"] = False
        session["practice_word_options"] = options
        session.pop("practice_word_last_answer", None)
        session.pop("practice_word_message", None)
        session.pop("practice_word_message_type", None)

        return word, options

    if request.args.get("new") == "1" or "practice_word_id" not in session:
        word, options = init_word()
    else:
        word = database.session.get(ChineseWord, session.get("practice_word_id"))
        if word is None:
            word, options = init_word()
        else:
            options = session.get("practice_word_options", [])
            if not options:
                word, options = init_word()

    if request.method == "POST":
        if session.get("practice_word_finished"):
            return redirect(url_for("practice_words"))

        selected_answer = request.form.get("answer", "")
        correct_answer = word.translation
        attempts_left = int(session.get("practice_word_attempts", 2))

        session["practice_word_last_answer"] = selected_answer

        if normalize_text(selected_answer) == normalize_text(correct_answer):
            first_try = attempts_left == 2
            session["practice_word_finished"] = True

            if first_try:
                add_points_to_user(current_user, add_rating=False)
                session["practice_word_message"] = f"Правильно! +1 очко • Всего очков: {current_user.points}"
            else:
                session["practice_word_message"] = "Правильно!"

            session["practice_word_message_type"] = "success"
        else:
            attempts_left -= 1
            session["practice_word_attempts"] = attempts_left

            if attempts_left > 0:
                session["practice_word_message"] = "Неправильно. Попробуй ещё раз."
                session["practice_word_message_type"] = "error"
            else:
                session["practice_word_finished"] = True
                session["practice_word_message"] = f"Неправильно. Правильный ответ: {correct_answer}"
                session["practice_word_message_type"] = "error"

        return redirect(url_for("practice_words"))

    message = session.pop("practice_word_message", None)
    message_type = session.pop("practice_word_message_type", None)
    last_answer = session.get("practice_word_last_answer")
    attempts_left = int(session.get("practice_word_attempts", 2))
    finished = bool(session.get("practice_word_finished"))

    return render_template(
        "practice_words.html",
        word=word,
        options=options,
        message=message,
        message_type=message_type,
        last_answer=last_answer,
        attempts_left=attempts_left,
        finished=finished
    )

@app.route("/practice/sentences", methods=["GET", "POST"])
@login_required
def practice_sentences():
    if not SENTENCES:
        return render_template("practice.html", message="В списке нет предложений", message_type="warning")

    def init_sentence():
        sentence = random.choice(SENTENCES)
        correct_answer = sentence["translation_ru"]

        wrong_answers = list(dict.fromkeys(
            item["translation_ru"] for item in SENTENCES if item["translation_ru"] != correct_answer
        ))
        random.shuffle(wrong_answers)

        options = [correct_answer] + wrong_answers[:3]
        random.shuffle(options)

        session["practice_sentence_id"] = sentence["id"]
        session["practice_sentence_attempts"] = 2
        session["practice_sentence_finished"] = False
        session["practice_sentence_options"] = options
        session.pop("practice_sentence_last_answer", None)
        session.pop("practice_sentence_message", None)
        session.pop("practice_sentence_message_type", None)

        return sentence, options

    if request.args.get("new") == "1" or "practice_sentence_id" not in session:
        sentence, options = init_sentence()
    else:
        sentence = next((item for item in SENTENCES if item["id"] == session.get("practice_sentence_id")), None)
        if sentence is None:
            sentence, options = init_sentence()
        else:
            options = session.get("practice_sentence_options", [])
            if not options:
                sentence, options = init_sentence()

    if request.method == "POST":
        if session.get("practice_sentence_finished"):
            return redirect(url_for("practice_sentences"))

        selected_answer = request.form.get("answer", "")
        correct_answer = sentence["translation_ru"]
        attempts_left = int(session.get("practice_sentence_attempts", 2))

        session["practice_sentence_last_answer"] = selected_answer

        if normalize_text(selected_answer) == normalize_text(correct_answer):
            first_try = attempts_left == 2
            session["practice_sentence_finished"] = True

            if first_try:
                add_points_to_user(current_user, add_rating=True)
                session["practice_sentence_message"] = f"Правильно! +1 очко • Всего очков: {current_user.points}"
            else:
                session["practice_sentence_message"] = "Правильно!"

            session["practice_sentence_message_type"] = "success"
        else:
            attempts_left -= 1
            session["practice_sentence_attempts"] = attempts_left

            if attempts_left > 0:
                session["practice_sentence_message"] = "Неправильно. Попробуй ещё раз."
                session["practice_sentence_message_type"] = "error"
            else:
                session["practice_sentence_finished"] = True
                session["practice_sentence_message"] = f"Неправильно. Правильный ответ: {correct_answer}"
                session["practice_sentence_message_type"] = "error"

        return redirect(url_for("practice_sentences"))

    message = session.pop("practice_sentence_message", None)
    message_type = session.pop("practice_sentence_message_type", None)
    last_answer = session.get("practice_sentence_last_answer")
    attempts_left = int(session.get("practice_sentence_attempts", 2))
    finished = bool(session.get("practice_sentence_finished"))

    return render_template(
        "practice_sentences.html",
        sentence=sentence,
        options=options,
        message=message,
        message_type=message_type,
        last_answer=last_answer,
        attempts_left=attempts_left,
        finished=finished
    )

@app.route("/cards")
@login_required
def cards():
    current_category = int(request.args.get("category", 0))
    current_index = int(request.args.get("index", 0))

    current_category = max(0, min(current_category, len(CARDS) - 1))
    entries = CARDS[current_category]["entries"]
    current_index = max(0, min(current_index, len(entries) - 1))

    return render_template(
        "cards.html",
        cards_data=CARDS,
        current_category=current_category,
        current_index=current_index
    )

@app.route("/history")
@login_required
def history():
    return render_template("history.html")

@app.route("/api/add_point", methods=["POST"])
@login_required
def add_point():
    add_points_to_user(current_user, add_rating=False)
    return jsonify({"ok": True, "points": current_user.points})

@app.route("/check_word_answer", methods=["POST"])
@login_required
def check_word_answer():
    data = request.get_json() or {}
    word_id = data.get("word_id")
    answer = normalize_text(data.get("answer", ""))
    word = database.session.get(ChineseWord, word_id)
    if not word:
        return jsonify({"correct": False, "message": "Слово не найдено"})
    correct_answer = normalize_text(word.translation)
    if answer == correct_answer:
        add_points_to_user(current_user, add_rating=True)
        return jsonify({"correct": True, "message": "Правильно!"})
    return jsonify({"correct": False, "message": f"Неправильно. Ответ: {word.translation}"})

@app.route("/check_sentence_answer", methods=["POST"])
@login_required
def check_sentence_answer():
    data = request.get_json() or {}
    sentence_id = data.get("sentence_id")
    answer = normalize_text(data.get("answer", ""))
    sentence = next((item for item in SENTENCES if item["id"] == sentence_id), None)
    if not sentence:
        return jsonify({"correct": False, "message": "Предложение не найдено"})
    correct_answer = normalize_text(sentence["translation_ru"])
    if answer == correct_answer:
        add_points_to_user(current_user, add_rating=True)
        return jsonify({"correct": True, "message": "Правильно!"})
    return jsonify({"correct": False, "message": f"Неправильно. Ответ: {sentence['translation_ru']}"})

@app.route("/api/words")
@login_required
def api_words():
    words = ChineseWord.query.all()
    return jsonify([
        {"id": word.id, "chinese": word.chinese_text, "pinyin": word.pinyin, "translation": word.translation}
        for word in words
    ])

if __name__ == "__main__":
    with app.app_context():
        database.create_all()
        sync_words_from_consts()
    app.run(host="127.0.0.1", port=8080, debug=True)