"""
main.py — FastAPI server entry point
WHY: This is the central hub — it receives Telegram messages,
     runs emotion analysis, stores results, and serves the frontend.
"""

import os
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from dotenv import load_dotenv

load_dotenv()

from database import create_tables, get_db, Message, Emotion, OverEvent
from emotion_engine import analyze_emotion, detect_spike, infer_over_number
from models import TelegramUpdate, EmotionScores, OverSummary, DashboardData

# ── Environment Variables ─────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Match start time (set this when a match begins — can be an API endpoint too)
MATCH_START_TIME = datetime.utcnow()  # Reset via /admin/start-match


# ── App Lifecycle ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    print("🚀 Crowd Pulse backend starting...")
    create_tables()  # Create DB tables if they don't exist
    print("✅ Database tables ready")
    yield
    print("👋 Crowd Pulse backend shutting down")


app = FastAPI(
    title="Crowd Pulse API",
    description="Real-time cricket emotion heatmap from Telegram",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS — Allow frontend (Vercel) to call this backend ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",              # Local dev
        "https://*.vercel.app",               # Vercel deployments
        os.getenv("FRONTEND_URL", "*"),       # Your specific Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════
# 🤖 TELEGRAM WEBHOOK ENDPOINT
# Telegram POSTs every group message here
# ════════════════════════════════════════════════════════════

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    WHY: Telegram sends a POST request to this URL every time
         someone sends a message in the group. We:
         1. Parse the message
         2. Save it to DB
         3. Run emotion analysis in the background (so we respond fast to Telegram)
    """
    try:
        body = await request.json()
        update = TelegramUpdate(**body)

        if not update.message or not update.message.text:
            return {"ok": True}  # Ignore non-text messages (stickers, etc.)

        msg = update.message
        username = msg.from_.username if msg.from_ else "anonymous"
        text = msg.text
        timestamp = datetime.utcfromtimestamp(msg.date)
        chat_id = str(msg.chat.id)
        telegram_msg_id = str(msg.message_id)

        # Skip duplicate messages
        existing = db.query(Message).filter(
            Message.telegram_id == telegram_msg_id
        ).first()
        if existing:
            return {"ok": True}

        # Save message to DB
        db_message = Message(
            telegram_id=telegram_msg_id,
            username=username,
            text=text,
            timestamp=timestamp,
            chat_id=chat_id,
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)

        print(f"📨 New message from @{username}: {text[:50]}")

        # Run emotion analysis in background (non-blocking)
        background_tasks.add_task(
            process_emotion,
            message_id=db_message.id,
            text=text,
            timestamp=timestamp
        )

        return {"ok": True}

    except Exception as e:
        print(f"[Webhook Error] {e}")
        return {"ok": True}  # Always return 200 to Telegram


# ════════════════════════════════════════════════════════════
# 🧠 BACKGROUND EMOTION PROCESSING
# ════════════════════════════════════════════════════════════

async def process_emotion(message_id: int, text: str, timestamp: datetime):
    """
    Runs in background after message is received.
    WHY: We don't want Telegram to timeout waiting for Gemini API.
         Background tasks let us respond instantly then process.
    """
    db = next(get_db())
    try:
        # Get emotion scores from Gemini
        scores = await analyze_emotion(text)

        over_number = infer_over_number(timestamp, MATCH_START_TIME)

        # Save individual emotion scores
        for emotion_type in ["joy", "tension", "anger", "surprise", "disbelief"]:
            emotion = Emotion(
                message_id=message_id,
                emotion_type=emotion_type,
                score=scores.get(emotion_type, 0.0),
                over_number=over_number,
            )
            db.add(emotion)
        db.commit()

        # Update the over-level aggregate
        await update_over_aggregate(over_number, db)

        print(f"✅ Emotions saved for message {message_id} | Over {over_number} | Dominant: {scores['dominant']}")

    except Exception as e:
        print(f"[EmotionProcessing Error] {e}")
    finally:
        db.close()


async def update_over_aggregate(over_number: int, db: Session):
    """
    Recalculate average emotions for an over after each new message.
    WHY: The frontend graph shows per-over averages, not per-message.
    """
    # Get all emotion scores for this over
    rows = db.query(Emotion).filter(Emotion.over_number == over_number).all()

    if not rows:
        return

    from collections import defaultdict
    sums = defaultdict(float)
    counts = defaultdict(int)

    for row in rows:
        sums[row.emotion_type] += row.score
        counts[row.emotion_type] += 1

    avgs = {e: (sums[e] / counts[e]) if counts[e] > 0 else 0
            for e in ["joy", "tension", "anger", "surprise", "disbelief"]}

    peak_emotion = max(avgs, key=avgs.get)
    message_count = db.query(Emotion.message_id).filter(
        Emotion.over_number == over_number
    ).distinct().count()

    # Check if previous over data exists for spike detection
    prev_over = db.query(OverEvent).filter(
        OverEvent.over_number == over_number - 1
    ).first()

    is_spike = False
    if prev_over:
        prev_scores = {
            "joy": prev_over.joy_avg,
            "tension": prev_over.tension_avg,
            "anger": prev_over.anger_avg,
            "surprise": prev_over.surprise_avg,
            "disbelief": prev_over.disbelief_avg,
        }
        is_spike = detect_spike(avgs, prev_scores)

    # Upsert (update or insert) the over event
    existing = db.query(OverEvent).filter(
        OverEvent.over_number == over_number
    ).first()

    if existing:
        existing.joy_avg = avgs["joy"]
        existing.tension_avg = avgs["tension"]
        existing.anger_avg = avgs["anger"]
        existing.surprise_avg = avgs["surprise"]
        existing.disbelief_avg = avgs["disbelief"]
        existing.peak_emotion = peak_emotion
        existing.message_count = message_count
        existing.is_spike = 1 if is_spike else 0
    else:
        over_event = OverEvent(
            over_number=over_number,
            peak_emotion=peak_emotion,
            joy_avg=avgs["joy"],
            tension_avg=avgs["tension"],
            anger_avg=avgs["anger"],
            surprise_avg=avgs["surprise"],
            disbelief_avg=avgs["disbelief"],
            message_count=message_count,
            is_spike=1 if is_spike else 0,
        )
        db.add(over_event)

    db.commit()


# ════════════════════════════════════════════════════════════
# 📊 DATA ENDPOINTS (Frontend calls these)
# ════════════════════════════════════════════════════════════

@app.get("/emotions", response_model=List[OverSummary])
def get_emotions(db: Session = Depends(get_db)):
    """
    Returns per-over emotion averages.
    Frontend uses this to draw the heatmap graph.
    """
    overs = db.query(OverEvent).order_by(OverEvent.over_number).all()
    return [
        OverSummary(
            over_number=o.over_number,
            peak_emotion=o.peak_emotion,
            joy_avg=round(o.joy_avg, 3),
            tension_avg=round(o.tension_avg, 3),
            anger_avg=round(o.anger_avg, 3),
            surprise_avg=round(o.surprise_avg, 3),
            disbelief_avg=round(o.disbelief_avg, 3),
            message_count=o.message_count,
            is_spike=bool(o.is_spike),
        )
        for o in overs
    ]


@app.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """
    Complete dashboard data in one API call.
    WHY: Reduces frontend API calls — one request gets everything.
    """
    overs = db.query(OverEvent).order_by(OverEvent.over_number).all()
    total_messages = db.query(Message).count()

    spike_overs = [o.over_number for o in overs if o.is_spike]

    # Find overall top emotion across the whole match
    emotion_totals = {"joy": 0, "tension": 0, "anger": 0, "surprise": 0, "disbelief": 0}
    for o in overs:
        emotion_totals["joy"] += o.joy_avg
        emotion_totals["tension"] += o.tension_avg
        emotion_totals["anger"] += o.anger_avg
        emotion_totals["surprise"] += o.surprise_avg
        emotion_totals["disbelief"] += o.disbelief_avg

    top_emotion = max(emotion_totals, key=emotion_totals.get) if overs else "joy"

    # Recent 10 messages
    recent_msgs = db.query(Message).order_by(desc(Message.timestamp)).limit(10).all()

    return {
        "overs": [
            {
                "over_number": o.over_number,
                "peak_emotion": o.peak_emotion,
                "joy_avg": round(o.joy_avg, 3),
                "tension_avg": round(o.tension_avg, 3),
                "anger_avg": round(o.anger_avg, 3),
                "surprise_avg": round(o.surprise_avg, 3),
                "disbelief_avg": round(o.disbelief_avg, 3),
                "message_count": o.message_count,
                "is_spike": bool(o.is_spike),
            }
            for o in overs
        ],
        "total_messages": total_messages,
        "top_emotion": top_emotion,
        "spike_overs": spike_overs,
        "recent_messages": [
            {
                "id": m.id,
                "username": m.username,
                "text": m.text[:100],
                "timestamp": m.timestamp.isoformat(),
            }
            for m in recent_msgs
        ],
    }


@app.get("/messages")
def get_messages(
    limit: int = 50,
    over: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get recent messages, optionally filtered by over number."""
    query = db.query(Message).order_by(desc(Message.timestamp))
    if over:
        # Filter messages whose emotions are tagged to this over
        msg_ids = db.query(Emotion.message_id).filter(
            Emotion.over_number == over
        ).distinct().subquery()
        query = query.filter(Message.id.in_(msg_ids))

    messages = query.limit(limit).all()
    return [
        {
            "id": m.id,
            "username": m.username,
            "text": m.text,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in messages
    ]


@app.get("/spikes")
def get_spike_moments(db: Session = Depends(get_db)):
    """
    Returns all spike/viral moments.
    WHY: These become the 'moment cards' on the dashboard.
    """
    spikes = db.query(OverEvent).filter(
        OverEvent.is_spike == 1
    ).order_by(desc(OverEvent.over_number)).all()

    return [
        {
            "over_number": s.over_number,
            "peak_emotion": s.peak_emotion,
            "message_count": s.message_count,
            "emotion_scores": {
                "joy": s.joy_avg,
                "tension": s.tension_avg,
                "anger": s.anger_avg,
                "surprise": s.surprise_avg,
                "disbelief": s.disbelief_avg,
            }
        }
        for s in spikes
    ]


# ════════════════════════════════════════════════════════════
# ⚙️ ADMIN / UTILITY ENDPOINTS
# ════════════════════════════════════════════════════════════

@app.post("/admin/start-match")
def start_match():
    """Reset match start time (call this when a match begins)."""
    global MATCH_START_TIME
    MATCH_START_TIME = datetime.utcnow()
    return {"message": "Match started!", "start_time": MATCH_START_TIME.isoformat()}


@app.post("/admin/set-webhook")
async def set_webhook(backend_url: str):
    """
    Registers our webhook URL with Telegram.
    WHY: Telegram needs to know WHERE to send messages.
         Call this once after deployment.
    
    Usage: POST /admin/set-webhook?backend_url=https://your-app.onrender.com
    """
    webhook_url = f"{backend_url}/telegram-webhook"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url}
        )
        data = resp.json()

    if data.get("ok"):
        return {"message": f"✅ Webhook set to: {webhook_url}"}
    else:
        raise HTTPException(status_code=400, detail=f"Telegram error: {data}")


@app.get("/admin/webhook-info")
async def get_webhook_info():
    """Check current webhook status."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{TELEGRAM_API}/getWebhookInfo")
    return resp.json()


@app.post("/admin/send-test-message")
async def send_test_message(chat_id: str, text: str = "🏏 Test from Crowd Pulse!"):
    """Send a test message to verify bot is working."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )
    return resp.json()


@app.delete("/admin/reset")
def reset_data(db: Session = Depends(get_db)):
    """⚠️ Delete all data (use only for testing)."""
    db.query(Emotion).delete()
    db.query(OverEvent).delete()
    db.query(Message).delete()
    db.commit()
    return {"message": "All data cleared"}


# ─────────────────────────────────────────────
# Health check — Render uses this to verify app is alive
# ─────────────────────────────────────────────
@app.get("/")
def health_check():
    return {
        "status": "🏏 Crowd Pulse is LIVE",
        "version": "1.0.0",
        "endpoints": ["/telegram-webhook", "/emotions", "/dashboard", "/spikes"]
    }


# ─────────────────────────────────────────────
# Local dev entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)