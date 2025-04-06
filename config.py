import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 거래소 설정
EXCHANGE = 'bithumb'  # 사용할 거래소
SYMBOL = 'BTC/KRW'  # 거래 페어

# API 키 설정
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

# 거래 설정
TRADE_AMOUNT = 100000  # 거래당 금액 (KRW)
PROFIT_PERCENT = 1.0   # 목표 수익률 (%)
STOP_LOSS_PERCENT = 1.0  # 손절률 (%)

# 기술적 지표 설정
MOVING_AVERAGE_PERIOD = 20  # 이동평균선 기간

# 빗썸 API 설정
BITHUMB_API_URL = 'https://api.bithumb.com'
BITHUMB_API_VERSION = 'v1' 