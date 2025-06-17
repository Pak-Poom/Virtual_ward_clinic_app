import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# Authenticate and connect to Google Sheets
def connect_to_gsheet(spreadsheet_name, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", 
             'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", 
             "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google"], scope)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(spreadsheet_name)  
    return spreadsheet.worksheet(sheet_name)  # Access specific sheet by name

# Google Sheet details
SPREADSHEET_NAME = 'ข้อมูลผู้ป่วย_Virtual_Ward_Clinic'
SHEET_NAME = 'Form_Records'

# Connect to the Google Sheet
sheet_by_name = connect_to_gsheet(SPREADSHEET_NAME, sheet_name=SHEET_NAME)

# st.set_page_config(page_title="Virtual Ward Clinic", layout="wide")
st.title("Virtual Ward Clinic")
st.write(":   ศูนย์หัวใจและหลอดเลือด -โรงพยาบาลจุฬาภรณ์")

# Read Data from Google Sheets
def read_data():
    data = sheet_by_name.get_all_records()  # Get all records from Google Sheet
    return pd.DataFrame(data)

# Add Data to Google Sheets
def add_data(row):
    sheet_by_name.append_row(row)  # Append the row to the Google Sheet

# Upload a file to Google Drive
def upload_to_drive(file_path, file_name, folder_id=None):
    scopes = ["https://www.googleapis.com/auth/drive.file"]
    credentials = service_account.Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
    drive_service = build('drive', 'v3', credentials=credentials)

    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]  # Optional: upload into a specific folder

    media = MediaFileUpload(file_path, mimetype='application/pdf')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Make the file public by setting sharing permission
    drive_service.permissions().create(
        fileId=uploaded_file['id'],
        body={'type': 'anyone', 'role': 'reader'},  # Anyone can view
    ).execute()

    return uploaded_file.get("webViewLink")  # Returns shareable view link

# Mainv iew form for data entry
st.write(" ")
st.subheader("แบบฟอร์มบันทึกข้อมูลผู้ป่วย : ")
with st.form(key="data_form", clear_on_submit=True):
    hn = st.text_input("เลขรหัสประจำตัวผู้ป่วย (HN)")
    bp = st.text_input("ค่าความดันโลหิต (BP)", placeholder="ตัวอย่างเช่น 120/80")
    hr = st.text_input("อัตราการเต้นของหัวใจ (HR)")
    oxygen = st.text_input("อัตราความเข้มข้นของออกซิเจนในเลือด (% O2)")
    uploaded_file = st.file_uploader("อัพโหลดไฟล์ ECG.pdf", type=["pdf"])

    # Submit button inside the form
    submitted = st.form_submit_button("ส่งข้อมูล")
    # Handle form submission
    if submitted:
        if all([hn, bp, hr, oxygen]):  # Basic validation to check if required fields are filled
            
            file_name = uploaded_file.name
            file_size = len(uploaded_file.getvalue())  # in bytes
            upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data_row = [file_name, f"{file_size // 1024} KB", upload_time]  # Save metadata only (all JSON-serializable)

            with open(file_name, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Upload to Google Drive
            drive_link = upload_to_drive(file_name, file_name=f'{file_name+upload_time}', folder_id="1zPAWPxFCz0emGFWx4nxxHVDwLSAqquOo")

            add_data([hn, bp, hr, oxygen, file_name, f"{file_size // 1024} KB", upload_time, drive_link])  # Append the Row and Drive Link to sheet
            os.remove(file_name)
            st.success("ข้อมูลได้ถูกทำการบันทึกเรียบร้อยแล้ว!")
        else:
            st.error("กรุณากรอกข้อมูลให้ครบถ้วนและถูกต้อง!!!")

with st.sidebar:
    # Display data in the sidebar view
    st.subheader("ประวัติการบันทึกข้อมูล :")
    df = read_data()
    
    if hn:
        filtered_df = df[df["HN"].astype(str) == hn]
        st.dataframe(filtered_df[['HN', 'BP', 'HR', 'O2_sat', 'Upload_Time']].reset_index().drop('index', axis=1), use_container_width=True)
    else:
        st.dataframe(df[['HN', 'BP', 'HR', 'O2_sat', 'Upload_Time']].head(0))
