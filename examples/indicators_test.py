#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
from datetime import datetime
import json
import pandas as pd
from pprint import pprint

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.new.indicators import Indicators

def print_section_header(title):
    """테스트 섹션 헤더를 출력합니다."""
    print("\n" + "=" * 80)
    print(f"🔍 {title}")
    print("=" * 80 + "\n")

def print_json(data):
    """딕셔너리 데이터를 예쁘게 출력합니다."""
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        pprint(data)

def test_evaluate_buy_entry_signal():
    """매수 진입 신호 평가 기능을 테스트합니다."""
    print_section_header("매수 진입 신호 평가 테스트 (evaluateBuyEntrySignal)")
    
    indicators = Indicators(market="KRW-BTC")
    
    print("📊 매수 진입 신호 평가 중...")
    entry_signal = indicators.evaluateBuyEntrySignal()
    
    print("\n📝 매수 진입 판단 결과:")
    print(f"진입 추천: {'✅ 예' if entry_signal['should_enter'] else '❌ 아니오'}")
    print(f"신뢰도: {entry_signal['confidence']:.2f} (0~1)")
    
    if entry_signal['reasons']:
        print("\n✅ 긍정적 요인:")
        for reason in entry_signal['reasons']:
            print(f"  • {reason}")
    
    if entry_signal['negative_reasons']:
        print("\n❌ 부정적 요인:")
        for reason in entry_signal['negative_reasons']:
            print(f"  • {reason}")
    
    print("\n📈 주요 지표 요약:")
    indicators_summary = {
        "호가 불균형 비율": entry_signal['indicators']['orderbook_imbalance'],
        "체결 우위 비율": entry_signal['indicators']['execution_bid_ratio'],
        "거래량 급증 비율": entry_signal['indicators']['volume_spike'],
        "매도벽 존재": entry_signal['indicators']['ask_wall']['is_wall_present'],
        "체결 속도 (3초간)": entry_signal['indicators']['tick_speed']['executions_count'],
        "캔들 방향": entry_signal['indicators']['candle_direction']['direction']
    }
    for key, value in indicators_summary.items():
        print(f"  • {key}: {value}")
    
    return entry_signal

def test_calculate_target_and_stop_loss():
    """목표가와 손절가 계산 기능을 테스트합니다."""
    print_section_header("목표가/손절가 계산 테스트 (calculateTargetAndStopLoss)")
    
    indicators = Indicators(market="KRW-BTC")
    
    # 현재가 가져오기
    candles_res = indicators.client.get_candles(market="KRW-BTC", interval="1m", limit=1)
    current_price = candles_res.candles[0].trade_price if candles_res.candles else 40000000
    
    print(f"📊 현재 BTC 가격: {current_price:,} KRW")
    
    # 세 가지 전략에 대해 테스트
    strategies = ["fast_scalping", "flow_tracking", "breakout"]
    
    for strategy in strategies:
        print(f"\n💡 {strategy.replace('_', ' ').title()} 전략:")
        
        target_stop_loss = indicators.calculateTargetAndStopLoss(
            entry_price=current_price,
            strategy_type=strategy
        )
        
        target_price = target_stop_loss["target_price"]
        stop_loss_price = target_stop_loss["stop_loss_price"]
        
        print(f"  • 진입가: {current_price:,} KRW")
        print(f"  • 목표가: {target_price:,} KRW ({target_stop_loss['target_ratio'] * 100:.2f}%)")
        print(f"  • 손절가: {stop_loss_price:,} KRW ({target_stop_loss['stop_loss_ratio'] * 100:.2f}%)")
        print(f"  • R/R 비율: {target_stop_loss['rr_ratio']:.2f}")
        print(f"  • 순수익률: {target_stop_loss['net_profit_ratio'] * 100:.2f}% (수수료 차감)")
        
        if target_stop_loss['strategy_info']:
            print("  • 전략 세부 정보:")
            for key, value in target_stop_loss['strategy_info'].items():
                print(f"    - {key}: {value}")
    
    return {
        "entry_price": current_price,
        "fast_scalping": indicators.calculateTargetAndStopLoss(current_price, "fast_scalping"),
        "flow_tracking": indicators.calculateTargetAndStopLoss(current_price, "flow_tracking"),
        "breakout": indicators.calculateTargetAndStopLoss(current_price, "breakout")
    }

