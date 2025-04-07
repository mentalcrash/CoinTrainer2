import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading_order import TradingOrder

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('trading_order_test')

def test_trading_order():
    """주문 처리 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # API 키 확인
    if not os.getenv('BITHUMB_API_KEY') or not os.getenv('BITHUMB_SECRET_KEY'):
        logger.error("API 키가 설정되지 않았습니다.")
        return
        
    # 주문 처리 객체 생성
    order = TradingOrder()
    
    # 테스트할 심볼
    symbol = 'BTC'
    
    try:
        # BTC 최소 단위 구매 테스트

        order_result = order.create_order(
            symbol=symbol,
            side='ask',
            order_type='market',
            price=0.00005,
        )

        print(order_result)
                
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        
if __name__ == '__main__':
    # 개발 모드 확인
    dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
    if dev_mode:
        logger.info("개발 모드로 실행됩니다.")
    
    test_trading_order() 