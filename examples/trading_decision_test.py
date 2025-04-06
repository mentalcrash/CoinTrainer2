import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.news import News
from src.trading_decision_maker import TradingDecisionMaker
from src.utils.logger import setup_logger

# 로거 설정
logger = setup_logger('trading_decision_test')

# .env 파일 로드
load_dotenv()

def test_trading_decision(dev_mode: bool = False):
    """매매 판단 테스트
    
    Args:
        dev_mode: 개발 모드 여부 (True일 경우 API 호출 없이 더미 데이터 사용)
    """
    try:
        # API 키 확인 (개발 모드가 아닐 때만)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        bithumb_api_key = os.getenv("BITHUMB_API_KEY")
        bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")
        
        if not dev_mode and not openai_api_key:
            logger.error("OPENAI_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)
            
        if not dev_mode and (not bithumb_api_key or not bithumb_secret_key):
            logger.error("BITHUMB_API_KEY 또는 BITHUMB_SECRET_KEY가 설정되지 않았습니다.")
            sys.exit(1)
            
        # News와 TradingDecisionMaker 인스턴스 생성
        logger.info("뉴스 수집기와 매매 판단기 초기화...")
        decision_maker = TradingDecisionMaker(
            bithumb_api_key=bithumb_api_key,
            bithumb_secret_key=bithumb_secret_key,
            openai_api_key=openai_api_key
        )
        
        # BTC 매매 판단
        symbol = "BTC"
        logger.info(f"{symbol} 매매 판단 시작...")
        
        # 매매 판단 실행
        logger.info(f"{symbol} 매매 판단 분석 중...")
        try:
            result = decision_maker.make_decision(
                symbol=symbol,
                dev_mode=dev_mode
            )
            
            if result["success"]:
                logger.info(f"{symbol} 매매 판단 완료")
                # 결과 출력
                print("\n" + "=" * 80)
                print(decision_maker.format_decision(result))
                print("=" * 80 + "\n")
            else:
                logger.error(f"{symbol} 매매 판단 실패: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"매매 판단 중 오류 발생: {str(e)}", exc_info=True)
            
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    # 환경 변수로 개발 모드 설정
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    test_trading_decision(dev_mode) 