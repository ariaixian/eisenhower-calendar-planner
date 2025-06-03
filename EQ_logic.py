import json
import random
from datetime import datetime, timedelta
import pytz
from googleapiclient.discovery import build

def schedule_tasks(tasks, creds, week_start, week_end,
                   hoursPerQuadrant, daysPerQuadrant,
                   runCount, indoorCount,
                   work_start, work_end, workouts,
                   get_free_blocks_func,
                   breakfast_start, breakfast_duration,
                   lunch_start, lunch_duration):

    tz = pytz.timezone("Europe/Berlin")
    service = build("calendar", "v3", credentials=creds)

    # Build calendar dates
    start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    end_dt = datetime.strptime(week_end, "%Y-%m-%d")
    date_range = [(start_dt + timedelta(days=i)).date() for i in range((end_dt - start_dt).days + 1)]

    # Init calendar structure
    calendar = {
        str(day): {
            "slots": [],
            "free_at": tz.localize(datetime.combine(day, datetime.strptime(work_start, "%H:%M").time()))
        } for day in date_range
    }

    scheduled = []
    # --------- Step 0: Insert fixed breakfast and lunch ----------
    for day_key in calendar:
        day_date = datetime.strptime(day_key, "%Y-%m-%d").date()

        b_start = tz.localize(datetime.combine(day_date, datetime.strptime(breakfast_start, "%H:%M").time()))
        b_end = b_start + timedelta(minutes=breakfast_duration)

        l_start = tz.localize(datetime.combine(day_date, datetime.strptime(lunch_start, "%H:%M").time()))
        l_end = l_start + timedelta(minutes=lunch_duration)

        for start_time, end_time, label in [
            (b_start, b_end, "🍳 Breakfast"),
            (l_start, l_end, "🥗 Lunch")
        ]:
            event = {
                "summary": label,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "Europe/Berlin"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "Europe/Berlin"},
                "colorId": "9"
            }
            service.events().insert(calendarId="primary", body=event).execute()

        # Push back free_at if it was before lunch
        calendar[day_key]["free_at"] = max(calendar[day_key]["free_at"], l_end + timedelta(minutes=10))

    # --------- Step 1: Schedule Workouts ----------
    for workout in workouts:
        for day_key in calendar:
            if datetime.strptime(day_key, "%Y-%m-%d").strftime('%A') == workout["day"]:
                start_time = tz.localize(datetime.combine(
                    datetime.strptime(day_key, "%Y-%m-%d").date(),
                    datetime.strptime("06:30", "%H:%M").time()
                ))
                end_time = start_time + timedelta(hours=1)
                calendar[day_key]["free_at"] = end_time + timedelta(minutes=10)

                event = {
                    "summary": workout["type"],
                    "start": {"dateTime": start_time.isoformat(), "timeZone": "Europe/Berlin"},
                    "end": {"dateTime": end_time.isoformat(), "timeZone": "Europe/Berlin"},
                    "colorId": "11" if "Run" in workout["type"] else "6"
                }

                service.events().insert(calendarId="primary", body=event).execute()

                scheduled.append({
                    "name": workout["type"],
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration": 1,
                    "quadrant": "workout"
                })
                break

    # --------- Step 2: Sort Tasks by Priority ----------
    priority_order = [
        "urgent_important",
        "important_not_urgent",
        "not_important_urgent",
        "not_important_not_urgent"
    ]

    tasks.sort(key=lambda t: priority_order.index(t.get("quadrant", "not_important_not_urgent")))

    unscheduled = []

    # --------- Step 3: Schedule Tasks by Quadrant Priority ----------
    for task in tasks:
        name = task["name"]
        quadrant = task.get("quadrant", "unsorted")
        duration = hoursPerQuadrant.get(quadrant, 1)
        repetitions = daysPerQuadrant.get(quadrant, 1)

        eligible_days = sorted(calendar.keys())
        chosen_days = []

        day_index = 0
        while len(chosen_days) < repetitions and day_index < len(eligible_days):
            day = eligible_days[day_index]

            # ✅ get actual free blocks from Google Calendar
            free_blocks = get_free_blocks_func(
                service, datetime.strptime(day, "%Y-%m-%d"), work_start, work_end, tz
            )

            # Find a block big enough for this task
            scheduled_today = False
            for block_start, block_end in free_blocks:
                if (block_end - block_start).total_seconds() >= duration * 3600:
                    start_time = block_start
                    end_time = start_time + timedelta(hours=duration)
                    scheduled_today = True
                    break

            if scheduled_today:
                chosen_days.append((day, start_time, end_time))  # store times
            day_index += 1

        if len(chosen_days) < repetitions:
            unscheduled.append(task)
            continue

        for day, start_time, end_time in chosen_days:
            event = {
                'summary': name,
                'start': {'dateTime': start_time.isoformat(), 'timeZone': "Europe/Berlin"},
                'end': {'dateTime': end_time.isoformat(), 'timeZone': "Europe/Berlin"},
            }

            service.events().insert(calendarId='primary', body=event).execute()

            scheduled.append({
                "name": name,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration": duration,
                "quadrant": quadrant
            })


    # --------- Step 4: Return or Save Summary ----------
    print("🔧 Received task list:", tasks)
    print("📅 Week range:", week_start, "to", week_end)
    print("🧠 Workouts:", workouts)
    print("🕓 Work window:", work_start, "→", work_end)
    print("🍽️ Meals:", breakfast_start, breakfast_duration, lunch_start, lunch_duration)
    if unscheduled:
        task_names = ', '.join(t["name"] for t in unscheduled)
        warning = (
            f"⚠️ {len(unscheduled)} task(s) could not be scheduled due to time constraints:\n{task_names}"
        )
        return [], warning

    with open('scheduled_tasks.json', 'w') as f:
        json.dump(scheduled, f, indent=2)

    return scheduled, ""
