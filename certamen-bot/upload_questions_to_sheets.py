import json
import time
import requests

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwk0qpdmiyMAIJEAsJvzS6tpHywNf9__OJJH_8nqOfHXq2lQH5SxJT1yT4tn-QDLRaznA/exec"
JSON_PATH = "src/data/questions.json"
BATCH_SIZE = 1000

def upload_questions():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total = len(questions)
    print(f"Total questions to upload: {total}")

    for i in range(0, total, BATCH_SIZE):
        batch = questions[i:i + BATCH_SIZE]
        payload = {
            "action": "importQuestions",
            "replace": (i == 0),
            "questions": batch
        }

        print(f"Uploading batch {i + 1} to {min(i + BATCH_SIZE, total)} / {total}...")
        try:
            res = requests.post(
                APPS_SCRIPT_URL,
                headers={"Content-Type": "text/plain;charset=utf-8"},
                data=json.dumps(payload),
                timeout=60
            )
            print(f"Status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            print(f"Error uploading batch {i}: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    upload_questions()
