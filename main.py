
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회 KOBIS 일별 박스오피스")

# --------------------------------------------------
# 2. 한국 시간 기준으로 어제 날짜 계산
#    서버의 시간대가 달라도 한국 날짜를 기준으로 함
# --------------------------------------------------
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = (korea_now - timedelta(days=1)).date()

# API에는 YYYYMMDD 형식으로 전달
target_dt = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.subheader(f"📅 조회 날짜: {display_date}")
st.caption("한국 시간 기준 어제의 집계 결과입니다.")

# --------------------------------------------------
# 3. API 인증키 읽기
#    인증키를 코드에 직접 입력하지 않음
#    Streamlit Cloud의 Secrets에 KOBIS_KEY 등록 필요
# --------------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 인증키를 찾을 수 없습니다.")
    st.markdown("""
    **확인 방법**
    1. Streamlit Cloud에서 앱의 Settings를 엽니다.
    2. Secrets 메뉴로 이동합니다.
    3. `KOBIS_KEY`라는 이름으로 발급받은 인증키를 등록합니다.
    4. 저장한 뒤 앱을 다시 실행합니다.

    인증키의 이름과 대소문자가 정확히 일치하는지 확인하세요.
    """)
    st.stop()

# 인증키가 빈 문자열인지 확인
if not str(api_key).strip():
    st.error("🔑 KOBIS_KEY 값이 비어 있습니다.")
    st.info("Streamlit Cloud의 Secrets에 올바른 인증키를 입력하세요.")
    st.stop()

# --------------------------------------------------
# 4. KOBIS API 요청
#    params를 사용하면 URL에 날짜와 인증키가 자동으로 전달됨
# --------------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

try:
    response = requests.get(
        API_URL,
        params={
            "key": str(api_key).strip(),
            "targetDt": target_dt
        },
        timeout=20
    )

    # HTTP 오류가 있으면 예외 발생
    response.raise_for_status()

    # JSON 형식으로 응답 읽기
    data = response.json()

except requests.exceptions.Timeout:
    st.error("⏱️ KOBIS API 응답 시간이 초과되었습니다.")
    st.info("잠시 기다린 뒤 새로고침하거나 네트워크 상태를 확인하세요.")
    st.stop()

except requests.exceptions.RequestException:
    st.error("🌐 KOBIS API 서버에 연결하지 못했습니다.")
    st.info(
        "인터넷 연결, API 주소, KOBIS 서버 상태를 확인한 뒤 "
        "다시 시도하세요."
    )
    st.stop()

except ValueError:
    st.error("📄 API 응답을 JSON으로 해석할 수 없습니다.")
    st.info("KOBIS 서버 응답 상태를 확인한 뒤 다시 시도하세요.")
    st.stop()

# --------------------------------------------------
# 5. HTTP 상태코드가 200이어도 API 자체 오류인지 확인
#    인증키 오류 등은 faultInfo 상자로 반환될 수 있음
# --------------------------------------------------
if not isinstance(data, dict):
    st.error("API 응답의 형식이 올바르지 않습니다.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo", {})

    # 오류 메시지와 코드가 있으면 화면에 표시
    if isinstance(fault, dict):
        fault_code = fault.get("errorCode", "확인 불가")
        fault_message = fault.get("message", "상세 오류 메시지가 없습니다.")
    else:
        fault_code = "확인 불가"
        fault_message = str(fault)

    st.error("🚨 KOBIS API에서 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {fault_code}")
    st.write(f"**오류 내용:** {fault_message}")
    st.markdown("""
    **확인할 사항**
    - Secrets에 등록한 `KOBIS_KEY`가 정확한지 확인합니다.
    - 인증키가 발급 및 사용 가능한 상태인지 확인합니다.
    - API 요청 한도나 KOBIS 서버 상태를 확인합니다.
    """)
    st.stop()

# --------------------------------------------------
# 6. 영화 목록 가져오기
# --------------------------------------------------
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("박스오피스 결과를 찾을 수 없습니다.")
    st.info("KOBIS API 응답 구조와 서버 상태를 확인하세요.")
    st.stop()

movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not isinstance(movie_list, list) or len(movie_list) == 0:
    st.warning(f"{display_date}의 영화 목록이 비어 있습니다.")
    st.info("""
    다음 사항을 확인해 보세요.

    - 해당 날짜의 박스오피스 집계가 완료되었는지 확인합니다.
    - KOBIS 홈페이지에서 같은 날짜의 일별 박스오피스를 조회합니다.
    - API 응답에 영화 목록이 포함되어 있는지 확인합니다.
    """)
    st.stop()

# --------------------------------------------------
# 7. 데이터 정리
#    API 숫자 값은 문자열이므로 정수로 변환
# --------------------------------------------------
df = pd.DataFrame(movie_list)

# 화면에 필요한 열이 있는지 확인
required_columns = [
    "rank", "movieNm", "openDt",
    "audiCnt", "audiAcc", "scrnCnt"
]

missing_columns = [
    col for col in required_columns if col not in df.columns
]

if missing_columns:
    st.error("API 응답에 필요한 데이터가 일부 없습니다.")
    st.write("누락된 항목:", ", ".join(missing_columns))
    st.info("KOBIS API 응답 형식이 변경되었는지 확인하세요.")
    st.stop()

# 숫자 열은 잘못된 값이 있더라도 앱이 중단되지 않도록 변환
number_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for col in number_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 영화명과 개봉일이 비어 있을 때 표시할 기본값
df["movieNm"] = df["movieNm"].fillna("영화명 없음")
df["openDt"] = df["openDt"].fillna("")
df = df.sort_values("rank").reset_index(drop=True)

# --------------------------------------------------
# 8. 1위 영화 지표 카드 3개
# --------------------------------------------------
st.divider()
st.header("🏆 오늘의 주인공")

first_movie = df.iloc[0]

st.subheader(f"🥇 {first_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="당일 관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개"
    )

# --------------------------------------------------
# 9. 관객수 상위 5편 막대그래프
# --------------------------------------------------
st.divider()
st.header("📊 관객수 상위 5편")

top5 = df.nlargest(5, "audiCnt").copy()

# 영화명을 그래프의 세로축으로 사용
chart_df = top5[["movieNm", "audiCnt"]].copy()
chart_df = chart_df.sort_values("audiCnt", ascending=True)
chart_df = chart_df.set_index("movieNm")
chart_df = chart_df.rename(columns={"audiCnt": "당일 관객수"})

st.bar_chart(chart_df, x_label="당일 관객수(명)")

# --------------------------------------------------
# 10. 전체 박스오피스 표
# --------------------------------------------------
st.divider()
st.header("🎞️ 전체 박스오피스 순위")

# 화면에 표시할 열과 한국어 이름 지정
table_df = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 날짜와 숫자를 보기 좋게 표시
table_df["개봉일"] = table_df["개봉일"].replace("", "정보 없음")

for col in ["관객수", "누적관객", "스크린수"]:
    table_df[col] = table_df[col].map(lambda value: f"{value:,}")

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# 11. 데이터 출처 안내
# --------------------------------------------------
st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 일별 박스오피스 API"
)
  
