#!/usr/bin/env python3
"""CLI tool to query the Pangram history database."""

import argparse
import json
import sqlite3

DATABASE = "pangram_history.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_credits(word_count: int) -> int:
    """Calculate credits (1 credit per 1000 words, minimum 1, rounded up)."""
    if word_count == 0:
        return 0
    return max(1, (word_count + 999) // 1000)


def cmd_stats(args):
    """Show usage statistics."""
    db = get_db()
    row = db.execute("""
        SELECT 
            COUNT(*) as total_analyses,
            COALESCE(SUM(word_count), 0) as total_words,
            MIN(created_at) as first_analysis,
            MAX(created_at) as last_analysis
        FROM analyses
    """).fetchone()

    # Calculate credits from word counts
    rows = db.execute("SELECT word_count FROM analyses").fetchall()
    total_credits = sum(calculate_credits(r["word_count"]) for r in rows)

    print("=== Pangram Usage Stats ===")
    print(f"Total analyses:  {row['total_analyses']}")
    print(f"Total words:     {row['total_words']:,}")
    print(f"Total credits:   {total_credits} (${total_credits * 0.05:.2f})")
    if row["first_analysis"]:
        print(f"First analysis:  {row['first_analysis']}")
        print(f"Last analysis:   {row['last_analysis']}")


def cmd_list(args):
    """List recent analyses."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, created_at, word_count, credits, prediction_short,
               fraction_ai, substr(text, 1, 60) as preview
        FROM analyses
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (args.limit,),
    ).fetchall()

    if not rows:
        print("No analyses found.")
        return

    print(
        f"{'ID':<5} {'Date':<20} {'Words':<7} {'Credits':<8} {'Result':<12} {'Preview'}"
    )
    print("-" * 100)
    for row in rows:
        date = row["created_at"][:19].replace("T", " ")
        preview = row["preview"].replace("\n", " ")
        if len(row["preview"]) >= 60:
            preview += "..."
        credits = calculate_credits(row["word_count"])
        print(
            f"{row['id']:<5} {date:<20} {row['word_count']:<7} {credits:<8} {row['prediction_short']:<12} {preview}"
        )


def cmd_show(args):
    """Show full details of an analysis."""
    db = get_db()
    row = db.execute(
        """
        SELECT * FROM analyses WHERE id = ?
    """,
        (args.id,),
    ).fetchone()

    if not row:
        print(f"Analysis {args.id} not found.")
        return

    print(f"=== Analysis #{row['id']} ===")
    print(f"Date:        {row['created_at']}")
    print(f"Words:       {row['word_count']}")
    print(f"Credits:     {calculate_credits(row['word_count'])}")
    print(f"Headline:    {row['headline']}")
    print(f"Prediction:  {row['prediction_short']}")
    print(f"AI:          {row['fraction_ai'] * 100:.1f}%")
    print(f"AI-Assisted: {row['fraction_ai_assisted'] * 100:.1f}%")
    print(f"Human:       {row['fraction_human'] * 100:.1f}%")
    print()
    print("=== Text ===")
    print(row["text"])

    if args.json:
        print()
        print("=== Response JSON ===")
        print(json.dumps(json.loads(row["response_json"]), indent=2))


def cmd_export(args):
    """Export analyses to JSON."""
    db = get_db()
    rows = db.execute("""
        SELECT id, created_at, text, word_count, credits,
               request_json, response_json
        FROM analyses
        ORDER BY created_at DESC
    """).fetchall()

    data = []
    for row in rows:
        data.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "text": row["text"],
                "word_count": row["word_count"],
                "credits": row["credits"],
                "request": json.loads(row["request_json"]),
                "response": json.loads(row["response_json"]),
            }
        )

    output = json.dumps(data, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Exported {len(data)} analyses to {args.output}")
    else:
        print(output)


def cmd_search(args):
    """Search analyses by text content."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, created_at, word_count, prediction_short,
               substr(text, 1, 80) as preview
        FROM analyses
        WHERE text LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (f"%{args.query}%", args.limit),
    ).fetchall()

    if not rows:
        print(f"No analyses matching '{args.query}'")
        return

    print(f"Found {len(rows)} matching analyses:")
    print()
    for row in rows:
        date = row["created_at"][:19].replace("T", " ")
        preview = row["preview"].replace("\n", " ")
        print(
            f"#{row['id']} [{row['prediction_short']}] {date} ({row['word_count']} words)"
        )
        print(f"  {preview}...")
        print()


def cmd_delete(args):
    """Delete an analysis."""
    db = get_db()
    row = db.execute("SELECT id FROM analyses WHERE id = ?", (args.id,)).fetchone()

    if not row:
        print(f"Analysis {args.id} not found.")
        return

    if not args.force:
        confirm = input(f"Delete analysis #{args.id}? [y/N] ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    db.execute("DELETE FROM analyses WHERE id = ?", (args.id,))
    db.commit()
    print(f"Deleted analysis #{args.id}")


def main():
    parser = argparse.ArgumentParser(description="Pangram history database CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stats
    subparsers.add_parser("stats", help="Show usage statistics")

    # list
    p_list = subparsers.add_parser("list", help="List recent analyses")
    p_list.add_argument("-n", "--limit", type=int, default=20, help="Number of results")

    # show
    p_show = subparsers.add_parser("show", help="Show full analysis details")
    p_show.add_argument("id", type=int, help="Analysis ID")
    p_show.add_argument("--json", action="store_true", help="Include raw JSON response")

    # export
    p_export = subparsers.add_parser("export", help="Export all analyses to JSON")
    p_export.add_argument("-o", "--output", help="Output file (default: stdout)")

    # search
    p_search = subparsers.add_parser("search", help="Search analyses by text")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument(
        "-n", "--limit", type=int, default=20, help="Number of results"
    )

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete an analysis")
    p_delete.add_argument("id", type=int, help="Analysis ID")
    p_delete.add_argument(
        "-f", "--force", action="store_true", help="Skip confirmation"
    )

    args = parser.parse_args()

    commands = {
        "stats": cmd_stats,
        "list": cmd_list,
        "show": cmd_show,
        "export": cmd_export,
        "search": cmd_search,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
