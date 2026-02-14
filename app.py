from flask import Flask, redirect, request, jsonify, render_template
from dotenv import load_dotenv
from bytez import Bytez
import os
import base64
import json
import traceback
from flask import render_template


import random
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client


from points_system import add_usage


from flask import session
from uuid import uuid4


import random





load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")



app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")


BYTEZ_API_KEY = os.getenv("BYTEZ_API_KEY")
if not BYTEZ_API_KEY:
    raise RuntimeError("Missing BYTEZ_API_KEY")
sdk = Bytez(BYTEZ_API_KEY)


# --------------------------------------------------------
# STATIC MODEL DEFINITIONS
# --------------------------------------------------------
MODELS = {

    # ---------------- TEXT ----------------
    "0-hero/Matter-0.1-Slim-7B-C": {
        "type": "Text",
        "icon": "https://bytez.com/favicon.ico",
        "label": "Matter 0.1 Slim 7B Chat"
    },
    "Qwen/Qwen3-4B": {
        "type": "Text",
        "icon": "https://qwen.ai/favicon.ico",
        "label": "Qwen 3-4B"
    },
    "Qwen/Qwen2-7B-Instruct": {
        "type": "Text",
        "icon": "https://qwen.ai/favicon.ico",
        "label": "Qwen 2 7B Instruct"
    },
    "microsoft/Phi-3-mini-4k-instruct": {
        "type": "Text",
        "icon": "https://learn.microsoft.com/favicon.ico",
        "label": "Microsoft Phi-3 Mini (4K)"
    },
    "openai/gpt-4o": {
        "type": "Text",
        "icon": "https://openai.com/favicon.ico",
        "label": "OpenAI GPT-4o"
    },
    "openai/gpt-4o-mini": {
        "type": "Text",
        "icon": "https://openai.com/favicon.ico",
        "label": "OpenAI GPT-4o Mini"
    },
    "anthropic/claude-3.5": {
        "type": "Text",
        "icon": "https://www.anthropic.com/favicon.ico",
        "label": "Anthropic Claude 3.5"
    },
    "google/gemini-1.5-flash": {
        "type": "Text",
        "icon": "https://www.google.com/favicon.ico",
        "label": "Google Gemini 1.5 Flash"
    },
    "cohere/command-r": {
        "type": "Text",
        "icon": "https://cohere.ai/favicon.ico",
        "label": "Cohere Command-R"
    },
    "mistral/mistral-small-latest": {
        "type": "Text",
        "icon": "https://mistral.ai/favicon.ico",
        "label": "Mistral Small Latest"
    },
    

    # ---------------- IMAGE ----------------
    "stabilityai/stable-diffusion-xl-base-1.0": {
        "type": "Image",
        "icon": "https://stability.ai/favicon.ico",
        "label": "Stable Diffusion XL Base"
    },
    "dreamlike-art/dreamlike-photoreal-2.0": {
        "type": "Image",
        "icon": "https://bytez.com/favicon.ico",
        "label": "Dreamlike Photoreal 2.0"
    },
    "openai/dall-e-3": {
        "type": "Image",
        "icon": "https://openai.com/favicon.ico",
        "label": "DALL·E 3"
    },
    "openai/dall-e-2": {
        "type": "Image",
        "icon": "https://openai.com/favicon.ico",
        "label": "DALL·E 2"
    },

    # ---------------- VIDEO ----------------
    "runway/gen-2": {
        "type": "Video",
        "icon": "https://runwayml.com/favicon.ico",
        "label": "Runway Gen-2"
    },
    "runway/gen-3": {
        "type": "Video",
        "icon": "https://runwayml.com/favicon.ico",
        "label": "Runway Gen-3"
    },
    "pika/pika-1.0": {
        "type": "Video",
        "icon": "https://pika.art/favicon.ico",
        "label": "Pika 1.0"
    },
    "meta-llama/Llama-3.2-11B-Vision-Instruct": {
        "type": "Video",
        "icon": "https://ai.meta.com/favicon.ico",
        "label": "LLaMA 3.2 Vision Instruct"
    }
}


