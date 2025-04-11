import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
from src.utils.log_manager import LogManager, LogCategory
from src.trading_logger import TradingLogger
from src.utils.logger import setup_logger

logger = setup_logger('trading_logger_test')

def test_trading_logger():
    """트레이딩 로거 테스트"""
    # 환경 변수 로드
    load_dotenv()
    
    # 필수 환경 변수 확인
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if not credentials_path:
        raise ValueError("GOOGLE_CREDENTIALS_PATH 환경 변수가 설정되지 않았습니다.")
    
    try:
        # TradingLogger 인스턴스 생성
        trading_logger = TradingLogger(credentials_path)
        
        # 테스트 데이터
        test_trade_data = {
            'symbol': 'BTC',
            'decision': {
                'action': '매수',
                'reason': '상승 추세 확인',
                'confidence': 0.85
            },
            'order_result': {
                'executed_price': 50000000,
                'quantity': 0.1,
                'fee': 500,
                'total_amount': 5000500
            }
        }
        
        test_asset_data = {
            'symbol': 'BTC',
            'balance': 0.1,
            'avg_buy_price': 50000000,
            'current_value': 5100000,
            'profit_loss_rate': 2.0,
            'krw_balance': 1000000
        }
        
        test_performance_data = {
            'symbol': 'BTC',
            'daily_roi': 2.0,
            'weekly_roi': 5.0,
            'monthly_roi': 10.0,
            'total_profit_loss': 100000,
            'win_rate': 0.65
        }
        
        test_decision_data = {
            'symbol': 'BTC',
            'decision': '매수',
            'target_price': 51000000,
            'stop_loss': 49000000,
            'confidence': 0.85,
            'reasons': ['상승 추세 확인', '거래량 증가'],
            'risk_factors': ['시장 변동성 높음']
        }
        
        # 각 로깅 함수 테스트
        trading_logger.log_trade(test_trade_data)
        trading_logger.log_asset_status(test_asset_data)
        trading_logger.log_performance(test_performance_data)
        trading_logger.log_decision(test_decision_data)
        
        logger.info("모든 테스트가 성공적으로 완료되었습니다.")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        raise

def test_query_trades():
    """매매 기록 조회 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # 로그 매니저 초기화
    log_manager = LogManager(base_dir="logs/trading_logger_test")
    
    # 트레이딩 로거 초기화
    trading_logger = TradingLogger(log_manager=log_manager)
    
    try:
        # 1. 대기 중인 주문 조회
        print("\n=== 대기 중인 주문 조회 ===")
        wait_orders = trading_logger.query_trades(
            conditions={"ID": "exec_20250410_234431_4da4957f"},
            sheet_name="decisions"
        )
        
        if wait_orders:
            # 첫 번째 대기 주문 선택
            target_order = wait_orders[0]
            order_id = target_order['ID']
            
            # 2. 주문 상태 업데이트
            print(f"\n=== 주문 상태 업데이트 (ID: {order_id}) ===")
            trading_logger.update_trade_record(
                conditions={'ID': order_id},
                updates={
                    "긴급도": "높음",  # 상태를 완료로 변경
                },
                sheet_name="decisions"
            )
            
    except Exception as e:
        print(f"테스트 중 에러 발생: {str(e)}")
        log_manager.log(
            category=LogCategory.ERROR,
            message="거래 기록 수정 테스트 실패",
            data={"error": str(e)}
        )

if __name__ == "__main__":
    test_query_trades() 