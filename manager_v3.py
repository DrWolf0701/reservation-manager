# -*- coding: utf-8 -*-
"""
預約系統管理介面 v3.3
Based on SPEC: https://docs/reservation_system_spec.md
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlite3
from pathlib import Path

# ==============================================
# 設定
# ==============================================
# 支援外部 API URL（用於 ngrok/雲端部署）
_API_URL = os.environ.get("RESERVATION_API_URL", "http://localhost:8520")
API_BASE = f"{_API_URL}/api/v1"
AUTH_API = f"{_API_URL}/api/v1/auth"

# 知識庫路徑（本地專用，雲端不使用）
CHUNK_PATH = {
    "default": "/Users/yu-tsehsiao/.openclaw/workspace/data/chunks.csv",
    "518dc260": "/Users/yu-tsehsiao/.openclaw/workspace-cust_002/data/chunks.csv"
}

# 檢查是否為 Streamlit Cloud 環境（只能寫 /mount/src）
IS_CLOUD = os.path.exists("/mount/src")

st.set_page_config(page_title="預約系統管理後台", page_icon="📅", layout="wide")

# ==============================================
# Session State
# ==============================================
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None

# ==============================================
# 直接寫入資料庫（繞過 API）
# ==============================================
DB_PATH = Path(__file__).parent / "reservation.db"

def db_set_slot_override(business_id: str, date: str, slot_id: str, max_bookings: int):
    """直接寫入 slot_overrides 表"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 先刪除舊的
        cursor.execute("""
            DELETE FROM slot_overrides 
            WHERE business_id=? AND date=? AND slot_id=?
        """, (business_id, date, slot_id))
        
        # 取得預設容量
        cursor.execute("""
            SELECT max_bookings FROM slots_config 
            WHERE business_id=? AND slot_id=?
        """, (business_id, slot_id))
        row = cursor.fetchone()
        default_max = row[0] if row else 1
        
        # 如果不是預設值，才寫入
        if max_bookings != default_max:
            cursor.execute("""
                INSERT INTO slot_overrides (business_id, date, slot_id, max_bookings)
                VALUES (?, ?, ?, ?)
            """, (business_id, date, slot_id, max_bookings))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

