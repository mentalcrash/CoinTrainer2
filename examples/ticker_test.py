import os
import sys
from datetime import datetime
from tabulate import tabulate

# src 디렉토리를 파이썬 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ticker import Ticker

def format_number(value: float) -> str:
    """숫자를 보기 좋게 포맷팅"""
    if abs(value) >= 1:
        return f"{value:,.2f}"
    else:
        return f"{value:.8f}"

def format_datetime(date: str, time: str) -> str:
    """날짜와 시간 문자열을 보기 좋게 포맷팅"""
    date_str = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    time_str = f"{time[:2]}:{time[2:4]}:{time[4:]}"
    return f"{date_str} {time_str}"

def test_ticker(symbol: str = "BTC"):
    """시세 정보 조회 테스트"""
    try:
        # Ticker 객체 생성
        ticker = Ticker()
        
        # 현재가 정보 조회
        print(f"\n=== {symbol} 현재가 정보 ===")
        price_info = ticker.get_current_price(symbol)
        
        if price_info:
            # 기본 정보
            basic_info = [
                ['종목코드', price_info['market']],
                ['거래시각(KST)', format_datetime(price_info['trade_date_kst'], price_info['trade_time_kst'])],
                ['현재가', format_number(price_info['trade_price'])],
                ['전일종가', format_number(price_info['prev_closing_price'])],
                ['변화량', f"{format_number(price_info['signed_change_price'])} ({price_info['signed_change_rate']}%)"],
                ['거래량(24h)', format_number(price_info['acc_trade_volume_24h'])],
                ['거래대금(24h)', f"₩{format_number(price_info['acc_trade_price_24h'])}"]
            ]
            print("\n[기본 정보]")
            print(tabulate(basic_info, tablefmt='grid'))
            
            # 가격 정보
            price_details = [
                ['시가', '고가', '저가', '현재가'],
                [
                    format_number(price_info['opening_price']),
                    format_number(price_info['high_price']),
                    format_number(price_info['low_price']),
                    format_number(price_info['trade_price'])
                ]
            ]
            print("\n[가격 정보]")
            print(tabulate(price_details, headers='firstrow', tablefmt='grid'))
            
            # 52주 정보
            week_52_info = [
                ['구분', '가격', '달성일'],
                ['52주 최고가', 
                 format_number(price_info['highest_52_week_price']),
                 price_info['highest_52_week_date']],
                ['52주 최저가',
                 format_number(price_info['lowest_52_week_price']),
                 price_info['lowest_52_week_date']]
            ]
            print("\n[52주 정보]")
            print(tabulate(week_52_info, headers='firstrow', tablefmt='grid'))
            
    except Exception as e:
        print(f"Error: 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    # BTC 시세 조회
    test_ticker("BTC")
    
    # XRP 시세 조회
    test_ticker("XRP") 