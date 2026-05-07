from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import database, User, ChineseWord
from consts import WORDS, CARDS, SENTENCES
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

        if word_text == "":
            continue

        existing_word = ChineseWord.query.filter_by(chinese_text=word_text).first()
        if existing_word:
            continue

        new_word = ChineseWord(
            chinese_text=word_text,
            pinyin=pinyin,
            translation=translation
        )

        database.session.add(new_word)
        added_count += 1

    database.session.commit()
    print(f"Loaded {added_count} words")


def normalize_text(text):
    return " ".join((text or "").strip().lower().split())


LESSONS = [
    {"number": i, "title": f"Урок {i}", "description": "Материалы для этого урока будут добавлены позже."}
    for i in range(1, 31)
]


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Введите логин и пароль", "danger")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Такой пользователь уже существует", "danger")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )

        database.session.add(new_user)
        database.session.commit()

        flash("Регистрация успешна", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f"Добро пожаловать, {username}!", "success")
            return redirect(url_for("vocabulary"))

        flash("Неверный логин или пароль", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("home"))


@app.route("/vocabulary")
@login_required
def vocabulary():
    return render_template("vocabulary.html", lessons=LESSONS)


@app.route("/words")
@login_required
def words():
    words_list = ChineseWord.query.order_by(ChineseWord.id.asc()).all()
    return render_template("words.html", words=words_list)


@app.route("/practice")
@login_required
def practice():
    return render_template("practice.html")


@app.route("/practice/words")
@login_required
def practice_words():
    words = ChineseWord.query.all()

    if not words:
        flash("Добавьте слова", "warning")
        return redirect(url_for("words"))

    random_word = random.choice(words)

    return render_template(
        "practice_words.html",
        word=random_word,
        all_word_translations=[word.translation for word in words]
    )


@app.route("/practice/sentences")
@login_required
def practice_sentences():
    if not SENTENCES:
        flash("В списке нет предложений", "warning")
        return redirect(url_for("practice"))

    random_sentence = random.choice(SENTENCES)

    return render_template(
        "practice_sentences.html",
        sentence=random_sentence,
        all_sentence_translations=[item["translation_ru"] for item in SENTENCES]
    )


@app.route("/cards")
@login_required
def cards():
    return render_template("cards.html", cards_data=CARDS)


@app.route("/history")
@login_required
def history():
    return render_template("history.html")


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
        return jsonify({"correct": True, "message": "Правильно!"})

    return jsonify({
        "correct": False,
        "message": f"Неправильно. Ответ: {word.translation}"
    })


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
        return jsonify({"correct": True, "message": "Правильно!"})

    return jsonify({
        "correct": False,
        "message": f"Неправильно. Ответ: {sentence['translation_ru']}"
    })


@app.route("/api/words")
@login_required
def api_words():
    words = ChineseWord.query.all()
    return jsonify([
        {
            "id": word.id,
            "chinese": word.chinese_text,
            "pinyin": word.pinyin,
            "translation": word.translation
        }
        for word in words
    ])


if __name__ == "__main__":
    with app.app_context():
        database.create_all()
        sync_words_from_consts()

    app.run(host="127.0.0.1", port=8080, debug=True)