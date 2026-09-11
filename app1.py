import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client, Client

st.set_page_config(
    page_title="업무관리 대시보드",
    page_icon="🏦",
    layout="wide",
)

# -----------------------------
# Supabase 연결
# -----------------------------
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# -----------------------------
# 공통 유틸
# -----------------------------
def fetch_table(table_name: str) -> pd.DataFrame:
    res = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(res.data or [])

def refresh():
    st.cache_data.clear()
    st.rerun()

def money(v):
    try:
        return f"{float(v):,.0f}원"
    except Exception:
        return "0원"

@st.cache_data(ttl=30)
def load_all():
    return {
        "branches": fetch_table("branches"),
        "members": fetch_table("members"),
        "deposit_accounts": fetch_table("deposit_accounts"),
        "loans": fetch_table("loans"),
        "transactions": fetch_table("transactions"),
    }

data = load_all()
branches = data["branches"]
members = data["members"]
deposits = data["deposit_accounts"]
loans = data["loans"]
transactions = data["transactions"]

branch_map = {}
if not branches.empty:
    branch_map = dict(zip(branches["branch_id"], branches["branch_name"]))

# -----------------------------
# 사이드바
# -----------------------------
with st.sidebar:
    st.title("🏦 업무관리")
    menu = st.radio(
        "메뉴",
        ["통합 대시보드", "조합원 관리", "예적금 관리", "대출 관리", "거래내역 조회"],
        index=0,
    )
    st.divider()
    if st.button("🔄 최신 데이터 새로고침", use_container_width=True):
        refresh()

