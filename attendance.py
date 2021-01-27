import os
import sys
import json
import glob
import tempfile
import pandas as pd
import numpy as np
from otter.generate.token import APIClient

# create and fill in this file
import config

# zoom participants export: https://csuf.screenstepslive.com/s/12867/m/59146/l/1219888-taking-attendance-in-a-zoom-meeting

# set these 3 variables
ATTENDANCE_CSVS_DIR = "data/zoom_sp21"
QUIZ_DATA_DIR = "data/gs_sp21"
COURSE_ID = config.COURSE_ID
ASSIGNMENT_ID = config.ASSIGNMENT_ID
ATTENDANCE_MINUTES_MIN = 60
QUIZ_SCORE_CUTOFF = 0.6

# don't change these ones
SUBMISSIONS = {}
EVERYONE_GETS_CREDIT = "--EVERYONE--"


def main():
    # registration = pd.read_csv(ZOOM_REGISTRATION_PATH)
    # registration["Name"] = registration.apply(lambda row: row["First Name"] + " " + row["Last Name"], axis=1)
    

    emails = set()
    quiz_dfs = []
    for fn in sorted(os.listdir(QUIZ_DATA_DIR)):
        fp = os.path.join(QUIZ_DATA_DIR, fn)
        df = pd.read_csv(fp)
        emails |= set(df["Email"])
        quiz_dfs.append(df)

    emails = list(sorted(emails))
    students = pd.DataFrame({"Email": emails})

    everyone = []
    for i, fn in enumerate(sorted(os.listdir(ATTENDANCE_CSVS_DIR))):
        fp = os.path.join(ATTENDANCE_CSVS_DIR, fn)
        with open(fp) as f:
            attendees = f.readlines()

        if attendees[0].strip() == EVERYONE_GETS_CREDIT:
            everyone.append((i, fn))

        else:

            zoom_attendees = pd.read_csv(fp)
            zoom_attendees = zoom_attendees[zoom_attendees["Total Duration (Minutes)"] >= ATTENDANCE_MINUTES_MIN]
            # attendee_emails = pd.read_csv(fp)["User Email"]
            # attendee_durations = pd.read_csv(fp)
            # attendees = [att.strip() for att in attendees]

            # attended = zoom_attendees["User Email"].isin(emails)

            # registration[f"attended_in_person_{fn}"] = registration["Name"].isin(attendees)
            # registration[f"attended_{fn}"] = registration[f"attended_in_person_{fn}"]
            
            # quiz_fp = os.path.join(QUIZ_DATA_DIR, os.path.splitext(fn)[0] + ".csv")
            quiz_scores = quiz_dfs[i]
            quiz_total_points = quiz_scores["Max Points"].max()

            def get_quiz_score(row):
                try:
                    row = quiz_scores[quiz_scores["Email"] == row["Email"]].iloc[0]
                    if row["Status"] == "Missing":
                        return np.nan
                    return row["Total Score"] / quiz_total_points
                except:
                    return np.nan

            # registration[f"quiz_score_{fn}"] = registration.apply(get_quiz_score, axis=1)
            lec_quiz_scores = students.apply(get_quiz_score, axis=1)
            students[f"quiz_score_{fn}"]  = lec_quiz_scores
            students[f"attended_in_person_{fn}"] = students["Email"].isin(zoom_attendees["User Email"])
            students[f"attended_{fn}"] = students[f"attended_in_person_{fn}"]
            students.loc[~students[f"attended_in_person_{fn}"] & (students[f"quiz_score_{fn}"] >= QUIZ_SCORE_CUTOFF), f"attended_{fn}"] = True
            students[f"quiz_score_{fn}"] = students[f"quiz_score_{fn}"].fillna("missing")

            # registration.loc[~registration[f"attended_in_person_{fn}"] & (registration[f"quiz_score_{fn}"] >= 0.8), f"attended_{fn}"] = True        

            for _, row in students.iterrows():
                if row["Email"] not in SUBMISSIONS:
                    SUBMISSIONS[row["Email"]] = []
                SUBMISSIONS[row["Email"]].append({
                    "lecture_file": fn,
                    "attended": row[f"attended_{fn}"],
                    "attended_in_person": row[f"attended_in_person_{fn}"],
                    "quiz_score": row[f"quiz_score_{fn}"],
                })

            if sum(students[f"attended_{fn}"]) < len(attendees):
                print(f"Some attendees in {fn} not found in registrants")
                print(zoom_attendees[~zoom_attendees["User Email"].isin(students["Email"])])
                print(students)
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
