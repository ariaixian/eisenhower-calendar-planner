import unittest

from app import validate_schedule_request


def valid_payload():
    return {
        "tasks": [{"name": "Prepare experiment", "quadrant": "urgent_important"}],
        "weekStart": "2026-08-24",
        "weekEnd": "2026-08-30",
        "workStart": "09:00",
        "workEnd": "18:00",
        "urgentImportantDays": 2,
        "urgentImportantHours": 2,
        "importantNotUrgentDays": 2,
        "importantNotUrgentHours": 1.5,
        "notImportantUrgentDays": 1,
        "notImportantUrgentHours": 1,
        "notUrgentNotImportantDays": 1,
        "notUrgentNotImportantHours": 1,
        "runCount": 2,
        "indoorCount": 1,
        "breakfastStart": "08:00",
        "breakfastDuration": 30,
        "lunchStart": "13:00",
        "lunchDuration": 45,
    }


class ScheduleRequestValidationTests(unittest.TestCase):
    def test_accepts_a_complete_request(self):
        self.assertIsNone(validate_schedule_request(valid_payload()))

    def test_rejects_missing_fields(self):
        payload = valid_payload()
        del payload["weekEnd"]
        self.assertIn("Missing required fields", validate_schedule_request(payload))

    def test_rejects_unknown_quadrants(self):
        payload = valid_payload()
        payload["tasks"][0]["quadrant"] = "unknown"
        self.assertIn("valid Eisenhower quadrant", validate_schedule_request(payload))

    def test_rejects_invalid_date_ranges(self):
        payload = valid_payload()
        payload["weekEnd"] = "2026-09-30"
        self.assertIn("between 1 and 14 days", validate_schedule_request(payload))


if __name__ == "__main__":
    unittest.main()
