from datetime import datetime, timedelta
from db import supabase

DAILY_REQUIREMENT = 60
DAILY_LIMIT = 60


def add_usage(email, usage_amount):
    today = datetime.utcnow().date()

    user = supabase.table("user_points") \
        .select("*") \
        .eq("email", email) \
        .single() \
        .execute()

    if not user.data:
        return {"allowed": True, "daily_completed": False}

    data = user.data

    daily_usage = data.get("daily_usage", 0)
    last_usage_date = data.get("last_usage_date")
    daily_streak = data.get("daily_streak", 0)
    last_completed_date = data.get("last_completed_date")
    points = data.get("points", 0)

    # 🔄 Reset if new day
    if not last_usage_date or str(today) != last_usage_date:
        daily_usage = 0

    # 🚫 HARD LIMIT CHECK
    if daily_usage + usage_amount > DAILY_LIMIT:
        return {"allowed": False, "daily_completed": False}

    daily_usage += usage_amount

    update_data = {
        "daily_usage": daily_usage,
        "last_usage_date": str(today)
    }

    daily_completed_now = False

    # 🎉 Daily session completed
    if daily_usage >= DAILY_REQUIREMENT:
        if str(today) != last_completed_date:

            yesterday = today - timedelta(days=1)

            if last_completed_date == str(yesterday):
                daily_streak += 1
            else:
                daily_streak = 1

            points += 50

            update_data["daily_streak"] = daily_streak
            update_data["last_completed_date"] = str(today)
            update_data["points"] = points

            daily_completed_now = True

    supabase.table("user_points") \
        .update(update_data) \
        .eq("email", email) \
        .execute()

    return {
        "allowed": True,
        "daily_completed": daily_completed_now
    }
