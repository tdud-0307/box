import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 설정 (타이틀, 레이아웃)
st.set_page_config(page_title="영화 박스오피스 순위", layout="wide")

st.title("🎬 영화 박스오피스 검색")
st.caption("영화진흥위원회(KOBIS) Open API 기반 데이터입니다.")


# 1. 한국 시간(KST) 기준 '어제' 날짜 계산 함수
def get_yesterday_kst_date():
    kst_tz = pytz.timezone("Asia/Seoul")
    now_kst = datetime.datetime.now(kst_tz)
    yesterday_kst = now_kst - datetime.timedelta(days=1)
    return yesterday_kst.date()


# 한국 시간 기준 어제 날짜 구하기 (달력 선택의 최대 가능 날짜)
max_selectable_date = get_yesterday_kst_date()

# 사이드바 설정: API 키 입력 및 날짜 선택 달력
st.sidebar.header("⚙️ 설정")
user_api_key = st.sidebar.text_input(
    "KOBIS API 키 입력",
    type="password",
    help="영화진흥위원회 오픈API에서 발급받은 키를 입력하세요.",
)

# 달력 선택기 (기본값: 어제 날짜, 선택 가능 최대 날짜: 어제)
selected_date = st.sidebar.date_input(
    "📅 조회할 날짜 선택",
    value=max_selectable_date,
    max_value=max_selectable_date,
    help="오늘 날짜는 아직 집계 전이므로 어제 날짜까지만 선택 가능합니다.",
)

# API 요청을 위한 YYYYMMDD 문자열 형태
target_date_str = selected_date.strftime("%Y%m%d")


# 2. API 데이터 호출 함수
@st.cache_data(ttl=3600)
def fetch_boxoffice_data(target_date, api_key):
    if not api_key:
        return None, "사이드바에 KOBIS API 키를 입력해 주세요."

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
                f"API 오류 발생: {error_message}\n(입력하신 API 키가 올바른지 확인해 주세요.)",
            )

        box_office_result = data.get("boxOfficeResult", {})
        daily_list = box_office_result.get("dailyBoxOfficeList", [])

        # 고른 날짜에 영화 목록이 비어서 오면 요구한 안내 메시지 반환
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

# API 키 입력 여부 확인
if not user_api_key:
    st.info("👈 왼쪽 사이드바에 KOBIS API 키를 입력하면 선택한 날짜의 박스오피스 순위를 조회할 수 있습니다.")
else:
    # 데이터 로딩
    daily_movies, error_msg = fetch_boxoffice_data(target_date_str, user_api_key)

    if error_msg:
        st.error("⚠️ 데이터를 불러오지 못했습니다.")
        st.warning(f"**확인 및 조치 사항:**\n- {error_msg}")
    else:
        df = pd.DataFrame(daily_movies)

        # API 응답값의 문자열 숫자를 수치형(int)으로 변환
        numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 3. 누적관객 100만 명 이상 영화명 옆에 🏆 이모지 붙이기
        df["movieNm_display"] = df.apply(
            lambda row: f"🏆 {row['movieNm']}" if row["audiAcc"] >= 1000000 else row["movieNm"],
            axis=1,
        )

        # 4. 순위 증감(rankInten) 화살표 표시 가공 (양수: 🔺 red, 음수: 🔻 blue, 0: -)
        def format_rank_inten(val):
            if val > 0:
                return f"🔺 +{val}"
            elif val < 0:
                return f"🔻 {val}"
            else:

                return "-"

        df["rankInten_display"] = df["rankInten"].apply(format_rank_inten)

        # 5. 1위 영화 지표 카드 출력
        st.markdown("---")
        st.subheader("🥇 해당 일자 1위 영화")

        top_movie = df.iloc[0]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="영화명", value=str(top_movie["movieNm_display"]))
        with col2:
            st.metric(label="일일 관객수", value=f"{top_movie['audiCnt']:,} 명")
        with col3:
            st.metric(label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명")

        st.markdown("---")

        # 6. 관객수 상위 5편 막대그래프 시각화
        st.subheader("📊 관객수 상위 5개 영화")
        top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
        top5_df = top5_df.rename(
            columns={"movieNm": "영화명", "audiCnt": "일일 관객수"}
        )
        top5_df = top5_df.set_index("영화명")

        st.bar_chart(top5_df)

        st.markdown("---")

        # 7. 전체 순위 표 출력 (순위 증감, 🏆 이모지 포함)
        st.subheader("📋 전체 순위표")

        display_df = df[
            [
                "rank",
                "rankInten_display",
                "movieNm_display",
                "openDt",
                "audiCnt",
                "audiAcc",
                "scrnCnt",
            ]
        ].copy()

        display_df.columns = [
            "순위",
            "순위 증감",
            "영화명",
            "개봉일",
            "관객수",
            "누적관객",
            "스크린수",
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "관객수": st.column_config.NumberColumn(format="%d명"),
                "누적관객": st.column_config.NumberColumn(format="%d명"),
                "스크린수": st.column_config.NumberColumn(format="%d개"),
            },
        )
