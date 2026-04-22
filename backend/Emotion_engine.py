"""
emotion_engine.py — AI-powered emotion detection
WHY: This is the brain of Crowd Pulse. Every incoming Telegram message
     goes through here to get classified into cricket emotions.
"""

import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# ─────────────────────────────────────────────
# EMOJI → EMOTION MAP
# WHY: Cricket fans express more via emojis than words.
#      We pre-map common ones before sending to Gemini.
# ─────────────────────────────────────────────
EMOJI_EMOTION_MAP = {
    # Joy / Excitement
    "🎉": "joy", "🏏": "joy", "💥": "joy", "🔥": "joy",
    "😍": "joy", "🥳": "joy", "👏": "joy", "🙌": "joy",
    "😁": "joy", "🤩": "joy", "❤️": "joy", "💪": "joy",

    # Tension / Nervousness
    "😬": "tension", "😰": "tension", "🤞": "tension",
    "😨": "tension", "🫣": "tension", "🙏": "tension",
    "😮‍💨": "tension", "⏳": "tension",

    # Anger / Frustration
    "😤": "anger", "😡": "anger", "🤬": "anger",
    "💢": "anger", "😠": "anger", "🤦": "anger",
    "👎": "anger", "🗑️": "anger",

    # Surprise / Shock
    "😲": "surprise", "😱": "surprise", "🤯": "surprise",
    "😮": "surprise", "👀": "surprise", "‼️": "surprise",
    "⁉️": "surprise",

    # Disbelief
    "😑": "disbelief", "🙄": "disbelief", "😒": "disbelief",
    "🤔": "disbelief", "😶": "disbelief", "💀": "disbelief",
    "☠️": "disbelief",
}

EMOTION_CATEGORIES = ["joy", "tension", "anger", "surprise", "disbelief"]

# Spike detection threshold — if avg score jumps 40% vs last over, it's a spike
SPIKE_THRESHOLD = 0.40


def extract_emoji_signals(text: str) -> dict:
    """
    Count emojis in a message and convert to emotion hints.
    Returns a dict like {"joy": 3, "tension": 1}
    """
    signals = {e: 0 for e in EMOTION_CATEGORIES}
    for char in text:
        if char in EMOJI_EMOTION_MAP:
            signals[EMOJI_EMOTION_MAP[char]] += 1
    return signals


def clean_text(text: str) -> str:
    """Remove URLs, extra spaces for cleaner NLP input."""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def analyze_emotion(text: str) -> dict:
    """
    Main function: send message to Gemini, get back emotion scores.

    Returns:
        {
            "joy": 0.8,
            "tension": 0.1,
            "anger": 0.05,
            "surprise": 0.3,
            "disbelief": 0.1,
            "dominant": "joy"
        }
    """
    cleaned = clean_text(text)
    emoji_signals = extract_emoji_signals(text)

    # Build a rich prompt with cricket context
    prompt = f"""
You are an AI analyzing cricket fan emotions from Telegram group messages during a live IPL match.

Message: "{cleaned}"
Emoji signals detected: {json.dumps(emoji_signals)}

Analyze the emotional content and return ONLY a valid JSON object (no markdown, no explanation) with these exact keys:
{{
  "joy": <float 0-1>,
  "tension": <float 0-1>,
  "anger": <float 0-1>,
  "surprise": <float 0-1>,
  "disbelief": <float 0-1>
}}

Context for scoring:
- joy: excitement, celebration, happiness about match events (6s, wickets for own team)
- tension: nervousness, suspense, close match situations
- anger: frustration with poor play, umpire decisions, dropped catches
- surprise: unexpected events (last-ball six, hat-trick, superb catch)
- disbelief: shocking outcomes, can't-believe moments, sarcasm

Scores should sum close to 1.0. Be nuanced — a message can have multiple emotions.
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip any accidental markdown fences
        raw = raw.replace("```json", "").replace("```", "").strip()
        scores = json.loads(raw)

        # Validate all keys exist
        for key in EMOTION_CATEGORIES:
            if key not in scores:
                scores[key] = 0.0
            scores[key] = float(scores[key])

        # Boost scores where emojis strongly signal an emotion
        for emotion, count in emoji_signals.items():
            if count > 0:
                scores[emotion] = min(1.0, scores[emotion] + (count * 0.05))

        # Find dominant emotion
        dominant = max(scores, key=scores.get)
        scores["dominant"] = dominant

        return scores

    except Exception as e:
        print(f"[EmotionEngine] Gemini error: {e}")
        # Fallback: emoji-only scoring if Gemini fails
        total = sum(emoji_signals.values()) or 1
        fallback = {k: v / total for k, v in emoji_signals.items()}
        fallback["dominant"] = max(fallback, key=fallback.get)
        return fallback


def detect_spike(current_scores: dict, previous_scores: dict) -> bool:
    """
    Compare current over's avg emotion vs previous over.
    If any emotion jumps by SPIKE_THRESHOLD, it's a viral/spike moment.

    WHY: Emotion spikes = wickets, sixes, controversial decisions.
         These are the "moment cards" we want to highlight.
    """
    if not previous_scores:
        return False

    for emotion in EMOTION_CATEGORIES:
        curr = current_scores.get(emotion, 0)
        prev = previous_scores.get(emotion, 0)
        if (curr - prev) >= SPIKE_THRESHOLD:
            print(f"[SPIKE DETECTED] {emotion}: {prev:.2f} → {curr:.2f}")
            return True
    return False


def infer_over_number(timestamp, match_start_time=None) -> int:
    """
    Estimate cricket over number from message timestamp.
    WHY: We group emotions per over for the heatmap graph.

    Simplified: assume T20, 1 over ≈ 4 minutes.
    In production, you'd sync with a live cricket API.
    """
    if match_start_time is None:
        return 1  # Default if no match time set

    from datetime import datetime
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)

    elapsed_minutes = (timestamp - match_start_time).total_seconds() / 60
    over = max(1, min(20, int(elapsed_minutes / 4) + 1))
    return over