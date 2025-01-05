import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image
import pytesseract
import re

# Thai translation support
st.set_page_config(page_title="เครื่องมือวิเคราะห์ปริมาณปัสสาวะ", layout="wide")

# Function to generate time slots with 15-minute intervals
def generate_time_slots():
    start_time = datetime.strptime("00:00", "%H:%M")
    time_slots = [(start_time + timedelta(minutes=15 * i)).strftime("%H:%M") for i in range(96)]
    return time_slots

# Generate 15-minute interval time slots
time_slots = generate_time_slots()

# Mapping for normalization
ACTIVITY_MAPPING = {
    "First Morning Void": "ตื่นนอน (First Morning Void)",
    "Daytime Void": "ปัสสาวะในระหว่างวัน (Daytime Void)",
    "Bedtime Void": "ปัสสาวะก่อนนอน (Bedtime Void)",
    "Nighttime Void": "ปัสสาวะกลางคืน (Nighttime Void)"
}

def normalize_activity(activity_text):
    """
    Normalize activity text using predefined mapping.
    """
    for key, value in ACTIVITY_MAPPING.items():
        if key.lower() in activity_text.lower():
            return value
    return "Unknown Activity"

def calculate_metrics(total_urine_volume, nocturnal_urine_volume, max_voided_volume, actual_night_urinations, user_age):
    """
    Calculate all necessary metrics for frequency volume chart analysis.
    """
    total_urine_flag = total_urine_volume > 40 * 1000  # Assuming weight 1kg = 1000 ml

    npi = (nocturnal_urine_volume / total_urine_volume) * 100 if total_urine_volume > 0 else 0
    nocturnal_polyuria_flag = False
    if user_age >= 40 and user_age <= 65:
        nocturnal_polyuria_flag = npi > 20  # Threshold for NPI for ages 40-65
    else:
        nocturnal_polyuria_flag = npi > 33  # Default threshold for NPI

    diminished_bladder_capacity_flag = max_voided_volume < 200

    ni = nocturnal_urine_volume / max_voided_volume if max_voided_volume > 0 else 0
    pnv = ni - 1 if ni > 1 else 0  # Ensure PNV cannot be negative

    nbci = actual_night_urinations - pnv

    return {
        "total_urine_flag": total_urine_flag,
        "npi": npi,
        "nocturnal_polyuria_flag": nocturnal_polyuria_flag,
        "diminished_bladder_capacity_flag": diminished_bladder_capacity_flag,
        "ni": ni,
        "pnv": pnv,
        "nbci": nbci,
    }

def extract_table_from_image(uploaded_image):
    """
    Extract and process data from an uploaded image using OCR (Tesseract).
    """
    image = Image.open(uploaded_image)
    custom_config = r'--oem 3 --psm 6'  # Set Tesseract to assume a uniform block of text
    extracted_text = pytesseract.image_to_string(image, lang="eng", config=custom_config)

    # Process extracted text into structured rows
    rows = extracted_text.strip().split("\n")
    structured_data = []

    for row in rows:
        # Use regex to extract and split columns
        match = re.match(r"^(.*?)(\d{2}:\d{2})\s+(\d+)\s+(\d+)\s+([YN])$", row)
        if match:
            activity, time, intake, output, leak = match.groups()
            normalized_activity = normalize_activity(activity.strip())
            structured_data.append([normalized_activity, time.strip(), int(intake), int(output), leak.strip()])
        else:
            # Append empty row if data doesn't match expected format
            structured_data.append(["Unknown Activity", "None", 0, 0, "None"])

    # Convert structured data to DataFrame
    df = pd.DataFrame(structured_data, columns=["กิจกรรม (Activity)", "เวลา (Time)", "ดื่มน้ำ (Intake, ml)", "ปัสสาวะ (Output, ml)", "รั่ว (Leak, Y/N)"])
    return df

