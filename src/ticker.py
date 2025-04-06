import requests
from typing import Dict, Optional
from datetime import datetime

class Ticker:
    def __init__(self):
        """빗썸 시세 조회 클래스 초기화"""
        self.base_url = "https://api.bithumb.com"
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """특정 심볼의 현재가 정보 조회
        
        Args:
            symbol (str): 심볼 (예: "BTC")
            
        Returns:
            Optional[Dict]: 
                성공시: {
                    'market': str,              # 종목 구분 코드
                    'trade_date': str,          # 최근 거래 일자(UTC)
                    'trade_time': str,          # 최근 거래 시각(UTC)
                    'trade_date_kst': str,      # 최근 거래 일자(KST)
                    'trade_time_kst': str,      # 최근 거래 시각(KST)
                    'opening_price': float,     # 시가
                    'high_price': float,        # 고가
                    'low_price': float,         # 저가
                    'trade_price': float,       # 종가(현재가)
                    'prev_closing_price': float,# 전일 종가
                    'change': str,              # EVEN: 보합, RISE: 상승, FALL: 하락
                    'change_price': float,      # 변화액의 절대값
                    'change_rate': float,       # 변화율의 절대값
                    'signed_change_price': float,# 부호가 있는 변화액
                    'signed_change_rate': float,# 부호가 있는 변화율
                    'trade_volume': float,      # 가장 최근 거래량
                    'acc_trade_volume': float,  # 누적 거래량
                    'acc_trade_volume_24h': float,  # 24시간 누적 거래량
                    'acc_trade_price': float,   # 누적 거래대금
                    'acc_trade_price_24h': float,   # 24시간 누적 거래대금
                    'highest_52_week_price': float, # 52주 신고가
                    'highest_52_week_date': str,    # 52주 신고가 달성일
                    'lowest_52_week_price': float,  # 52주 신저가
                    'lowest_52_week_date': str,     # 52주 신저가 달성일
                    'timestamp': int            # 타임스탬프
                }
                실패시: None
        """
        try:
            url = f"{self.base_url}/v1/ticker"
            params = {'markets': f'KRW-{symbol}'}
            headers = {"accept": "application/json"}
            
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return self._format_ticker_data(data[0])
                else:
                    print(f"예상치 못한 응답 형식: {data}")
                    return None
            else:
                print(f"HTTP 오류: {response.status_code}")
                print(f"응답 내용: {response.text}")
                return None
                
        except Exception as e:
            print(f"시세 조회 중 오류 발생: {e}")
            return None
    
    def _format_ticker_data(self, data: Dict) -> Dict:
        """시세 데이터 포맷팅
        
        Args:
            data (Dict): API 응답 데이터
            
        Returns:
            Dict: 포맷팅된 시세 정보
        """
        return {
            'market': data['market'],
            'trade_date': data['trade_date'],
            'trade_time': data['trade_time'],
            'trade_date_kst': data['trade_date_kst'],
            'trade_time_kst': data['trade_time_kst'],
            'opening_price': float(data['opening_price']),
            'high_price': float(data['high_price']),
            'low_price': float(data['low_price']),
            'trade_price': float(data['trade_price']),
            'prev_closing_price': float(data['prev_closing_price']),
            'change': data['change'],
            'change_price': float(data['change_price']),
            'change_rate': float(data['change_rate']),
            'signed_change_price': float(data['signed_change_price']),
            'signed_change_rate': float(data['signed_change_rate']),
            'trade_volume': float(data['trade_volume']),
            'acc_trade_volume': float(data['acc_trade_volume']),
            'acc_trade_volume_24h': float(data['acc_trade_volume_24h']),
            'acc_trade_price': float(data['acc_trade_price']),
            'acc_trade_price_24h': float(data['acc_trade_price_24h']),
            'highest_52_week_price': float(data['highest_52_week_price']),
            'highest_52_week_date': data['highest_52_week_date'],
            'lowest_52_week_price': float(data['lowest_52_week_price']),
            'lowest_52_week_date': data['lowest_52_week_date'],
            'timestamp': int(data['timestamp'])
        } 