# --------------------------------------------------------
# IMAGE NORMALIZER
# --------------------------------------------------------
def extract_image_url(output):
    if output is None:
        return ""

    if isinstance(output, str) and output.startswith("data:image"):
        return output

    if isinstance(output, (bytes, bytearray)):
        return "data:image/png;base64," + base64.b64encode(output).decode()

    if isinstance(output, str) and output.startswith(("http://", "https://")):
        return output

    if isinstance(output, list) and len(output) > 0:
        first = output[0]
        if isinstance(first, dict):
            if "url" in first and first["url"]:
                return first["url"]
            if "image_base64" in first and first["image_base64"]:
                return "data:image/png;base64," + first["image_base64"]
        for item in output:
            if isinstance(item, str) and item.startswith(("http", "data:image")):
                return item

    if isinstance(output, dict):
        if "url" in output and output["url"]:
            return output["url"]
        if "image_base64" in output and output["image_base64"]:
            return "data:image/png;base64," + output["image_base64"]
        if "content" in output and isinstance(output["content"], list):
            for c in output["content"]:
                if isinstance(c, dict) and "image_base64" in c:
                    return "data:image/png;base64," + c["image_base64"]
                if isinstance(c, str) and c.startswith(("http", "data:image")):
                    return c

    return ""


# --------------------------------------------------------
# VIDEO NORMALIZER
# --------------------------------------------------------
def extract_video_url(output):
    if output is None:
        return ""

    if isinstance(output, str) and output.startswith(("http://", "https://", "data:video")):
        return output

    if isinstance(output, dict):
        if "url" in output and output["url"]:
            return output["url"]
        if "video_base64" in output:
            return "data:video/mp4;base64," + output["video_base64"]
        if "output" in output:
            return extract_video_url(output["output"])
        if "result" in output:
            return extract_video_url(output["result"])

    if isinstance(output, list):
        for item in output:
            video = extract_video_url(item)
            if video:
                return video

    return ""


# --------------------------------------------------------
# TEXT NORMALIZER
# --------------------------------------------------------
def extract_text(output):
    if output is None:
        return ""

    if isinstance(output, str):
        return output

    if isinstance(output, dict):
        if "messages" in output:
            m = output["messages"]
            if isinstance(m, str):
                return m
            if isinstance(m, list):
                return "\n".join(str(i.get("content", i)) for i in m)

        if "content" in output:
            c = output["content"]
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "\n".join(str(i.get("text", i)) for i in c)

        if "output" in output:
            return extract_text(output["output"])

        if "result" in output:
            return extract_text(output["result"])

        return json.dumps(output)

    if isinstance(output, list):
        return "\n".join(str(i) for i in output)

    return str(output)











# --------------------------------------------------------
# ROUTES
# --------------------------------------------------------




load_dotenv()


# --------------------- BYTEZ SDK ---------------------
BYTEZ_API_KEY = os.getenv("BYTEZ_API_KEY")
if not BYTEZ_API_KEY:
    raise RuntimeError("Missing BYTEZ_API_KEY")
sdk = Bytez(BYTEZ_API_KEY)

# --------------------- SUPABASE ---------------------
# Project A — Whitelist
whitelist = create_client(
    os.getenv("WHITELIST_SUPABASE_URL"),
    os.getenv("WHITELIST_SUPABASE_KEY")
)

# Project B — Auth + Points
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# --------------------- ROUTES ---------------------
@app.route("/")
def home():
    daily_completed = session.pop("daily_completed", False)
    return render_template(
        "index.html",
        models=MODELS,
        daily_completed=daily_completed
    )



