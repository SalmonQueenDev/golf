import time
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# 1. 크롤링 함수 (페이징 처리 포함)
# ---------------------------------------------------------
def fetch_golfpang_all_pages() -> list[dict]:
    """1페이지부터 끝 페이지까지 모든 골프장 데이터를 수집합니다."""
    url = "https://www.golfpang.com/web/round/special_tblList.do"
    
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": "PROJECT0_JSESSIONID=3669D2F5ED539DF736C9160C6CB8C93B.jvm1; PCID=17883204134917083351605;", 
        "Host": "www.golfpang.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    all_results = []
    
    for page in range(1, 21):
        payload = {
            "pageNum": str(page),
            "bkOrder": "",
            "sector": "",
            "club_name": "",
            "idx": "",
            "rd_status": "0",
            "scroll": "0",
            "param": "",
            "chnr_type_cd": ""
        }

        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select('table.type11 tbody tr')
            
            if not rows:
                break
                
            for row in rows:
                name_tag = row.select_one('span.golf')
                if not name_tag:
                    continue
                    
                name = name_tag.text.strip()
                weekday_str = row.select_one('span.weekdays').text.strip().replace(',', '')
                weekend_str = row.select_one('span.weekend').text.strip().replace(',', '')
                
                weekday_price = int(weekday_str) if weekday_str.isdigit() else 0
                weekend_price = int(weekend_str) if weekend_str.isdigit() else 0
                
                if weekday_price > 0 or weekend_price > 0:
                    all_results.append({
                        "골프장명": name,
                        "주중그린피": weekday_price,
                        "주말그린피": weekend_price,
                        "기본카트비": 100000, 
                        "기본캐디피": 150000  
                    })
            
            time.sleep(0.5)

        except Exception as e:
            st.error(f"데이터 수집 중 오류 발생: {e}")
            break
            
    return all_results

# ---------------------------------------------------------
# 2. 비용 계산 및 지도 링크 생성 함수
# ---------------------------------------------------------
def calculate_total_costs(courses: list[dict], team_size: int) -> pd.DataFrame:
    """1인당 카트비/캐디피를 분할하여 실결제 총비용 및 지도 검색 링크를 산출합니다."""
    df = pd.DataFrame(courses)
    if df.empty:
        return df

    df["1인_카트비"] = df["기본카트비"] / team_size
    df["1인_캐디피"] = df["기본캐디피"] / team_size
    
    df["주중_총비용(1인)"] = df["주중그린피"] + df["1인_카트비"] + df["1인_캐디피"]
    df["주말_총비용(1인)"] = df["주말그린피"] + df["1인_카트비"] + df["1인_캐디피"]

    # 이름에서 대괄호 '[' ']' 를 제거하여 검색 정확도 향상
    clean_names = df['골프장명'].str.replace('[', '', regex=False).str.replace(']', '', regex=False)
    # 네이버 지도 검색 URL 생성
    df['지도보기'] = "https://map.naver.com/v5/search/" + clean_names + "%20골프장"

    columns = [
        "골프장명", "주중그린피", "주말그린피", 
        "1인_카트비", "1인_캐디피", 
        "주중_총비용(1인)", "주말_총비용(1인)", "지도보기"
    ]
    return df[columns].sort_values(by="주중_총비용(1인)", ascending=True).reset_index(drop=True)

# ---------------------------------------------------------
# 3. Streamlit GUI 화면 구성
# ---------------------------------------------------------
st.set_page_config(page_title="실시간 골프장 가격 비교", page_icon="⛳", layout="wide")

if "raw_data" not in st.session_state:
    st.session_state.raw_data = []

st.title("⛳ 실시간 골프장 1인 총비용 비교")
st.markdown("데이터를 한 번 수집한 후에는 **인원수를 변경해도 실시간으로 즉각 계산**됩니다.")

with st.sidebar:
    st.header("🔍 설정 및 수집")
    
    if st.button("🔄 실시간 데이터 긁어오기", type="primary"):
        with st.spinner("웹사이트에서 데이터를 수집 중입니다..."):
            st.session_state.raw_data = fetch_golfpang_all_pages()
            st.success("데이터 수집 완료!")
            
    st.divider()
    
    team_size = st.slider(
        "👥 현재 팀 인원 설정", 
        min_value=1, max_value=4, value=4, 
        help="인원을 변경하면 1인당 부담할 카트비와 캐디피가 즉시 재계산됩니다."
    )

if st.session_state.raw_data:
    result_df = calculate_total_costs(st.session_state.raw_data, team_size)
    
    if not result_df.empty:
        st.subheader("🏆 현재 조건 최저가 골프장")
        
        min_weekday_idx = result_df['주중_총비용(1인)'].idxmin()
        min_weekend_idx = result_df['주말_총비용(1인)'].idxmin()
        
        cheapest_weekday = result_df.iloc[min_weekday_idx]
        cheapest_weekend = result_df.iloc[min_weekend_idx]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="☀️ 주중 최저가 (1인 총액)", 
                value=f"{cheapest_weekday['주중_총비용(1인)']:,.0f} 원",
                delta=cheapest_weekday['골프장명'],
                delta_color="off"
            )
        with col2:
            st.metric(
                label="🌈 주말 최저가 (1인 총액)", 
                value=f"{cheapest_weekend['주말_총비용(1인)']:,.0f} 원",
                delta=cheapest_weekend['골프장명'],
                delta_color="off"
            )
            
        st.divider()
        st.write(f"총 **{len(result_df)}**개의 골프장 데이터가 있습니다. (단위: 원)")
        
        format_mapping = {
            "주중그린피": "{:,.0f}",
            "주말그린피": "{:,.0f}",
            "1인_카트비": "{:,.0f}",
            "1인_캐디피": "{:,.0f}",
            "주중_총비용(1인)": "{:,.0f}",
            "주말_총비용(1인)": "{:,.0f}"
        }
        
        # 글자색과 배경색을 동시에 지정하여 가독성 개선
        def highlight_min_custom(s):
            is_min = s == s.min()
            return ['background-color: #FFE600; color: black; font-weight: bold;' if v else '' for v in is_min]
        
        styled_df = result_df.style.format(format_mapping).apply(
            highlight_min_custom, 
            subset=["주중_총비용(1인)", "주말_총비용(1인)"]
        )
        
        # 표 출력 시 지도 링크를 클릭 가능한 버튼으로 설정
        st.dataframe(
            styled_df, 
            use_container_width=True, 
            height=600,
            column_config={
                "지도보기": st.column_config.LinkColumn(
                    "🗺️ 위치 확인", 
                    help="클릭하면 네이버 지도로 이동하여 위치를 확인합니다.",
                    display_text="지도 열기 📍"
                )
            }
        )
else:
    st.info("👈 왼쪽 사이드바에서 '실시간 데이터 긁어오기' 버튼을 눌러주세요.")
