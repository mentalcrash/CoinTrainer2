from src.new.scalping_trader import ScalpingTrader
from src.new.strategy.strategy_generator import StrategyGenerator
import logging
import os
from datetime import datetime

# --- 전역 로깅 설정 ---
def setup_logging():
    """전체 애플리케이션 로깅을 설정합니다."""
    log_dir = "logs/scalping" # 통합 로그 디렉토리
    os.makedirs(log_dir, exist_ok=True)

    # 통합 로그 파일 이름 설정 (예: logs/scalping/traders_2025-04-16.log)
    # 날짜별로 파일을 생성하도록 변경
    log_filename = f"{log_dir}/traders_{datetime.now().strftime('%Y-%m-%d')}.log"

    # 로거 가져오기 (루트 로거 사용)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # 처리할 최소 로그 레벨 설정

    # 핸들러 중복 추가 방지
    if not logger.handlers:
        # 로그 포맷 설정 (스레드 이름 포함)
        # %(threadName)s 를 사용하여 로그를 발생시킨 스레드의 이름을 기록
        log_formatter = logging.Formatter(
            "[%(asctime)s] [%(threadName)s] %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        # 콘솔에는 조금 더 간결한 포맷 사용 가능
        console_formatter = logging.Formatter("[%(threadName)s] [%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        logging.info("통합 로깅 설정 완료. 로그 파일: %s", log_filename)

if __name__ == "__main__":
    setup_logging()
    scalping_trader = ScalpingTrader(market="KRW-XRP") 
    scalping_trader.run_forever()
    
    # strategy_generator = StrategyGenerator()
    # code = strategy_generator.generate_latest()
    # print(code)
    
    