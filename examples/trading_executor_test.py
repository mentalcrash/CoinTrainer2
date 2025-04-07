import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading_executor import TradingExecutor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('trading_executor_test')

def test_trading_executor():
    """매매 실행 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # API 키 확인
    if not os.getenv('BITHUMB_API_KEY') or not os.getenv('BITHUMB_SECRET_KEY') or not os.getenv('OPENAI_API_KEY'):
        logger.error("API 키가 설정되지 않았습니다.")
        return
        
    # 매매 실행 객체 생성
    executor = TradingExecutor(
        bithumb_api_key=os.getenv('BITHUMB_API_KEY'),
        bithumb_secret_key=os.getenv('BITHUMB_SECRET_KEY'),
        openai_api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # 테스트할 심볼
    symbol = 'ETH'
    
    try:
        # 매매 실행
        logger.info(f"{symbol} 매매 실행 테스트 시작...")
        result = executor.execute_trade(
            symbol=symbol,
            max_age_hours=24,
            limit=5,
            dev_mode=False  # 실제 모드로 실행
        )
        
        if result['success']:
            logger.info(f"매매 실행 결과: {result}")
            
            if result['action'] == '관망':
                logger.info("관망 판단으로 매매를 실행하지 않았습니다.")
            else:
                logger.info(f"매매 종류: {result['action']}")
                logger.info(f"주문 결과: {result['order_result']}")
                logger.info(f"다음 매매 판단까지 대기 시간: {result['next_decision_time']}분")
        else:
            logger.error(f"매매 실행 실패: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        
if __name__ == '__main__':
    test_trading_executor() 