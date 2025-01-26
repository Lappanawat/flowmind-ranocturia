import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from PIL import Image
import pytesseract
import re

# ------------------------------------------------------------------------------------------
# Thai translation support
# ------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="เครื่องมือวิเคราะห์ปริมาณปัสสาวะ",
    layout="wide"
)

# ---------------------- (A) GLOBAL STYLING FOR 3D TABS & TABLE HEADERS --------------------
st.markdown(
    """
    <style>
    /* Make the tabs look like 3D buttons */
    div[role="tablist"] > div[role="tab"] {
        background-color: #f0f0f0;
        border: 2px solid #ccc;
        border-radius: 10px;
        box-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        margin-right: 5px;
        padding: 8px 16px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div[role="tablist"] > div[role="tab"]:hover {
        background-color: #ddd;
        box-shadow: inset 1px 1px 4px rgba(0,0,0,0.3);
        cursor: pointer;
    }
    div[role="tablist"] > div[role="tab"][aria-selected="true"] {
        background-color: #ffd700;
        border-color: #ffd700;
        box-shadow: 2px 2px 8px rgba(255, 215, 0, 0.6);
        color: #000;
    }

    /* Make the table header more colorful */
    [data-baseweb="data-table"] thead > tr > th {
        background-color: #d7ebfe !important; /* light blue background */
        color: #000000 !important;           /* black text */
        font-weight: bold !important;
        text-align: center !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------------------------------------
# 1. Utility Functions
# ------------------------------------------------------------------------------------------
def generate_time_slots():
    """
    Generate time slots in 15-minute increments for a 24-hour period.
    Returns a list of HH:MM strings from 00:00 to 23:59.
    """
    start_time = datetime.strptime("00:00", "%H:%M")
    return [
        (start_time + timedelta(minutes=15 * i)).strftime("%H:%M") 
        for i in range(96)
    ]

def parse_time_to_minutes(time_str):
    """
    Convert 'HH:MM' string to integer minutes from 00:00.
    e.g. '01:15' -> 75
    """
    hh, mm = time_str.split(':')
    return int(hh) * 60 + int(mm)

def normalize_activity(activity_text):
    """
    Map raw text to standard English FVC activity names.
    """
    ACTIVITY_MAPPING = {
        "First Morning Void": "First Morning Void",
        "Daytime Void": "Daytime Void",
        "Bedtime Void": "Bedtime Void",
        "Nighttime Void": "Nighttime Void"
    }
    for key, value in ACTIVITY_MAPPING.items():
        if key.lower() in activity_text.lower():
            return value
    return "Unknown Activity"

def calculate_metrics(
    total_urine_volume: float, 
    nocturnal_urine_volume: float, 
    max_voided_volume: float, 
    actual_night_urinations: int, 
    user_age: int
) -> dict:
    """
    Frequency volume chart metrics, unchanged logic.
    """
    # 1. 24-hour Polyuria check
    total_urine_flag = total_urine_volume > 40 * 1000  # 40k ml

    # 2. Nocturnal Polyuria Index
    if total_urine_volume > 0:
        npi = (nocturnal_urine_volume / total_urine_volume) * 100
    else:
        npi = 0

    if 40 <= user_age <= 65:
        nocturnal_polyuria_flag = (npi > 20)
    else:
        nocturnal_polyuria_flag = (npi > 33)

    # 3. Diminished Bladder Capacity
    diminished_bladder_capacity_flag = (max_voided_volume < 200)

    # 4. Nocturia Index & PNV
    if max_voided_volume > 0:
        ni = nocturnal_urine_volume / max_voided_volume
    else:
        ni = 0
    pnv = (ni - 1) if ni > 1 else 0

    # 5. NBCI
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
    OCR extraction for FVC table.
    """
    image = Image.open(uploaded_image)
    custom_config = r'--oem 3 --psm 6'
    extracted_text = pytesseract.image_to_string(
        image, 
        lang="eng", 
        config=custom_config
    )

    rows = extracted_text.strip().split("\n")
    structured_data = []
    pattern = r"^(.*?)(\d{2}:\d{2})\s+(\d+)\s+(\d+)\s+([YN])$"

    for row in rows:
        match = re.match(pattern, row)
        if match:
            activity, time_val, intake, output, leak = match.groups()
            normalized_act = normalize_activity(activity.strip())
            structured_data.append([
                normalized_act,
                time_val.strip(),
                int(intake),
                int(output),
                leak.strip()
            ])
        else:
            structured_data.append([
                "Unknown Activity",
                "None",
                0,
                0,
                "None"
            ])

    df = pd.DataFrame(
        structured_data,
        columns=[
            "กิจกรรม (Activity)",
            "เวลา (Time)",
            "ดื่มน้ำ (Intake, ml)",
            "ปัสสาวะ (Output, ml)",
            "รั่ว (Leak, Y/N)"
        ]
    )
    return df

# ------------------------------------------------------------------------------------------
# 2. Dashboard / Visualization Functions
# ------------------------------------------------------------------------------------------
def plot_dashboard(df: pd.DataFrame):
    """
    3D-like donut chart with Thai + English labels.
    """
    LEGEND_MAPPING = {
        "First Morning Void": "ตื่นนอน (First Morning Void)",
        "Daytime Void": "ปัสสาวะในระหว่างวัน (Daytime Void)",
        "Bedtime Void": "ปัสสาวะก่อนนอน (Bedtime Void)",
        "Nighttime Void": "ปัสสาวะกลางคืน (Nighttime Void)"
    }
    df_for_chart = df.copy()
    df_for_chart["กิจกรรม (Activity)"] = df_for_chart["กิจกรรม (Activity)"].apply(
        lambda x: LEGEND_MAPPING.get(x, "Unknown Activity")
    )

    grouped_data = df_for_chart.groupby("กิจกรรม (Activity)")["ปัสสาวะ (Output, ml)"].sum().reset_index()

    chart = (
        alt.Chart(grouped_data)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta(field="ปัสสาวะ (Output, ml)", type="quantitative"),
            color=alt.Color(
                field="กิจกรรม (Activity)",
                type="nominal",
                legend=alt.Legend(title="กิจกรรม (Activity)")
            ),
            tooltip=["กิจกรรม (Activity)", "ปัสสาวะ (Output, ml)"]
        )
        .properties(
            width=400,
            height=400,
            title="Voiding Volume by Activity (3D-like Donut)"
        )
    )
    st.altair_chart(chart, use_container_width=True)

