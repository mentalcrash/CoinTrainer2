import sys
import os
import time
from datetime import datetime
import logging
import threading

# 프로젝트 루트 경로 추가 (기존 코드 유지)
# sys.path.append(...) 

from src.new.scalping_trader import ScalpingTrader # ScalpingTrader 임포트 확인

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

        # 파일 핸들러 설정
        file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)

        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        # 콘솔에는 조금 더 간결한 포맷 사용 가능
        console_formatter = logging.Formatter("[%(threadName)s] [%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        logging.info("통합 로깅 설정 완료. 로그 파일: %s", log_filename)

def run_trader(symbol: str):
    """지정된 심볼에 대한 ScalpingTrader를 실행합니다."""
    
    # 이제 run_trader 내에서는 로깅 설정을 하지 않습니다.
    # 대신 설정된 전역 로거를 사용합니다.
    logger = logging.getLogger() # 루트 로거를 가져옵니다.

    logger.info(f"ScalpingTrader 스레드 시작 (Market: KRW-{symbol})")
    try:
        # ScalpingTrader는 내부적으로 logging 모듈을 사용한다고 가정합니다.
        # 만약 특정 로거 인스턴스를 전달해야 한다면, setup_logging에서 생성한 로거를 전달할 수 있습니다.
        # logger = logging.getLogger(threading.current_thread().name) # 이렇게 스레드별 로거를 가져와 전달해도 됩니다.
        scalping_trader = ScalpingTrader(market=f"KRW-{symbol}") 
        scalping_trader.run_forever()
    except Exception as e:
        # 오류 발생 시 스레드 이름과 심볼 정보를 포함하여 로깅
        logger.error(f"KRW-{symbol} 트레이더 실행 중 오류 발생: {e}", exc_info=True)
    finally:
        logger.info(f"ScalpingTrader 스레드 종료 (Market: KRW-{symbol})")

def main():
    """메인 실행 함수"""
    
    # 처리할 심볼 리스트 정의
    symbols = ["AERGO", "ARDR", "STRAX", "ARK", "DOGE", "LAYER", "GAS", "KERNEL", "WCT"] # 예시 심볼, 필요에 따라 수정하세요

    # 로깅 설정 호출 (스레드 시작 전)
    setup_logging()

    logging.info(f"총 {len(symbols)}개의 심볼에 대해 스캘핑 트레이더를 시작합니다: {', '.join(symbols)}")

    threads = []
    for symbol in symbols:
        # 각 심볼에 대해 스레드 생성 (스레드 이름 지정 중요!)
        thread_name = f"Trader-{symbol}" 
        thread = threading.Thread(target=run_trader, args=(symbol,), name=thread_name)
        threads.append(thread)
        thread.start() # 스레드 시작
        # time.sleep(1) # 필요 시 API 요청 분산을 위한 딜레이

    # 모든 스레드가 종료될 때까지 대기
    for thread in threads:
        thread.join()

    logging.info("모든 트레이더 스레드가 종료되었습니다.")

if __name__ == "__main__":
    main()