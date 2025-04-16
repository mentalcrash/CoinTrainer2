from src.new.api.bithumb import BithumbApiClient
import numpy as np
from typing import List, Tuple, Dict, Literal
import time

class Indicators:
    def __init__(self, market: str = "KRW-BTC"):
        self.market = market
        self.client = BithumbApiClient()
        self._prev_order_diff = None  # 이전 호가 불균형 차이 저장
        self._prev_order_diff_time = 0  # 이전 호가 불균형 체크 시간
        self._recent_executions = []  # 최근 체결 시간 저장 (체결 속도 계산용)

    # 0.5를 기준으로 0.5 초과면 매수 우위, 0.5 미만이면 매도 우위
    def getOrderBookImbalanceRatio(self) -> float:
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        return orderbook.total_bid_size / (orderbook.total_ask_size + orderbook.total_bid_size)
    
    def getOrderBookImbalanceDifference(self) -> float:
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        return orderbook.total_bid_size - orderbook.total_ask_size
    
    # 체결 우위 비율 (Execution Bid Ratio)
    # BID 체결량 / 전체 체결량 (최근 10건)
    # 0.5를 기준으로 0.5 초과면 매수 우위, 0.5 미만이면 매도 우위
    def getExecutionBidRatio(self, count: int = 10) -> float:
        """
        최근 체결 내역에서 매수(BID) 체결량의 비율을 계산합니다.
        
        Args:
            count: 분석할 최근 체결 건수 (기본값: 10)
            
        Returns:
            float: 매수 체결량 / 전체 체결량 비율 (0~1 사이 값)
        """
        trades_res = self.client.get_trades(market=self.market, count=count)
        trades = trades_res.trades
        
        # 현재 체결 시간 기록 (체결 속도 계산용)
        if trades and len(trades) > 0:
            from datetime import datetime
            trade_time_str = f"{trades[0].trade_date_utc}T{trades[0].trade_time_utc}"
            trade_time = datetime.fromisoformat(trade_time_str).timestamp()
            self._recent_executions.append(trade_time)
            
            # 최근 10개 체결만 유지
            if len(self._recent_executions) > 10:
                self._recent_executions = self._recent_executions[-10:]
        
        # 매수(BID)와 매도(ASK) 체결량 합산
        bid_volume = sum(trade.trade_volume for trade in trades if trade.ask_bid == "BID")
        total_volume = sum(trade.trade_volume for trade in trades)
        
        # 총 거래량이 0인 경우 처리
        if total_volume == 0:
            return 0.5  # 기본값으로 중립 반환
            
        return bid_volume / total_volume
    
    # 체결량 변화율 (Volume Change Ratio)
    # 최근 N개 체결량 / 이전 N개 체결량
    def getVolumeChangeRatio(self, recent_count: int = 5, prev_count: int = 5) -> float:
        """
        최근 체결량과 이전 체결량의 비율을 계산하여 체결량의 변화율을 구합니다.
        
        Args:
            recent_count: 최근 체결 건수 (기본값: 5)
            prev_count: 이전 체결 건수 (기본값: 5)
            
        Returns:
            float: 최근 체결량 / 이전 체결량 비율
                  1보다 크면 체결량 증가, 1보다 작으면 체결량 감소
        """
        total_count = recent_count + prev_count
        trades_res = self.client.get_trades(market=self.market, count=total_count)
        trades = trades_res.trades
        
        # 최근 체결과 이전 체결 분리
        recent_trades = trades[:recent_count]
        prev_trades = trades[recent_count:total_count]
        
        # 체결량 합산
        recent_volume = sum(trade.trade_volume for trade in recent_trades)
        prev_volume = sum(trade.trade_volume for trade in prev_trades)
        
        # 이전 체결량이 0인 경우 처리
        if prev_volume == 0:
            return float('inf') if recent_volume > 0 else 1.0
            
        return recent_volume / prev_volume
    
    # 평균 체결 단가 변화 (Moving Average Price Change)
    # 최근 N개 체결 평균가 - 이전 N개 체결 평균가
    def getPriceMovingAverageChange(self, window_size: int = 5) -> Tuple[float, float, float]:
        """
        최근 체결 가격의 이동평균을 계산하고 변화량을 구합니다.
        
        Args:
            window_size: 이동평균 윈도우 크기 (기본값: 5)
            
        Returns:
            Tuple[float, float, float]: 
                (현재 이동평균, 이전 이동평균, 변화율)
        """
        # 충분한 데이터를 확보하기 위해 window_size의 3배 데이터 요청
        count = window_size * 3
        trades_res = self.client.get_trades(market=self.market, count=count)
        trades = trades_res.trades
        
        # 체결 가격 추출
        prices = [trade.trade_price for trade in trades]
        
        # 최근 이동평균
        recent_ma = np.mean(prices[:window_size]) if len(prices) >= window_size else 0
        
        # 이전 이동평균
        prev_ma = np.mean(prices[window_size:window_size*2]) if len(prices) >= window_size*2 else 0
        
        # 변화율 계산
        change_rate = 0
        if prev_ma > 0:
            change_rate = (recent_ma - prev_ma) / prev_ma
            
        return (recent_ma, prev_ma, change_rate)
    
    # 체결 클러스터링 지표 (Execution Clustering Index)
    # 최근 체결들의 시간 간격 분석
    def getExecutionClustering(self, count: int = 10) -> float:
        """
        최근 체결들의 시간 간격을 분석하여 클러스터링 지수를 계산합니다.
        값이 작을수록 체결이 집중적으로 발생함을 의미합니다.
        
        Args:
            count: 분석할 최근 체결 건수 (기본값: 10)
            
        Returns:
            float: 체결 클러스터링 지수 (표준화된 시간 간격의 평균)
        """
        trades_res = self.client.get_trades(market=self.market, count=count)
        trades = trades_res.trades
        
        if len(trades) < 2:
            return 0.0
            
        # 타임스탬프 추출 (UTC 시간을 초 단위로 변환)
        from datetime import datetime
        
        timestamps = []
        for trade in trades:
            dt_str = f"{trade.trade_date_utc}T{trade.trade_time_utc}"
            dt = datetime.fromisoformat(dt_str)
            timestamps.append(dt.timestamp())
            
        # 시간 간격 계산
        time_intervals = [timestamps[i] - timestamps[i+1] for i in range(len(timestamps)-1)]
        
        # 평균 시간 간격
        mean_interval = np.mean(time_intervals) if time_intervals else 0
        
        # 표준 편차
        std_dev = np.std(time_intervals) if len(time_intervals) > 1 else 1.0
        
        # 클러스터링 지수 (표준화된 간격)
        # 값이 작을수록 체결이 집중적으로 발생
        clustering_index = mean_interval / (std_dev + 1e-9)  # 0으로 나누는 것 방지
        
        return clustering_index
        
    #
    # 캔들 기반 지표
    #
    
    # 거래량 급증 비율 (Volume Spike Ratio)
    # 현재 캔들 거래량 / 이전 3개 평균
    def getVolumeSpikeRatio(self, interval: Literal["1m", "3m", "5m", "10m", "30m", "1h"] = "1m") -> float:
        """
        현재 캔들의 거래량과 이전 3개 캔들의 평균 거래량 비율을 계산합니다.
        
        Args:
            interval: 캔들 간격 (기본값: "1m" - 1분봉)
            
        Returns:
            float: 현재 캔들 거래량 / 이전 3개 캔들 평균 거래량
                 1보다 크면 거래량 급증, 1보다 작으면 거래량 감소
        """
        # 최소 4개의 캔들 데이터 가져오기 (현재 + 이전 3개)
        candles_res = self.client.get_candles(market=self.market, interval=interval, limit=4)
        candles = candles_res.candles
        
        if len(candles) < 4:
            return 1.0  # 충분한 데이터가 없으면 중립값 반환
        
        # 현재 캔들(인덱스 0)과 이전 3개 캔들 추출
        current_candle = candles[0]
        previous_candles = candles[1:4]
        
        # 거래량 추출
        current_volume = current_candle.candle_acc_trade_volume
        previous_volumes = [candle.candle_acc_trade_volume for candle in previous_candles]
        
        # 이전 3개 캔들의 평균 거래량
        avg_previous_volume = np.mean(previous_volumes)
        
        # 평균 거래량이 0인 경우 처리
        if avg_previous_volume == 0:
            return float('inf') if current_volume > 0 else 1.0
        
        # 현재 캔들 거래량 / 이전 3개 평균 거래량
        return current_volume / avg_previous_volume
    
    # 직전 캔들 방향 (Previous Candle Direction)
    # close > open → 양봉(bullish), close < open → 음봉(bearish)
    def getCandleDirection(self, interval: Literal["1m", "3m", "5m", "10m", "30m", "1h"] = "1m") -> Dict:
        """
        직전 캔들의 방향(양봉/음봉)과 관련 정보를 반환합니다.
        
        Args:
            interval: 캔들 간격 (기본값: "1m" - 1분봉)
            
        Returns:
            Dict: 캔들 방향 정보가 담긴 딕셔너리
                {
                    "direction": "bullish"|"bearish"|"neutral",  # 양봉/음봉/동일
                    "strength": float,                           # 캔들 세기 (종가-시가)/시가
                    "body_ratio": float,                         # 캔들 몸통 비율 (종가-시가)/(고가-저가)
                    "is_bullish": bool                           # 양봉 여부
                }
        """
        # 최근 캔들 데이터 가져오기
        candles_res = self.client.get_candles(market=self.market, interval=interval, limit=1)
        candles = candles_res.candles
        
        if not candles:
            # 캔들 데이터가 없는 경우 기본값 반환
            return {
                "direction": "neutral",
                "strength": 0.0,
                "body_ratio": 0.0,
                "is_bullish": False
            }
        
        candle = candles[0]
        
        # 캔들 방향 판단
        if candle.trade_price > candle.opening_price:
            direction = "bullish"  # 양봉
            is_bullish = True
        elif candle.trade_price < candle.opening_price:
            direction = "bearish"  # 음봉
            is_bullish = False
        else:
            direction = "neutral"  # 보합
            is_bullish = False
        
        # 캔들 세기 계산 (종가 변화율)
        strength = 0.0
        if candle.opening_price > 0:
            strength = (candle.trade_price - candle.opening_price) / candle.opening_price
        
        # 캔들 몸통 비율 계산
        body_size = abs(candle.trade_price - candle.opening_price)
        range_size = candle.high_price - candle.low_price
        body_ratio = 0.0
        
        if range_size > 0:
            body_ratio = body_size / range_size
        
        return {
            "direction": direction,
            "strength": strength,
            "body_ratio": body_ratio,
            "is_bullish": is_bullish
        }
    
    # 당일 가격 변동폭 비율 (Daily Price Range Ratio)
    # (당일 최고가 - 당일 최저가) / 시가
    def getDailyPriceRangeRatio(self) -> Dict:
        """
        당일 가격 변동폭과 관련된 비율을 계산합니다.
        
        Returns:
            Dict: 가격 변동폭 정보가 담긴 딕셔너리
                {
                    "range": float,                # 당일 고가-저가 (원화)
                    "range_ratio": float,          # 변동폭 / 시가 (%)
                    "current_in_range": float,     # 현재가의 레벨 (0~1, 0:저가, 1:고가)
                    "volatility": float            # 변동성 지표 (ATR 기반)
                }
        """
        # 당일 캔들 데이터 가져오기 (1시간 캔들, 최대 24개)
        candles_res = self.client.get_candles(market=self.market, interval="1h", limit=24)
        candles = candles_res.candles
        
        if not candles:
            # 캔들 데이터가 없는 경우 기본값 반환
            return {
                "range": 0.0,
                "range_ratio": 0.0,
                "current_in_range": 0.5,
                "volatility": 0.0
            }
        
        # 현재가 가져오기 (최신 캔들의 종가)
        current_price = candles[0].trade_price
        
        # 당일 시가 (최신 캔들이 당일 첫 캔들이 아닐 수 있으므로 여러 캔들 확인)
        # 간단히 하기 위해 가장 오래된 캔들의 시가를 당일 시가로 가정
        daily_open = candles[-1].opening_price if candles else current_price
        
        # 당일 최고가와 최저가 계산
        daily_high = max(candle.high_price for candle in candles)
        daily_low = min(candle.low_price for candle in candles)
        
        # 변동폭 계산
        price_range = daily_high - daily_low
        
        # 변동폭 비율 계산 (변동폭 / 시가)
        range_ratio = 0.0
        if daily_open > 0:
            range_ratio = price_range / daily_open
        
        # 현재가가 일일 범위 내에서 어디에 위치하는지 계산 (0: 저가, 1: 고가)
        current_in_range = 0.5  # 기본값
        if price_range > 0:
            current_in_range = (current_price - daily_low) / price_range
        
        # 변동성 지표 계산 (ATR 응용)
        # 각 캔들의 진폭 평균 (단순화된 ATR)
        candle_ranges = [candle.high_price - candle.low_price for candle in candles]
        volatility = np.mean(candle_ranges) / daily_open if daily_open > 0 else 0.0
        
        return {
            "range": price_range,
            "range_ratio": range_ratio,
            "current_in_range": current_in_range,
            "volatility": volatility
        }
        
    # 종합 캔들 지표 (Comprehensive Candle Indicators)
    # 모든 캔들 기반 지표를 종합적으로 반환
    def getAllCandleIndicators(self, interval: Literal["1m", "3m", "5m", "10m", "30m", "1h"] = "1m") -> Dict:
        """
        모든 캔들 기반 지표를 종합적으로 계산하여 반환합니다.
        
        Args:
            interval: 캔들 간격 (기본값: "1m" - 1분봉)
            
        Returns:
            Dict: 모든 캔들 기반 지표 정보
        """
        # 캔들 데이터 가져오기 (타임스탬프 용도)
        candles_res = self.client.get_candles(market=self.market, interval=interval, limit=1)
        
        volume_spike = self.getVolumeSpikeRatio(interval)
        candle_direction = self.getCandleDirection(interval)
        price_range = self.getDailyPriceRangeRatio()
        
        # 스캘핑 적합도 계산 (변동성과 거래량 급증 정도를 고려)
        scalping_suitability = (price_range["volatility"] * 0.7) + (min(volume_spike, 3.0) / 3.0 * 0.3)
        
        return {
            "volume_spike_ratio": volume_spike,
            "candle_direction": candle_direction,
            "price_range": price_range,
            "scalping_suitability": scalping_suitability,
            "timestamp": candles_res.candles[0].timestamp if candles_res.candles else 0
        }
        
    #
    # 추가 분석 지표
    #

    # 호가 벽 탐지 (Ask Wall Detection)
    def getAskWallPresence(self, threshold_ratio: float = 3.0) -> Dict:
        """
        상위 5개 호가에서 매도량이 급격히 증가하는 '매도벽'이 있는지 탐지합니다.
        
        Args:
            threshold_ratio: 벽으로 판단할 기준 비율 (기본값: 3.0)
                            이전 호가 대비 이 비율 이상 증가하면 벽으로 간주
                            
        Returns:
            Dict: 매도벽 정보가 담긴 딕셔너리
                {
                    "is_wall_present": bool,     # 매도벽 존재 여부
                    "wall_price": float,         # 벽이 있는 가격
                    "wall_size": float,          # 벽의 크기
                    "wall_ratio": float          # 이전 호가 대비 비율
                }
        """
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        
        if len(orderbook.orderbook_units) < 5:
            return {
                "is_wall_present": False,
                "wall_price": 0.0,
                "wall_size": 0.0,
                "wall_ratio": 0.0
            }
        
        # 상위 5개 호가 추출
        top_asks = [(unit.ask_price, unit.ask_size) for unit in orderbook.orderbook_units[:5]]
        
        # 매도벽 탐지
        is_wall_present = False
        wall_price = 0.0
        wall_size = 0.0
        wall_ratio = 0.0
        
        for i in range(len(top_asks) - 1):
            current_price, current_size = top_asks[i]
            next_price, next_size = top_asks[i+1]
            
            # 다음 호가의 크기가 현재 호가보다 threshold_ratio 배 이상 크면 벽으로 간주
            if next_size > current_size * threshold_ratio and next_size > 0:
                is_wall_present = True
                wall_price = next_price
                wall_size = next_size
                wall_ratio = next_size / current_size if current_size > 0 else threshold_ratio
                break
        
        return {
            "is_wall_present": is_wall_present,
            "wall_price": wall_price,
            "wall_size": wall_size,
            "wall_ratio": wall_ratio
        }
    
    # 대기 주문량 변화 감지 (Order Size Change Detection)
    def getOrderSizeChangeTrend(self) -> Dict:
        """
        총 매수/매도 대기 주문량의 변화 추세를 감지합니다.
        이전 불균형 차이와 현재 차이를 비교하여 추세를 판단합니다.
        
        Returns:
            Dict: 주문량 변화 추세 정보
                {
                    "current_difference": float,    # 현재 매수-매도 차이
                    "previous_difference": float,   # 이전 매수-매도 차이
                    "trend": str,                   # 'increasing', 'decreasing', 'neutral'
                    "significant_change": bool      # 변화가 유의미한지 여부
                }
        """
        current_diff = self.getOrderBookImbalanceDifference()
        current_time = time.time()
        
        # 이전 데이터가 없거나 2초 이상 지났으면 갱신
        if self._prev_order_diff is None or (current_time - self._prev_order_diff_time) > 2:
            trend = "neutral"
            significant_change = False
            prev_diff = 0
        else:
            prev_diff = self._prev_order_diff
            
            # 추세 판단
            if current_diff > prev_diff * 1.05:  # 5% 이상 증가
                trend = "increasing"
                significant_change = (current_diff > prev_diff * 1.10)  # 10% 이상 증가면 유의미
            elif current_diff < prev_diff * 0.95:  # 5% 이상 감소
                trend = "decreasing"
                significant_change = (current_diff < prev_diff * 0.90)  # 10% 이상 감소면 유의미
            else:
                trend = "neutral"
                significant_change = False
        
        # 현재 값을 이전 값으로 저장
        self._prev_order_diff = current_diff
        self._prev_order_diff_time = current_time
        
        return {
            "current_difference": current_diff,
            "previous_difference": prev_diff,
            "trend": trend,
            "significant_change": significant_change
        }
    
    # 체결 속도 확인 (Execution Speed Check)
    def getRecentTickSpeed(self, duration: float = 3.0, min_executions: int = 3) -> Dict:
        """
        최근 체결 속도를 확인합니다.
        지정된 기간 동안 최소 지정된 수 이상의 체결이 있었는지 확인합니다.
        
        Args:
            duration: 확인할 기간 (초) (기본값: 3.0)
            min_executions: 최소 체결 수 (기본값: 3)
            
        Returns:
            Dict: 체결 속도 정보
                {
                    "is_high_speed": bool,       # 빠른 체결 여부
                    "executions_count": int,     # 기간 내 체결 수
                    "average_interval": float,   # 평균 체결 간격 (초)
                }
        """
        if len(self._recent_executions) < 2:
            return {
                "is_high_speed": False,
                "executions_count": 0,
                "average_interval": 0.0
            }
        
        # 현재 시간
        current_time = time.time()
        
        # 지정된 기간 내의 체결만 필터링
        recent_executions = [t for t in self._recent_executions if (current_time - t) <= duration]
        
        # 체결 횟수
        execution_count = len(recent_executions)
        
        # 평균 체결 간격 계산
        avg_interval = 0.0
        if execution_count > 1:
            intervals = [recent_executions[i] - recent_executions[i+1] for i in range(execution_count-1)]
            avg_interval = np.mean(intervals)
        
        # 빠른 체결 여부 판단
        is_high_speed = execution_count >= min_executions
        
        return {
            "is_high_speed": is_high_speed,
            "executions_count": execution_count,
            "average_interval": avg_interval
        }
    
    # 매수 진입 종합 판단 (Buy Entry Decision)
    def evaluateBuyEntrySignal(self) -> Dict:
        """
        모든 지표를 종합적으로 분석하여 매수 진입 신호를 판단합니다.
        
        Returns:
            Dict: 매수 진입 판단 결과
                {
                    "should_enter": bool,        # 진입 추천 여부
                    "confidence": float,         # 신뢰도 (0~1)
                    "reasons": list,             # 판단 근거
                    "indicators": Dict           # 사용된 모든 지표 값
                }
        """
        # 1. 각 지표 계산
        orderbook_imbalance = self.getOrderBookImbalanceRatio()
        ask_wall = self.getAskWallPresence()
        order_trend = self.getOrderSizeChangeTrend()
        execution_bid_ratio = self.getExecutionBidRatio()
        volume_change = self.getVolumeChangeRatio()
        tick_speed = self.getRecentTickSpeed()
        volume_spike = self.getVolumeSpikeRatio()
        candle_direction = self.getCandleDirection()
        price_range = self.getDailyPriceRangeRatio()
        
        # 2. 모든 지표 종합
        all_indicators = {
            "orderbook_imbalance": orderbook_imbalance,
            "ask_wall": ask_wall,
            "order_trend": order_trend,
            "execution_bid_ratio": execution_bid_ratio,
            "volume_change": volume_change,
            "tick_speed": tick_speed,
            "volume_spike": volume_spike,
            "candle_direction": candle_direction,
            "price_range": price_range
        }
        
        # 3. 진입 조건 체크 및 결과 저장
        reasons = []
        negative_reasons = []
        
        # 호가 불균형 비율 체크 (0.6 이상이면 매수 우위)
        if orderbook_imbalance > 0.6:
            reasons.append("호가 불균형 비율이 0.6 이상 (현재: {:.2f})".format(orderbook_imbalance))
        else:
            negative_reasons.append("호가 불균형 비율이 0.6 미만 (현재: {:.2f})".format(orderbook_imbalance))
        
        # 매도벽 유무 체크 (매도벽이 없어야 함)
        if not ask_wall["is_wall_present"]:
            reasons.append("상위 호가에 매도벽 없음")
        else:
            negative_reasons.append("매도벽 감지됨 (가격: {}, 크기: {})".format(
                ask_wall["wall_price"], ask_wall["wall_size"]))
        
        # 체결 우위 비율 체크 (0.7 이상이면 강한 매수세)
        if execution_bid_ratio > 0.7:
            reasons.append("체결 우위 비율이 0.7 이상 (현재: {:.2f})".format(execution_bid_ratio))
        else:
            negative_reasons.append("체결 우위 비율이 0.7 미만 (현재: {:.2f})".format(execution_bid_ratio))
        
        # 체결 속도 체크 (빠른 체결이 있어야 함)
        if tick_speed["is_high_speed"]:
            reasons.append("최근 체결 속도가 빠름 ({}초간 {}회)".format(
                3.0, tick_speed["executions_count"]))
        else:
            negative_reasons.append("체결 속도가 느림 ({}초간 {}회)".format(
                3.0, tick_speed["executions_count"]))
        
        # 거래량 급증 비율 체크 (1.5 이상이면 유의미한 유입)
        if volume_spike > 1.5:
            reasons.append("거래량 급증 비율이 1.5 이상 (현재: {:.2f})".format(volume_spike))
        else:
            negative_reasons.append("거래량 급증 비율이 1.5 미만 (현재: {:.2f})".format(volume_spike))
        
        # 캔들 방향 체크 (양봉이면 상승 흐름)
        if candle_direction["is_bullish"]:
            reasons.append("직전 캔들이 양봉")
        else:
            negative_reasons.append("직전 캔들이 음봉 또는 보합")
        
        # 변동성 체크 (0.005(0.5%) 이상이면 변동성 충분)
        minute_volatility = price_range["volatility"] / 24  # 시간 변동성을 분 단위로 환산 (대략적)
        if minute_volatility > 0.0005:  # 0.05% 정도면 1분봉에서 의미있는 변동성
            reasons.append("1분봉 변동성이 충분함 (현재: {:.4f})".format(minute_volatility))
        else:
            negative_reasons.append("1분봉 변동성이 낮음 (현재: {:.4f})".format(minute_volatility))
        
        # 4. 최종 판단
        # 핵심 지표 3개: 호가 불균형, 체결 우위, 거래량 급증
        core_conditions = [
            orderbook_imbalance > 0.6,
            execution_bid_ratio > 0.7,
            volume_spike > 1.5
        ]
        
        # 보조 지표 3개: 매도벽 없음, 체결 속도, 캔들 방향
        auxiliary_conditions = [
            not ask_wall["is_wall_present"],
            tick_speed["is_high_speed"],
            candle_direction["is_bullish"]
        ]
        
        # 핵심 조건 중 최소 2개와 보조 조건 중 최소 2개를 만족해야 진입 추천
        core_met = sum(core_conditions) >= 2
        auxiliary_met = sum(auxiliary_conditions) >= 2
        
        should_enter = core_met and auxiliary_met
        
        # 신뢰도 계산 (0~1)
        # 핵심 지표 70%, 보조 지표 30% 비중
        core_confidence = sum(core_conditions) / len(core_conditions) * 0.7
        auxiliary_confidence = sum(auxiliary_conditions) / len(auxiliary_conditions) * 0.3
        confidence = core_confidence + auxiliary_confidence
        
        return {
            "should_enter": should_enter,
            "confidence": confidence,
            "reasons": reasons,
            "negative_reasons": negative_reasons,
            "indicators": all_indicators
        }
        
    # 목표가와 손절가 계산 (Target and Stop Loss Calculator)
    def calculateTargetAndStopLoss(self, entry_price: float, strategy_type: Literal["fast_scalping", "flow_tracking", "breakout"] = "fast_scalping") -> Dict:
        """
        매수 진입 가격을 기준으로 목표가와 손절가를 계산합니다.
        
        Args:
            entry_price: 매수 진입 가격
            strategy_type: 전략 유형
                - fast_scalping: 초단타 전략 (빠른 회전, 작은 수익)
                - flow_tracking: 흐름 추적 전략 (체결/호가 지표 기반)
                - breakout: 돌파 추세 전략 (전고점 돌파 목표)
                
        Returns:
            Dict: 목표가와 손절가 정보
                {
                    "target_price": float,            # 목표가
                    "stop_loss_price": float,         # 손절가
                    "target_ratio": float,            # 목표 수익률
                    "stop_loss_ratio": float,         # 손절 비율
                    "rr_ratio": float,                # Risk/Reward 비율
                    "net_profit_ratio": float,        # 수수료 차감 후 순수익률
                    "strategy_info": Dict             # 전략별 추가 정보
                }
        """
        # 기본 비율 설정 (전략별로 차등 적용)
        if strategy_type == "fast_scalping":
            base_target_ratio = 0.004  # 0.4%
            base_stop_loss_ratio = 0.002  # 0.2%
        elif strategy_type == "flow_tracking":
            base_target_ratio = 0.006  # 0.6%
            base_stop_loss_ratio = 0.003  # 0.3%
        elif strategy_type == "breakout":
            base_target_ratio = 0.008  # 0.8%
            base_stop_loss_ratio = 0.004  # 0.4%
        else:
            base_target_ratio = 0.005  # 0.5%
            base_stop_loss_ratio = 0.002  # 0.2%
            
        # 시장 지표를 활용한 동적 조정
        # 1. 호가창 데이터 활용
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        orderbook_units = orderbook.orderbook_units[:5]  # 상위 5개 호가만 확인
        
        # 2. 최근 캔들 데이터 활용
        candles_res = self.client.get_candles(market=self.market, interval="1m", limit=5)
        candles = candles_res.candles
        
        # 3. 현재 시장 변동성 고려
        volatility_info = self.getDailyPriceRangeRatio()
        minute_volatility = volatility_info["volatility"] / 24  # 시간 변동성을 분 단위로 환산
        
        # 목표가 동적 계산
        target_ratio = base_target_ratio
        stop_loss_ratio = base_stop_loss_ratio
        strategy_info = {}
        
        # 전략별 동적 조정
        if strategy_type == "fast_scalping":
            # 초단타: 호가창 기준 매도 2~3호가 이상에 목표가 설정
            if len(orderbook_units) >= 3:
                # 상위 3개 호가에서 의미있는 매도 저항 찾기
                for i, unit in enumerate(orderbook_units[:3]):
                    if unit.ask_price > entry_price:
                        # 목표가를 해당 호가에 설정 (약간의 마진 고려)
                        target_price_by_orderbook = unit.ask_price * 0.9999
                        dynamic_target_ratio = (target_price_by_orderbook - entry_price) / entry_price
                        
                        # 기본 수치와 호가 기반 수치 중 더 보수적인 값 선택
                        target_ratio = max(base_target_ratio, dynamic_target_ratio)
                        break
            
            # 손절가는 직전 캔들 저가의 약간 아래로 설정
            if candles and len(candles) > 0:
                prev_candle_low = candles[0].low_price
                if prev_candle_low < entry_price:
                    dynamic_stop_loss_ratio = (entry_price - prev_candle_low) / entry_price
                    dynamic_stop_loss_ratio += 0.0005  # 추가 마진
                    
                    # 기본 수치와 캔들 기반 수치 중 더 타이트한 값 선택
                    stop_loss_ratio = min(base_stop_loss_ratio, dynamic_stop_loss_ratio)
        
        elif strategy_type == "flow_tracking":
            # 흐름 추적: 변동성에 따라 목표가 조정
            # 변동성이 높을수록 목표가를 높게 설정
            volatility_factor = min(2.0, max(1.0, minute_volatility / 0.0005 * 1.2))
            target_ratio = base_target_ratio * volatility_factor
            
            # 체결 세기에 따라 손절폭 조정
            execution_strength = self.getExecutionBidRatio()
            if execution_strength > 0.8:  # 매수세가 매우 강할 때
                stop_loss_ratio = base_stop_loss_ratio * 0.8  # 손절폭 축소
            else:
                stop_loss_ratio = base_stop_loss_ratio
                
            # 추가 정보 저장
            strategy_info["volatility_factor"] = volatility_factor
            strategy_info["execution_strength"] = execution_strength
            
        elif strategy_type == "breakout":
            # 돌파 추세: 최근 5개 캔들 중 고가를 목표로 설정
            if candles and len(candles) >= 3:
                # 최근 5분 내 최고가 찾기
                recent_high = max(candle.high_price for candle in candles)
                
                if recent_high > entry_price:
                    dynamic_target_ratio = (recent_high - entry_price) / entry_price
                    # 약간의 추가 마진
                    target_ratio = dynamic_target_ratio * 1.05
                
                # 최근 5분 내 최저가 기준 손절 설정
                recent_low = min(candle.low_price for candle in candles)
                if recent_low < entry_price:
                    dynamic_stop_loss_ratio = (entry_price - recent_low) / entry_price
                    # 약간의 추가 마진
                    stop_loss_ratio = dynamic_stop_loss_ratio * 1.05
                
                # 추가 정보 저장
                strategy_info["recent_high"] = recent_high
                strategy_info["recent_low"] = recent_low
        
        # 최종 목표가와 손절가 계산
        target_price = entry_price * (1 + target_ratio)
        stop_loss_price = entry_price * (1 - stop_loss_ratio)
        
        # RR 비율 검증 및 조정 (최소 1.5:1 이상)
        rr_ratio = target_ratio / stop_loss_ratio if stop_loss_ratio > 0 else 0
        
        # RR 비율이 1.5 미만이면 목표가 상향 조정
        if rr_ratio < 1.5 and stop_loss_ratio > 0:
            target_ratio = stop_loss_ratio * 1.5
            target_price = entry_price * (1 + target_ratio)
            rr_ratio = 1.5
        
        # 수수료 반영 실제 수익률 계산 (업비트 기준 매수+매도 약 0.04%)
        total_fee_ratio = 0.0004  # 0.04%
        net_profit_ratio = target_ratio - total_fee_ratio
        
        return {
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "target_ratio": target_ratio,
            "stop_loss_ratio": stop_loss_ratio,
            "rr_ratio": rr_ratio,
            "net_profit_ratio": net_profit_ratio,
            "strategy_info": strategy_info
        }
    
    # 진입 후 동적 목표가/손절가 업데이트 (Dynamic Target/Stop Loss Update)
    def updateTargetAndStopLoss(self, entry_price: float, current_price: float, initial_target: Dict, elapsed_seconds: int = 0) -> Dict:
        """
        진입 후 시장 상황에 따라 목표가와 손절가를 동적으로 업데이트합니다.
        
        Args:
            entry_price: 매수 진입 가격
            current_price: 현재 가격
            initial_target: calculateTargetAndStopLoss 함수에서 반환된 초기 목표가/손절가 정보
            elapsed_seconds: 진입 후 경과 시간(초)
            
        Returns:
            Dict: 업데이트된 목표가와 손절가 정보
        """
        # 기존 목표가와 손절가
        original_target = initial_target["target_price"]
        original_stop_loss = initial_target["stop_loss_price"]
        
        # 현재 수익률 계산
        current_profit_ratio = (current_price - entry_price) / entry_price
        
        # 업데이트된 목표가와 손절가 (기본값은 원래 값)
        updated_target = original_target
        updated_stop_loss = original_stop_loss
        
        # 체결 흐름 확인
        execution_bid_ratio = self.getExecutionBidRatio()
        
        # 1. 상승 중인 경우 손절가 상향 조정 (이익 보호)
        # 수익이 발생 중이고 (현재가 > 진입가), 진입가의 50% 이상 올랐을 경우
        if current_profit_ratio > 0:
            # 목표의 50% 이상 달성 시 손절가를 원가 이상으로 이동
            target_achievement = current_profit_ratio / ((original_target - entry_price) / entry_price)
            
            if target_achievement >= 0.5:
                # 손절가를 원가 또는 현재가의 일정 비율 아래로 설정
                new_stop_loss = max(entry_price, current_price * 0.998)  # 최소 원가, 또는 현재가의 0.2% 아래
                updated_stop_loss = new_stop_loss
        
        # 2. 체결 흐름 변화에 따른 조기 손절 또는 목표가 조정
        if execution_bid_ratio < 0.4:  # 매도 체결이 급증하는 경우
            # 상승 중이면 목표가를 하향 조정하여 빠르게 익절
            if current_profit_ratio > 0:
                # 현재 위치에서 목표가까지의 거리를 줄임 (예: 남은 거리의 70%만 목표로)
                remaining_distance = original_target - current_price
                updated_target = current_price + (remaining_distance * 0.7)
            
            # 이미 손실 상태이면 손절 범위 좁힘 (추가 손실 방지)
            elif current_profit_ratio < 0 and elapsed_seconds > 30:  # 최소 30초 경과 후
                updated_stop_loss = current_price * 0.998  # 현재가에서 0.2% 아래로 손절 위치 좁힘
        
        # 3. 시간 경과에 따른 조정 (장시간 횡보 시 탈출 전략)
        if elapsed_seconds > 300:  # 5분 이상 경과
            # 수익 중이면 목표가 하향 조정
            if current_profit_ratio > 0.001:  # 0.1% 이상 수익 중
                updated_target = min(updated_target, current_price * 1.002)  # 현재가의 0.2% 상방으로 목표가 하향
            
            # 손실 최소화를 위한 손절가 상향
            if current_profit_ratio > -0.001:  # 손실이 0.1% 미만인 경우
                updated_stop_loss = max(updated_stop_loss, entry_price * 0.998)  # 원가의 0.2% 이내로 손절가 상향
        
        # 추가 상태 정보
        update_info = {
            "current_profit_ratio": current_profit_ratio,
            "execution_bid_ratio": execution_bid_ratio,
            "elapsed_seconds": elapsed_seconds,
            "price_moved": current_price != entry_price,
            "stop_loss_moved": updated_stop_loss != original_stop_loss,
            "target_moved": updated_target != original_target
        }
        
        # 최종 결과 반환
        return {
            "target_price": updated_target,
            "stop_loss_price": updated_stop_loss,
            "entry_price": entry_price,
            "current_price": current_price,
            "update_info": update_info
        }
