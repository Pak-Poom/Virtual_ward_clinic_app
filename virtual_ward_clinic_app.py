import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import time

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# === GOOGLE SHEETS AUTH ===
def connect_to_gsheet(spreadsheet_name, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds",
             'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file",
             "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google"], scope)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(spreadsheet_name)
    return spreadsheet.worksheet(sheet_name)

# === GOOGLE DRIVE AUTH (OAuth) ===
def upload_to_drive(file_path, file_name, folder_id=None):
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["google_oauth"]["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["google_oauth"]["client_id"],
        client_secret=st.secrets["google_oauth"]["client_secret"],
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    drive_service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, mimetype='application/pdf')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    drive_service.permissions().create(
        fileId=uploaded_file['id'],
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()

    return uploaded_file.get("webViewLink")

# === SETUP ===
SPREADSHEET_NAME = '1.1 ข้อมูลผู้ป่วย_Virtual_Ward_Clinic'
SHEET_NAME = 'Form_Records'
FOLDER_ID = st.secrets["google_oauth"]["folder_id"]

sheet_by_name = connect_to_gsheet(SPREADSHEET_NAME, SHEET_NAME)

st.title("Virtual Ward Clinic ⸝⸝⸝ 🚑")
st.write("ᯓᡣ𐭩 ศูนย์หัวใจและหลอดเลือด -โรงพยาบาลจุฬาภรณ์")
st.write("")

# === GOOGLE SHEETS HELPERS ===
def read_data():
    data = sheet_by_name.get_all_records()
    return pd.DataFrame(data)

def add_data(row):
    sheet_by_name.append_row(row)

preData_df = read_data()

# === FORM ===
st.subheader("แบบฟอร์มบันทึกข้อมูลผู้ป่วย : ")
with st.form(key="data_form", clear_on_submit=True):
    hn = st.text_input("เลขรหัสประจำตัวผู้ป่วย (HN)")
    bp = st.text_input("ค่าความดันโลหิต (BP)", placeholder="ตัวอย่าง 120/80")
    hr = st.text_input("อัตราการเต้นของหัวใจ (HR)", placeholder="ตัวอย่าง 72")
    oxygen = st.text_input("อัตราออกซิเจนในเลือด (% O2)", placeholder="ตัวอย่าง 98")

    col1, col2, col3 = st.columns([1, 1, 5])
    with col1:
        st.markdown("อาการ :")
    with col2:
        st.markdown("<p style='padding-top:5px'></p>", unsafe_allow_html=True)
        no_symptoms = st.checkbox("ไม่มี", key="no_symptoms")
    with col3:
        st.markdown("<p style='padding-top:5px'></p>", unsafe_allow_html=True)
        any_symptoms = st.checkbox("มีอาการ", key="any_symptoms")
    
    col1, col2, col3 = st.columns([1, 1, 5])
    with col3:
        identify_symptoms = st.text_area("ระบุอาการ (ถ้ามี) ;", placeholder="เช่น ... ใจสั่นเล็กน้อย, เจ็บแน่นหน้าอก, จุกที่ลิ้นปี่")
        
    uploaded_file = st.file_uploader("อัปโหลดไฟล์ ECG (PDF)", type=["pdf"])

    submitted = st.form_submit_button("ส่งข้อมูล")
    if submitted:
        with st.status("กำลังส่งข้อมูล...", expanded=True) as status:
            time.sleep(1)
    
            if all([hn, bp, hr, oxygen]):
                bangkok_time = datetime.now(ZoneInfo("Asia/Bangkok"))
                upload_time = bangkok_time.strftime("%Y-%m-%d %H:%M:%S")
    
                file_name = ""
                file_size = ""
                drive_link = ""
    
                # 🟢 Check if a file was uploaded
                if uploaded_file is not None and uploaded_file.size > 0:
                    file_name = uploaded_file.name
                    file_size = uploaded_file.size
    
                    # block duplicates
                    if not preData_df.empty and preData_df["File_Name"].astype(str).eq(str(file_name)).any():
                        status.update(label="❌ ไฟล์อัพโหลดซ้ำ", state="error")
                        st.stop()
    
                    safe_local_name = f"temp_{int(time.time())}_{file_name}"
                    with open(safe_local_name, "wb") as f:
                        f.write(uploaded_file.getbuffer())
    
                    drive_link = upload_to_drive(
                        file_path=safe_local_name,
                        file_name=f"{file_name}_{hn}_{upload_time}",
                        folder_id=FOLDER_ID
                    )
                    os.remove(safe_local_name)
    
                # symptom checks
                if no_symptoms and any_symptoms:
                    status.update(label="❌ กรุณาเลือกอาการเพียง 1 ตัวเลือก", state="error")
                    st.stop()
                if not no_symptoms and not any_symptoms:
                    status.update(label="❌ กรุณาเลือกอาการ", state="error")
                    st.stop()
    
                # Add row
                if no_symptoms:
                    add_data([hn, bp, hr, oxygen, "ไม่มีอาการ", "-", file_name, file_size, upload_time, drive_link])
                else:
                    add_data([hn, bp, hr, oxygen, "มีอาการ", identify_symptoms, file_name, file_size, upload_time, drive_link])
    
                status.update(label="✅ ส่งข้อมูลสำเร็จ!", state="complete")
                st.toast("🎉 ส่งข้อมูลเรียบร้อยแล้ว!")
            else:
                status.update(label="❌ กรุณากรอกข้อมูลให้ครบถ้วน", state="error")
                st.toast("⚠️ โปรดกรอกข้อมูลให้ครบถ้วน")

# === TABLE ===
st.subheader("ประวัติการบันทึกข้อมูล :")
df = read_data()
if hn:
    filtered_df = df[df["HN"].astype(str) == hn]
    st.dataframe(filtered_df[['HN', 'BP', 'HR', 'O2_sat', 'iden_symptoms', 'Upload_Time', 'File_Name']], use_container_width=True)
else:
    st.dataframe(df[['HN', 'BP', 'HR', 'O2_sat', 'iden_symptoms', 'Upload_Time', 'File_Name']].head(0))
