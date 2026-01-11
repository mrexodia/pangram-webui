import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g
from pangram import Pangram

app = Flask(__name__)

DATABASE = "pangram_history.db"

PANGRAM_API_KEY = os.getenv("PANGRAM_API_KEY")
if not PANGRAM_API_KEY:
    raise ValueError("PANGRAM_API_KEY is not set in environment variables.")

pangram = Pangram(api_key=PANGRAM_API_KEY)


def get_db():
    """Get database connection for current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database schema."""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                credits REAL NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                headline TEXT,
                prediction_short TEXT,
                fraction_ai REAL,
                fraction_ai_assisted REAL,
                fraction_human REAL
            )
        """)
        conn.commit()


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def calculate_credits(word_count: int) -> int:
    """Calculate credits (1 credit per 1000 words, minimum 1, rounded up)."""
    if word_count == 0:
        return 0
    return max(1, (word_count + 999) // 1000)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    word_count = count_words(text)
    credits = calculate_credits(word_count)

    include_dashboard_link = data.get("include_dashboard_link", False)
    request_data = {"text": text, "include_dashboard_link": include_dashboard_link}

    try:
        result = pangram.predict(text, public_dashboard_link=include_dashboard_link)

        # Save to database
        db = get_db()
        db.execute(
            """
            INSERT INTO analyses 
            (created_at, text, word_count, credits, request_json, response_json,
             headline, prediction_short, fraction_ai, fraction_ai_assisted, fraction_human)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now().isoformat(),
                text,
                word_count,
                credits,
                json.dumps(request_data),
                json.dumps(result),
                result.get("headline"),
                result.get("prediction_short"),
                result.get("fraction_ai", 0),
                result.get("fraction_ai_assisted", 0),
                result.get("fraction_human", 0),
            ),
        )
        db.commit()
        analysis_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        return jsonify(
            {
                "id": analysis_id,
                "word_count": word_count,
                "credits": credits,
                "headline": result.get("headline", ""),
                "prediction": result.get("prediction", ""),
                "prediction_short": result.get("prediction_short", ""),
                "fraction_ai": result.get("fraction_ai", 0),
                "fraction_ai_assisted": result.get("fraction_ai_assisted", 0),
                "fraction_human": result.get("fraction_human", 0),
                "num_ai_segments": result.get("num_ai_segments", 0),
                "num_ai_assisted_segments": result.get("num_ai_assisted_segments", 0),
                "num_human_segments": result.get("num_human_segments", 0),
                "windows": result.get("windows", []),
                "dashboard_link": result.get("dashboard_link"),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history")
def get_history():
    """Get list of past analyses for sidebar."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, created_at, word_count, credits, headline, prediction_short,
               fraction_ai, fraction_ai_assisted, fraction_human,
               substr(text, 1, 100) as text_preview
        FROM analyses
        ORDER BY created_at DESC
        LIMIT 100
    """
    ).fetchall()

    return jsonify(
        [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "word_count": row["word_count"],
                "credits": calculate_credits(row["word_count"]),
                "headline": row["headline"],
                "prediction_short": row["prediction_short"],
                "fraction_ai": row["fraction_ai"],
                "fraction_ai_assisted": row["fraction_ai_assisted"],
                "fraction_human": row["fraction_human"],
                "text_preview": row["text_preview"],
            }
            for row in rows
        ]
    )


@app.route("/history/<int:analysis_id>")
def get_analysis(analysis_id):
    """Get full analysis by ID."""
    db = get_db()
    row = db.execute(
        """
        SELECT id, created_at, text, word_count, credits, response_json
        FROM analyses WHERE id = ?
    """,
        (analysis_id,),
    ).fetchone()

    if not row:
        return jsonify({"error": "Analysis not found"}), 404

    result = json.loads(row["response_json"])

    return jsonify(
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "text": row["text"],
            "word_count": row["word_count"],
            "credits": row["credits"],
            "headline": result.get("headline", ""),
            "prediction": result.get("prediction", ""),
            "prediction_short": result.get("prediction_short", ""),
            "fraction_ai": result.get("fraction_ai", 0),
            "fraction_ai_assisted": result.get("fraction_ai_assisted", 0),
            "fraction_human": result.get("fraction_human", 0),
            "num_ai_segments": result.get("num_ai_segments", 0),
            "num_ai_assisted_segments": result.get("num_ai_assisted_segments", 0),
            "num_human_segments": result.get("num_human_segments", 0),
            "windows": result.get("windows", []),
            "dashboard_link": result.get("dashboard_link"),
        }
    )


@app.route("/stats")
def get_stats():
    """Get usage statistics."""
    db = get_db()
    row = db.execute(
        """
        SELECT 
            COUNT(*) as total_analyses,
            COALESCE(SUM(word_count), 0) as total_words
        FROM analyses
    """
    ).fetchone()

    # Calculate credits from word counts
    rows = db.execute("SELECT word_count FROM analyses").fetchall()
    total_credits = sum(calculate_credits(r["word_count"]) for r in rows)

    return jsonify(
        {
            "total_analyses": row["total_analyses"],
            "total_words": row["total_words"],
            "total_credits": total_credits,
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
