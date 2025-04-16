#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAITrader 클래스를 테스트하는 예제 코드
"""

import sys
import os
import logging
from dotenv import load_dotenv
import json
from datetime import datetime
import time

# 프로젝트 루트 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 환경 변수 로드 (.env 파일)
load_dotenv()

from src.new.openai_trader import OpenAITrader

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def display_ticker_info(trader):
    """
    현재가(Ticker) 정보를 가져와 표시합니다.
    
    Args:
        trader: OpenAITrader 인스턴스
    """
    try:
        # 비트코인 현재가 정보 가져오기
        market = "KRW-BTC"
        ticker_response = trader.bithumb_client.get_ticker(markets=market)
        
        if ticker_response and hasattr(ticker_response, 'tickers') and len(ticker_response.tickers) > 0:
            ticker = ticker_response.tickers[0]
            
            logger.info(f"===== {market} 현재가 정보 =====")
            logger.info(f"현재가: {ticker.trade_price:,} 원")
            logger.info(f"변동률: {ticker.signed_change_rate * 100:.2f}%")
            logger.info(f"거래량(24h): {ticker.acc_trade_volume_24h:,.8f} BTC")
            logger.info(f"거래대금(24h): {ticker.acc_trade_price_24h:,.0f} 원")
            
            # 시세 변동 상태 표시
            if ticker.change == "RISE":
                change_status = "상승"
            elif ticker.change == "FALL":
                change_status = "하락"
            else:
                change_status = "보합"
                
            logger.info(f"시세 변동 상태: {change_status}")
            logger.info(f"52주 최고가: {ticker.highest_52_week_price:,} 원 ({ticker.highest_52_week_date})")
            logger.info(f"52주 최저가: {ticker.lowest_52_week_price:,} 원 ({ticker.lowest_52_week_date})")
            logger.info("")
            
        else:
            logger.error("현재가 정보를 가져오지 못했습니다.")
    
    except Exception as e:
        logger.error(f"현재가 정보 조회 중 오류 발생: {e}")


def display_orderbook_info(trader):
    """
    호가창(Orderbook) 정보를 가져와 표시합니다.
    
    Args:
        trader: OpenAITrader 인스턴스
    """
    try:
        # 비트코인 호가창 정보 가져오기
        market = "KRW-BTC"
        orderbook_response = trader.bithumb_client.get_orderbook(markets=market)
        
        if orderbook_response and hasattr(orderbook_response, 'orderbooks') and len(orderbook_response.orderbooks) > 0:
            orderbook = orderbook_response.orderbooks[0]
            
            logger.info(f"===== {market} 호가창 정보 =====")
            logger.info(f"총 매도 주문량: {orderbook.total_ask_size:,.8f} BTC")
            logger.info(f"총 매수 주문량: {orderbook.total_bid_size:,.8f} BTC")
            logger.info("")
            
            # 호가 불균형 계산
            imbalance_ratio = orderbook.total_bid_size / (orderbook.total_bid_size + orderbook.total_ask_size)
            logger.info(f"호가 불균형 비율: {imbalance_ratio:.4f} (0.5보다 크면 매수 우위)")
            
            # 상위 5개 호가 정보 표시
            logger.info("상위 5개 매도/매수 호가:")
            for i, unit in enumerate(orderbook.orderbook_units[:5], 1):
                logger.info(f"[{i}] 매도: {unit.ask_price:,}원 ({unit.ask_size:.8f} BTC) | 매수: {unit.bid_price:,}원 ({unit.bid_size:.8f} BTC)")
            
            logger.info("")
            
        else:
            logger.error("호가창 정보를 가져오지 못했습니다.")
    
    except Exception as e:
        logger.error(f"호가창 정보 조회 중 오류 발생: {e}")


def display_trades_info(trader):
    """
    최근 체결 내역을 가져와 표시합니다.
    
    Args:
        trader: OpenAITrader 인스턴스
    """
    try:
        # 비트코인 최근 체결 내역 가져오기
        market = "KRW-BTC"
        trades_response = trader.bithumb_client.get_trades(market=market, count=5)
        
        if trades_response and hasattr(trades_response, 'trades') and len(trades_response.trades) > 0:
            trades = trades_response.trades
            
            logger.info(f"===== {market} 최근 체결 내역 =====")
            for i, trade in enumerate(trades, 1):
                # 매수/매도 구분
                trade_type = "매도" if trade.ask_bid == "ASK" else "매수"
                
                # UTC 시간을 KST로 변환 (UTC+9)
                trade_dt = datetime.fromisoformat(f"{trade.trade_date_utc}T{trade.trade_time_utc}")
                
                logger.info(f"[{i}] {trade_dt.strftime('%Y-%m-%d %H:%M:%S')} | {trade_type} | 가격: {trade.trade_price:,}원 | 수량: {trade.trade_volume:.8f} BTC")
            
            logger.info("")
            
        else:
            logger.error("최근 체결 내역을 가져오지 못했습니다.")
    
    except Exception as e:
        logger.error(f"최근 체결 내역 조회 중 오류 발생: {e}")


def display_candles_info(trader):
    """
    캔들 차트 데이터를 가져와 표시합니다.
    
    Args:
        trader: OpenAITrader 인스턴스
    """
    try:
        # 비트코인 1시간 캔들 데이터 가져오기
        market = "KRW-BTC"
        interval = "1h"
        candles_response = trader.bithumb_client.get_candles(market=market, interval=interval, limit=5)
        
        if candles_response and hasattr(candles_response, 'candles') and len(candles_response.candles) > 0:
            candles = candles_response.candles
            
            logger.info(f"===== {market} {interval} 캔들 차트 데이터 =====")
            for i, candle in enumerate(candles, 1):
                # 시간 형식 변환
                candle_dt = datetime.fromisoformat(candle.candle_date_time_kst.replace('Z', '+00:00'))
                
                # 상승/하락 여부 확인
                status = "▲" if candle.trade_price > candle.opening_price else "▼"
                
                logger.info(f"[{i}] {candle_dt.strftime('%Y-%m-%d %H:%M')} | 시가: {candle.opening_price:,}원 | 고가: {candle.high_price:,}원 | 저가: {candle.low_price:,}원 | 종가: {candle.trade_price:,}원 {status} | 거래량: {candle.candle_acc_trade_volume:.8f} BTC")
            
            logger.info("")
            
        else:
            logger.error("캔들 차트 데이터를 가져오지 못했습니다.")
    
    except Exception as e:
        logger.error(f"캔들 차트 데이터 조회 중 오류 발생: {e}")


def test_get_indicators(trader):
    """
    OpenAITrader의 get_indicators 메서드를 테스트합니다.
    
    Args:
        trader: OpenAITrader 인스턴스
    """
    try:
        logger.info("===== OpenAITrader.get_indicators 테스트 =====")
        
        # get_indicators 메서드 호출
        market = "KRW-BTC"
        indicators = trader.get_indicators(market=market)
        
        # 반환값 출력 또는 처리
        if indicators:
            logger.info("지표 데이터 가져오기 성공")
            logger.info(json.dumps(indicators, indent=2, ensure_ascii=False))
        else:
            logger.info("지표 데이터가 비어있습니다.")
        
        logger.info("")
        
    except Exception as e:
        logger.error(f"get_indicators 테스트 중 오류 발생: {e}")


def format_time(seconds):
    """
    초 단위의 시간을 읽기 쉬운 형식으로 변환합니다.
    
    Args:
        seconds: 초 단위 시간
        
    Returns:
        str: 형식화된 시간 문자열
    """
    if seconds < 0.001:  # 1ms 미만
        return f"{seconds * 1000000:.2f} μs"
    elif seconds < 1:  # 1초 미만
        return f"{seconds * 1000:.2f} ms"
    elif seconds < 60:  # 1분 미만
        return f"{seconds:.2f} 초"
    else:
        minutes, seconds = divmod(seconds, 60)
        return f"{int(minutes)}분 {seconds:.2f}초"


def main():
    """
    메인 실행 함수
    """
    try:
        logger.info("OpenAITrader 테스트를 시작합니다.")
        
        # 총 실행 시간 측정 시작
        total_start_time = time.time()
        
        # OpenAITrader 인스턴스 생성
        trader = OpenAITrader()
        
        # 지표 데이터 수집 시간 측정
        logger.info("지표 데이터 수집 중...")
        indicators_start_time = time.time()
        indicators = trader.get_indicators()
        indicators_end_time = time.time()
        indicators_time = indicators_end_time - indicators_start_time
        logger.info(f"지표 데이터 수집 완료 (소요시간: {format_time(indicators_time)})")
        
        # 프롬프트 생성 시간 측정
        logger.info("프롬프트 생성 중...")
        prompt_start_time = time.time()
        prompt = trader.make_prompt_style(indicators)
        prompt_end_time = time.time()
        prompt_time = prompt_end_time - prompt_start_time
        logger.info(f"프롬프트 생성 완료 (소요시간: {format_time(prompt_time)})")
        
        # AI 분석 시간 측정
        logger.info("AI 분석 중...")
        analysis_start_time = time.time()
        analysis = trader.get_analysis(prompt)
        analysis_end_time = time.time()
        analysis_time = analysis_end_time - analysis_start_time
        logger.info(f"AI 분석 완료 (소요시간: {format_time(analysis_time)})")
        
        # 분석 결과 출력
        logger.info("분석 결과:")
        logger.info(json.dumps(analysis, indent=2, ensure_ascii=False))
        
        # AI 분석 시간 측정
        logger.info("AI 분석 중...2")
        analysis_start_time = time.time()
        analysis = trader.get_analysis(prompt)
        analysis_end_time = time.time()
        analysis_time = analysis_end_time - analysis_start_time
        logger.info(f"AI 분석 완료 (소요시간: {format_time(analysis_time)})")
        
        # 분석 결과 출력
        logger.info("분석 결과:")
        logger.info(json.dumps(analysis, indent=2, ensure_ascii=False))
        
        # 총 실행 시간 계산
        total_end_time = time.time()
        total_time = total_end_time - total_start_time
        
        logger.info("OpenAITrader 테스트를 완료했습니다.")
        logger.info(f"========================================")
        logger.info(f"실행 시간 요약:")
        logger.info(f"- 지표 데이터 수집: {format_time(indicators_time)} ({indicators_time/total_time*100:.1f}%)")
        logger.info(f"- 프롬프트 생성: {format_time(prompt_time)} ({prompt_time/total_time*100:.1f}%)")
        logger.info(f"- AI 분석: {format_time(analysis_time)} ({analysis_time/total_time*100:.1f}%)")
        logger.info(f"- 총 실행 시간: {format_time(total_time)}")
        logger.info(f"========================================")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main() 