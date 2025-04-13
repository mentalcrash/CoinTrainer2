import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
import threading

# 상위 디렉토리의 모듈을 import 하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.log_manager import LogManager, LogCategory
from src.round.manager import RoundManager
from src.round.models import RoundStatus
from src.models.market_data import MarketOverview

def create_sample_market_data(current_price: float = 65000000) -> MarketOverview:
    """테스트용 시장 데이터를 생성합니다."""
    return MarketOverview(
        current_price=current_price,
        volume_trend_1m="상승",
        price_trend_1m="상승",
        candle_strength="강세",
        candle_body_ratio=0.8,
        rsi_1=65.5,
        rsi_3=62.3,
        rsi_7=58.7,
        rsi_14=55.2,
        ma1=current_price * 0.995,
        ma3=current_price * 0.99,
        ma5=current_price * 0.985,
        ma10=current_price * 0.98,
        volatility_3m=0.8,
        volatility_5m=1.2,
        volatility_10m=1.5,
        volatility_15m=1.8,
        vwap_3m=current_price * 1.002,
        bb_width=2.5,
        order_book_ratio=1.2,
        spread=0.15,
        premium_rate=0.25,
        funding_rate=0.01,
        price_stability="안정",
        new_high_5m=True,
        new_low_5m=False
    )

def test_round_creation():
    """라운드 생성 테스트"""
    print("\n=== 라운드 생성 테스트 ===")
    
    log_manager = LogManager(log_mode="console")
    round_manager = RoundManager(log_manager=log_manager)
    
    # 라운드 생성
    trading_round = round_manager.create_round(symbol="BTC")
    if not trading_round:
        print("❌ 라운드 생성 실패")
        return
        
    print(f"✅ 라운드 생성 성공 (ID: {trading_round.id})")
    print(f"- 심볼: {trading_round.symbol}")
    print(f"- 상태: {trading_round.status}")
    print(f"- 생성 시간: {trading_round.start_time}")

def test_round_watching():
    """라운드 관찰 및 GPT 매수 결정 테스트"""
    print("\n=== 라운드 관찰 테스트 ===")
    
    log_manager = LogManager(log_mode="console")
    log_manager.start_logging_thread()
    round_manager = RoundManager(log_manager=log_manager)
    
    # 라운드 생성
    trading_round = round_manager.create_round(symbol="XRP")
    if not trading_round:
        print("❌ 라운드 생성 실패")
        return
        
    print(f"✅ 라운드 생성됨 (ID: {trading_round.id})")
    
    # 관찰 시작
    if round_manager.start_watching(trading_round.id):
        print("✅ 라운드 관찰 시작")
        
        # 라운드 상태 확인
        round_info = round_manager.get_round_summary(trading_round.id)
        if round_info:
            print("\n[라운드 상태]")
            print(f"- 상태: {round_info['status']}")
            if round_info['status'] == RoundStatus.ENTRY_READY:
                print(f"- 목표가: {round_info['take_profit']:,.0f}")
                print(f"- 손절가: {round_info['stop_loss']:,.0f}")
    else:
        print("❌ 라운드 관찰 실패")

def test_round_lifecycle():
    """라운드 전체 수명주기 테스트"""
    print("\n=== 라운드 수명주기 테스트 ===")
    
    log_manager = LogManager(log_mode="console", console_format="detailed")
    log_manager.start_logging_thread()
    round_manager = RoundManager(log_manager=log_manager)
    
    # 1. 라운드 생성
    trading_round = round_manager.create_round(symbol="BTC")
    if not trading_round:
        print("❌ 라운드 생성 실패")
        return
        
    print(f"✅ 1. 라운드 생성됨 (ID: {trading_round.id})")
    
    # 2. 관찰 시작
    if not round_manager.start_watching(trading_round.id):
        print("❌ 관찰 시작 실패")
        return
        
    print("✅ 2. 관찰 시작")
    
    # 3. 상태 변경 테스트
    states_to_test = [
        (RoundStatus.ENTRY_READY, "매수 시그널 발생"),
        (RoundStatus.ENTRY_ORDERED, "매수 주문 발생"),
        (RoundStatus.HOLDING, "매수 체결"),
        (RoundStatus.EXIT_READY, "매도 시그널 발생"),
        (RoundStatus.EXIT_ORDERED, "매도 주문 발생"),
        (RoundStatus.COMPLETED, "매도 체결")
    ]
    
    for new_status, reason in states_to_test:
        if round_manager.update_round_status(trading_round.id, new_status, reason):
            print(f"✅ 상태 변경: {new_status} ({reason})")
            time.sleep(0.5)  # 상태 변경 간 딜레이
        else:
            print(f"❌ 상태 변경 실패: {new_status}")
            return
    
    # 4. 최종 상태 확인
    final_round = round_manager.get_round_summary(trading_round.id)
    if final_round:
        print("\n[최종 라운드 상태]")
        print(f"- 상태: {final_round['status']}")
        print(f"- 종료 사유: {final_round['exit_reason']}")
        print(f"- 소요 시간: {final_round['duration']}")

