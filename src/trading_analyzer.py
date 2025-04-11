from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from src.account import Account
from src.ticker import Ticker
from src.candle import Candle
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import (
    MarketOverview, TradingSignals, AssetInfo, AnalysisResult,
    PriceTrendType, VolumeTrendType, CurrentPrice,
    SignalType, MomentumType, VolumeSignalType,
    OrderbookType, MarketStateType, OverallSignalType, EntryTimingType
)

class TradingAnalyzer:
    """암호화폐 매매 판단을 위한 데이터 수집 및 분석 클래스"""
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        log_manager: Optional[LogManager] = None
    ):
        """초기화
        
        Args:
            api_key: 빗썸 API 키
            secret_key: 빗썸 Secret 키
            log_manager: 로그 매니저 (선택사항)
        """
        self.account = Account(api_key, secret_key, log_manager)
        self.ticker = Ticker(log_manager)
        self.candle = Candle(log_manager)
        self.log_manager = log_manager
        
        # 실행 시간 기반 디렉토리 생성
        base_dir = Path(".temp")
        base_dir.mkdir(exist_ok=True)
        
        now = datetime.now()
        run_id = now.strftime("%Y%m%d_%H%M%S")
        self.run_dir = base_dir / run_id
        self.run_dir.mkdir(exist_ok=True)
        
    def get_market_overview(self, symbol: str, current_price: CurrentPrice) -> MarketOverview:
        """
        분봉 기준 시장 개요 조회 (스캘핑 트레이딩용)

        Args:
            symbol: 심볼 (예: BTC, ETH)
            current_price: 현재가 정보 (선택사항, 없으면 조회)

        Returns:
            MarketOverview: 시장 개요 데이터
        """
        try:
            # 호가 데이터 조회
            orderbook = self.ticker.get_orderbook(symbol)
            
            # 1분봉 데이터 조회 (최근 5분)
            candles = self.candle.get_minute_candles(symbol=symbol, unit=1, count=50)
            df = pd.DataFrame(candles)
            df['close'] = pd.to_numeric(df['trade_price'])
            df['volume'] = pd.to_numeric(df['candle_acc_trade_volume'])
            df['open'] = pd.to_numeric(df['opening_price'])
            df['high'] = pd.to_numeric(df['high_price'])
            df['low'] = pd.to_numeric(df['low_price'])
            
            # 이동평균 계산
            ma1 = df['close'].rolling(window=1).mean().iloc[0]
            ma3 = df['close'].rolling(window=3).mean().iloc[0]
            ma5 = df['close'].rolling(window=5).mean().iloc[0]
            ma10 = df['close'].rolling(window=10).mean().iloc[0]
            ma20 = df['close'].rolling(window=20).mean().iloc[0]
            
            # RSI 계산 (1분, 3분)
            def calculate_rsi(prices: pd.Series, period: int) -> float:
                # 가격 변화 계산
                delta = prices.diff()

                # 상승폭과 하락폭 분리
                gains = delta.where(delta > 0, 0)
                losses = -delta.where(delta < 0, 0)  # 절대값으로 변환

                # 첫 평균 계산 (SMA 방식)
                avg_gains = gains.rolling(window=period, min_periods=1).mean()
                avg_losses = losses.rolling(window=period, min_periods=1).mean()

                # RS 계산 (0으로 나누기 방지)
                rs = avg_gains / avg_losses.replace(0, float('inf'))

                # RSI 계산
                rsi = 100 - (100 / (1 + rs))
                return float(rsi.iloc[0])  # 가장 최근 값 반환

            rsi_1 = calculate_rsi(df['close'], 1)
            rsi_3 = calculate_rsi(df['close'], 3)
            rsi_7 = calculate_rsi(df['close'], 7)
            rsi_14 = calculate_rsi(df['close'], 14)
            
            # 변동성 계산
            def calculate_volatility(prices: pd.Series, window: int) -> float:
                # 수익률 계산
                returns = prices.pct_change()
                
                # 이상치 제거 (상하위 1% 제거)
                lower_bound = returns.quantile(0.01)
                upper_bound = returns.quantile(0.99)
                returns = returns.clip(lower=lower_bound, upper=upper_bound)
                
                # 변동성 계산 (연율화하지 않은 표준편차)
                volatility = returns.rolling(window=window, min_periods=1).std()
                
                # 퍼센트로 변환
                return float(volatility.iloc[0] * 100)

            volatility_3m = calculate_volatility(df['close'], 3)
            volatility_5m = calculate_volatility(df['close'], 5)
            volatility_10m = calculate_volatility(df['close'], 10)
            volatility_15m = calculate_volatility(df['close'], 15)
            
            # VWAP 계산
            df['vwap'] = (df['close'] * df['volume']).rolling(window=3).sum() / df['volume'].rolling(window=3).sum()
            vwap_3m = df['vwap'].iloc[0]
            
            # 볼린저 밴드 폭
            bb_std = df['close'].rolling(window=3).std()
            bb_upper = df['close'].rolling(window=3).mean() + (bb_std * 2)
            bb_lower = df['close'].rolling(window=3).mean() - (bb_std * 2)
            bb_width = ((bb_upper - bb_lower) / df['close'].rolling(window=3).mean() * 100).iloc[0]
            
            # 호가 데이터 분석
            bid_total = sum([float(bid['price']) * float(bid['quantity']) for bid in orderbook['bids']])
            ask_total = sum([float(ask['price']) * float(ask['quantity']) for ask in orderbook['asks']])
            order_book_ratio = bid_total / ask_total if ask_total > 0 else 1.0
            
            # 호가 스프레드
            best_bid = float(orderbook['bids'][0]['price'])
            best_ask = float(orderbook['asks'][0]['price'])
            spread = (best_ask - best_bid) / best_bid * 100
            
            # 추세 계산 (1분)
            def get_trend(current: float, previous: float) -> PriceTrendType:
                change = (current - previous) / previous * 100
                if change > 0.1:  # 0.1% 이상
                    return "상승"
                elif change < -0.1:  # -0.1% 이하
                    return "하락"
                return "횡보"
                
            price_trend_1m = get_trend(df['close'].iloc[0], df['close'].iloc[1])
            volume_trend_1m = get_trend(df['volume'].iloc[0], df['volume'].iloc[1])
            
            # 선물 데이터
            futures_data = self.ticker.analyze_premium_index(symbol)
            
            # 캔들 실체 강도 분석
            def analyze_candle_strength(row: pd.Series) -> Tuple[float, str]:
                candle_body = row['close'] - row['open']
                candle_range = row['high'] - row['low']
                body_ratio = abs(candle_body) / candle_range if candle_range != 0 else 0
                
                # 캔들 강도 해석
                if body_ratio > 0.7:
                    strength = "강함"
                elif body_ratio > 0.4:
                    strength = "중간"
                else:
                    strength = "약함"
                
                return body_ratio, strength
            
            latest_candle = df.iloc[0]
            body_ratio, candle_strength = analyze_candle_strength(latest_candle)
            
            # 단기 고점/저점 갱신 여부 확인
            new_high = bool(df['close'].iloc[0] > df['high'].rolling(window=5).max().shift(1).iloc[0])
            new_low = bool(df['close'].iloc[0] < df['low'].rolling(window=5).min().shift(1).iloc[0])
            
            # MarketOverview 객체 생성
            result = MarketOverview(
                current_price=current_price.trade_price,
                ma1=ma1,
                ma3=ma3,
                ma5=ma5,
                ma10=ma10,
                ma20=ma20,
                rsi_1=rsi_1,
                rsi_3=rsi_3,
                rsi_7=rsi_7,
                rsi_14=rsi_14,
                volatility_3m=volatility_3m,
                volatility_5m=volatility_5m,
                volatility_10m=volatility_10m,
                volatility_15m=volatility_15m,
                price_trend_1m=price_trend_1m,
                volume_trend_1m=volume_trend_1m,
                vwap_3m=vwap_3m,
                bb_width=bb_width,
                order_book_ratio=order_book_ratio,
                spread=spread,
                premium_rate=futures_data['premium_rate'],
                funding_rate=futures_data['funding_rate'],
                price_stability=futures_data['price_stability'],
                candle_body_ratio=body_ratio,
                candle_strength=candle_strength,
                new_high_5m=new_high,
                new_low_5m=new_low
            )
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message=f"{symbol} 스캘핑 시장 분석 완료",
                    data=result.__dict__  # dataclass를 dict로 변환하여 로깅
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 시장 분석 실패: {str(e)}",
                    data={"symbol": symbol, "error": str(e)}
                )
            raise
            
    def get_trading_signals(self, market_data: MarketOverview) -> TradingSignals:
        """스캘핑 매매를 위한 신호 분석
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            TradingSignals: 매매 신호 데이터
        """
        try:
            # 1. 가격 신호 분석 (이동평균, VWAP 기반)
            price_signal: SignalType = "중립"
            current_price = market_data.current_price
            
            # 단기 이동평균 정배열/역배열 확인
            if current_price > market_data.ma1 > market_data.ma3:
                price_signal = "매수"
            elif current_price < market_data.ma1 < market_data.ma3:
                price_signal = "매도"
                
            # VWAP과의 관계 확인
            vwap_diff = (current_price - market_data.vwap_3m) / market_data.vwap_3m * 100
            if abs(vwap_diff) > 0.1:  # 0.1% 이상 차이
                price_signal = "매수" if vwap_diff < 0 else "매도"  # VWAP 회귀 전략
            
            # 2. 모멘텀 신호 분석 (RSI, 볼린저밴드 기반)
            momentum_signal: MomentumType = "중립"
            
            # RSI 1분봉 기준
            if market_data.rsi_1 < 30:
                momentum_signal = "강세"
            elif market_data.rsi_1 > 70:
                momentum_signal = "약세"
            
            # RSI 방향성 확인
            if market_data.rsi_1 > market_data.rsi_3:
                momentum_signal = "강세" if momentum_signal != "약세" else "중립"
            elif market_data.rsi_1 < market_data.rsi_3:
                momentum_signal = "약세" if momentum_signal != "강세" else "중립"
            
            # 3. 거래량 신호 분석
            volume_signal: VolumeSignalType = "중립"
            if market_data.volume_trend_1m == "상승":
                volume_signal = "활발"
            elif market_data.volume_trend_1m == "하락":
                volume_signal = "침체"
            
            # 4. 호가창 신호 분석
            orderbook_signal: OrderbookType = "중립"
            if market_data.order_book_ratio > 1.1:  # 매수세 10% 이상 우위
                orderbook_signal = "매수세"
            elif market_data.order_book_ratio < 0.9:  # 매도세 10% 이상 우위
                orderbook_signal = "매도세"
            
            # 5. 선물 신호 분석 (프리미엄/펀딩비율 기반)
            futures_signal: SignalType = "중립"
            if market_data.premium_rate < -0.2 and market_data.funding_rate < -0.008:
                futures_signal = "매수"
            elif market_data.premium_rate > 0.2 and market_data.funding_rate > 0.008:
                futures_signal = "매도"
            
            # 6. 시장 상태 판단
            market_state: MarketStateType = "안정"
            if (market_data.volatility_3m > 0.5 or  # 변동성 0.5% 초과
                market_data.bb_width > 0.8 or       # 볼린저밴드 폭 0.8% 초과
                market_data.spread > 0.1):          # 스프레드 0.1% 초과
                market_state = "불안정"
            
            # 7. 종합 신호 계산
            signal_points = 0
            total_points = 0
            
            # 가격 신호 (2.0)
            if price_signal == "매수":
                signal_points += 2.0
            elif price_signal == "매도":
                signal_points -= 2.0
            total_points += 2.0
            
            # 모멘텀 신호 (1.5)
            if momentum_signal == "강세":
                signal_points += 1.5
            elif momentum_signal == "약세":
                signal_points -= 1.5
            total_points += 1.5
            
            # 거래량 신호 (1.0)
            if volume_signal == "활발":
                signal_points += 1.0
            elif volume_signal == "침체":
                signal_points -= 1.0
            total_points += 1.0
            
            # 호가창 신호 (2.0)
            if orderbook_signal == "매수세":
                signal_points += 2.0
            elif orderbook_signal == "매도세":
                signal_points -= 2.0
            total_points += 2.0
            
            # 선물 신호 (1.5)
            if futures_signal == "매수":
                signal_points += 1.5
            elif futures_signal == "매도":
                signal_points -= 1.5
            total_points += 1.5
            
            # 신호 강도 계산 (-1.0 ~ 1.0)
            signal_strength = signal_points / total_points
            
            # 8. 종합 신호 및 진입 타이밍 결정
            overall_signal: OverallSignalType
            entry_timing: EntryTimingType
            
            if market_state == "불안정" and abs(signal_strength) < 0.5:
                overall_signal = "관망"
                entry_timing = "대기"
            elif signal_strength > 0.2:  # 매수 임계값 0.2
                overall_signal = "매수"
                entry_timing = "즉시" if signal_strength > 0.4 else "대기"
            elif signal_strength < -0.2:  # 매도 임계값 -0.2
                overall_signal = "매도"
                entry_timing = "즉시" if signal_strength < -0.4 else "대기"
            else:
                overall_signal = "관망"
                entry_timing = "대기"
            
            result = TradingSignals(
                price_signal=price_signal,
                momentum_signal=momentum_signal,
                volume_signal=volume_signal,
                orderbook_signal=orderbook_signal,
                futures_signal=futures_signal,
                market_state=market_state,
                overall_signal=overall_signal,
                signal_strength=abs(signal_strength),
                entry_timing=entry_timing
            )
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message="매매 신호 분석 완료",
                    data=result.__dict__
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"매매 신호 분석 실패: {str(e)}",
                    data={"error": str(e)}
                )
            raise
            
    def get_asset_info(self, symbol: str, current_price: CurrentPrice) -> AssetInfo:
        """계정 자산 정보 조회
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            current_price: 현재가 정보 (선택사항, 없으면 조회)
            
        Returns:
            AssetInfo: 자산 정보 데이터
        """
        try:
            # 계정 잔고 조회
            balances = self.account.get_balance()
            if not balances:
                raise Exception("잔고 조회 실패")
                
            # KRW 잔고 찾기
            krw_balance = 0.0
            krw_locked = 0.0
            for balance in balances:
                if balance['currency'] == 'KRW':
                    krw_balance = float(balance['balance'])
                    krw_locked = float(balance['locked'])
                    break
                
            # 해당 심볼의 잔고 찾기
            asset = None
            for balance in balances:
                if balance['currency'] == symbol:
                    asset = balance
                    break
                    
            if not asset:
                result = AssetInfo(
                    balance=0.0,
                    locked=0.0,
                    avg_buy_price=0.0,
                    current_value=0.0,
                    profit_loss=0.0,
                    profit_loss_rate=0.0,
                    krw_balance=krw_balance,
                    krw_locked=krw_locked
                )
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ASSET,
                        message=f"{symbol} 자산 정보 조회 완료",
                        data={"symbol": symbol, "status": "미보유"}
                    )
                
                return result
                
            # 평가금액 계산
            current_value = float(asset['balance']) * current_price.trade_price
            
            # 평가손익 계산
            invested = float(asset['balance']) * float(asset['avg_buy_price'])
            profit_loss = current_value - invested
            profit_loss_rate = (profit_loss / invested * 100) if invested > 0 else 0.0
            
            result = AssetInfo(
                balance=float(asset['balance']),
                locked=float(asset['locked']),
                avg_buy_price=float(asset['avg_buy_price']),
                current_value=current_value,
                profit_loss=profit_loss,
                profit_loss_rate=profit_loss_rate,
                krw_balance=krw_balance,
                krw_locked=krw_locked
            )
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ASSET,
                    message=f"{symbol} 자산 정보 조회 완료",
                    data=result.__dict__
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 자산 정보 조회 실패: {str(e)}",
                    data={"symbol": symbol, "error": str(e)}
                )
            raise
            
    def analyze(self, symbol: str) -> AnalysisResult:
        """심볼에 대한 전체 분석을 수행합니다.
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            AnalysisResult: 종합 분석 결과 데이터
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{symbol} 시장 분석 시작",
                data={"symbol": symbol}
            )
        
        try:
            # 0. 현재가 조회 (공통으로 사용)
            current_price = self.ticker.get_current_price(symbol)
        
            # 1. 시장 데이터 수집
            market_data = self.get_market_overview(symbol, current_price)

            # 2. 매매 신호 분석
            signals = self.get_trading_signals(market_data)

            # 3. 자산 정보 조회
            asset_info = self.get_asset_info(symbol, current_price)
            
            # 데이터 유효성 검사 (데이터클래스는 항상 True이므로 None 체크로 변경)
            if any(data is None for data in [market_data, signals, asset_info]):
                error_msg = "데이터 조회 실패"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=error_msg,
                        data={
                            "market_data_success": market_data is not None,
                            "signals_success": signals is not None,
                            "asset_info_success": asset_info is not None
                        }
                    )
                raise Exception(error_msg)
            
            return AnalysisResult(
                success=True,
                market_data=market_data,
                signals=signals,
                asset_info=asset_info,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 분석 실패: {str(e)}",
                    data={"error": str(e)}
                )
            
            raise