#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
빗썸 API 클라이언트의 get_candles 메서드 테스트 예제
"""

import sys
import os
import logging
from datetime import datetime
from typing import List
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

# 프로젝트 루트 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.new.api.bithumb import BithumbApiClient
from src.new.models.bithumb.response import Candle, CandlesResponse

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def display_candles(candles: List[Candle]) -> None:
    """
    캔들 데이터를 콘솔에 표시합니다.
    
    Args:
        candles: 캔들 데이터 목록
    """
    for i, candle in enumerate(candles[:5], 1):  # 처음 5개만 표시
        logger.info(f"캔들 {i}:")
        logger.info(f"  시장: {candle.market}")
        logger.info(f"  시각(KST): {candle.candle_date_time_kst}")
        logger.info(f"  시가: {candle.opening_price}")
        logger.info(f"  고가: {candle.high_price}")
        logger.info(f"  저가: {candle.low_price}")
        logger.info(f"  종가: {candle.trade_price}")
        logger.info(f"  거래량: {candle.candle_acc_trade_volume}")
        logger.info("")
    
    logger.info(f"총 {len(candles)}개의 캔들 데이터를 가져왔습니다.")


def plot_candles(candles: List[Candle], market: str, interval: str) -> None:
    """
    캔들 차트를 시각화합니다.
    
    Args:
        candles: 캔들 데이터 목록
        market: 시장 정보 (예: 'BTC-KRW')
        interval: 시간 간격
    """
    try:
        # 판다스 데이터프레임으로 변환
        df = pd.DataFrame([
            {
                'Date': datetime.fromisoformat(candle.candle_date_time_kst.replace('Z', '+00:00')),
                'Open': candle.opening_price,
                'High': candle.high_price,
                'Low': candle.low_price,
                'Close': candle.trade_price,
                'Volume': candle.candle_acc_trade_volume
            }
            for candle in candles
        ])
        
        # 날짜 기준으로 정렬 및 인덱스 설정
        df = df.sort_values('Date')
        df.set_index('Date', inplace=True)
        
        # 캔들차트 그리기
        mpf.plot(
            df,
            type='candle',
            title=f'{market} ({interval})',
            ylabel='가격',
            volume=True,
            style='yahoo',
            figsize=(12, 8)
        )
        
        logger.info("캔들차트가 표시됩니다. 창을 닫으면 프로그램이 종료됩니다.")
        plt.show()
        
    except Exception as e:
        logger.error(f"차트 생성 중 오류가 발생했습니다: {e}")


def main():
    """
    메인 실행 함수
    """
    try:
        # 빗썸 API 클라이언트 초기화
        client = BithumbApiClient()
        
        # 테스트할 시장 및 시간 간격 설정
        market = "KRW-BTC"  # 비트코인-원화 시장
        interval = "1h"     # 1시간 간격
        limit = 100         # 최대 100개 캔들
        
        logger.info(f"{market} 시장의 {interval} 간격 캔들 데이터를 요청합니다...")
        
        # 캔들 데이터 요청
        candles_response = client.get_orderbook(
            markets=market
        )
        
        # 결과 출력
        logger.info(f"캔들 데이터: {candles_response}")
        
        ticker_response = client.get_ticker(markets=market)
        logger.info(f"현재가 데이터: {ticker_response}")
        
        trades_response = client.get_trades(markets=market, co)
        logger.info(f"체결 내역 데이터: {trades_response}")
        
    except Exception as e:
        logger.error(f"오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main() 