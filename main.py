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
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 100만 관객 트로피 표시
    df["movieNm_display"] = df.apply(
        lambda row: f"🏆 {row['movieNm']}" if row["audiAcc"] >= 1000000 else row["movieNm"],
        axis=1,
    )

    # 순위 증감 화살표
    def format_rank_inten(val):
        if val > 0:
            return f"🔺 +{val}"
        elif val < 0:
            return f"🔻 {val}"
        else:
            return "-"

    df["rankInten_display"] = df["rankInten"].apply(format_rank_inten)

    # 3. 1위 영화 지표 카드
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

    # 4. 박스오피스 대표 레드 색상을 적용한 고정 막대그래프
    st.subheader("📊 관객수 상위 5개 영화")
    top5_df = df.sort_values(by="audiCnt", ascending=False).head(5)[["movieNm", "audiCnt"]].copy()

    # Altair 그래프에 박스오피스 시네마 레드 색상 적용 (#E50914)
    chart = (
        alt.Chart(top5_df)
        .mark_bar(color=CINEMA_RED)
        .encode(
            x=alt.X("movieNm:N", sort=None, title="영화명", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("audiCnt:Q", title="일일 관객수(명)"),
            tooltip=[
                alt.Tooltip("movieNm:N", title="영화명"),
                alt.Tooltip("audiCnt:Q", title="일일 관객수", format=","),
            ],
        )
        .properties(height=350)
    )

    st.altair_chart(chart, use_container_width=True)

    st.markdown("---")

    # 5. 전체 TOP 10 순위 표 출력
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

    # 6. KOBIS 데이터 기반 효율성 분석 표
    st.markdown("---")
    st.subheader("📈 상영 및 관객 효율성 분석 (순위 표 하단)")

    total_top10_audi = df["audiCnt"].sum()

    analysis_df = df.copy()
    analysis_df["screen_efficiency"] = (analysis_df["audiCnt"] / analysis_df["scrnCnt"].replace(0, 1)).round(1)
    analysis_df["show_efficiency"] = (analysis_df["audiCnt"] / analysis_df["showCnt"].replace(0, 1)).round(1)
    analysis_df["share"] = ((analysis_df["audiCnt"] / total_top10_audi) * 100).round(1)

    calc_display_df = analysis_df[
        ["rank", "movieNm", "scrnCnt", "showCnt", "screen_efficiency", "show_efficiency", "share"]
    ].copy()

    calc_display_df.columns = [
        "순위",
        "영화명",
        "스크린수",
        "상영횟수",
        "스크린당 관객수",
        "1회 상영당 관객수",
        "TOP10 관객 점유율",
    ]

    st.dataframe(
        calc_display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "스크린수": st.column_config.NumberColumn(format="%d개"),
            "상영횟수": st.column_config.NumberColumn(format="%d회"),
            "스크린당 관객수": st.column_config.NumberColumn(format="%.1f명"),
            "1회 상영당 관객수": st.column_config.NumberColumn(format="%.1f명"),
            "TOP10 관객 점유율": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
