import os
from dotenv import load_dotenv
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

if __name__ == "__main__":
    test_trading_logger() 