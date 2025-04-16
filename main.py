import logging
import os
from datetime import datetime
from src.new.scalping_trader import ScalpingTrader

def main():
    symbol = "AERGO"

    # 로그 디렉토리 설정
    log_dir = "logs/scalping"
    os.makedirs(log_dir, exist_ok=True)

    # 로그 파일 이름 설정 (예: 2025-04-16_21-30-AERGO.log)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_filename = f"{log_dir}/{timestamp}_{symbol}.log"

    # 로깅 설정: 파일 핸들러
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    # 로깅 설정: 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)

    # 루트 로거 설정
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

    # 트레이더 실행
    scalping_trader = ScalpingTrader(market=f"KRW-{symbol}")
    scalping_trader.run_forever()

if __name__ == "__main__":
    main()