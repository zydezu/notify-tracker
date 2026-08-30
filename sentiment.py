#!/usr/bin/env python3
"""Daily sentiment breakdown for tracked notifications.

Reads the same SQLite DB that tracker.py writes to, scores each message's
text with a small built-in positive/negative word lexicon (no external
dependencies, so it works with the bare system Python this project already
assumes), and prints one sentiment percentage per day.

The percentage is 0-100 where 50% is neutral, >50% leans positive and <50%
leans negative for that day's messages.
"""
import re
import sys
from collections import defaultdict
from datetime import datetime

from rich.console import Console
from rich.table import Table

from tracker import init_db

BAR_WIDTH = 20
console = Console()

# Hand-picked lexicon covering common chat/notification language, including
# gen-z/gaming slang and text emoticons. Not a research-grade sentiment
# model -- good enough for a rough daily trend.
POSITIVE_WORDS = {
    "good", "great", "awesome", "amazing", "excellent", "fantastic", "nice",
    "love", "loved", "loves", "loving", "lovely", "adore", "adorable",
    "happy", "happiness", "glad", "excited", "excite", "exciting", "yay",
    "congrats", "congratulations", "thanks", "thank", "thankful", "grateful",
    "appreciate", "appreciated", "appreciation", "cool", "sweet", "perfect",
    "perfection", "beautiful", "gorgeous", "stunning", "cute", "wholesome",
    "wonderful", "marvelous", "delightful", "pleasant", "pleasing",
    "best", "better", "win", "wins", "won", "winning", "victory",
    "success", "successful", "succeed", "yes", "yep", "yup", "agree",
    "agreed", "welcome", "fun", "funny", "hilarious", "haha", "hehe",
    "lol", "lmao", "rofl", "lit", "hype", "hyped", "proud", "brilliant",
    "impressive", "impressed", "enjoy", "enjoyed", "enjoying", "enjoyable",
    "goodnight", "gg", "poggers", "pog",
    "yesss", "yess", "based", "slay", "slaps",
    "fire", "goated", "legend", "legendary", "iconic", "epic", "banger",
    "vibe", "vibing", "vibes", "w", "dub", "clutch", "carried", "goat",
    "solid", "smooth", "flawless", "genius", "smart", "clever", "kind",
    "kindness", "sweetheart", "sweetie", "darling", "hug", "hugs", "kiss",
    "kisses", "cheers", "blessed", "blessing", "lucky", "fortunate",
    "relax", "relaxing", "chill", "comfy", "cozy", "peaceful", "calm",
    "safe", "healed", "healing", "recovered", "recovery", "improve",
    "improved", "improvement", "progress", "deserve",
    "deserved", "rich", "wealthy", "healthy", "strong", "powerful",
    "efficient", "fast", "quick", "reliable", "trust", "trustworthy",
    "honest", "yesyes", "hooray", "woohoo", "woo",
    "yippee", "bravo", "kudos", "salute", "respect", "respected",
    ":)", ":-)", ":d", ":-d", "xd", "^^", "^_^", "n_n", "uwu", "owo",
    "😀", "😃", "😄", "😁", "😆", "😊", "🙂", "😍", "🥰", "😘",
    "😎", "🤩", "🎉", "🥳", "❤️", "❤", "💕", "💖", "💗", "💓", "💞",
    "👍", "👏", "🙌", "🔥", "✨", "💯", "🙏", "😇", "🤗", "😌", "☺️",
    "😻", "🏆", "🥇", "💪", "🌟", "⭐",
}

NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "horrific", "atrocious",
    "hate", "hated", "hates", "hating", "sad", "sadness", "sorry",
    "angry", "anger", "mad", "furious", "upset", "annoyed", "annoying",
    "irritated", "irritating", "frustrated", "frustrating", "frustration",
    "worst", "worse", "fail", "failed", "failing", "failure", "problem",
    "problems", "issue", "issues", "error", "errors", "broken", "break",
    "crash", "crashed", "crashing", "bug", "buggy", "glitch", "glitchy",
    "sucks", "sucked", "sucking", "stupid", "dumb", "idiot", "idiotic",
    "moronic", "pathetic", "lame", "cringe", "cringey", "mid", "trash",
    "garbage", "junk", "ugly", "gross", "disgusting", "nasty", "vile",
    "ugh", "argh", "wtf", "smh", "damn", "shit", "shitty", "fuck",
    "fucking", "fucked", "screwed", "no", "nope", "never", "cancel",
    "cancelled", "canceled", "cant", "can't", "cannot", "wont", "won't",
    "sick", "ill", "tired", "exhausted", "drained",
    "stressed", "stress", "stressful", "worried", "worry", "worrying",
    "afraid", "scared", "scary", "terrified", "fear", "fearful",
    "anxious", "anxiety", "nervous", "die", "died", "dying", "dead",
    "kill", "killed", "killing", "murder", "hurt", "hurts", "hurting",
    "pain", "painful", "suffer", "suffering", "lost", "lose", "losing",
    "loss", "regret", "regretted", "regrettable", "disappointed",
    "disappointing", "disappointment", "boring", "bored", "dull",
    "lonely", "loneliness", "alone", "abandoned", "rejected", "rejection",
    "betrayed", "betrayal", "toxic", "rude", "cruel", "harsh", "mean",
    "bully", "bullied", "bullying", "creepy", "weird", "awkward",
    "embarrassing", "embarrassed", "ashamed", "shame", "guilt", "guilty",
    "broke", "poor", "unfair", "unjust", "wrong", "mistake", "mistaken",
    "ruined", "ruin", "destroyed", "destroy", "wasted", "waste",
    "useless", "worthless", "hopeless", "helpless", "desperate",
    "desperation", "panic", "panicking", "grief", "grieving", "sorryy",
    "rip", "l", "ratio", "flop", "flopped", "mald", "malding", "yikes",
    "oof", "bruh", "meh", "ew", "eww", "cry", "crying", "cried", "sob",
    "sobbing", "tragic", "tragedy", "devastated", "devastating",
    "unbearable", "miserable", "misery", ":(", ":-(", ":'(", "d:",
    "😢", "😭", "😡", "😠", "🤬", "😞", "😔", "😟", "😰", "😨", "😱",
    "💀", "👎", "🙁", "☹️", "😩", "😫", "😖", "😣", "😓", "🤢", "🤮",
    "😤", "😒", "😑", "🖕",
}

NEGATORS = {"not", "no", "never", "cant", "can't", "cannot", "dont", "don't"}

# Try known ASCII emoticons first (colon/caret sequences), then word
# runs, then fall back to a single punctuation/symbol character at a time.
WORD_RE = re.compile(r":-?\)|:-?\(|:'\(|d:|\^_?\^|[a-z'_]+|[^\sa-zA-Z0-9]", re.UNICODE)


def score_message(text: str) -> int:
    """Return a rough integer sentiment score: +1 per positive cue, -1 per negative cue.

    A negator within the two preceding tokens flips the sign of a cue, so
    "not good" scores negative instead of positive.
    """
    tokens = WORD_RE.findall(text.lower())
    score = 0
    for i, tok in enumerate(tokens):
        polarity = 0
        if tok in POSITIVE_WORDS:
            polarity = 1
        elif tok in NEGATIVE_WORDS:
            polarity = -1
        else:
            continue

        window = tokens[max(0, i - 3):i]
        if any(w in NEGATORS for w in window):
            polarity = -polarity

        score += polarity
    return score


def local_date(iso_ts: str) -> str:
    return datetime.fromisoformat(iso_ts).astimezone().strftime("%Y-%m-%d")


def sentiment_bar(pct: float) -> str:
    filled = round(pct / 100 * BAR_WIDTH)
    color = "green" if pct > 55 else "red" if pct < 45 else "yellow"
    return f"[{color}]{'█' * filled}{'░' * (BAR_WIDTH - filled)}[/{color}]"


def analyze(app_filter: str | None = None) -> None:
    conn = init_db()
    if app_filter:
        rows = conn.execute(
            "SELECT message, received_at FROM notifications WHERE app_name LIKE ? OR sender LIKE ?",
            (f"%{app_filter}%", f"%{app_filter}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT message, received_at FROM notifications").fetchall()

    if not rows:
        console.print("No notifications logged yet.")
        return

    days: dict[str, list[int]] = defaultdict(list)
    for message, received_at in rows:
        days[local_date(received_at)].append(score_message(message))

    table = Table(title="Daily sentiment", title_style="bold", header_style="bold")
    table.add_column("date", style="cyan", no_wrap=True)
    table.add_column("msgs", justify="right")
    table.add_column("pos", justify="right", style="green")
    table.add_column("neg", justify="right", style="red")
    table.add_column("sentiment", justify="right")
    table.add_column("")

    for day in sorted(days):
        scores = days[day]
        total = len(scores)
        pos = sum(1 for s in scores if s > 0)
        neg = sum(1 for s in scores if s < 0)

        # Clamp each message's score to [-3, 3], average across the day,
        # then map the [-1, 1] average onto a 0-100% scale (50% = neutral).
        normalized = [max(-3, min(3, s)) / 3 for s in scores]
        avg = sum(normalized) / total
        sentiment_pct = (avg + 1) / 2 * 100

        table.add_row(
            day, str(total), str(pos), str(neg),
            f"{sentiment_pct:.1f}%", sentiment_bar(sentiment_pct),
        )

    console.print(table)


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else None)
