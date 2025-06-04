import os
import json
import datetime
import random
import io

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from EQ_logic import schedule_tasks
from flask_cors import CORS
from datetime import datetime as dt, timedelta
import os
import random
from flask import Flask, render_template

# Allow insecure transport for local dev (no HTTPS)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_fallback")

app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
    SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_sessions'),
    SESSION_FILE_THRESHOLD=100,
    SESSION_COOKIE_NAME='session'  # ✅ THIS is the critical fix
)

Session(app)


SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5050/oauth2callback")




@app.route('/')
def index():
    print("SESSION CONTENT:", dict(session))  # 👈 Debug print

    logged_in = 'credentials' in session

    gif_folder = os.path.join(app.root_path, "static", "gifs")
    gif_files = [f for f in os.listdir(gif_folder) if f.endswith(".gif")]
    selected_gif = random.choice(gif_files) if gif_files else None

    return render_template(
        'index.html',
        logged_in=logged_in,
        gif_filename=f"gifs/{selected_gif}" if selected_gif else None
    )

@app.route('/login')
def login():
    flow = Flow.from_client_config(
    json.loads(os.environ["GOOGLE_OAUTH_JSON"]),
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)
    authorization_url, state = flow.authorization_url()
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.context_processor
def inject_random():
    import random
    return dict(random=random.random)

@app.route('/oauth2callback')
def oauth2callback():
    # Debug prints (optional, remove in prod)
    print("Returned state:", request.args.get("state"))
    print("Expected state:", session.get("oauth_state"))

    if request.args.get('state') != session.get('oauth_state'):
        return "State mismatch — possible CSRF attack", 400

    # Rebuild flow WITHOUT setting state manually
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Complete token exchange
    flow.fetch_token(authorization_response=request.url)

    # Save credentials into session
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/generate_workouts')
def generate_workouts():
    runs = int(request.args.get("runs", 2))
    indoor = int(request.args.get("indoor", 2))

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    random.shuffle(days)
    selected = days[:runs + indoor]

    workouts = [{"day": d, "type": "Run"} for d in selected[:runs]] + \
               [{"day": d, "type": "Indoor Training"} for d in selected[runs:runs + indoor]]

    return jsonify({"workouts": workouts})


def generate_workouts_from_date_range(start_str, end_str, runCount, indoorCount):
    start_date = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(end_str, "%Y-%m-%d").date()
    days_range = [(start_date + datetime.timedelta(days=i)).strftime('%A') for i in range((end_date - start_date).days + 1)]

    random.shuffle(days_range)
    run_days = days_range[:runCount]
    indoor_days = days_range[runCount:runCount + indoorCount]

    return [{"type": "🏃 Run", "day": d} for d in run_days] + \
           [{"type": "🏋️ Functional", "day": d} for d in indoor_days]


def get_free_blocks(service, day, work_start, work_end, tz):
    start_of_day = tz.localize(datetime.datetime.combine(day, datetime.datetime.strptime(work_start, "%H:%M").time()))
    end_of_day = tz.localize(datetime.datetime.combine(day, datetime.datetime.strptime(work_end, "%H:%M").time()))

    response = service.freebusy().query(body={
        "timeMin": start_of_day.isoformat(),
        "timeMax": end_of_day.isoformat(),
        "timeZone": "Europe/Berlin",
        "items": [{"id": "primary"}]
    }).execute()

    busy_times = response['calendars']['primary']['busy']
    free_blocks = []

    last_end = start_of_day
    for event in busy_times:
        busy_start = datetime.datetime.fromisoformat(event['start'])
        busy_end = datetime.datetime.fromisoformat(event['end'])

        if last_end < busy_start:
            free_blocks.append((last_end, busy_start))
        last_end = max(last_end, busy_end)

    if last_end < end_of_day:
        free_blocks.append((last_end, end_of_day))

    return free_blocks


@app.route('/schedule', methods=['POST'])
def schedule():
    if 'credentials' not in session:
        return 'User not logged in', 401

    creds = Credentials(**session['credentials'])
    data = request.get_json()

    events, warning = schedule_tasks(
        data["tasks"], creds, data["weekStart"], data["weekEnd"],
        {
            "urgent_important": data["urgentImportantHours"],
            "important_not_urgent": data["importantNotUrgentHours"],
            "not_important_urgent": data["notImportantUrgentHours"],
            "not_important_not_urgent": data["notUrgentNotImportantHours"]
        },
        {
            "urgent_important": data["urgentImportantDays"],
            "important_not_urgent": data["importantNotUrgentDays"],
            "not_important_urgent": data["notImportantUrgentDays"],
            "not_important_not_urgent": data["notUrgentNotImportantDays"]
        },
        data["runCount"], data["indoorCount"],
        data["workStart"], data["workEnd"],
        generate_workouts_from_date_range(
            data["weekStart"],
            data["weekEnd"],
            data["runCount"],
            data["indoorCount"]
        ),
        get_free_blocks,
        data["breakfastStart"], data["breakfastDuration"],
        data["lunchStart"], data["lunchDuration"]
    )

    return jsonify({"status": "success", "warning": warning})


if __name__ == '__main__':
    app.run(debug=True, port=5050)
