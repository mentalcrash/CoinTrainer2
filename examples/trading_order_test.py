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
        # BTC 시장가 매도 테스트
        volume = 0.00005  # BTC 매도 수량
        
        logger.info(f"{symbol} 시장가 매도 주문 시도 (수량: {volume} BTC)...")
        order_result = order.create_order(
            symbol=symbol,
            side='ask',
            order_type='market',
            volume=volume
        )
        
        if order_result:
            order_id = order_result.get('uuid')
            logger.info(f"주문 생성 완료: {order_result}")
            
            # 주문 조회
            logger.info(f"주문 조회 중...")
            order_info = order.get_order(symbol, order_id)
            if order_info:
                logger.info(f"주문 정보: {order_info}")
                
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        
if __name__ == '__main__':
    # 개발 모드 확인
    dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
    if dev_mode:
        logger.info("개발 모드로 실행됩니다.")
    
    test_trading_order() 