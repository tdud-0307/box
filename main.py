import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 설정 (타이틀, 레이아웃)
st.set_page_config(page_title="어제 박스오피스 순위", layout="wide")

st.title("🎬 어제의 영화 박스오피스 TOP 10")
st.caption("영화진흥위원회(KOBIS) Open API 기반 데이터입니다.")


# 1. 한국 시간(KST) 기준 '어제' 날짜 계산 함수
def get_yesterday_kst():
    # 배포 서버의 시계가 해외 기준일 수 있으므로 Asia/Seoul 타임존을 명시 적용
    kst_tz = pytz.timezone("Asia/Seoul")
    now_kst = datetime.datetime.now(kst_tz)
    yesterday_kst = now_kst - datetime.timedelta(days=1)
    # yyyymmdd 8자리 문자열 형식으로 변환 (예: '20261020')
    return yesterday_kst.strftime("%Y%m%d")


# 2. API 데이터 호출 함수
@st.cache_data(ttl=3600)  # 1시간 동안 API 호출 결과를 캐싱하여 사용
def fetch_boxoffice_data(target_date):
    # Streamlit Secrets(비밀 금고)에서 KOBIS API 키 불러오기
    # .streamlit/secrets.toml 파일 또는 Streamlit Cloud Secrets에 설정 필요
    api_key = st.secrets.get("KOBIS_KEY")

    if not api_key:
        return None, "API 키(KOBIS_KEY)가 secrets에 설정되지 않았습니다."

    url = f"https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={api_key}&targetDt={target_date}"

    try:
        response = requests.get(url, timeout=10)
        # HTTP 응답 상태 코드가 200(성공)이 아닌 경우
        if response.status_code != 200:
            return (
                None,
                f"서버 응답 오류 (상태 코드: {response.status_code}). 잠시 후 다시 시도해 주세요.",
            )

        data = response.json()

        # KOBIS API 특성: 인증키 오류 등의 경우 faultInfo 개체가 반환됨
        if "faultInfo" in data:
            error_message = data["faultInfo"].get(
                "message", "인증키 또는 API 요청 오류가 발생했습니다."
            )
            return (
                None,
                f"API 오류 발생: {error_message}\n(Secrets의 KOBIS_KEY 값을 확인해 주세요.)",
            )

        # 박스오피스 목록 추출
        box_office_result = data.get("boxOfficeResult", {})
        daily_list = box_office_result.get("dailyBoxOfficeList", [])

        # 결과 목록이 비어있는 경우
        if not daily_list:
            return (
                None,
                f"조회된 영화 데이터가 없습니다 (조회 일자: {target_date}). 데이터 집계 중일 수 있습니다.",
            )

        return daily_list, None

    except requests.exceptions.RequestException as e:
        return (
            None,
            f"네트워크 연결 오류가 발생했습니다: {e}\n인터넷 연결 상태를 확인해 주세요.",
        )
    except Exception as e:
        return None, f"데이터 처리 중 알 수 없는 오류가 발생했습니다: {e}"


# 어제 날짜 구하기 및 화면 표시
target_date_str = get_yesterday_kst()
formatted_date = (
    f"{target_date_str[:4]}년 {target_date_str[4:6]}월 {target_date_str[6:]}일"
)
st.subheader(f"📅 기준일: {formatted_date}")

# 데이터 로딩
daily_movies, error_msg = fetch_boxoffice_data(target_date_str)

# 3. 에러 안내 또는 화면 출력
if error_msg:
    # 요청 실패, 키 오류, 데이터 공백 시 한국어 안내 상자 출력
    st.error("⚠️ 데이터를 불러오지 못했습니다.")
    st.warning(f"**확인 및 조치 사항:**\n- {error_msg}")
else:
    # 데이터프레임 생성
    df = pd.DataFrame(daily_movies)

    # API 응답값의 문자열 숫자를 정수(int)형으로 변환
    numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4. 1위 영화 지표 카드 (st.metric) 3개 크게 출력
    st.markdown("---")
    st.subheader("🥇 어제의 1위 영화")

    top_movie = df.iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="영화명", value=str(top_movie["movieNm"]))
    with col2:
        st.metric(
            label="일일 관객수", value=f"{top_movie['audiCnt']:,} 명"
        )
    with col3:
        st.metric(
            label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명"
        )

    st.markdown("---")

    # 5. 관객수 상위 5편 막대그래프 시각화
    st.subheader("📊 관객수 상위 5개 영화")
    top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
    top5_df = top5_df.rename(
        columns={"movieNm": "영화명", "audiCnt": "일일 관객수"}
    )
    top5_df = top5_df.set_index("영화명")

    # Streamlit 기본 막대그래프 출력
    st.bar_chart(top5_df)

    st.markdown("---")

    # 6. 전체 TOP 10 순위 표 출력
    st.subheader("📋 전체 순위표")

    # 필요한 컬럼만 추출 및 이름 변경
    display_df = df[
        ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
    ].copy()
    display_df.columns = [
        "순위",
        "영화명",
        "개봉일",
        "관객수",
        "누적관객",
        "스크린수",
    ]

    # 숫자 데이터 콤마(,) 서식 적용
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
