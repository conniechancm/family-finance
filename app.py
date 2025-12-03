import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定頁面 ---
st.set_page_config(page_title="溫馨家庭理財", page_icon="🏠", layout="centered")

# --- 自定義 CSS (柔和風格) ---
st.markdown("""
    <style>
    .stApp { background-color: #fdfbf7; color: #5d5d5d; }
    .stButton>button { background-color: #ffb7b2; color: white; border-radius: 20px; border: none; padding: 10px 24px; font-weight: bold; }
    .stButton>button:hover { background-color: #ff9e99; border: none; }
    h1, h2, h3 { color: #6d6875; }
    .stSelectbox, .stDateInput, .stNumberInput { border-radius: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 連接 Google Sheets 函式 ---
def get_data():
    # 從 Streamlit Secrets 獲取憑證
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 開啟試算表 (請確保名稱正確，或使用 URL)
    sheet_url = st.secrets["private_gsheets_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

def load_df(sheet):
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["日期", "成員", "收支類型", "主類別", "細項", "金額", "備註"])
    return pd.DataFrame(data)

def save_entry(sheet, entry_list):
    # entry_list 格式: [日期, 成員, 收支類型, 主類別, 細項, 金額, 備註]
    # 注意：日期需轉為字串
    sheet.append_row(entry_list)

# --- 定義類別 ---
MEMBERS = ["Connie", "Kam", "曦晴", "曦朗"]
CATEGORIES = {
    "收入": {
        "薪金": ["每月薪金"],
        "其他": ["花紅", "投資回報", "其他收入"]
    },
    "支出": {
        "家庭支出": ["供樓", "管理費", "水費", "電費", "煤氣費", "電話費", "上網費", "串流平台", "差餉", "外傭薪金", "家庭日常用品"],
        "個人支出": ["早午晚三餐", "購物", "娛樂", "個人其他"],
        "小朋友支出": ["學費", "興趣班", "醫療", "其他費用"],
        "交通費用": ["車費", "車充電費用", "泊車", "交通其他"],
        "儲蓄與保險": ["存款", "保險", "旅遊基金"]
    }
}

# --- 主程式 ---
def main():
    st.title("🏠 溫馨家庭理財簿 (雲端版)")
    
    # 初始化連接
    try:
        sheet = get_data()
        df = load_df(sheet)
    except Exception as e:
        st.error(f"無法連接資料庫，請檢查設定。錯誤: {e}")
        st.stop()

    tab1, tab2 = st.tabs(["📝 記賬", "📊 當月報表"])

    # --- Tab 1: 記賬 ---
    with tab1:
        st.subheader("新增一筆交易")
        tx_type = st.radio("交易種類", ["支出", "收入"], horizontal=True)
        
        c1, c2 = st.columns(2)
        member = c1.selectbox("成員", MEMBERS)
        date = c2.date_input("日期", datetime.today())

        available_main = list(CATEGORIES[tx_type].keys())
        default_idx = 0
        if tx_type == "支出" and member in ["曦晴", "曦朗"] and "小朋友支出" in available_main:
            default_idx = available_main.index("小朋友支出")
            
        main_cat = st.selectbox("主分類", available_main, index=default_idx)
        sub_cat = st.selectbox("細項", CATEGORIES[tx_type][main_cat])
        amount = st.number_input("金額 ($)", min_value=0.0, format="%.2f")
        note = st.text_input("備註", placeholder="選填")

        if st.button("✅ 確認儲存"):
            # 轉換日期為字串以儲存
            date_str = date.strftime("%Y-%m-%d")
            entry = [date_str, member, tx_type, main_cat, sub_cat, amount, note]
            
            with st.spinner("正在儲存到雲端..."):
                save_entry(sheet, entry)
            
            st.success(f"已儲存！{member} {sub_cat} ${amount}")
            # 強制重新整理以顯示最新數據
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        if not df.empty:
            st.caption("最近 5 筆紀錄 (來自 Google Sheet)：")
            st.dataframe(df.tail(5), use_container_width=True)

    # --- Tab 2: 報表 ---
    with tab2:
        if df.empty:
            st.info("暫無資料。")
        else:
            df["日期"] = pd.to_datetime(df["日期"])
            current_month = datetime.now().month
            selected_month = st.selectbox("選擇月份", range(1, 13), index=current_month-1)
            
            m_df = df[df["日期"].dt.month == selected_month]
            
            if m_df.empty:
                st.warning(f"{selected_month} 月無資料。")
            else:
                inc = m_df[m_df["收支類型"]=="收入"]["金額"].sum()
                exp = m_df[m_df["收支類型"]=="支出"]["金額"].sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("總收入", f"${inc:,.0f}")
                col2.metric("總支出", f"${exp:,.0f}", delta_color="inverse")
                col3.metric("結餘", f"${inc-exp:,.0f}")
                
                exp_df = m_df[m_df["收支類型"]=="支出"]
                if not exp_df.empty:
                    st.markdown("### 支出分佈")
                    fig = px.sunburst(exp_df, path=['主類別', '細項'], values='金額', color='主類別', color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### 詳細列表")
                    summary = exp_df.groupby(["主類別", "細項", "成員"])["金額"].sum().reset_index()
                    st.dataframe(summary, use_container_width=True)

if __name__ == "__main__":
    main()