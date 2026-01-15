# 기상청 API를 통해 기상 데이터를 가져오는 서비스 모듈
from app.schemas.weather import ObservationStationInfo, WeatherData
from app.config.config import settings
import requests

def fetch_observation_station_info() -> dict[int, ObservationStationInfo]:
    """
    한반도 전체의 최신 지상 관측소(SFC) 정보 배열 반환(이름 및 기타 정보)

    Returns:
        관측소 정보 dict[int, ObservationStationInfo]: {station_id: ObservationStationInfo객체} 형태의 딕셔너리
    """
    url = settings.KMA_STATION_INFO_URL
    station_map = {}

    try:
        response = requests.get(url)
        response.encoding = 'euc-kr'

        if response.status_code == 200:
            raw_data = parse_kma_text_data(response.text)
            
            for parts in raw_data:
                # 데이터 유효성 검사 (최소 11개 필드 필요: STN_KO가 인덱스 10)
                if len(parts) < 11:
                    continue

                try:
                    # 데이터 매핑
                    # 0: STN_ID, 1: LON, 2: LAT, 10: STN_KO
                    station_id = int(parts[0])
                    station_info = ObservationStationInfo(
                        id=station_id,
                        longitude=float(parts[1]),
                        latitude=float(parts[2]),
                        station_name_ko=parts[10]
                    )
                    station_map[station_id] = station_info
                except (ValueError, IndexError):
                    continue
            
            # 데이터 일부 출력 (요구사항 2)
            print(f"✅ 관측소 정보 파싱 성공: {len(station_map)}개의 데이터 가져옴")
            if station_map:
                print("--- 관측소 정보 예시 (3개) ---")
                count = 0
                for info in station_map.values():
                    print(info)
                    count += 1
                    if count >= 3:
                        break
                print("------------------------------")
        else:
            print(f"Error: Status Code {response.status_code}")

    except Exception as e:
        print(f"Exception occurred in fetch_observation_station_info: {str(e)}")

    return station_map


def fetch_latest_weather_data() -> dict[int, WeatherData]:
    """
    최신 기상 데이터 가져오기 (기상청 API 활용)

    Returns:
        dict[int, WeatherData]: {station_id: WeatherData객체} 형태의 딕셔너리
    """
    url = settings.KMA_ASOS_URL

    try:
        response = requests.get(url)

        # ★ 중요: 한글 깨짐 방지를 위해 인코딩 설정 (EUC-KR)
        response.encoding = 'euc-kr'

        if response.status_code == 200:
            # response.json() 대신 텍스트 파싱 함수 호출
            raw_lines = parse_kma_text_data(response.text)
            parsed_data = []

            for parts in raw_lines:
                # 3. 데이터 유효성 검사 (컬럼 개수가 너무 적으면 데이터 아님)
                if len(parts) < 15:
                    continue

                # 4. 데이터 매핑 (제공해주신 주석 기준 인덱스 매핑)
                # 0:TM, 1:STN, 3:WS(풍속), 11:TA(기온), 13:HM(습도) ...
                try:
                    record = {
                        "observation_time": parts[0],  # TM: 관측시각
                        "station_id": int(parts[1]),  # STN: 지점번호
                        "wind_speed": float(parts[3]),  # WS: 풍속
                        "temperature": float(parts[11]),  # TA: 기온 (12번째 항목 -> 인덱스 11)
                        "humidity": float(parts[13]),  # HM: 상대습도 (14번째 항목 -> 인덱스 13)
                        "pressure": float(parts[7]),  # PA: 현지기압 (8번째 항목 -> 인덱스 7)
                    }
                    parsed_data.append(record)
                except (ValueError, IndexError):
                    continue

            # 파싱 결과 확인용 출력 TODO:(나중에 삭제)
            print(f"✅ 파싱 성공: {len(parsed_data)}개의 데이터 가져옴")
            if parsed_data:
                print(f"첫 번째 데이터 예시: {parsed_data[0]}")

            return parsed_data
        else:
            print(f"Error: Status Code {response.status_code}")
            return []

    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return []


def parse_kma_text_data(text_data):
    """
    기상청 텍스트 데이터를 파싱하여 공백으로 분리된 문자열 리스트의 리스트로 반환합니다.
    """
    data_list = []
    lines = text_data.splitlines()

    for line in lines:
        line = line.strip()

        # 1. #으로 시작하거나 빈 줄은 건너뜀 (헤더 및 꼬리말 제거)
        if not line or line.startswith('#'):
            continue

        # 2. 공백을 기준으로 데이터 분리
        parts = line.split()
        
        if parts:
            data_list.append(parts)

    return data_list