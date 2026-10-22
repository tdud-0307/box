import datetime
import requests
import pandas as pd
import pytz
import altair as alt
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="영화 박스오피스 순위", layout="wide")

# 영화관/박스오피스 대표 시네마 레드 컬러 정의
CINEMA_RED = "#E50914"

# 스타일 커스텀: 대표 색상을 활용한 메트릭 카드의 빨간 포인트 선 적용
st.markdown(
    f"""
    <style>
    div[data-testid="stMetric"] {{
        border-left: 4px solid {CINEMA_RED};
        padding-left: 12px;
        background-color: rgba(229, 9, 20, 0.03);
        border-radius: 4px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 영화 박스오피스 검색")
st.caption("영화진흥위원회(KOBIS) Open API 기반 데이터입니다.")


# 1. 한국 시간(KST) 기준 '어제' 날짜 계산 함수
def get_yesterday_kst_date():
    kst_tz = pytz.timezone("Asia/Seoul")
    now_kst = datetime.datetime.now(kst_tz)
    yesterday_kst = now_kst - datetime.timedelta(days=1)
    return yesterday_kst.date()


max_selectable_date = get_yesterday_kst_date()

# 사이드바 설정: 날짜 선택
st.sidebar.header("⚙️ 설정")
selected_date = st.sidebar.date_input(
    "📅 조회할 날짜 선택",
    value=max_selectable_date,
    max_value=max_selectable_date,
    help="오늘 날짜는 아직 집계 전이므로 어제 날짜까지만 선택할 수 있습니다.",
)

target_date_str = selected_date.strftime("%Y%m%d")


# 2. 박스오피스 API 데이터 호출 함수
@st.cache_data(ttl=3600)
def fetch_boxoffice_data(target_date):
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return (
            None,
            "Streamlit Secrets에 'KOBIS_KEY'가 설정되지 않았습니다. Secrets 설정을 확인해 주세요.",
        )

    if not api_key:
        return None, "API 키가 비어 있습니다. Secrets의 KOBIS_KEY 값을 확인해 주세요."

    url = f"https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={api_key}&targetDt={target_date}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return (
                None,
                f"서버 응답 오류 (상태 코드: {response.status_code}). 잠시 후 다시 시도해 주세요.",
            )

        data = response.json()

        if "faultInfo" in data:
            error_message = data["faultInfo"].get(
                "message", "인증키 또는 API 요청 오류가 발생했습니다."
            )
            return (
                None,
                f"API 오류 발생: {error_message}\n(Secrets에 설정된 KOBIS_KEY가 올바른지 확인해 주세요.)",
            )

        box_office_result = data.get("boxOfficeResult", {})
        daily_list = box_office_result.get("dailyBoxOfficeList", [])

        if not daily_list:
            return None, "그날은 아직 집계 전입니다."

        return daily_list, None

    except requests.exceptions.RequestException as e:
        return (
            None,
            f"네트워크 연결 오류가 발생했습니다: {e}\n인터넷 연결 상태를 확인해 주세요.",
        )
    except Exception as e:
        return None, f"데이터 처리 중 알 수 없는 오류가 발생했습니다: {e}"


# 선택된 날짜 화면 표시
formatted_date = selected_date.strftime("%Y년 %m월 %d일")
st.subheader(f"📅 기준일: {formatted_date}")

# 데이터 로딩
daily_movies, error_msg = fetch_boxoffice_data(target_date_str)

if error_msg:
    st.error("⚠️ 데이터를 불러오지 못했습니다.")
    st.warning(f"**확인 및 조치 사항:**\n- {error_msg}")
else:
    df = pd.DataFrame(daily_movies)

    # 문자열 숫자를 수치형(int)으로 변환
    numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df