def main():
    # Header with FLOWMIND-RA branding
    st.markdown(
        """
        <style>
        .flowmind-header {
            font-size: 3rem;
            font-weight: bold;
        }
        .flowmind-ra {
            color: #2E8B8E;  /* Flow color for FLOW */
        }
        .flowmind-mind {
            color: #1A237E;  /* Mind color */
        }
        .flowmind-ra-orange {
            color: #E65100;  /* RA color */
        }
        </style>
        <div class="flowmind-header">
            <span class="flowmind-ra">FLOW</span><span class="flowmind-mind">MIND</span><span class="flowmind-ra-orange">-RA</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # App description
    st.header("Frequency Volume Chart Analysis Tool")
    st.write(
        "ใช้เครื่องมือนี้เพื่อวิเคราะห์ปริมาณปัสสาวะใน 24 ชั่วโมง, Nocturnal Polyuria, "
        "และความจุของกระเพาะปัสสาวะ\n\n"
        "This tool helps analyze 24-hour polyuria, nocturnal polyuria, and bladder capacity."
    )
    
    # Sidebar Input
    st.sidebar.header("📋 ข้อมูลผู้ป่วย (Patient Information)")
    st.sidebar.subheader("กรุณากรอกข้อมูลด้านล่าง (Enter your details below):")
    
    user_type = st.sidebar.selectbox(
        "เลือกรูปแบบการใช้งาน (Select User Type)",
        ["ผู้ป่วย (Patient)", "แพทย์ (Doctor)"]
    )
    user_age = st.sidebar.number_input("อายุผู้ใช้งาน (User Age)", min_value=0, step=1)

    if user_type == "ผู้ป่วย (Patient)":
        st.sidebar.write("**ตัวอย่างการกรอกข้อมูล (Example of Data Entry):**")
        demo_data = pd.DataFrame(
            columns=["กิจกรรม (Activity)", "เวลา (Time)", "ดื่มน้ำ (Intake, ml)", "ปัสสาวะ (Output, ml)", "รั่ว (Leak, Y/N)"],
            data=[
                ["ตื่นนอน (First Morning Void)", "06:00", 0, 150, "N"],
                ["ปัสสาวะในระหว่างวัน (Daytime Void)", "08:00", 250, 200, "N"],
                ["ปัสสาวะในระหว่างวัน (Daytime Void)", "12:00", 300, 250, "N"],
                ["ปัสสาวะในระหว่างวัน (Daytime Void)", "18:00", 400, 300, "N"],
                ["ปัสสาวะก่อนนอน (Bedtime Void)", "22:00", 200, 100, "N"],
                ["ปัสสาวะกลางคืน (Nighttime Void)", "02:00", 0, 150, "Y"],
            ],
        )
        st.sidebar.dataframe(demo_data)

        # Frequency Volume Chart Input
        st.subheader("📋 ตารางวิเคราะห์ปริมาณปัสสาวะ (Frequency Volume Chart)")
        st.write("กรอกข้อมูลเกี่ยวกับปริมาณการดื่มน้ำ การปัสสาวะ และช่วงเวลากลางคืน (Fill out details about fluid intake, urination, and nighttime data):")
        
        uploaded_image = st.file_uploader("อัปโหลดภาพตารางข้อมูล (Upload table image)", type=["jpg", "png", "jpeg"])
        extracted_data = None
        if uploaded_image:
            st.write("📤 กำลังประมวลผลภาพ (Processing uploaded image)...")
            try:
                extracted_data = extract_table_from_image(uploaded_image)
                st.write("✅ ข้อมูลที่ได้จากภาพ (Data extracted from image):")
                st.dataframe(extracted_data)
            except Exception as e:
                st.error(f"⚠️ ไม่สามารถประมวลผลภาพได้ (Failed to process image): {e}")

        with st.form("frequency_volume_chart_form"):
            activity_options = [
                "ตื่นนอน (First Morning Void)",
                "ปัสสาวะในระหว่างวัน (Daytime Void)",
                "ปัสสาวะก่อนนอน (Bedtime Void)",
                "ปัสสาวะกลางคืน (Nighttime Void)"
            ]
            if extracted_data is not None:
                data = extracted_data
            else:
                data = pd.DataFrame(
                    columns=["กิจกรรม (Activity)", "เวลา (Time)", "ดื่มน้ำ (Intake, ml)", "ปัสสาวะ (Output, ml)", "รั่ว (Leak, Y/N)"],
                    data=[
                        [activity_options[0], time_slots[0], 0, 150, "N"],
                        [activity_options[1], time_slots[1], 250, 200, "N"],
                        [activity_options[1], time_slots[2], 300, 250, "N"],
                        [activity_options[1], time_slots[3], 400, 300, "N"],
                        [activity_options[2], time_slots[4], 200, 100, "N"],
                        [activity_options[3], time_slots[5], 0, 150, "Y"],
                    ],
                )
            st.write("**แก้ไขข้อมูลในตารางด้านล่าง (Edit data in the table below):**")
            edited_data = st.data_editor(
                data,
                num_rows="dynamic",
                column_config={
                    "กิจกรรม (Activity)": st.column_config.SelectboxColumn(
                        options=activity_options,
                        label="กิจกรรม (Activity)"
                    ),
                    "เวลา (Time)": st.column_config.SelectboxColumn(
                        options=time_slots,
                        label="เวลา (Time)"
                    )
                }
            )
            submit_button = st.form_submit_button("วิเคราะห์ข้อมูล (Analyze Data)")

        if submit_button:
            # Summarize Data
            total_intake = edited_data["ดื่มน้ำ (Intake, ml)"].sum()
            total_output = edited_data["ปัสสาวะ (Output, ml)"].sum()
            
            nocturnal_output = edited_data[edited_data["กิจกรรม (Activity)"] == "ปัสสาวะกลางคืน (Nighttime Void)"]["ปัสสาวะ (Output, ml)"].sum()
            first_morning_void = edited_data[edited_data["กิจกรรม (Activity)"] == "ตื่นนอน (First Morning Void)"]["ปัสสาวะ (Output, ml)"].sum()
            nocturnal_output += first_morning_void  # Include first morning void in nocturnal urine volume
            max_voided_volume = edited_data["ปัสสาวะ (Output, ml)"].max()
            nocturnal_urinations = len(edited_data[edited_data["กิจกรรม (Activity)"] == "ปัสสาวะกลางคืน (Nighttime Void)"])

            metrics = calculate_metrics(total_output, nocturnal_output, max_voided_volume, nocturnal_urinations, user_age)

            st.subheader("📊 ผลลัพธ์ (Results):")
            st.write(f"**ปริมาณของเหลวที่ดื่มทั้งหมด (Total Fluid Intake):** {total_intake} ml")
            st.write(f"**ปริมาณปัสสาวะทั้งหมด (Total Urine Volume):** {total_output} ml")
            st.write(f"**ปริมาณปัสสาวะกลางคืน (Nocturnal Urine Volume):** {nocturnal_output} ml")
            st.write(f"**ปริมาณปัสสาวะสูงสุด (Max Voided Volume):** {max_voided_volume} ml")
            st.write(f"**จำนวนครั้งที่ปัสสาวะตอนกลางคืน (Nighttime Voids):** {nocturnal_urinations}")
            st.write(f"**ดัชนี Nocturnal Polyuria (NPI):** {metrics['npi']:.2f}%")
            st.write(f"**ดัชนี Nocturia (Ni):** {metrics['ni']:.2f}")
            st.write(f"**จำนวนครั้งที่คาดว่าจะปัสสาวะตอนกลางคืน (PNV):** {metrics['pnv']:.2f}")
            st.write(f"**ดัชนีความจุของกระเพาะปัสสาวะตอนกลางคืน (NBCI):** {metrics['nbci']:.2f}")

            if metrics["total_urine_flag"]:
                st.warning("⚠️ ตรวจพบ 24-Hour Polyuria: ปริมาณปัสสาวะทั้งหมดเกิน 40 ml/kg (Total Urine Volume > 40 ml/kg).")
            else:
                st.success("✅ ไม่พบ 24-Hour Polyuria (No 24-Hour Polyuria Detected).")

            if metrics["nocturnal_polyuria_flag"]:
                st.warning("⚠️ ตรวจพบ Nocturnal Polyuria.")
            else:
                st.success("✅ ไม่พบ Nocturnal Polyuria.")

            if metrics["diminished_bladder_capacity_flag"]:
                st.warning("⚠️ ตรวจพบความจุกระเพาะปัสสาวะลดลง (MVV < 200 ml).")
            else:
                st.success("✅ ความจุกระเพาะปัสสาวะปกติ (No Diminished Bladder Capacity Detected).")

            if metrics["nbci"] > 2:
                st.warning("⚠️ NBCI > 2: ปริมาตรความจุของกระเพาะปัสสาวะตอนกลางคืน น้อยกว่าปริมาตรความจุสูงสุดของกระเพาะปัสสาวะ และมีการปัสสาวะตอนกลางคืนมาก Associated with severe nocturia.")
            elif metrics["nbci"] > 1.3:
                st.warning("⚠️ NBCI > 1.3: ปริมาตรความจุของกระเพาะปัสสาวะตอนกลางคืน น้อยกว่าปริมาตรความจุสูงสุดของกระเพาะปัสสาวะ Related to diminished nocturnal bladder capacity.")
            elif metrics["nbci"] > 0:
                st.warning("⚠️ NBCI > 0: ถือว่าผู้ป่วยมีปริมาตรความจุของกระเพาะปัสสาวะในเวลากลางคืนน้อยกว่าความจุของกระเพาะปัสสาวะ (MVV) Indicates nocturia where each volume is less than MVV.")
            else:
                st.success("✅ NBCI ไม่พบความผิดปกติ ปริมาตรความจุของกระเพาะปัสสาวะตอนกลางคืน น้อยกว่าปริมาตรความจุสูงสุดของกระเพาะปัสสาวะ indicates no nocturia issues.")

            # Add links at the bottom
            st.markdown("---")
            st.markdown("👉 **Scan Add Line:** [https://line.me/R/ti/p/@415xpdzm](https://line.me/R/ti/p/@415xpdzm)")
            st.markdown("🌎 **เยี่ยมชม เว็ปไซต์ ดูข้อมูลยา:** [https://flowmind-ra.my.canva.site/](https://flowmind-ra.my.canva.site/)")
            st.write("🔧 พัฒนาเพื่อผู้สูงอายุ ให้สามารถใช้งานง่ายและแสดงผลลัพธ์แบบทันที (Developed for elderly users with simple inputs and real-time results).")
            st.write("👨‍💻 พัฒนาโดย: นพ. ลาภณวัส สันติธรรม ")

if __name__ == "__main__":
    main()