# ------------------------------------------------------------------------------------------
# 3. Main App
# ------------------------------------------------------------------------------------------
def main():
    """
    Updated code:
      1) Time Wake Up, Time Go to Bed above the main table
      2) These times do not appear in main table
      3) If Nocturnal Polyuria & we find user intake in 4 hrs before bedtime => 
         "💧มีการทานน้ำในระยะเวลา 4 ชั่วโมงก่อนนอน"
      4) "เวลา (Time)" in the table uses a Selectbox of 15-min intervals from generate_time_slots()
    """

    # Branding
    st.markdown(
        """
        <style>
        .flowmind-header {
            font-size: 3rem;
            font-weight: bold;
        }
        .flowmind-ra {
            color: #2E8B8E;
        }
        .flowmind-mind {
            color: #1A237E;
        }
        .flowmind-ra-orange {
            color: #E65100;
        }
        </style>
        <div class="flowmind-header">
            <span class="flowmind-ra">FLOW</span><span class="flowmind-mind">MIND</span><span class="flowmind-ra-orange">-RA</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.header("Frequency Volume Chart Analysis Tool")
    st.write(
        "ใช้เครื่องมือนี้เพื่อวิเคราะห์ปริมาณปัสสาวะใน 24 ชั่วโมง, Nocturnal Polyuria, และความจุของกระเพาะปัสสาวะ\n\n"
        "This tool helps analyze 24-hour polyuria, nocturnal polyuria, and bladder capacity."
    )

    st.info(
        "ℹ️ **คำอธิบาย (Explanation)**\n\n"
        "ระบบใช้งานคำภาษาอังกฤษสำหรับกิจกรรม ดังนี้:\n\n"
        "- **First Morning Void** = ตื่นนอน\n"
        "- **Daytime Void** = ปัสสาวะในระหว่างวัน\n"
        "- **Bedtime Void** = ปัสสาวะก่อนนอน\n"
        "- **Nighttime Void** = ปัสสาวะกลางคืน\n\n"
        "หมายเหตุ: สามารถเลือกรายการภาษาอังกฤษ แต่ในความเป็นจริงคือ "
        "การบันทึกตารางปัสสาวะในภาษาไทย"
    )

    st.sidebar.header("📋 ข้อมูลผู้ป่วย (Patient Information)")
    st.sidebar.subheader("กรุณากรอกข้อมูลด้านล่าง (Enter your details below):")

    user_type = st.sidebar.selectbox(
        "เลือกรูปแบบการใช้งาน (Select User Type)",
        ["ผู้ป่วย (Patient)", "แพทย์ (Doctor)"]
    )
    user_age = st.sidebar.number_input("อายุผู้ใช้งาน (User Age)", min_value=0, step=1)

    if user_type == "ผู้ป่วย (Patient)":
        # We'll need time_slots for the "เวลา (Time)" column in the table
        full_time_slots = generate_time_slots()

        day_tabs = st.tabs(["Day1", "Day2", "Day3"])
        
        for idx, tab_label in enumerate(["Day1", "Day2", "Day3"], start=1):
            with day_tabs[idx-1]:
                st.markdown(f"## {tab_label}: Frequency Volume Chart")
                st.write(
                    f"เก็บข้อมูลของ {tab_label}. "
                    "คุณสามารถอัปโหลดภาพ หรือใส่ข้อมูลด้านล่าง"
                )

                with st.expander(f"ตัวอย่างข้อมูล {tab_label}"):
                    demo_data = pd.DataFrame(
                        columns=[
                            "กิจกรรม (Activity)",
                            "เวลา (Time)",
                            "ดื่มน้ำ (Intake, ml)",
                            "ปัสสาวะ (Output, ml)",
                            "รั่ว (Leak, Y/N)"
                        ],
                        data=[
                            ["First Morning Void", "06:00", 0, 150, "N"],
                            ["Daytime Void", "08:00", 250, 200, "N"],
                            ["Daytime Void", "12:00", 300, 250, "N"],
                            ["Daytime Void", "18:00", 400, 300, "N"],
                            ["Bedtime Void", "22:00", 200, 100, "N"],
                            ["Nighttime Void", "02:00", 0, 150, "Y"],
                        ]
                    )
                    st.dataframe(demo_data)

                # 1) New inputs: Time Wake Up, Time Go to Bed
                st.write("**กรุณากรอกเวลาตื่นนอน (Time Wake Up) และเวลาที่เข้านอน (Time Go to Bed):**")
                all_time_slots = generate_time_slots()  # 15-min increments for bedtime/wakeup
                wake_up_time = st.selectbox(
                    f"[{tab_label}] เวลาตื่นนอน (Time Wake Up)",
                    all_time_slots,
                    index=6  # default 06:00
                )
                bed_time = st.selectbox(
                    f"[{tab_label}] เวลาที่เข้านอน (Time Go to Bed)",
                    all_time_slots,
                    index=40  # default 22:00
                )

                # OCR File Uploader
                uploaded_image = st.file_uploader(
                    f"📤 อัปโหลดภาพตารางข้อมูลสำหรับ {tab_label}",
                    type=["jpg", "png", "jpeg"]
                )
                extracted_data = None
                if uploaded_image:
                    st.write("⌛ กำลังประมวลผลภาพ (Processing uploaded image)...")
                    try:
                        extracted_data = extract_table_from_image(uploaded_image)
                        st.write("✅ ข้อมูลที่ได้จากภาพ (Data extracted from image):")
                        st.dataframe(extracted_data)
                    except Exception as e:
                        st.error(f"⚠️ ไม่สามารถประมวลผลภาพได้ (Failed to process image): {e}")

                activity_options = [
                    "First Morning Void",
                    "Daytime Void",
                    "Bedtime Void",
                    "Nighttime Void"
                ]

                with st.form(f"frequency_volume_chart_form_{tab_label}"):
                    if extracted_data is not None:
                        data = extracted_data
                    else:
                        data = pd.DataFrame(
                            columns=[
                                "กิจกรรม (Activity)",
                                "เวลา (Time)",
                                "ดื่มน้ำ (Intake, ml)",
                                "ปัสสาวะ (Output, ml)",
                                "รั่ว (Leak, Y/N)"
                            ],
                            data=[
                                [activity_options[0], "06:00", 0, 150, "N"],
                                [activity_options[1], "08:00", 250, 200, "N"],
                                [activity_options[1], "12:00", 300, 250, "N"],
                                [activity_options[1], "18:00", 400, 300, "N"],
                                [activity_options[2], "22:00", 200, 100, "N"],
                                [activity_options[3], "02:00", 0, 150, "Y"],
                            ]
                        )

                    st.write(f"**ตารางบันทึกข้อมูล {tab_label}** (Edit data in the table below):")
                    edited_data = st.data_editor(
                        data,
                        num_rows="dynamic",
                        column_config={
                            "กิจกรรม (Activity)": st.column_config.SelectboxColumn(
                                options=activity_options,
                                label="กิจกรรม (Activity)"
                            ),
                            # 4) Now "เวลา (Time)" uses a 15-min increment selectbox
                            "เวลา (Time)": st.column_config.SelectboxColumn(
                                options=full_time_slots,
                                label="เวลา (Time)"
                            )
                        }
                    )
                    
                    submit_button = st.form_submit_button(f"วิเคราะห์ข้อมูล {tab_label} (Analyze Data)")

                # -------------------- AFTER CLICK ANALYZE -----------------------
                if submit_button:
                    st.subheader(f"📊 ผลลัพธ์ {tab_label} (Results)")
                    total_intake = edited_data["ดื่มน้ำ (Intake, ml)"].sum()
                    total_output = edited_data["ปัสสาวะ (Output, ml)"].sum()

                    # Combine nighttime + first morning void
                    nocturnal_output = edited_data[
                        edited_data["กิจกรรม (Activity)"] == "Nighttime Void"
                    ]["ปัสสาวะ (Output, ml)"].sum()
                    first_morning_void = edited_data[
                        edited_data["กิจกรรม (Activity)"] == "First Morning Void"
                    ]["ปัสสาวะ (Output, ml)"].sum()
                    nocturnal_output += first_morning_void

                    max_voided_volume = edited_data["ปัสสาวะ (Output, ml)"].max()
                    nocturnal_urinations = len(
                        edited_data[
                            edited_data["กิจกรรม (Activity)"] == "Nighttime Void"
                        ]
                    )

                    # Calculate metrics
                    metrics = calculate_metrics(
                        total_urine_volume=total_output, 
                        nocturnal_urine_volume=nocturnal_output, 
                        max_voided_volume=max_voided_volume, 
                        actual_night_urinations=nocturnal_urinations, 
                        user_age=user_age
                    )

                    st.write(f"**ปริมาณของเหลวที่ดื่มทั้งหมด (Total Fluid Intake):** {total_intake} ml")
                    st.write(f"**ปริมาณปัสสาวะทั้งหมด (Total Urine Volume):** {total_output} ml")
                    st.write(f"**ปริมาณปัสสาวะกลางคืน (Nocturnal Urine Volume):** {nocturnal_output} ml")
                    st.write(f"**ปริมาณปัสสาวะสูงสุด (Max Voided Volume):** {max_voided_volume} ml")
                    st.write(f"**จำนวนครั้งที่ปัสสาวะตอนกลางคืน (Nighttime Voids):** {nocturnal_urinations}")
                    st.write(f"**ดัชนี Nocturnal Polyuria (NPI):** {metrics['npi']:.2f}%")
                    st.write(f"**ดัชนี Nocturia (Ni):** {metrics['ni']:.2f}")
                    st.write(f"**จำนวนครั้งที่คาดว่าจะปัสสาวะตอนกลางคืน (PNV):** {metrics['pnv']:.2f}")
                    st.write(f"**ดัชนีความจุของกระเพาะปัสสาวะตอนกลางคืน (NBCI):** {metrics['nbci']:.2f}")

                    # Interpretations
                    # 24-hour polyuria check
                    if metrics["total_urine_flag"]:
                        st.warning(
                            "⚠️ ตรวจพบ 24-Hour Polyuria: ปริมาณปัสสาวะทั้งหมดเกิน 40 ml/kg "
                            "(Total Urine Volume > 40 ml/kg)."
                        )
                    else:
                        st.success("✅ ไม่พบ 24-Hour Polyuria (No 24-Hour Polyuria Detected).")

                    # Nocturnal polyuria check
                    if metrics["nocturnal_polyuria_flag"]:
                        st.warning("⚠️ ตรวจพบ Nocturnal Polyuria.")
                    else:
                        st.success("✅ ไม่พบ Nocturnal Polyuria.")

                    # ---------- Check if there's intake in 4 hrs before bedtime ----------
                    if metrics["nocturnal_polyuria_flag"]:
                        bed_time_mins = parse_time_to_minutes(bed_time)
                        cutoff = bed_time_mins - 240  # 4 hours => 240 minutes
                        if cutoff < 0:
                            # wrap around
                            cutoff += 1440

                        found_4hr_intake = False
                        for _, row in edited_data.iterrows():
                            if row["ดื่มน้ำ (Intake, ml)"] > 0:
                                t_str = row["เวลา (Time)"]
                                t_mins = parse_time_to_minutes(t_str)
                                if cutoff < bed_time_mins:
                                    # normal scenario
                                    if cutoff <= t_mins < bed_time_mins:
                                        found_4hr_intake = True
                                        break
                                else:
                                    # wrap scenario
                                    if t_mins >= cutoff or t_mins < bed_time_mins:
                                        found_4hr_intake = True
                                        break
                        if found_4hr_intake:
                            st.info("💧มีการทานน้ำในระยะเวลา 4 ชั่วโมงก่อนนอน")

                    # NBCI
                    if metrics["nbci"] > 2:
                        st.warning(
                            "⚠️ NBCI > 2: ปริมาตรความจุของกระเพาะปัสสาวะตอนกลางคืน "
                            "น้อยกว่าปริมาตรความจุสูงสุดของกระเพาะปัสสาวะ และมีการปัสสาวะตอนกลางคืนมาก "
                            "Associated with severe nocturia."
                        )
                    elif metrics["nbci"] > 1.3:
                        st.warning(
                            "⚠️ NBCI > 1.3: ปริมาตรความจุของกระเพาะปัสสาวะตอนกลางคืน "
                            "น้อยกว่าปริมาตรความจุสูงสุดของกระเพาะปัสสาวะ Related to diminished nocturnal "
                            "bladder capacity."
                        )
                    elif metrics["nbci"] > 0:
                        st.warning(
                            "⚠️ NBCI > 0: ⁉️สงสัยความจุกระเพาะปัสสาวะลดลง (Diminished Bladder Capacity suspected)."
                        )
                    else:
                        st.success(
                            "✅ ความจุกระเพาะปัสสาวะปกติ (No Diminished Bladder Capacity Detected)."
                        )

                    st.markdown(f"#### {tab_label} Dashboard Visualization (3D Pie)")
                    st.write(
                        "Below is a 3D-like donut chart illustrating how each activity category "
                        f"contributed to total void volume on {tab_label}."
                    )
                    plot_dashboard(edited_data)

    else:
        st.write("สำหรับแพทย์ (Doctor view) - คุณสามารถนำเสนอฟีเจอร์เพิ่มเติมได้ที่นี่ในอนาคต")

    st.markdown("---")
    st.write(
        "🔧 พัฒนาเพื่อผู้สูงอายุ ให้สามารถใช้งานง่ายและแสดงผลลัพธ์แบบทันที "
        "(Developed for elderly users with simple inputs and real-time results)."
    )
    st.write("👨‍💻 พัฒนาโดย: **FLOWMIND-RA**")


# ------------------------------------------------------------------------------------------
# 4. Run the Application
# ------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()