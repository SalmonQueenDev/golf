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
    
    # 1페이지부터 최대 20페이지까지 반복 (안전장치)
    for page in range(1, 21):
        # 첨부해주신 페이로드(Payload) 적용
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
            
            # 해당 페이지에 데이터가 없으면(끝 페이지 도달 시) 반복문 종료
            if not rows:
                break
                
            for row in rows:
                name_tag = row.select_one('span.golf')
                if not name_tag:
                    continue
                    
                name = name_tag.text.strip()
                weekday_str = row.select_one('span.weekdays').text.strip().replace(',', '')
                weekend_str = row.select_one('span.weekend').text.strip().replace(',', '')
                
                # 빈 값 처리 후 정수 변환
                weekday_price = int(weekday_str) if weekday_str.isdigit() else 0
                weekend_price = int(weekend_str) if weekend_str.isdigit() else 0
                
                all_results.append({
                    "골프장명": name,
                    "주중그린피": weekday_price,
                    "주말그린피": weekend_price,
                    "기본카트비": 100000, # 임의의 팀당 기본 카트비
                    "기본캐디피": 150000  # 임의의 팀당 기본 캐디피
                })
            
            # 서버에 부담을 주지 않기 위해 페이지 요청 간 0.5초 대기
            time.sleep(0.5)

        except Exception as e:
            st.error(f"데이터 수집 중 오류 발생 (페이지 {page}): {e}")
            break
            
    return all_results

# ---------------------------------------------------------
# 2. 비용 계산 함수
# ---------------------------------------------------------
def calculate_total_costs(courses: list[dict], team_size: int = 4) -> pd.DataFrame:
    """1인당 카트비/캐디피를 분할하여 실결제 총비용을 계산합니다."""
    df = pd.DataFrame(courses)
    if df.empty:
        return df

    # 1/N 계산
    df["1인_카트비"] = df["기본카트비"] / team_size
    df["1인_캐디피"] = df["기본캐디피"] / team_size
    
    # 1인 총비용 산출
    df["주중_총비용(1인)"] = df["주중그린피"] + df["1인_카트비"] + df["1인_캐디피"]
    df["주말_총비용(1인)"] = df["주말그린피"] + df["1인_카트비"] + df["1인_캐디피"]

    # 필요한 컬럼만 정리 및 주중 총비용 기준 오름차순 정렬
    columns = [
        "골프장명", "주중그린피", "주말그린피", 
        "1인_카트비", "1인_캐디피", 
        "주중_총비용(1인)", "주말_총비용(1인)"
    ]
    
    return df[columns].sort_values(by="주중_총비용(1인)", ascending=True).reset_index(drop=True)

# ---------------------------------------------------------
# 3. Streamlit GUI 화면 구성
# ---------------------------------------------------------
st.set_page_config(page_title="실시간 골프장 가격 비교", page_icon="⛳", layout="wide")

st.title("⛳ 실시간 골프장 1인 총비용 비교")
st.markdown("현재 웹사이트에 등록된 **모든 골프장의 데이터를 실시간으로 수집**하여, 카트비와 캐디피를 포함한 '진짜 1인당 총비용'을 계산합니다.")

with st.sidebar:
    st.header("🔍 검색 옵션")
    team_size = st.number_input("팀 인원 (명)", min_value=1, max_value=4, value=4)
    search_button = st.button("실시간 데이터 수집 및 비교", type="primary")

if search_button:
    with st.spinner("서버에서 모든 페이지의 데이터를 긁어오는 중입니다... (약 3~5초 소요)"):
        # 1. 크롤링 실행
        raw_data = fetch_golfpang_all_pages()
        
        if not raw_data:
            st.warning("수집된 데이터가 없습니다.")
        else:
            # 2. 비용 계산
            result_df = calculate_total_costs(raw_data, team_size=team_size)
            
            # 3. 화면 출력
            st.success(f"성공! 총 {len(result_df)}개의 골프장 데이터를 수집했습니다. (주중 총비용 저렴한 순)")
            
            # 금액 포맷팅 (보기 좋게 콤마 추가)
            format_mapping = {
                "주중그린피": "{:,.0f} 원",
                "주말그린피": "{:,.0f} 원",
                "1인_카트비": "{:,.0f} 원",
                "1인_캐디피": "{:,.0f} 원",
                "주중_총비용(1인)": "{:,.0f} 원",
                "주말_총비용(1인)": "{:,.0f} 원"
            }
            
            st.dataframe(
                result_df.style.format(format_mapping),
                use_container_width=True,
                height=600
            )