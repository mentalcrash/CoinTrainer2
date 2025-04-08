import os
import logging
from dotenv import load_dotenv

from src.trading_executor import TradingExecutor
from src.discord_notifier import DiscordNotifier
from src.trading_scheduler import TradingScheduler
from src.utils.log_manager import LogManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_trading_scheduler():
    """트레이딩 스케줄러 테스트"""
    # 환경 변수 로드
    load_dotenv()

    # API 키 확인
    bithumb_api_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not all([bithumb_api_key, bithumb_secret_key, openai_api_key, discord_webhook_url]):
        raise ValueError("필요한 환경 변수가 설정되지 않았습니다.")

    try:
        # LogManager 생성
        log_manager = LogManager(base_dir="logs/trading_test")  # 테스트용 로그 디렉토리 지정

        # TradingExecutor 생성
        trading_executor = TradingExecutor(
            bithumb_api_key=bithumb_api_key,
            bithumb_secret_key=bithumb_secret_key,
            openai_api_key=openai_api_key,
            log_manager=log_manager
        )

        # DiscordNotifier 생성
        discord_notifier = DiscordNotifier(discord_webhook_url)

        # TradingScheduler 생성
        scheduler = TradingScheduler(
            trading_executor=trading_executor,
            log_manager=log_manager,
            discord_notifier=discord_notifier,
            dev_mode=False  # 개발 모드로 실행
        )

        # 트레이딩 시작
        symbol = "XRP"  # 테스트용 심볼
        logger.info(f"{symbol} 자동 매매 스케줄러 테스트 시작...")
        
        # 스케줄러 시작
        scheduler.start(symbol)

    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
        if 'scheduler' in locals():
            scheduler.stop()

    except Exception as e:
        logger.error(f"에러 발생: {str(e)}")
        if 'scheduler' in locals():
            scheduler.stop()
        raise

if __name__ == "__main__":
    test_trading_scheduler() 