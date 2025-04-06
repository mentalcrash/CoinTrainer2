from src.candle import Candle
from datetime import datetime, timedelta
import json

def main():
    candle = Candle()
    
    # BTC 1분봉 조회
    minute_candles = candle.get_minute_candles(
        symbol="BTC",
        unit=1,
        count=10
    )
    print("\n=== BTC 1분봉 데이터 ===")
    print(json.dumps(minute_candles, indent=2, ensure_ascii=False))
    
    # BTC 일봉 조회 (원화 환산 포함)
    daily_candles = candle.get_daily_candles(
        symbol="BTC",
        count=5,
        converting_price_unit="KRW"
    )
    print("\n=== BTC 일봉 데이터 ===")
    print(json.dumps(daily_candles, indent=2, ensure_ascii=False))
    
    # BTC 주봉 조회
    weekly_candles = candle.get_weekly_candles(
        symbol="BTC",
        count=3
    )
    print("\n=== BTC 주봉 데이터 ===")
    print(json.dumps(weekly_candles, indent=2, ensure_ascii=False))
    
    # BTC 월봉 조회
    monthly_candles = candle.get_monthly_candles(
        symbol="BTC",
        count=3
    )
    print("\n=== BTC 월봉 데이터 ===")
    print(json.dumps(monthly_candles, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main() 