@app.route("/route", methods=["POST"])
def route_model_ai():
    try:
        data = request.get_json(force=True)
        model_id = data.get("model")
        prompt = data.get("prompt", "")

        if not model_id or model_id not in MODELS:
            return jsonify({"error": "Invalid model."}), 400

        email = session["user"]["email"]

        model_type = MODELS[model_id]["type"]
        model = sdk.model(model_id)

        # ---------------- COST CHECK ----------------

        usage_result = None

        if model_type == "Text":
            usage_result = add_usage(email, 1)

        elif model_type == "Image":
            usage_result = add_usage(email, 5)

        elif model_type == "Video":
            usage_result = add_usage(email, 10)
            
            print("USAGE RESULT:", usage_result)

        # 🚫 HARD LIMIT
        if not usage_result or not usage_result.get("allowed", True):
            return jsonify({"error": "Daily limit reached"}), 403

        daily_completed = usage_result.get("daily_completed", False)

        # ---------------- RUN MODEL ----------------

        if model_type == "Image":
            run_payload = prompt
        else:
            run_payload = [{"role": "user", "content": prompt}]

        res = model.run(run_payload)
        output = res[0] if isinstance(res, (tuple, list)) else getattr(res, "output", res)

        # ---------------- RESPONSE ----------------

        # IMAGE RESPONSE
        if model_type == "Image":
            img = extract_image_url(output)
            if not img:
                return jsonify({"error": "Empty image result"}), 500
            return jsonify({
                "response": img,
                "is_image": True,
                "is_video": False,
                "daily_completed": daily_completed
            })

        # VIDEO RESPONSE
        if model_type == "Video":
            video = extract_video_url(output)
            if not video:
                return jsonify({"error": "Empty video result"}), 500
            return jsonify({
                "response": video,
                "is_image": False,
                "is_video": True,
                "daily_completed": daily_completed
            })

        # TEXT RESPONSE
        text = extract_text(output)
        return jsonify({
            "response": text,
            "is_image": False,
            "is_video": False,
            "daily_completed": daily_completed
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500




@app.route("/admin")
def admin():
    if not is_admin():
        return "Forbidden", 403

    users = supabase.table("user_points") \
        .select("email, points") \
        .order("points", desc=True) \
        .execute()

    return render_template("admin.html", users=users.data)



@app.route("/login")
def login_page():
    return render_template("login.html")

from datetime import datetime, timezone

@app.route("/verify")
def verify_page():
    email = request.args.get("email")

    if not email:
        return redirect("/login")

    # Fetch latest OTP for this email
    row = (
        supabase.table("email_verifications")
        .select("expires_at")
        .eq("email", email)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    expires_at_ts = 0

    if row.data:
        expires_at = datetime.fromisoformat(
            row.data[0]["expires_at"].replace("Z", "+00:00")
        )
        expires_at_ts = int(expires_at.timestamp() * 1000)

    return render_template(
        "verify.html",
        email=email,
        expires_at_ts=expires_at_ts
    )


# --------------------- SEND OTP ---------------------
@app.route("/api/send-code", methods=["POST"])
def send_code():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    # Check whitelist
    wl = whitelist.table("emails").select("email").eq("email", email).execute()
    if not wl.data:
        return jsonify({"error": "Account not found"}), 404

    # Check if locked
    res = supabase.table("email_verifications") \
        .select("*") \
        .eq("email", email) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if res.data:
        record = res.data[0]
        locked_until = record.get("locked_until")
        if locked_until:
            locked_dt = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < locked_dt:
                secs = int((locked_dt - datetime.now(timezone.utc)).total_seconds())
                return jsonify({
                    "error": "Too many attempts, try again later",
                    "locked": True,
                    "retry_after": max(secs, 1)
                }), 429

    # Generate new code
    code = str(random.randint(100000, 999999))
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    # Cleanup old OTP (only expired ones, not locked)
    supabase.table("email_verifications") \
        .delete() \
        .eq("email", email) \
        .execute()

    # Save new OTP
    supabase.table("email_verifications").insert({
        "email": email,
        "code": code,
        "verified": False,
        "expires_at": expires_at
    }).execute()

    # ... rest of your email sending code ...


    # Send email
    html = f"""
    <div style="margin:0;padding:0;background-color:#0a0a0a;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center" style="padding:60px 20px;">
            <table width="620" style="background:#0d0d0d;border-radius:24px;">
              <tr>
                <td style="padding:60px;text-align:center;color:#fff;">
                  <img src="https://cookie-dex-official-waitlist.vercel.app/cookie-logo.png"
                       width="80" style="border-radius:22px;margin-bottom:25px;">
                  <h1 style="color:#ffcc66;">Your Verification Code</h1>
                  <div style="
                    font-size:44px;
                    letter-spacing:12px;
                    font-weight:800;
                    padding:20px 40px;
                    background:#000;
                    border-radius:16px;
                    margin:30px 0;
                  ">{code}</div>
                  <p style="color:#aaa;">Code expires in 10 minutes | if you have not requested this please ignore it</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Cookie DEX <{os.getenv('SMTP_USER')}>"
        msg["To"] = email
        msg["Subject"] = "Your Login Code"
        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        server.sendmail(msg["From"], email, msg.as_string())
        server.quit()
    except Exception as e:
        print("SMTP ERROR:", e)
        return jsonify({"error": "Failed to send email"}), 500

    return jsonify({"success": True})




def generate_public_name():
    return f"COOKIE-{random.randint(10000, 99999)}"


# --------------------- VERIFY OTP ---------------------

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.get_json()
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({"error": "Email and code required"}), 400

    # Fetch active OTP
    res = supabase.table("email_verifications") \
        .select("*") \
        .eq("email", email) \
        .eq("verified", False) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if not res.data:
        return jsonify({"error": "Invalid or expired code"}), 400

    record = res.data[0]

    # Parse expires_at safely as UTC
    expires_at = record.get("expires_at")
    if not expires_at:
        return jsonify({"error": "Invalid OTP record"}), 500

    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    # Expired
    if datetime.now(timezone.utc) > expires_dt:
        return jsonify({"error": "Code expired"}), 400

    # Locked
    locked_until = record.get("locked_until")
    if locked_until:
        locked_dt = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < locked_dt:
            secs = int((locked_dt - datetime.now(timezone.utc)).total_seconds())
            return jsonify({
                "error": "Too many attempts",
                "locked": True,
                "retry_after": max(secs, 1)
            }), 429

    # Wrong code
    if record["code"] != code:
        attempts = record.get("attempts", 0) + 1
        update = {"attempts": attempts}

        if attempts >= 3:
            update["locked_until"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        supabase.table("email_verifications") \
            .update(update) \
            .eq("email", email) \
            .execute()

        return jsonify({
            "error": f"Invalid code ({attempts}/3)",
            "locked": attempts >= 3
        }), 400

    # ✅ SUCCESS: mark verified
    supabase.table("email_verifications") \
        .update({"verified": True}) \
        .eq("email", email) \
        .execute()

    # Set session
    session["user"] = {
        "email": email,
        "is_admin": email.endswith("renzom851@gmail.com")
    }
    
    
        # Set session
    session["user"] = {
        "email": email,
        "is_admin": email.endswith("renzom851@gmail.com")
    }

    # Ensure user_points exists + public name
    existing = supabase.table("user_points") \
        .select("public_name") \
        .eq("email", email) \
        .execute()

    public_name = (
        existing.data[0]["public_name"]
        if existing.data and existing.data[0].get("public_name")
        else generate_public_name()
    )

    supabase.table("user_points").upsert(
        {
            "email": email,
            "public_name": public_name
        },
        on_conflict="email"
    ).execute()

    
    
    
    



    return jsonify({
        "success": True,
        "user": {"email": email}
    })
    

@app.route("/points")
def points():
    if not require_login():
        return redirect("/login")

    email = session["user"]["email"]

    res = supabase.table("user_points") \
        .select("points, daily_usage, daily_streak") \
        .eq("email", email) \
        .single() \
        .execute()

    if not res.data:
        return render_template(
            "points.html",
            points=0,
            daily_usage=0,
            daily_streak=0
        )

    return render_template(
        "points.html",
        points=res.data.get("points", 0),
        daily_usage=res.data.get("daily_usage", 0),
        daily_streak=res.data.get("daily_streak", 0)
    )




@app.route("/leaderboard")
def leaderboard():
    # Fetch top users
    users = supabase.table("user_points") \
        .select("email, public_name, points") \
        .order("points", desc=True) \
        .limit(100) \
        .execute()

    current_email = None
    current_public_name = None

    # If user is logged in
    if "user" in session:
        current_email = session["user"]["email"]

        me = supabase.table("user_points") \
            .select("public_name") \
            .eq("email", current_email) \
            .single() \
            .execute()

        if me.data:
            current_public_name = me.data["public_name"]

    return render_template(
        "leaderboard.html",
        users=users.data,
        current_email=current_email,
        current_public_name=current_public_name
    )


    

@app.route("/api/me")
def api_me():
    if "user" not in session:
        return jsonify({"user": None})
    return jsonify({"user": session["user"]})



def require_login():
    if "user" not in session:
        return False
    return True


def is_admin():
    return session.get("user", {}).get("is_admin", False)







if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

    
    
    




