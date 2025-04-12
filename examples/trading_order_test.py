import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading_order import TradingOrder
from src.trading_logger import LogManager, LogCategory

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
        
def test_get_order():
    """주문 조회 테스트"""
    
    # TradingOrder 객체 생성
    trading_order = TradingOrder(
        api_key=os.getenv('BITHUMB_API_KEY'),          # 실제 API 키로 교체
        secret_key=os.getenv('BITHUMB_SECRET_KEY'),    # 실제 Secret 키로 교체
    )
    
    try:
        # 주문 조회 테스트
        order_response = trading_order.get_order(
            order_id="C0106000001067036920"      # 실제 주문 ID로 교체
        )
        
        # 주문 정보 출력
        print("\n=== 주문 조회 결과 ===")
        print(f"주문 ID: {order_response.uuid}")
        print(f"주문 종류: {order_response.side}")
        print(f"주문 방식: {order_response.ord_type}")
        print(f"주문 상태: {order_response.state}")
        print(f"마켓: {order_response.market}")
        print(f"생성 시간: {order_response.created_at}")
        print(f"\n=== 주문 수량 정보 ===")
        print(f"주문 가격: {order_response.price}")
        print(f"주문 수량: {order_response.volume}")
        print(f"남은 수량: {order_response.remaining_volume}")
        print(f"체결된 수량: {order_response.executed_volume}")
        print(f"\n=== 수수료 정보 ===")
        print(f"예약된 수수료: {order_response.reserved_fee}")
        print(f"남은 수수료: {order_response.remaining_fee}")
        print(f"사용된 수수료: {order_response.paid_fee}")
        print(f"사용중인 비용: {order_response.locked}")
        print(f"\n=== 체결 정보 ===")
        print(f"체결 횟수: {order_response.trades_count}")
        
        if order_response.trades:
            print("\n체결 내역:")
            for trade in order_response.trades:
                print(f"- 체결 ID: {trade.uuid}")
                print(f"  마켓: {trade.market}")
                print(f"  가격: {trade.price}")
                print(f"  수량: {trade.volume}")
                print(f"  총액: {trade.funds}")
                print(f"  종류: {trade.side}")
                print(f"  시각: {trade.created_at}")
                print()
                
    except Exception as e:
        print(f"\n주문 조회 실패: {e}")

if __name__ == '__main__':
    # 개발 모드 확인
    dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
    if dev_mode:
        logger.info("개발 모드로 실행됩니다.")
    
    test_get_order() 