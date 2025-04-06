import ccxt
import time
import schedule
import config
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import hashlib
import hmac
import urllib.parse
import json

class BithumbTrader:
    def __init__(self):
        self.exchange = ccxt.bithumb({
            'apiKey': config.API_KEY,
            'secret': config.SECRET_KEY,
        })
        self.symbol = config.SYMBOL.replace('/', '_')  # BTC/KRW -> BTC_KRW
        
    def _create_signature(self, endpoint, params):
        """빗썸 API 서명 생성"""
        endpoint_url = f"/{config.BITHUMB_API_VERSION}/{endpoint}"
        query_string = urllib.parse.urlencode(params)
        
        message = endpoint_url + chr(0) + query_string + chr(0) + str(int(time.time() * 1000))
        signature = hmac.new(config.SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha512).hexdigest()
        return signature

    def get_balance(self):
        """계좌 잔고 조회"""
        try:
            endpoint = "account/balance"
            params = {
                'currency': self.symbol.split('_')[0]
            }
            
            headers = {
                'Api-Key': config.API_KEY,
                'Api-Sign': self._create_signature(endpoint, params),
                'Api-Nonce': str(int(time.time() * 1000))
            }
            
            response = requests.get(
                f"{config.BITHUMB_API_URL}/{config.BITHUMB_API_VERSION}/{endpoint}",
                params=params,
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()['data']
            return None
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {e}")
            return None

    def get_ticker(self):
        """현재가 조회"""
        try:
            response = requests.get(
                f"{config.BITHUMB_API_URL}/public/ticker/{self.symbol}"
            )
            if response.status_code == 200:
                data = response.json()['data']
                return {
                    'last': float(data['closing_price']),
                    'open': float(data['opening_price']),
                    'high': float(data['max_price']),
                    'low': float(data['min_price']),
                    'volume': float(data['units_traded'])
                }
            return None
        except Exception as e:
            print(f"현재가 조회 중 오류 발생: {e}")
            return None

    def get_candlestick(self, interval='24h'):
        """캔들스틱 데이터 조회"""
        try:
            response = requests.get(
                f"{config.BITHUMB_API_URL}/public/candlestick/{self.symbol}/{interval}"
            )
            if response.status_code == 200:
                data = response.json()['data']
                return data
            return None
        except Exception as e:
            print(f"캔들스틱 데이터 조회 중 오류 발생: {e}")
            return None

    def analyze_market(self):
        """시장 분석"""
        try:
            # 일봉 데이터 가져오기
            candles = self.get_candlestick('24h')
            if not candles:
                return None
                
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'close', 'high', 'low', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('timestamp')
            
            # 이동평균선 계산
            df['MA'] = df['close'].rolling(window=config.MOVING_AVERAGE_PERIOD).mean()
            
            return df
        except Exception as e:
            print(f"시장 분석 중 오류 발생: {e}")
            return None

    def execute_strategy(self):
        """매매 전략 실행"""
        try:
            df = self.analyze_market()
            if df is None:
                return
            
            current_price = self.get_ticker()['last']
            ma = df['MA'].iloc[-1]
            
            # 간단한 이동평균선 돌파 전략
            if current_price > ma:
                print(f"매수 신호: 현재가({current_price}) > 이동평균선({ma})")
                # TODO: 실제 매수 로직 구현
            elif current_price < ma:
                print(f"매도 신호: 현재가({current_price}) < 이동평균선({ma})")
                # TODO: 실제 매도 로직 구현
                
        except Exception as e:
            print(f"전략 실행 중 오류 발생: {e}")

def main():
    trader = BithumbTrader()
    
    def job():
        print(f"\n=== 자동매매 실행 ({datetime.now()}) ===")
        trader.execute_strategy()
    
    # 1분마다 전략 실행
    schedule.every(1).minutes.do(job)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"오류 발생: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main() 