# -----------------------------
# 통합 대시보드
# -----------------------------
if menu == "통합 대시보드":
    st.title("📊 통합 경영 대시보드")
    st.caption("Supabase 데이터를 페이지 로드 시점 및 새로고침 시점에 다시 조회합니다.")

    total_members = len(members)
    total_deposits = float(pd.to_numeric(deposits.get("balance", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    total_loans = float(pd.to_numeric(loans.get("loan_amount", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    overdue_count = 0
    if not loans.empty and "status" in loans.columns:
        overdue_count = int(loans["status"].astype(str).str.contains("연체", na=False).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 조합원", f"{total_members:,}명")
    c2.metric("예적금 총액", money(total_deposits))
    c3.metric("대출 총액", money(total_loans))
    c4.metric("연체 건수", f"{overdue_count:,}건")

    st.divider()

    # 지점별 조합원 수
    member_by_branch = pd.DataFrame()
    if not members.empty:
        member_by_branch = (
            members.groupby("branch_id", as_index=False)
            .size()
            .rename(columns={"size": "조합원 수"})
        )
        member_by_branch["지점"] = member_by_branch["branch_id"].map(branch_map).fillna(
            member_by_branch["branch_id"].astype(str)
        )

    # 지점별 예적금
    deposit_by_branch = pd.DataFrame()
    if not deposits.empty:
        deposits_tmp = deposits.copy()
        deposits_tmp["balance"] = pd.to_numeric(deposits_tmp["balance"], errors="coerce").fillna(0)
        deposit_by_branch = (
            deposits_tmp.groupby("branch_id", as_index=False)["balance"]
            .sum()
            .rename(columns={"balance": "예적금 총액"})
        )
        deposit_by_branch["지점"] = deposit_by_branch["branch_id"].map(branch_map).fillna(
            deposit_by_branch["branch_id"].astype(str)
        )

    # 지점별 대출
    loan_by_branch = pd.DataFrame()
    if not loans.empty:
        loans_tmp = loans.copy()
        loans_tmp["loan_amount"] = pd.to_numeric(loans_tmp["loan_amount"], errors="coerce").fillna(0)
        loan_by_branch = (
            loans_tmp.groupby("branch_id", as_index=False)["loan_amount"]
            .sum()
            .rename(columns={"loan_amount": "대출 총액"})
        )
        loan_by_branch["지점"] = loan_by_branch["branch_id"].map(branch_map).fillna(
            loan_by_branch["branch_id"].astype(str)
        )

    r1, r2 = st.columns(2)
    with r1:
        st.subheader("지점별 조합원 수")
        if not member_by_branch.empty:
            fig = px.bar(member_by_branch, x="지점", y="조합원 수", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("표시할 조합원 데이터가 없습니다.")

    with r2:
        st.subheader("지점별 예적금 총액")
        if not deposit_by_branch.empty:
            fig = px.bar(deposit_by_branch, x="지점", y="예적금 총액", text_auto=".3s")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("표시할 예적금 데이터가 없습니다.")

    st.subheader("지점별 대출 총액")
    if not loan_by_branch.empty:
        fig = px.bar(loan_by_branch, x="지점", y="대출 총액", text_auto=".3s")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("표시할 대출 데이터가 없습니다.")

    st.divider()
    st.subheader("최근 데이터")
    t1, t2, t3 = st.tabs(["조합원", "예적금", "대출"])
    with t1:
        st.dataframe(members.tail(10), use_container_width=True, hide_index=True)
    with t2:
        st.dataframe(deposits.tail(10), use_container_width=True, hide_index=True)
    with t3:
        st.dataframe(loans.tail(10), use_container_width=True, hide_index=True)

# -----------------------------
# 조합원 관리
# -----------------------------
elif menu == "조합원 관리":
    st.title("👥 조합원 관리")

    view_tab, add_tab, edit_tab, delete_tab = st.tabs(["조회", "등록", "수정", "삭제"])

    with view_tab:
        keyword = st.text_input("이름 또는 전화번호 검색")
        df = members.copy()
        if keyword and not df.empty:
            mask = (
                df["name"].astype(str).str.contains(keyword, case=False, na=False)
                | df["phone"].astype(str).str.contains(keyword, case=False, na=False)
            )
            df = df[mask]
        if not df.empty and "branch_id" in df.columns:
            df["branch_name"] = df["branch_id"].map(branch_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with add_tab:
        with st.form("member_add_form", clear_on_submit=True):
            name = st.text_input("이름")
            birth_date = st.date_input("생년월일", value=date(1990, 1, 1))
            gender = st.selectbox("성별", ["남", "여"])
            join_date = st.date_input("가입일", value=date.today())
            branch_name = st.selectbox("지점", list(branch_map.values()))
            phone = st.text_input("전화번호")
            submitted = st.form_submit_button("조합원 등록", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("이름을 입력하세요.")
            else:
                branch_id = next(k for k, v in branch_map.items() if v == branch_name)
                payload = {
                    "name": name.strip(),
                    "birth_date": birth_date.isoformat(),
                    "gender": gender,
                    "join_date": join_date.isoformat(),
                    "branch_id": int(branch_id),
                    "phone": phone.strip(),
                }
                try:
                    supabase.table("members").insert(payload).execute()
                    st.success("조합원이 등록되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"등록 실패: {e}")

    with edit_tab:
        if members.empty:
            st.info("수정할 조합원이 없습니다.")
        else:
            member_ids = members["member_id"].tolist()
            selected_id = st.selectbox("조합원 ID", member_ids, key="member_edit_id")
            row = members[members["member_id"] == selected_id].iloc[0]

            with st.form("member_edit_form"):
                name = st.text_input("이름", value=str(row["name"]))
                birth_date = st.date_input("생년월일", value=pd.to_datetime(row["birth_date"]).date())
                gender_opts = ["남", "여"]
                current_gender = str(row["gender"]).strip()
                gender = st.selectbox("성별", gender_opts, index=gender_opts.index(current_gender) if current_gender in gender_opts else 0)
                join_date = st.date_input("가입일", value=pd.to_datetime(row["join_date"]).date())
                current_branch_name = branch_map.get(row["branch_id"], list(branch_map.values())[0])
                branch_values = list(branch_map.values())
                branch_name = st.selectbox("지점", branch_values, index=branch_values.index(current_branch_name))
                phone = st.text_input("전화번호", value=str(row["phone"]))
                submitted = st.form_submit_button("수정 저장", use_container_width=True)

            if submitted:
                branch_id = next(k for k, v in branch_map.items() if v == branch_name)
                payload = {
                    "name": name.strip(),
                    "birth_date": birth_date.isoformat(),
                    "gender": gender,
                    "join_date": join_date.isoformat(),
                    "branch_id": int(branch_id),
                    "phone": phone.strip(),
                }
                try:
                    supabase.table("members").update(payload).eq("member_id", int(selected_id)).execute()
                    st.success("조합원 정보가 수정되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    with delete_tab:
        if members.empty:
            st.info("삭제할 조합원이 없습니다.")
        else:
            selected_id = st.selectbox("삭제할 조합원 ID", members["member_id"].tolist(), key="member_delete_id")
            selected = members[members["member_id"] == selected_id].iloc[0]
            st.warning(f"삭제 대상: {selected['name']} / ID {selected_id}")
            confirm = st.checkbox("삭제를 확인합니다.", key="member_delete_confirm")
            if st.button("🗑️ 조합원 삭제", disabled=not confirm, type="primary"):
                try:
                    supabase.table("members").delete().eq("member_id", int(selected_id)).execute()
                    st.success("조합원이 삭제되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"삭제 실패: 관련 예적금/대출 데이터가 있으면 먼저 정리해야 할 수 있습니다. ({e})")

# -----------------------------
# 예적금 관리
# -----------------------------
elif menu == "예적금 관리":
    st.title("💰 예적금 관리")
    view_tab, add_tab, edit_tab, delete_tab = st.tabs(["조회", "등록", "수정", "삭제"])

    with view_tab:
        df = deposits.copy()
        if not df.empty:
            df["branch_name"] = df["branch_id"].map(branch_map)
            if not members.empty:
                member_name_map = dict(zip(members["member_id"], members["name"]))
                df["member_name"] = df["member_id"].map(member_name_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with add_tab:
        if members.empty:
            st.info("먼저 조합원을 등록하세요.")
        else:
            with st.form("deposit_add_form", clear_on_submit=True):
                member_id = st.selectbox("조합원 ID", members["member_id"].tolist())
                member_branch = int(members.loc[members["member_id"] == member_id, "branch_id"].iloc[0])
                account_type = st.selectbox("상품 유형", ["요구불예금", "정기예금", "적금"])
                open_date = st.date_input("개설일", value=date.today())
                balance = st.number_input("잔액", min_value=0.0, step=10000.0, format="%.0f")
                interest_rate = st.number_input("금리(%)", min_value=0.0, step=0.1, format="%.2f")
                submitted = st.form_submit_button("예적금 계좌 등록", use_container_width=True)

            if submitted:
                payload = {
                    "member_id": int(member_id),
                    "branch_id": member_branch,
                    "account_type": account_type,
                    "open_date": open_date.isoformat(),
                    "balance": float(balance),
                    "interest_rate": float(interest_rate),
                }
                try:
                    supabase.table("deposit_accounts").insert(payload).execute()
                    st.success("예적금 계좌가 등록되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"등록 실패: {e}")

    with edit_tab:
        if deposits.empty:
            st.info("수정할 계좌가 없습니다.")
        else:
            account_id = st.selectbox("계좌 ID", deposits["account_id"].tolist(), key="deposit_edit_id")
            row = deposits[deposits["account_id"] == account_id].iloc[0]
            with st.form("deposit_edit_form"):
                account_type = st.text_input("상품 유형", value=str(row["account_type"]))
                open_date = st.date_input("개설일", value=pd.to_datetime(row["open_date"]).date())
                balance = st.number_input("잔액", min_value=0.0, value=float(row["balance"]), step=10000.0, format="%.0f")
                interest_rate = st.number_input("금리(%)", min_value=0.0, value=float(row["interest_rate"]), step=0.1, format="%.2f")
                submitted = st.form_submit_button("수정 저장", use_container_width=True)

            if submitted:
                payload = {
                    "account_type": account_type.strip(),
                    "open_date": open_date.isoformat(),
                    "balance": float(balance),
                    "interest_rate": float(interest_rate),
                }
                try:
                    supabase.table("deposit_accounts").update(payload).eq("account_id", int(account_id)).execute()
                    st.success("예적금 정보가 수정되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    with delete_tab:
        if deposits.empty:
            st.info("삭제할 계좌가 없습니다.")
        else:
            account_id = st.selectbox("삭제할 계좌 ID", deposits["account_id"].tolist(), key="deposit_delete_id")
            confirm = st.checkbox("삭제를 확인합니다.", key="deposit_delete_confirm")
            if st.button("🗑️ 예적금 계좌 삭제", disabled=not confirm, type="primary"):
                try:
                    supabase.table("deposit_accounts").delete().eq("account_id", int(account_id)).execute()
                    st.success("예적금 계좌가 삭제되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"삭제 실패: 거래내역 등 참조 데이터가 있으면 먼저 정리해야 할 수 있습니다. ({e})")

# -----------------------------
# 대출 관리
# -----------------------------
elif menu == "대출 관리":
    st.title("🏦 대출 관리")
    view_tab, add_tab, edit_tab, delete_tab = st.tabs(["조회", "등록", "수정", "삭제"])

    with view_tab:
        df = loans.copy()
        if not df.empty:
            df["branch_name"] = df["branch_id"].map(branch_map)
            if not members.empty:
                member_name_map = dict(zip(members["member_id"], members["name"]))
                df["member_name"] = df["member_id"].map(member_name_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with add_tab:
        if members.empty:
            st.info("먼저 조합원을 등록하세요.")
        else:
            with st.form("loan_add_form", clear_on_submit=True):
                member_id = st.selectbox("조합원 ID", members["member_id"].tolist(), key="loan_add_member")
                member_branch = int(members.loc[members["member_id"] == member_id, "branch_id"].iloc[0])
                loan_type = st.selectbox("대출 유형", ["신용대출", "담보대출", "기타"])
                loan_amount = st.number_input("대출금액", min_value=0.0, step=100000.0, format="%.0f")
                interest_rate = st.number_input("금리(%)", min_value=0.0, step=0.1, format="%.2f", key="loan_add_rate")
                start_date = st.date_input("대출 시작일", value=date.today())
                due_date = st.date_input("만기일", value=date.today())
                status = st.selectbox("상태", ["정상", "연체", "상환완료"])
                submitted = st.form_submit_button("대출 등록", use_container_width=True)

            if submitted:
                if due_date < start_date:
                    st.error("만기일은 대출 시작일보다 빠를 수 없습니다.")
                else:
                    payload = {
                        "member_id": int(member_id),
                        "branch_id": member_branch,
                        "loan_type": loan_type,
                        "loan_amount": float(loan_amount),
                        "interest_rate": float(interest_rate),
                        "start_date": start_date.isoformat(),
                        "due_date": due_date.isoformat(),
                        "status": status,
                    }
                    try:
                        supabase.table("loans").insert(payload).execute()
                        st.success("대출이 등록되었습니다.")
                        refresh()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

    with edit_tab:
        if loans.empty:
            st.info("수정할 대출이 없습니다.")
        else:
            loan_id = st.selectbox("대출 ID", loans["loan_id"].tolist(), key="loan_edit_id")
            row = loans[loans["loan_id"] == loan_id].iloc[0]
            with st.form("loan_edit_form"):
                loan_type = st.text_input("대출 유형", value=str(row["loan_type"]))
                loan_amount = st.number_input("대출금액", min_value=0.0, value=float(row["loan_amount"]), step=100000.0, format="%.0f")
                interest_rate = st.number_input("금리(%)", min_value=0.0, value=float(row["interest_rate"]), step=0.1, format="%.2f", key="loan_edit_rate")
                start_date = st.date_input("대출 시작일", value=pd.to_datetime(row["start_date"]).date())
                due_date = st.date_input("만기일", value=pd.to_datetime(row["due_date"]).date())
                status_opts = ["정상", "연체", "상환완료"]
                current_status = str(row["status"])
                status = st.selectbox("상태", status_opts, index=status_opts.index(current_status) if current_status in status_opts else 0)
                submitted = st.form_submit_button("수정 저장", use_container_width=True)

            if submitted:
                payload = {
                    "loan_type": loan_type.strip(),
                    "loan_amount": float(loan_amount),
                    "interest_rate": float(interest_rate),
                    "start_date": start_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "status": status,
                }
                try:
                    supabase.table("loans").update(payload).eq("loan_id", int(loan_id)).execute()
                    st.success("대출 정보가 수정되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    with delete_tab:
        if loans.empty:
            st.info("삭제할 대출이 없습니다.")
        else:
            loan_id = st.selectbox("삭제할 대출 ID", loans["loan_id"].tolist(), key="loan_delete_id")
            confirm = st.checkbox("삭제를 확인합니다.", key="loan_delete_confirm")
            if st.button("🗑️ 대출 삭제", disabled=not confirm, type="primary"):
                try:
                    supabase.table("loans").delete().eq("loan_id", int(loan_id)).execute()
                    st.success("대출이 삭제되었습니다.")
                    refresh()
                except Exception as e:
                    st.error(f"삭제 실패: {e}")

# -----------------------------
# 거래내역
# -----------------------------
elif menu == "거래내역 조회":
    st.title("🧾 거래내역 조회")
    df = transactions.copy()

    if not df.empty:
        account_ids = ["전체"] + sorted(df["account_id"].dropna().unique().tolist())
        selected_account = st.selectbox("계좌 필터", account_ids)
        if selected_account != "전체":
            df = df[df["account_id"] == selected_account]

        if "transaction_date" in df.columns:
            df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
            df = df.sort_values("transaction_date", ascending=False)

    st.dataframe(df, use_container_width=True, hide_index=True)