# ==============================================
# API 函式
# ==============================================
def api_get(endpoint, params=None, token=None):
    try:
        url = f"{API_BASE}/{endpoint}"
        if token:
            params = params or {}
            params["token"] = token
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_post(endpoint, data=None, params=None, token=None):
    try:
        url = f"{API_BASE}/{endpoint}"
        if token:
            params = params or {}
            params["token"] = token
        resp = requests.post(url, json=data, params=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}
    try:
        resp = requests.post(f"{API_BASE}/{endpoint}", json=data, params=params, headers=headers, timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_put(endpoint, data=None, token=None):
    try:
        url = f"{API_BASE}/{endpoint}"
        if token:
            url += f"?token={token}"
        resp = requests.put(url, json=data, timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_delete(endpoint, params=None, token=None):
    try:
        url = f"{API_BASE}/{endpoint}"
        if token:
            url += f"?token={token}"
        resp = requests.delete(url, params=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def login(username, password):
    try:
        resp = requests.post(f"{AUTH_API}/login", params={"username": username, "password": password}, timeout=10)
        return resp.json()
    except:
        return {"success": False, "detail": "Connection error"}

def logout(token):
    try:
        requests.post(f"{AUTH_API}/logout", params={"token": token}, timeout=5)
    except:
        pass

# ==============================================
# 登入頁面
# ==============================================
def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 預約系統管理後台")
        st.markdown("---")
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("帳號", placeholder="輸入帳號")
            password = st.text_input("密碼", type="password", placeholder="輸入密碼")
            submitted = st.form_submit_button("登入", type="primary")
            if submitted:
                if not username or not password:
                    st.error("請輸入帳號和密碼")
                else:
                    result = login(username, password)
                    if result.get("success"):
                        st.session_state.token = result.get("token")
                        st.session_state.user = result.get("user")
                        st.success("登入成功!")
                        st.rerun()
                    else:
                        st.error(f"登入失敗:{result.get('detail', '未知錯誤')}")
        st.markdown("---")
        st.caption("預設帳號:chris / admin123")

if not st.session_state.token:
    show_login()
    st.stop()

# ==============================================
# 已登入
# ==============================================
token = st.session_state.token
user = st.session_state.user

# 側邊欄
with st.sidebar:
    st.header(f"👤 {user.get('name', 'User')}")
    st.caption(f"角色:{user.get('role', 'owner')}")
    st.markdown("---")

    # 商家選擇
    st.header("🏢 商家選擇")
    businesses_data = api_get("businesses", token=token)
    if businesses_data.get("success") and businesses_data.get("data"):
        user_role = user.get('role', 'owner')
        user_biz_id = user.get('business_id', '')
        if user_role == 'admin':
            biz_list = businesses_data["data"]
        else:
            biz_list = [b for b in businesses_data["data"] if b["business_id"] == user_biz_id]
        business_dict = {b["business_id"]: b["name"] for b in biz_list}
        selected_business = st.selectbox(
            "選擇商家",
            options=list(business_dict.keys()),
            format_func=lambda x: business_dict[x]
        )
    else:
        selected_business = user.get('business_id', 'default')
        st.warning("只有預設商家")

    st.markdown("---")
    if st.button("登出"):
        logout(token)
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()

# 取得商家資訊
business_info = {}
if businesses_data.get("success"):
    for b in businesses_data["data"]:
        if b["business_id"] == selected_business:
            business_info = b
            break

services = business_info.get("services", "full")
booking_mode = business_info.get("booking_mode", "per_staff")
business_name = business_info.get("name", selected_business)

st.title(f"📅 預約系統管理 - {business_name}")

# ==============================================
# Tabs 定義
# ==============================================
TAB_KB = "📚 知識庫"
TAB_BOOKING = "📊 預約總表"
TAB_SLOTS = "📅 時段設定"
TAB_STAFF = "👥 員工管理"
TAB_SETTINGS = "⚙️ 系統設定"
TAB_BUSINESS = "🏢 商家管理"
TAB_ACCOUNT = "🔐 帳號管理"

tabs_list = [TAB_KB]
if services == "full":
    tabs_list.extend([TAB_BOOKING, TAB_SLOTS])
    if booking_mode == "per_staff":
        tabs_list.append(TAB_STAFF)
if user.get('role') == 'admin':
    tabs_list.extend([TAB_SETTINGS, TAB_BUSINESS, TAB_ACCOUNT])

all_tabs = st.tabs(tabs_list)
tab = {tabs_list[i]: all_tabs[i] for i in range(len(tabs_list))}

# ==============================================
# Tab: 知識庫
# ==============================================
with tab[TAB_KB]:
    st.header("📚 知識庫管理")

    # 雲端環境不支援本地知識庫
    if IS_CLOUD:
        st.info("☁️ 雲端環境不支援知識庫管理，請使用本地版本")
        st.stop()

    chunk_file = CHUNK_PATH.get(selected_business, CHUNK_PATH["default"])
    os.makedirs(os.path.dirname(chunk_file), exist_ok=True)

    # 讀取知識庫
    df_chunks = pd.DataFrame()
    if os.path.exists(chunk_file):
        df_all = pd.read_csv(chunk_file, header=None, names=["business_id", "chunk_id", "content", "tags"])
        df_chunks = df_all[df_all["business_id"] == selected_business]

    total_chars = df_chunks["content"].str.len().sum() if not df_chunks.empty else 0
    col1, col2 = st.columns(2)
    col1.metric("📄 知識庫", "已上傳" if not df_chunks.empty else "空白")
    col2.metric("📊 總字數", f"{total_chars:,}")

    st.markdown("---")

    # 下載按鈕
    if not df_chunks.empty:
        csv_data = df_chunks.to_csv(index=False)
        st.download_button(
            label="📥 下載 CSV",
            data=csv_data,
            file_name=f"knowledge_{selected_business}.csv",
            mime="text/csv"
        )
    else:
        st.info("尚無知識庫資料")

    # 顯示現有知識
    if not df_chunks.empty:
        with st.expander("📋 展開查看知識內容"):
            for idx, row in df_chunks.iterrows():
                with st.container():
                    st.markdown(f"**📄 {row.get('tags', '未知檔案')}**")
                    st.text(row.get('content', '')[:500] + "..." if len(str(row.get('content', ''))) > 500 else row.get('content', ''))
                    st.caption(f"ID: {row.get('chunk_id', '')}")
                    st.divider()

    # 上傳新知識
    st.subheader("➕ 上傳知識庫")
    st.caption("⚠️ 檔案限制 5MB 內,新檔案會覆蓋舊檔案")

    # 檢查現有知識庫狀態
    if os.path.exists(chunk_file):
        df_chunks = pd.read_csv(chunk_file, header=None, names=["business_id", "chunk_id", "content", "tags"])
        df_chunks = df_chunks[df_chunks["business_id"] == selected_business]
        if not df_chunks.empty:
            # 取得第一筆記錄的 tags 作為來源檔案名稱
            source_file = df_chunks.iloc[0].get('tags', '未知')
            st.info(f"📁 目前知識庫:{source_file}({len(df_chunks)} 筆記錄)")

    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("選擇檔案", type=["txt", "md", "csv"])
        submitted = st.form_submit_button("上傳覆蓋", type="primary")

        if submitted and uploaded_file:
            # 檢查檔案大小
            file_size = uploaded_file.size
            if file_size > 5 * 1024 * 1024:
                st.error("❌ 檔案超過 5MB 限制!")
            else:
                content = uploaded_file.read().decode('utf-8', errors='ignore').strip()
                if len(content) > 20:
                    # 刪除舊檔案的 chunks
                    if os.path.exists(chunk_file):
                        df_all = pd.read_csv(chunk_file, header=None, names=["business_id", "chunk_id", "content", "tags"])
                        df_all = df_all[df_all["business_id"] != selected_business]
                        df_all.to_csv(chunk_file, header=False, index=False)

                    # 寫入新 chunks(直接寫 content,不切割)
                    file_name = uploaded_file.name
                    chunk_id = uuid.uuid4().hex[:8]
                    with open(chunk_file, "a", encoding="utf-8") as f:
                        # 儲存:business_id, chunk_id, content, source_filename
                        f.write(f"{selected_business},{chunk_id},{content[:5000]},{file_name}\n")

                    st.success(f"✅ 已上傳:{file_name}({file_size} bytes)")
                    st.rerun()
                else:
                    st.error("內容太短(至少20字)")

# ==============================================
# Tab: 預約總表
# ==============================================
if services == "full" and TAB_BOOKING in tab:
    with tab[TAB_BOOKING]:
        st.header("📊 預約總表")

        # 日期範圍(預設一週)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("開始日期", datetime.now(), min_value=datetime.now().date(), key="booking_start")
        with col2:
            end_date = st.date_input("結束日期", start_date + timedelta(days=6), min_value=start_date, key="booking_end")

        # 日期列表
        date_list = []
        d = start_date
        while d <= end_date:
            date_list.append(d)
            d += timedelta(days=1)

        # 取得所有預約
        all_bookings = api_get("bookings", {"business_id": selected_business}, token=token)

        # 取得時段
        slots_data = api_get("slots", {"business_id": selected_business, "date": start_date.strftime("%Y-%m-%d")}, token=token)
        slots_list = slots_data.get("slots", []) if isinstance(slots_data, dict) else []

        # 表格顯示
        if slots_list and len(date_list) <= 14:

            if booking_mode == "per_staff":
                # ===== per_staff 模式:按員工區分 =====
                staff_data = api_get("staff", {"business_id": selected_business}, token=token)

                if staff_data.get("success") and staff_data.get("data"):
                    for sf in staff_data.get("data", []):
                        sf_id = sf.get("staff_id")
                        sf_name = sf.get("name", "")

                        with st.expander(f"👤 {sf_name}", expanded=True):
                            # 表頭
                            cols = st.columns(len(date_list) + 1)
                            with cols[0]:
                                st.write("**時段▼**")
                            for i, dd in enumerate(date_list):
                                with cols[i+1]:
                                    st.write(f"**{dd.strftime('%m/%d')}\n{dd.strftime('%a')}**")

                            # 每個時段一行
                            for slot in slots_list:
                                sid = slot.get("slot_id")
                                sname = slot.get("name", "")
                                start = slot.get("start_time", "")
                                end = slot.get("end_time", "")

                                cols = st.columns(len(date_list) + 1)
                                with cols[0]:
                                    st.write(f"**{sname}**\n{start}-{end}")

                                for i, dd in enumerate(date_list):
                                    with cols[i+1]:
                                        date_str = dd.strftime("%Y-%m-%d")

                                        # 檢查該員工該日該時段是否上班
                                        ss = api_get(f"staff/{sf_id}/slots", {"date": date_str, "business_id": selected_business}, token=token)
                                        is_working = False
                                        if ss.get("success"):
                                            for s in ss.get("data", []):
                                                if s.get("slot_id") == sid and s.get("is_available") == 1:
                                                    is_working = True
                                                    break

                                        if not is_working:
                                            st.error("不可")
                                        else:
                                            slot_bookings = []
                                            if all_bookings.get("success"):
                                                df = pd.DataFrame(all_bookings.get("data", []))
                                                if not df.empty and "date" in df.columns:
                                                    df["date"] = pd.to_datetime(df["date"])
                                                    day_df = df[df["date"].dt.date == dd]
                                                    slot_df = day_df[(day_df["slot"] == sid) & (day_df["staff_id"] == sf_id)]
                                                    slot_bookings = slot_df.to_dict('records')

                                            booked = len([b for b in slot_bookings if b.get('status') != 'cancelled'])

                                            if booked > 0:
                                                st.warning("已預")
                                            else:
                                                st.success("可")
                else:
                    st.info("尚無員工")

            else:
                # ===== shared_capacity 模式(洗車):顯示剩餘 capacity =====
                # 表頭
                cols = st.columns(len(date_list) + 1)
                with cols[0]:
                    st.write("**時段▼**")
                for i, dd in enumerate(date_list):
                    with cols[i+1]:
                        st.write(f"**{dd.strftime('%m/%d')}\n{dd.strftime('%a')}**")

                # 每個時段一行
                for slot in slots_list:
                    sid = slot.get("slot_id")
                    sname = slot.get("name", "")
                    start = slot.get("start_time", "")
                    end = slot.get("end_time", "")
                    max_b = slot.get("max_bookings", 1)

                    cols = st.columns(len(date_list) + 1)
                    with cols[0]:
                        st.write(f"**{sname}**\n{start}-{end}")

                    for i, dd in enumerate(date_list):
                        with cols[i+1]:
                            # 計算已預約數
                            booked = 0
                            if all_bookings.get("success"):
                                df = pd.DataFrame(all_bookings.get("data", []))
                                if not df.empty and "date" in df.columns:
                                    df["date"] = pd.to_datetime(df["date"])
                                    day_df = df[df["date"].dt.date == dd]
                                    slot_df = day_df[day_df["slot"] == sid]
                                    booked = len([b for b in slot_df.to_dict('records') if b.get('status') != 'cancelled'])

                            remaining = max_b - booked

                            if remaining <= 0:
                                st.error("滿")
                            elif remaining < max_b:
                                st.warning(f"{remaining}")
                            else:
                                st.success(f"{remaining}")

                st.caption("數字 = 剩餘可預約名額")

        elif len(date_list) > 14:
            st.warning("日期範圍請選擇 14 天以內")

        else:
            st.info("沒有時段設定")

# ==============================================
# Tab: 時段設定
# ==============================================
if services == "full" and TAB_SLOTS in tab:
    with tab[TAB_SLOTS]:
        st.header("📅 班表設定")

        # ===== Admin: 商家時段設定 =====
        if user.get('role') == 'admin':
            with st.expander("🏢 商家時段設定", expanded=False):
                # 取得所有商家
                biz_data = api_get("businesses", token=token)
                biz_list = biz_data.get("data", []) if biz_data.get("success") else []
                biz_dict = {b["business_id"]: b["name"] for b in biz_list}

                admin_biz = st.selectbox(
                    "選擇商家",
                    options=list(biz_dict.keys()),
                    format_func=lambda x: biz_dict[x],
                    key="admin_slot_biz"
                )

                # 取得該商家的時段設定和模式
                config_data = api_get("slots/config", {"business_id": admin_biz}, token=token)
                current_slots = config_data.get("slots", []) if config_data.get("success") else []
                biz_detail = next((b for b in biz_list if b["business_id"] == admin_biz), None)
                is_shared = biz_detail.get("booking_mode") == "shared_capacity" if biz_detail else False

                st.write(f"**目前時段數：{len(current_slots)}** ({'共享產能模式' if is_shared else '指定員工模式'})")

                # 編輯時段
                st.write("**編輯時段：**")
                slot_count = st.number_input("時段數量", 1, 10, max(1, len(current_slots)), key="slot_count")

                # 收集新的時段設定
                new_slots = []
                if is_shared:
                    hdr_cols = st.columns(5)
                    with hdr_cols[0]: st.write("**名稱**")
                    with hdr_cols[1]: st.write("**開始**")
                    with hdr_cols[2]: st.write("**結束**")
                    with hdr_cols[3]: st.write("**容量**")
                    with hdr_cols[4]: st.write("**啟用**")
                else:
                    hdr_cols = st.columns(4)
                    with hdr_cols[0]: st.write("**名稱**")
                    with hdr_cols[1]: st.write("**開始**")
                    with hdr_cols[2]: st.write("**結束**")
                    with hdr_cols[3]: st.write("**啟用**")

                for i in range(int(slot_count)):
                    if i < len(current_slots):
                        cs = current_slots[i]
                        default_name = cs.get("name", f"時段{i+1}")
                        default_start = cs.get("start_time", "09:00")
                        default_end = cs.get("end_time", "10:00")
                        default_max = cs.get("max_bookings", 1)
                        default_enabled = cs.get("enabled", 1)
                    else:
                        default_name = f"時段{i+1}"
                        default_start = "09:00"
                        default_end = "10:00"
                        default_max = 1
                        default_enabled = 1

                    if is_shared:
                        row_cols = st.columns(5)
                        with row_cols[0]:
                            name = st.text_input("名稱", default_name, key=f"slot_name_{i}", label_visibility="collapsed")
                        with row_cols[1]:
                            start = st.text_input("開始", default_start, key=f"slot_start_{i}", label_visibility="collapsed")
                        with row_cols[2]:
                            end = st.text_input("結束", default_end, key=f"slot_end_{i}", label_visibility="collapsed")
                        with row_cols[3]:
                            max_b = st.number_input("容量", 1, 10, default_max, key=f"slot_max_{i}", label_visibility="collapsed")
                        with row_cols[4]:
                            enabled = st.checkbox("", value=(default_enabled == 1), key=f"slot_en_{i}", label_visibility="collapsed")
                    else:
                        row_cols = st.columns(4)
                        with row_cols[0]:
                            name = st.text_input("名稱", default_name, key=f"slot_name_{i}", label_visibility="collapsed")
                        with row_cols[1]:
                            start = st.text_input("開始", default_start, key=f"slot_start_{i}", label_visibility="collapsed")
                        with row_cols[2]:
                            end = st.text_input("結束", default_end, key=f"slot_end_{i}", label_visibility="collapsed")
                        with row_cols[3]:
                            enabled = st.checkbox("", value=(default_enabled == 1), key=f"slot_en_{i}", label_visibility="collapsed")
                        max_b = 1  # per_staff 模式固定為 1

                    new_slots.append({
                        "name": name,
                        "start_time": start,
                        "end_time": end,
                        "max_bookings": max_b,
                        "enabled": 1 if enabled else 0
                    })

                # 檢查是否與原本不同
                is_different = (len(new_slots) != len(current_slots))
                if not is_different:
                    for i, (ns, cs) in enumerate(zip(new_slots, current_slots)):
                        if ns["name"] != cs.get("name") or ns["start_time"] != cs.get("start_time") or ns["end_time"] != cs.get("end_time") or ns["max_bookings"] != cs.get("max_bookings") or ns["enabled"] != cs.get("enabled"):
                            is_different = True
                            break

                if is_different:
                    st.warning("⚠️ 設定與目前不同，確認後將取代現有員工班表（所有員工預設為不上班）")

                # 確認按鈕
                if st.button("✅ 確認套用", type="primary", disabled=not new_slots):
                    if is_different:
                        # 雙重確認
                        st.error("⚠️ 再次確認：這將取代現有員工班表")
                        if st.button("🚫 確認取代", type="secondary"):
                            result = api_put(f"slots/config?business_id={admin_biz}", {"slots": new_slots}, token=token)
                            if result.get("success"):
                                st.success("✅ 商家時段設定已套用！")
                                st.rerun()
                            else:
                                st.error(f"套用失敗：{result.get('detail', '未知錯誤')}")
                    else:
                        # 沒變動，直接儲存
                        result = api_put(f"slots/config?business_id={admin_biz}", {"slots": new_slots}, token=token)
                        if result.get("success"):
                            st.success("✅ 商家時段設定已套用！")
                            st.rerun()
                        else:
                            st.error(f"套用失敗：{result.get('detail', '未知錯誤')}")

        st.markdown("---")

        # ===== 班表設定 =====
        st.subheader("📊 班表設定")

        # 取得時段
        slots_data = api_get("slots", {"business_id": selected_business, "date": datetime.now().strftime("%Y-%m-%d")}, token=token)
        slots_list = slots_data.get("slots", []) if isinstance(slots_data, dict) else []

        # 日期範圍
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("📅 開始日期", datetime.now(), min_value=datetime.now().date(), key="matrix_start")
        with col2:
            end_date = st.date_input("📅 結束日期", start_date + timedelta(days=14), min_value=start_date, key="matrix_end")

        # 日期列表
        date_list = []
        d = start_date
        while d <= end_date:
            date_list.append(d)
            d += timedelta(days=1)

        st.markdown("---")

        if slots_list and len(date_list) <= 35:
            if booking_mode == "per_staff":
                # ===== per_staff 模式 =====
                staff_data = api_get("staff", {"business_id": selected_business}, token=token)
                if staff_data.get("success") and staff_data.get("data"):
                    staff_options = {sf["staff_id"]: sf["name"] for sf in staff_data["data"]}
                    selected_staff = st.selectbox("👤 選擇員工", list(staff_options.keys()), format_func=lambda x: staff_options[x], key="matrix_staff")

                    # 表頭
                    cols = st.columns(len(date_list) + 1)
                    with cols[0]:
                        st.write("**時段▼**")
                    for i, dd in enumerate(date_list):
                        with cols[i+1]:
                            st.write(f"**{dd.strftime('%m/%d')}\n{dd.strftime('%a')}**")

                    # 每一個時段一行
                    for slot in slots_list:
                        sid = slot.get("slot_id")
                        slot_name = slot.get("name", "")
                        start_time = slot.get("start_time", "")
                        end_time = slot.get("end_time", "")

                        cols = st.columns(len(date_list) + 1)
                        with cols[0]:
                            st.write(f"**{slot_name}**\n{start_time}-{end_time}")

                        for i, dd in enumerate(date_list):
                            date_str = dd.strftime("%Y-%m-%d")
                            with cols[i+1]:
                                ss = api_get(f"staff/{selected_staff}/slots", {"date": date_str, "business_id": selected_business}, token=token)
                                is_avail = 0
                                if ss.get("success"):
                                    for s in ss.get("data", []):
                                        if s.get("slot_id") == sid and s.get("is_available") == 1:
                                            is_avail = 1
                                            break

                                if is_avail == 1:
                                    if st.button("🟢", key=f"on_{sid}_{date_str}", help="點一下取消"):
                                        api_post(f"staff/{selected_staff}/slots", {"date": date_str, "slot_id": sid, "is_available": 0, "business_id": selected_business}, token=token)
                                        st.rerun()
                                else:
                                    if st.button("⚪", key=f"off_{sid}_{date_str}", help="點一下設為上班"):
                                        api_post(f"staff/{selected_staff}/slots", {"date": date_str, "slot_id": sid, "is_available": 1, "business_id": selected_business}, token=token)
                                        st.rerun()

                    # 全選/取消全選
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 全選全部"):
                            for slot in slots_list:
                                sid = slot.get("slot_id")
                                for dd in date_list:
                                    api_post(f"staff/{selected_staff}/slots", {"date": dd.strftime("%Y-%m-%d"), "slot_id": sid, "is_available": 1, "business_id": selected_business}, token=token)
                            st.success("✅ 已全選!")
                            st.rerun()
                    with col2:
                        if st.button("❌ 取消全部"):
                            for slot in slots_list:
                                sid = slot.get("slot_id")
                                for dd in date_list:
                                    api_post(f"staff/{selected_staff}/slots", {"date": dd.strftime("%Y-%m-%d"), "slot_id": sid, "is_available": 0, "business_id": selected_business}, token=token)
                            st.success("❌ 已取消!")
                            st.rerun()
                else:
                    st.info("尚無員工")

            else:
                # ===== shared_capacity 模式：容量調整 =====
                st.info("共享產能模式：可直接調整各時段容量")
                
                # 取得該商家的時段設定
                config_data = api_get("slots/config", {"business_id": selected_business}, token=token)
                all_slots = config_data.get("slots", []) if config_data.get("success") else []
                
                # 表頭
                cols = st.columns(len(date_list) + 1)
                with cols[0]:
                    st.write("**時段▼**")
                for i, dd in enumerate(date_list):
                    with cols[i+1]:
                        st.write(f"**{dd.strftime('%m/%d')}\n{dd.strftime('%a')}**")
                
                # 每個時段一行
                for slot in all_slots:
                    sid = slot.get("slot_id")
                    slot_name = slot.get("name", "")
                    start_time = slot.get("start_time", "")
                    end_time = slot.get("end_time", "")
                    default_max = slot.get("max_bookings", 1)
                    
                    cols = st.columns(len(date_list) + 1)
                    with cols[0]:
                        st.write(f"**{slot_name}**\n{start_time}-{end_time}\n(預設:{default_max})")
                    
                    for i, dd in enumerate(date_list):
                        date_str = dd.strftime("%Y-%m-%d")
                        
                        with cols[i+1]:
                            # 直接從資料庫讀取覆寫值
                            conn = sqlite3.connect(str(DB_PATH))
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT max_bookings FROM slot_overrides 
                                WHERE business_id=? AND date=? AND slot_id=?
                            """, (selected_business, date_str, sid))
                            row = cursor.fetchone()
                            current_max = row[0] if row else default_max
                            
                            # 取得已預約數量
                            bookings_data = api_get(
                                "bookings",
                                {
                                    "business_id": selected_business,
                                    "date": date_str,
                                    "slot_id": sid
                                },
                                token=token
                            )
                            current_bookings = 0
                            if bookings_data.get("success"):
                                current_bookings = len([b for b in bookings_data.get("data", []) if b.get("status") != "cancelled"])
                            conn.close()
                            
                            # 顯示狀態
                            changed = current_max != default_max
                            if changed:
                                st.write(f"🟡 {current_max}(已改)")
                            else:
                                st.write(f"🔵 {current_max}")
                            
                            # 增減按鈕
                            col_up, col_dn = st.columns(2)
                            with col_up:
                                if st.button("▲", key=f"up_{sid}_{date_str}", help="增加容量", use_container_width=True):
                                    if current_max < 10:
                                        db_set_slot_override(selected_business, date_str, sid, current_max + 1)
                                        st.rerun()
                            with col_dn:
                                if st.button("▼", key=f"dn_{sid}_{date_str}", help="減少容量", use_container_width=True):
                                    if current_max > 0:
                                        db_set_slot_override(selected_business, date_str, sid, current_max - 1)
                                        st.rerun()

        elif len(date_list) > 35:
            st.warning("日期範圍請選擇 35 天以內")

        elif slots_list:
            st.info("日期範圍太長,請選擇 14 天以內")

        else:
            st.info("尚無時段設定")

# ==============================================
# Tab: 員工管理
# ==============================================
if services == "full" and booking_mode == "per_staff" and TAB_STAFF in tab:
    with tab[TAB_STAFF]:
        st.header("👥 員工管理")

        # 新增員工
        with st.expander("➕ 新增員工", expanded=False):
            with st.form("add_staff_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("姓名")
                    new_role = st.selectbox("角色", ["designer", "therapist", "staff"])
                with col2:
                    new_phone = st.text_input("電話(選填)")
                    new_email = st.text_input("Email(選填)")

                submitted = st.form_submit_button("新增員工", type="primary")
                if submitted and new_name:
                    result = api_post("staff", {
                        "name": new_name,
                        "role": new_role,
                        "phone": new_phone,
                        "email": new_email,
                        "business_id": selected_business
                    }, token=token)
                    if result.get("success"):
                        st.success("✅ 員工已新增!")
                        st.rerun()
                    else:
                        st.error(f"新增失敗:{result.get('detail', '未知錯誤')}")

        st.markdown("---")

        # 員工列表
        staff_data = api_get("staff", {"business_id": selected_business}, token=token)
        if staff_data.get("success"):
            for staff in staff_data.get("data", []):
                with st.expander(f"👤 {staff.get('name', '')} ({staff.get('role', '')})"):
                    st.write(f"**ID:** `{staff.get('staff_id', '')}`")
                    st.write(f"**電話:** {staff.get('phone', '-')}")
                    st.write(f"**Email:** {staff.get('email', '-')}")
                    st.write(f"**狀態:** {'在職' if staff.get('is_active') == 1 else '離職'}")
        else:
            st.info("尚無員工資料")

# ==============================================
# Tab: 系統設定(只有 admin)
# ==============================================
if user.get('role') == 'admin' and TAB_SETTINGS in tab:
    with tab[TAB_SETTINGS]:
        st.header("⚙️ 系統設定")

        # 統計
        col1, col2, col3 = st.columns(3)
        bookings_data = api_get("bookings", {"business_id": selected_business}, token=token)
        staff_data = api_get("staff", {"business_id": selected_business}, token=token)

        with col1:
            total_bookings = len(bookings_data.get("data", [])) if bookings_data.get("success") else 0
            st.metric("總預約數", total_bookings)
        with col2:
            total_staff = len(staff_data.get("data", [])) if staff_data.get("success") else 0
            st.metric("員工數", total_staff)
        with col3:
            chunk_file = CHUNK_PATH.get(selected_business, CHUNK_PATH["default"])
            kb_count = 0
            if os.path.exists(chunk_file):
                df = pd.read_csv(chunk_file, header=None, names=["bid", "cid", "content", "tags"])
                kb_count = len(df[df["bid"] == selected_business])
            st.metric("知識庫筆數", kb_count)

        st.markdown("---")

        # 密碼修改（顯示所有帳號）
        st.subheader("🔐 修改密碼")
        st.caption("顯示所有帳號，可修改密碼或刪除")

        # 取得所有帳號和商家
        accounts_data = api_get("auth/accounts", token=token)
        biz_data = api_get("businesses", token=token)
        biz_names = {}
        if biz_data.get("success"):
            for b in biz_data["data"]:
                biz_names[b["business_id"]] = b.get("name", b["business_id"])

        if accounts_data.get("success"):
            for acc in accounts_data.get("data", []):
                biz_id = acc.get('business_id', '')
                biz_name = biz_names.get(biz_id, biz_id) if biz_id else '全部商家'
                role_icon = "👑" if acc.get('role') == 'admin' else "👤"
                is_me = acc.get('username', '') == user.get('username', '')

                with st.expander(f"{role_icon} {acc.get('name', '')} (@{acc.get('username', '')}){' (我)' if is_me else ''}"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**角色**: {acc.get('role', '')}")
                    col2.write(f"**商家**: {biz_name}")

                    # 修改密碼
                    st.markdown("**修改密碼:**")
                    with st.form(f"pw_{acc.get('user_id', '')}", clear_on_submit=True):
                        new_pw = st.text_input("新密碼", type="password", key=f"pw_{acc.get('user_id', '')}")
                        new_pw2 = st.text_input("確認密碼", type="password", key=f"pw2_{acc.get('user_id', '')}")
                        submitted = st.form_submit_button("儲存")
                        if submitted:
                            if new_pw != new_pw2:
                                st.error("❌ 密碼不一致")
                            elif len(new_pw) < 8:
                                st.error("❌ 密碼至少8字元")
                            else:
                                result = api_post("auth/password", params={
                                    "token": token,
                                    "old_password": new_pw,
                                    "new_password": new_pw,
                                    "target_user": acc.get('user_id', '')
                                })
                                if result.get("success"):
                                    st.success("✅ 密碼已修改!")
                                else:
                                    st.error(f"修改失敗: {result.get('detail', '未知錯誤')}")

                    # 刪除帳號（不能刪除自己）
                    if not is_me:
                        st.markdown("---")
                        st.warning("⚠️ 刪除帳號")
                        confirm = st.checkbox(f"確認刪除 {acc.get('name', '')}", key=f"del_{acc.get('user_id', '')}")
                        if confirm:
                            if st.button(f"🚫 確認刪除", key=f"conf_{acc.get('user_id', '')}", type="secondary"):
                                result = api_delete(f"auth/accounts/{acc.get('user_id', '')}", token=token)
                                if result.get("success"):
                                    st.success("✅ 帳號已刪除!")
                                    st.rerun()
                                else:
                                    st.error(f"刪除失敗: {result.get('detail', '未知錯誤')}")

# ==============================================
# Tab: 商家管理(只有 admin)
# ==============================================
if user.get('role') == 'admin' and TAB_BUSINESS in tab:
    with tab[TAB_BUSINESS]:
        st.header("🏢 商家管理")
        st.caption("修改商家設定")

        # 新增商家
        with st.expander("➕ 新增商家", expanded=False):
            with st.form("add_biz_form", clear_on_submit=True):
                new_biz_name = st.text_input("商家名稱")
                submitted = st.form_submit_button("新增", type="primary")
                if submitted and new_biz_name:
                    result = api_post("businesses", {"name": new_biz_name}, token=token)
                    if result.get("success"):
                        st.success("✅ 商家已新增!")
                        st.rerun()
                    else:
                        st.error(f"新增失敗:{result.get('detail', '未知錯誤')}")

        st.markdown("---")

        all_businesses = api_get("businesses", token=token)
        if all_businesses.get("success"):
            biz_dict = {b["business_id"]: b["name"] for b in all_businesses["data"]}
            sel_biz = st.selectbox(
                "選擇商家",
                options=list(biz_dict.keys()),
                format_func=lambda x: biz_dict[x],
                key="biz_selector"
            )

            # 取得該商家詳細資料
            biz_detail = None
            for b in all_businesses["data"]:
                if b["business_id"] == sel_biz:
                    biz_detail = b
                    break

            if biz_detail:
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("商家名稱", biz_detail.get("name", ""))
                with col2:
                    new_services = st.selectbox(
                        "服務模式",
                        ["knowledge_only", "full"],
                        index=0 if biz_detail.get("services") == "knowledge_only" else 1,
                        format_func=lambda x: "僅知識庫" if x == "knowledge_only" else "完整預約"
                    )

                col3, col4 = st.columns(2)
                with col3:
                    new_mode = st.selectbox(
                        "預約模式",
                        ["per_staff", "shared_capacity"],
                        index=0 if biz_detail.get("booking_mode") == "per_staff" else 1,
                        format_func=lambda x: "指定員工" if x == "per_staff" else "共享產能"
                    )
                with col4:
                    new_active = st.checkbox("啟用", value=(biz_detail.get("is_active") == 1))

                if st.button("💾 儲存設定", type="primary"):
                    result = api_put(
                        f"businesses/{sel_biz}",
                        {
                            "name": new_name,
                            "services": new_services,
                            "booking_mode": new_mode,
                            "is_active": 1 if new_active else 0
                        },
                        token=token
                    )
                    if result.get("success"):
                        st.success("✅ 商家設定已儲存!")
                        st.rerun()
                    else:
                        st.error(f"儲存失敗:{result.get('detail', '未知錯誤')}")

# ==============================================
# Tab: 帳號管理(只有 admin)
# ==============================================
if user.get('role') == 'admin' and TAB_ACCOUNT in tab:
    with tab[TAB_ACCOUNT]:
        st.header("🔐 帳號管理")
        st.caption("新增和管理帳號")

        # 新增帳號
        with st.expander("➕ 新增帳號", expanded=False):
            with st.form("add_account_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    acc_name = st.text_input("姓名")
                    acc_username = st.text_input("帳號")
                with col2:
                    acc_password = st.text_input("密碼", type="password")
                    acc_role = st.selectbox("角色", ["owner", "admin"])
                
                # 根據角色顯示商家選擇
                if acc_role == "owner":
                    # owner 才能選擇商家
                    all_biz = api_get("businesses", token=token)
                    if all_biz.get("success"):
                        biz_options = {b["business_id"]: b["name"] for b in all_biz["data"]}
                        acc_biz = st.selectbox("商家", options=list(biz_options.keys()), format_func=lambda x: biz_options[x])
                    else:
                        acc_biz = st.text_input("商家 ID")
                else:
                    # admin 預設全部商家
                    st.write("**商家**: 全部商家")
                    acc_biz = None
                
                submitted = st.form_submit_button("新增帳號", type="primary")
                if submitted:
                    if not acc_name or not acc_username or not acc_password:
                        st.error("請填寫所有欄位")
                    elif acc_role == "owner" and not acc_biz:
                        st.error("請選擇商家")
                    else:
                        biz_id = acc_biz if acc_role == "owner" else selected_business
                        result = api_post("auth/register", params={
                            "username": acc_username,
                            "password": acc_password,
                            "name": acc_name,
                            "role": acc_role,
                            "business_id": biz_id,
                            "admin_token": token
                        })
                        if result.get("success"):
                            st.success("✅ 帳號已新增！")
                            st.rerun()
                        else:
                            st.error(f"新增失敗：{result.get('detail', '未知錯誤')}")

        st.markdown("---")
        st.subheader("👥 現有帳號")

        # 取得帳號列表
        accounts_data = api_get("auth/accounts", token=token)
        # 取得商家列表
        businesses_data = api_get("businesses", token=token)
        business_names = {}
        if businesses_data.get("success"):
            for b in businesses_data["data"]:
                business_names[b["business_id"]] = b.get("name", b["business_id"])

        if accounts_data.get("success"):
            for acc in accounts_data.get("data", []):
                biz_id = acc.get('business_id', '')
                biz_name = business_names.get(biz_id, biz_id)
                role_icon = "👑" if acc.get('role') == 'admin' else "👤"
                with st.expander(f"{role_icon} {acc.get('name', '')} (@{acc.get('username', '')})"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**角色**: {acc.get('role', '')}")
                    col2.write(f"**商家**: {biz_name if acc.get('role') != 'admin' else '全部商家'}")
                    col3, col4 = st.columns(2)
                    col3.write(f"**建立**: {acc.get('created_at', '')[:10]}")

                    # 狀態開關(只有 admin 可以改,且不能改 admin 自己)
                    if user.get('role') == 'admin' and acc.get('role') != 'admin':
                        is_on = st.toggle("狀態", value=(acc.get('is_active') == 1), key=f"status_{acc.get('user_id', '')}")
                        if is_on != (acc.get('is_active') == 1):
                            result = api_put(f"auth/accounts/{acc.get('user_id', '')}/status", {"is_active": 1 if is_on else 0}, token=token)
                            if result.get("success"):
                                st.success("✅ 狀態已更新")
                                st.rerun()
                    else:
                        col4.write(f"**狀態**: {'✅ 開啟' if acc.get('is_active') == 1 else '❌ 停用'}")

                    # 更改商家綁定(只有 admin 可以改,且不能改 admin 自己)
                    if user.get('role') == 'admin' and acc.get('role') != 'admin':
                        st.markdown("---")
                        new_biz = st.selectbox(
                            "更改商家",
                            options=list(business_names.keys()),
                            index=list(business_names.keys()).index(biz_id) if biz_id in business_names else 0,
                            format_func=lambda x: business_names[x],
                            key=f"biz_{acc.get('user_id', '')}"
                        )
                        if st.button("💾 更新綁定", key=f"upd_{acc.get('user_id', '')}"):
                            if new_biz != biz_id:
                                result = api_put(f"auth/accounts/{acc.get('user_id', '')}/business", {"business_id": new_biz}, token=token)
                                if result.get("success"):
                                    st.success("✅ 商家綁定已更新!")
                                    st.rerun()
                                else:
                                    st.error("更新失敗")
        else:
            st.info("暫無帳號資料")

# ==============================================
# 底部
# ==============================================
st.markdown("---")
st.caption("預約系統管理後台 v3.2 | 2026-04-05")