def test_entry_process():
    """매수 진입 프로세스 테스트"""
    print("\n=== 매수 진입 프로세스 테스트 ===")
    
    log_manager = LogManager(base_dir="logs/round_manager_test", log_mode="both", console_format="detailed")
    log_manager.start_logging_thread()
    round_manager = RoundManager(log_manager=log_manager)
    
    try:
        # 1. 라운드 생성
        trading_round = round_manager.create_round(symbol="BTC")
        if not trading_round:
            print("❌ 라운드 생성 실패")
            return
            
        print(f"✅ 1. 라운드 생성됨 (ID: {trading_round.id})")
        
        # 2. 관찰 시작 및 매수 시그널 대기
        if not round_manager.start_watching(trading_round.id):
            print("❌ 관찰 시작 실패")
            return
            
        print("✅ 2. 관찰 시작 및 매수 시그널 확인")
        
        # 3. 라운드 상태 확인
        round_info = round_manager.get_round_summary(trading_round.id)
        if not round_info or round_info['status'] != RoundStatus.ENTRY_READY:
            print("❌ 매수 시그널 발생 실패")
            return
            
        print("\n[매수 진입 준비 상태]")
        print(f"- 상태: {round_info['status']}")
        print(f"- 목표가: {round_info['take_profit']:,.0f}")
        print(f"- 손절가: {round_info['stop_loss']:,.0f}")
        
        # 4. 매수 진입 프로세스 실행
        if round_manager.execute_entry_process(trading_round.id):
            print("\n✅ 4. 매수 진입 프로세스 완료")
            
            # 5. 최종 상태 확인
            final_round = round_manager.get_round_summary(trading_round.id)
            if final_round:
                print("\n[최종 상태]")
                print(f"- 상태: {final_round['status']}")
                if final_round['entry_price']:
                    print(f"- 매수가: {final_round['entry_price']:,.0f}")
                print(f"- 목표가: {final_round['take_profit']:,.0f}")
                print(f"- 손절가: {final_round['stop_loss']:,.0f}")
        else:
            print("❌ 매수 진입 프로세스 실패")
            
            # 실패 상태 확인
            failed_round = round_manager.get_round_summary(trading_round.id)
            print("\n[실패 상태]")
            print(f"- 상태: {failed_round['status']}")
    
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
    
    finally:
        # 테스트 종료 대기
        time.sleep(1)

def test_monitoring_process():
    """포지션 모니터링 프로세스 테스트"""
    print("\n=== 포지션 모니터링 프로세스 테스트 ===")
    
    log_manager = LogManager(base_dir="logs/round_manager_test", log_mode="both", console_format="detailed")
    log_manager.start_new_trading_session("BTC")
    round_manager = RoundManager(log_manager=log_manager)
    
    try:
        # 1. 라운드 생성 및 매수 진입
        trading_round = round_manager.create_round(symbol="BTC")
        if not trading_round:
            print("❌ 라운드 생성 실패")
            return
            
        print(f"✅ 1. 라운드 생성됨 (ID: {trading_round.id})")
        
        # 2. 관찰 시작 및 매수 진입
        if not round_manager.start_watching(trading_round.id):
            print("❌ 관찰 시작 실패")
            return
            
        print("✅ 2. 관찰 및 매수 진입 완료")
        
        # 3. 라운드 상태 확인
        round_info = round_manager.get_round_summary(trading_round.id)
        if not round_info or round_info['status'] != RoundStatus.HOLDING:
            print("❌ 매수 진입 실패")
            return
            
        print("\n[매수 진입 상태]")
        print(f"- 상태: {round_info['status']}")
        print(f"- 매수가: {round_info['entry_price']:,.0f}")
        print(f"- 목표가: {round_info['take_profit']:,.0f}")
        print(f"- 손절가: {round_info['stop_loss']:,.0f}")
        
        # 4. 모니터링 시작
        print("\n[모니터링 시작]")
        
        # 5. 모니터링 상태 출력 (30초 동안)
        start_time = time.time()
        monitoring_duration = 30  # seconds
        
        while time.time() - start_time < monitoring_duration:
            # 모니터링 프로세스 실행
            monitoring_result = round_manager.start_monitoring(trading_round.id)
            if monitoring_result:
                print("\n✅ 모니터링 프로세스 완료")
                break
                
            current_info = round_manager.get_round_summary(trading_round.id)
            if not current_info:
                print("❌ 라운드 정보 조회 실패")
                break
                
            # 상태가 변경된 경우
            if current_info['status'] != RoundStatus.HOLDING:
                print(f"\n✅ 상태 변경 감지: {current_info['status']}")
                print(f"- 종료 사유: {current_info.get('exit_reason', 'N/A')}")
                if current_info.get('current_metrics'):
                    print(f"- 수익률: {current_info['current_metrics'].get('profit_loss_rate', 0):.2f}%")
                break
                
            # 5초마다 상태 출력
            if int(time.time() - start_time) % 5 == 0:
                print(f"\n[모니터링 진행 중... {int(time.time() - start_time)}초]")
                print(f"- 현재 상태: {current_info['status']}")
                if current_info.get('current_metrics'):
                    print(f"- 현재 수익률: {current_info['current_metrics'].get('profit_loss_rate', 0):.2f}%")
                time.sleep(1)  # 출력 간격 조절
                
        print("\n[모니터링 테스트 완료]")
        final_info = round_manager.get_round_summary(trading_round.id)
        if final_info:
            print(f"- 최종 상태: {final_info['status']}")
            print(f"- 결과: {final_info.get('exit_reason', 'N/A')}")
            if final_info.get('current_metrics'):
                print(f"- 최종 수익률: {final_info['current_metrics'].get('profit_loss_rate', 0):.2f}%")
    
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
    
    finally:
        # 테스트 종료 대기
        time.sleep(1)
        print("\n테스트 종료")

def main():
    """메인 테스트 함수"""
    # 환경 변수 로드
    load_dotenv()
    
    # 각 테스트 실행
    # test_round_creation()
    # test_round_watching()
    # test_round_lifecycle()
    # test_entry_process()
    test_monitoring_process()

if __name__ == "__main__":
    main() 