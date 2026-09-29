# Survey Assignment Manager

A separate Streamlit app for cutting survey shifts from a Raw Weekday workbook. The OD collection dashboard is not part of this project.

## Run it locally

```powershell
cd D:\SURVEY_ASSIGNMENT_MANAGER
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

The app opens at http://localhost:8501.

## What you do in the app

1. Upload the client workbook. A sheet named like Raw Weekday is converted into the working Weekday grid. If that workbook also has a Weekday sheet with assignment numbers already filled in, you choose whether to start fresh or continue those numbers.
2. Leave the assignment name blank for the next number, or type a name such as `Aisha 1`.
3. Pick the block and suggest a full shift, a round trip, or the next piece of a person who changes buses.
4. Shorten or lengthen the preview, add a note if needed, then save.
5. Download `Weekday.xlsx` (the live grid plus a Made assignments sheet) and the Word packet.

Garage moves stay visible and are left blank unless **Include garage moves** is on.

## Settings

`.env` is optional. Defaults match a normal CATS shift: 6.5 to 9 hours, starting at Charlotte Transportation Center, with 10 to 90 minutes to change buses.

## Deploy on Streamlit Community Cloud

1. Push this folder to its own GitHub repository.
2. In Streamlit Community Cloud, create an app from that repo.
3. Main file: `app.py`.
4. Requirements file: `requirements.txt`.
5. No secrets are required.

Python 3.11 is set in `runtime.txt`.
