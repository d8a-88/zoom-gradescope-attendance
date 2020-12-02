import os
import sys
import json
import tempfile
import pandas as pd
from otter.generate.token import APIClient

# create and fill in this file
import config


# set these 3 variableas
ZOOM_REGISTRATION_PATH = "data/zoom_registration.csv"
ATTENDANCE_LISTS_DIR = "data/zoom_attendance_data"
QUIZ_DATA_DIR = "data/gs_quiz_data"
COURSE_ID = config.COURSE_ID
ASSIGNMENT_ID = config.ASSIGNMENT_ID

# don't change these ones
SUBMISSIONS = {}
EVERYONE_GETS_CREDIT = "--EVERYONE--"


def main():
    registration = pd.read_csv(ZOOM_REGISTRATION_PATH)
    registration["Name"] = registration.apply(lambda row: row["First Name"] + " " + row["Last Name"], axis=1)

    everyone = []
    for i, fn in enumerate(sorted(os.listdir(ATTENDANCE_LISTS_DIR))):
        fp = os.path.join(ATTENDANCE_LISTS_DIR, fn)
        with open(fp) as f:
            attendees = f.readlines()

        if attendees[0].strip() == EVERYONE_GETS_CREDIT:
            everyone.append((i, fn))

        else:

            attendees = [att.strip() for att in attendees]

            registration[f"attended_in_person_{fn}"] = registration["Name"].isin(attendees)
            registration[f"attended_{fn}"] = registration[f"attended_in_person_{fn}"]
            
            quiz_fp = os.path.join(QUIZ_DATA_DIR, os.path.splitext(fn)[0] + ".csv")
            quiz_scores = pd.read_csv(quiz_fp)
            quiz_total_points = quiz_scores["Max Points"].max()

            def get_quiz_score(row):
                try:
                    return quiz_scores[quiz_scores["Email"] == row["Email"]].iloc[0]["Total Score"] / quiz_total_points
                except:
                    return 0

            registration[f"quiz_score_{fn}"] = registration.apply(get_quiz_score, axis=1)

            registration.loc[~registration[f"attended_in_person_{fn}"] & (registration[f"quiz_score_{fn}"] >= 0.8), f"attended_{fn}"] = True        

            for _, row in registration.iterrows():
                if row["Email"] not in SUBMISSIONS:
                    SUBMISSIONS[row["Email"]] = []
                SUBMISSIONS[row["Email"]].append({
                    "lecture_file": fn,
                    "attended": row[f"attended_{fn}"],
                    "attended_in_person": row[f"attended_in_person_{fn}"],
                    "quiz_score": row[f"quiz_score_{fn}"] if not pd.isna(row[f"quiz_score_{fn}"]) else 0,
                })

            if sum(registration[f"attended_{fn}"]) < len(attendees):
                print(f"Some attendees in {fn} not found in registrants")
                print([att for att in attendees if att not in registration["Name"].tolist()])
                print(registration)
                sys.exit(1)


    for i, fn in everyone:
        for stu in SUBMISSIONS:
            att = SUBMISSIONS[stu]
            att.insert(i, {
                "lecture_file": fn,
                "attended": True,
                "freebie": True,
            })

    with open("output.json", "w+") as f:
        json.dump(SUBMISSIONS, f, indent=2)

    token = APIClient.get_token()
    client = APIClient(token=token)
    del token


    for email, subm in SUBMISSIONS.items():
        with open("attendance.json", "w+") as f:
            json.dump(subm, f, indent=2)

        resp = client.upload_programming_submission(COURSE_ID, ASSIGNMENT_ID, email, ["attendance.json"])
        if resp.status_code != 200:
            print(f"Upload failed for {email}:\n{resp.text}")

        os.remove("attendance.json")
        
        print(f"Uploaded submission for {email}")


if __name__ == "__main__":
    main()