def test_update_target_and_stop_loss():
    """진입 후 동적 목표가/손절가 업데이트 기능을 테스트합니다."""
    print_section_header("동적 목표가/손절가 업데이트 테스트 (updateTargetAndStopLoss)")
    
    indicators = Indicators(market="KRW-BTC")
    
    # 현재가 가져오기
    candles_res = indicators.client.get_candles(market="KRW-BTC", interval="1m", limit=1)
    current_price = candles_res.candles[0].trade_price if candles_res.candles else 40000000
    
    # 시뮬레이션 설정
    entry_price = current_price  # 초기 진입가
    target_info = indicators.calculateTargetAndStopLoss(entry_price, "flow_tracking")  # 초기 목표가/손절가
    
    # 다양한 가격 변동 시나리오와 시간 경과 시뮬레이션
    scenarios = [
        {"name": "초기 상태", "price_change": 0, "elapsed_seconds": 0},
        {"name": "소폭 상승", "price_change": 0.002, "elapsed_seconds": 60},  # 0.2% 상승, 1분 경과
        {"name": "목표의 50% 달성", "price_change": target_info["target_ratio"] * 0.5, "elapsed_seconds": 120},
        {"name": "매도세 급증 상황", "price_change": 0.001, "elapsed_seconds": 180, "execution_override": 0.3},  # 매도세 급증 시뮬
        {"name": "장시간 횡보", "price_change": 0.0005, "elapsed_seconds": 360}  # 약 상승 후 6분 경과
    ]
    
    results = []
    
    for scenario in scenarios:
        # 시나리오 기반 현재가 계산
        simulated_price = entry_price * (1 + scenario["price_change"])
        elapsed_seconds = scenario["elapsed_seconds"]
        
        print(f"\n💡 시나리오: {scenario['name']}")
        print(f"  • 진입가: {entry_price:,} KRW")
        print(f"  • 현재가: {simulated_price:,} KRW ({scenario['price_change'] * 100:.3f}%)")
        print(f"  • 경과 시간: {elapsed_seconds}초")
        
        if "execution_override" in scenario:
            # 테스트용 임시 체결 비율 오버라이드 (원래 값은 restore_method에 저장)
            original_method = indicators.getExecutionBidRatio
            indicators.getExecutionBidRatio = lambda: scenario["execution_override"]
        
        # 목표가/손절가 업데이트
        updated_targets = indicators.updateTargetAndStopLoss(
            entry_price=entry_price,
            current_price=simulated_price,
            initial_target=target_info,
            elapsed_seconds=elapsed_seconds
        )
        
        if "execution_override" in scenario:
            # 원래 메서드 복원
            indicators.getExecutionBidRatio = original_method
        
        # 결과 출력
        print("\n  📊 업데이트된 목표가/손절가:")
        print(f"  • 목표가: {updated_targets['target_price']:,} KRW")
        print(f"  • 손절가: {updated_targets['stop_loss_price']:,} KRW")
        
        # 변경 사항 출력
        if updated_targets["update_info"]["target_moved"]:
            print(f"  • ⚠️ 목표가 조정됨: {target_info['target_price']:,} → {updated_targets['target_price']:,}")
        
        if updated_targets["update_info"]["stop_loss_moved"]:
            print(f"  • ⚠️ 손절가 조정됨: {target_info['stop_loss_price']:,} → {updated_targets['stop_loss_price']:,}")
        
        # 현재 수익률 출력
        print(f"  • 현재 수익률: {updated_targets['update_info']['current_profit_ratio'] * 100:.3f}%")
        
        results.append({
            "scenario": scenario["name"],
            "updated_targets": updated_targets
        })
    
    return results

def run_continuous_monitoring():
    """실시간으로 지표를 모니터링합니다."""
    print_section_header("실시간 지표 모니터링")
    
    indicators = Indicators(market="KRW-BTC")
    
    try:
        iteration = 1
        while iteration <= 10:  # 10회만 실행
            print(f"\n📊 모니터링 #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            
            # 매수 신호 평가
            entry_signal = indicators.evaluateBuyEntrySignal()
            
            print(f"매수 진입 신호: {'✅' if entry_signal['should_enter'] else '❌'} (신뢰도: {entry_signal['confidence']:.2f})")
            
            # 핵심 지표만 요약
            print("주요 지표:")
            print(f"  • 호가 불균형: {entry_signal['indicators']['orderbook_imbalance']:.2f}")
            print(f"  • 체결 우위: {entry_signal['indicators']['execution_bid_ratio']:.2f}")
            print(f"  • 거래량 급증: {entry_signal['indicators']['volume_spike']:.2f}")
            
            # 매수 신호가 있을 경우 목표가/손절가 계산
            if entry_signal['should_enter']:
                candles_res = indicators.client.get_candles(market="KRW-BTC", interval="1m", limit=1)
                current_price = candles_res.candles[0].trade_price
                
                target_info = indicators.calculateTargetAndStopLoss(current_price, "flow_tracking")
                
                print("\n✅ 매수 신호 감지! 목표가/손절가:")
                print(f"  • 진입가: {current_price:,} KRW")
                print(f"  • 목표가: {target_info['target_price']:,} KRW (+{target_info['target_ratio'] * 100:.2f}%)")
                print(f"  • 손절가: {target_info['stop_loss_price']:,} KRW (-{target_info['stop_loss_ratio'] * 100:.2f}%)")
            
            iteration += 1
            time.sleep(5)  # 5초 대기
            
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 모니터링이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

def main():
    """메인 함수"""
    print_section_header("Indicators 테스트 시작")
    
    # 명령줄 인자가 있으면 특정 테스트만 실행
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "entry":
            test_evaluate_buy_entry_signal()
        elif test_name == "target":
            test_calculate_target_and_stop_loss()
        elif test_name == "update":
            test_update_target_and_stop_loss()
        elif test_name == "monitor":
            run_continuous_monitoring()
        else:
            print(f"알 수 없는 테스트: {test_name}")
    else:
        # 모든 테스트 실행
        test_evaluate_buy_entry_signal()
        test_calculate_target_and_stop_loss()
        test_update_target_and_stop_loss()
        
        # 실시간 모니터링은 기본적으로 실행하지 않음
        print("\n실시간 모니터링을 시작하려면 다음 명령어 실행:")
        print("python indicators_test.py monitor")
    
    print("\n✅ 테스트 완료!")

if __name__ == "__main__":
    main() 