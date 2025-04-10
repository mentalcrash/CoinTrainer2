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
        
    def get_market_overview(self, symbol: str) -> Dict:
        """
        분봉 기준 시장 개요 조회 (스캘핑 트레이딩용)

        Returns:
            Dict: {
                'current_price': float,       # 현재가
                'ma1': float,                 # 1분 이동평균
                'ma3': float,                 # 3분 이동평균
                'ma5': float,                 # 5분 이동평균
                'rsi_1': float,               # 1분 RSI
                'rsi_3': float,               # 3분 RSI
                'volatility_3m': float,       # 3분 변동성
                'volatility_5m': float,       # 5분 변동성
                'price_trend_1m': str,        # 1분 가격 추세
                'volume_trend_1m': str,       # 1분 거래량 추세
                'vwap_3m': float,            # 3분 VWAP
                'bb_width': float,           # 볼린저 밴드 폭
                'order_book_ratio': float,   # 매수/매도 호가 비율
                'spread': float,             # 호가 스프레드
                'premium_rate': float,       # 선물 프리미엄/디스카운트
                'funding_rate': float,       # 선물 펀딩비율
                'price_stability': float,    # 가격 안정성 점수
            }
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.MARKET,
                message=f"{symbol} 시장 개요 조회 시작",
                data={"symbol": symbol}
            )

        try:
            # 현재가 및 호가 데이터 조회
            current_data = self.ticker.get_current_price(symbol)
            orderbook = self.ticker.get_orderbook(symbol)
            
            # 1분봉 데이터 조회 (최근 5분)
            candles = self.candle.get_minute_candles(symbol=symbol, unit=1, count=5)
            df = pd.DataFrame(candles)
            df['close'] = pd.to_numeric(df['trade_price'])
            df['volume'] = pd.to_numeric(df['candle_acc_trade_volume'])
            
            # 이동평균 계산
            ma1 = df['close'].rolling(window=1).mean().iloc[-1]
            ma3 = df['close'].rolling(window=3).mean().iloc[-1]
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            
            # RSI 계산 (1분, 3분)
            def calculate_rsi(prices: pd.Series, period: int) -> float:
                delta = prices.diff()
                gain = delta.where(delta > 0, 0).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                return 100 - (100 / (1 + rs)).iloc[-1]
                
            rsi_1 = calculate_rsi(df['close'], 1)
            rsi_3 = calculate_rsi(df['close'], 3)
            
            # 변동성 계산
            volatility_3m = df['close'].pct_change().rolling(window=3).std().iloc[-1] * 100
            volatility_5m = df['close'].pct_change().rolling(window=5).std().iloc[-1] * 100
            
            # VWAP 계산
            df['vwap'] = (df['close'] * df['volume']).rolling(window=3).sum() / df['volume'].rolling(window=3).sum()
            vwap_3m = df['vwap'].iloc[-1]
            
            # 볼린저 밴드 폭
            bb_std = df['close'].rolling(window=3).std()
            bb_upper = df['close'].rolling(window=3).mean() + (bb_std * 2)
            bb_lower = df['close'].rolling(window=3).mean() - (bb_std * 2)
            bb_width = ((bb_upper - bb_lower) / df['close'].rolling(window=3).mean() * 100).iloc[-1]
            
            # 호가 데이터 분석
            bid_total = sum([float(bid['price']) * float(bid['quantity']) for bid in orderbook['bids']])
            ask_total = sum([float(ask['price']) * float(ask['quantity']) for ask in orderbook['asks']])
            order_book_ratio = bid_total / ask_total if ask_total > 0 else 1.0
            
            # 호가 스프레드
            best_bid = float(orderbook['bids'][0]['price'])
            best_ask = float(orderbook['asks'][0]['price'])
            spread = (best_ask - best_bid) / best_bid * 100
            
            # 추세 계산 (1분)
            def get_trend(current: float, previous: float) -> str:
                change = (current - previous) / previous * 100
                if change > 0.1:  # 0.1% 이상
                    return "상승"
                elif change < -0.1:  # -0.1% 이하
                    return "하락"
                return "횡보"
                
            price_trend_1m = get_trend(df['close'].iloc[-1], df['close'].iloc[-2])
            volume_trend_1m = get_trend(df['volume'].iloc[-1], df['volume'].iloc[-2])
            
            # 선물 데이터
            futures_data = self.ticker.analyze_premium_index(symbol)
            
            result = {
                'current_price': current_data['trade_price'],
                'ma1': ma1,
                'ma3': ma3,
                'ma5': ma5,
                'rsi_1': rsi_1,
                'rsi_3': rsi_3,
                'volatility_3m': volatility_3m,
                'volatility_5m': volatility_5m,
                'price_trend_1m': price_trend_1m,
                'volume_trend_1m': volume_trend_1m,
                'vwap_3m': vwap_3m,
                'bb_width': bb_width,
                'order_book_ratio': order_book_ratio,
                'spread': spread,
                'premium_rate': futures_data['premium_rate'],
                'funding_rate': futures_data['funding_rate'],
                'price_stability': futures_data['price_stability']
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message=f"{symbol} 스캘핑 시장 분석 완료",
                    data=result
                )
            
            return result
            
        except Exception as e:
            error_msg = f"{symbol} 시장 개요 조회 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data={"error": str(e)}
                )
            raise
            
    def get_trading_signals(self, market_data: dict) -> Dict:
        """스캘핑 매매를 위한 신호 분석
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            Dict: {
                'price_signal': str,        # 가격 신호 (매수/매도/중립)
                'momentum_signal': str,     # 모멘텀 신호 (강세/약세/중립)
                'volume_signal': str,       # 거래량 신호 (활발/침체/중립)
                'orderbook_signal': str,    # 호가창 신호 (매수세/매도세/중립)
                'futures_signal': str,      # 선물 신호 (매수/매도/중립)
                'market_state': str,        # 시장 상태 (안정/불안정)
                'overall_signal': str,      # 종합 신호 (매수/매도/관망)
                'signal_strength': float,   # 신호 강도 (0.0 ~ 1.0)
                'entry_timing': str,        # 진입 타이밍 (즉시/대기)
            }
        """
        try:
            # 1. 가격 신호 분석 (이동평균, VWAP 기반)
            price_signal = "중립"
            current_price = market_data['current_price']
            
            # 단기 이동평균 정배열/역배열 확인
            if current_price > market_data['ma1'] > market_data['ma3']:
                price_signal = "매수"
            elif current_price < market_data['ma1'] < market_data['ma3']:
                price_signal = "매도"
                
            # VWAP과의 관계 확인
            vwap_diff = (current_price - market_data['vwap_3m']) / market_data['vwap_3m'] * 100
            if abs(vwap_diff) > 0.1:  # 0.1% 이상 차이
                price_signal = "매수" if vwap_diff < 0 else "매도"  # VWAP 회귀 전략
            
            # 2. 모멘텀 신호 분석 (RSI, 볼린저밴드 기반)
            momentum_signal = "중립"
            
            # RSI 1분봉 기준
            if market_data['rsi_1'] < 30:
                momentum_signal = "강세"
            elif market_data['rsi_1'] > 70:
                momentum_signal = "약세"
            
            # RSI 방향성 확인
            if market_data['rsi_1'] > market_data['rsi_3']:
                momentum_signal = "강세" if momentum_signal != "약세" else "중립"
            elif market_data['rsi_1'] < market_data['rsi_3']:
                momentum_signal = "약세" if momentum_signal != "강세" else "중립"
            
            # 3. 거래량 신호 분석
            volume_signal = "중립"
            if market_data['volume_trend_1m'] == "상승":
                volume_signal = "활발"
            elif market_data['volume_trend_1m'] == "하락":
                volume_signal = "침체"
            
            # 4. 호가창 신호 분석
            orderbook_signal = "중립"
            if market_data['order_book_ratio'] > 1.1:  # 매수세 10% 이상 우위
                orderbook_signal = "매수세"
            elif market_data['order_book_ratio'] < 0.9:  # 매도세 10% 이상 우위
                orderbook_signal = "매도세"
            
            # 5. 선물 신호 분석 (프리미엄/펀딩비율 기반)
            futures_signal = "중립"
            if market_data['premium_rate'] < -0.2 and market_data['funding_rate'] < -0.008:
                futures_signal = "매수"
            elif market_data['premium_rate'] > 0.2 and market_data['funding_rate'] > 0.008:
                futures_signal = "매도"
            
            # 6. 시장 상태 판단
            market_state = "안정"
            if (market_data['volatility_3m'] > 0.5 or  # 변동성 0.5% 초과
                market_data['bb_width'] > 0.8 or       # 볼린저밴드 폭 0.8% 초과
                market_data['spread'] > 0.1):          # 스프레드 0.1% 초과
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
            
            result = {
                'price_signal': price_signal,
                'momentum_signal': momentum_signal,
                'volume_signal': volume_signal,
                'orderbook_signal': orderbook_signal,
                'futures_signal': futures_signal,
                'market_state': market_state,
                'overall_signal': overall_signal,
                'signal_strength': abs(signal_strength),
                'entry_timing': entry_timing
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message="스캘핑 매매 신호 분석 완료",
                    data=result
                )
            
            return result
            
        except Exception as e:
            error_msg = f"매매 신호 분석 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data={"error": str(e)}
                )
            raise
            
    def get_asset_info(self, symbol: str) -> Dict:
        """계정 자산 정보 조회
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            Dict: {
                'balance': float,           # 보유 수량
                'locked': float,            # 거래중 수량
                'avg_buy_price': float,     # 매수 평균가
                'current_value': float,     # 현재 평가금액
                'profit_loss': float,       # 평가손익
                'profit_loss_rate': float,  # 수익률(%)
                'krw_balance': float,       # 보유 현금(KRW)
                'krw_locked': float,        # 거래중인 현금(KRW)
            }
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.ASSET,
                message=f"{symbol} 자산 정보 조회 시작",
                data={"symbol": symbol}
            )
        
        try:
            # 계정 잔고 조회
            balances = self.account.get_balance()
            if not balances:
                raise Exception("잔고 조회 실패")
                
            # 현재가 조회
            current_price = self.ticker.get_current_price(symbol)
            if not current_price:
                raise Exception("현재가 조회 실패")
                
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
                result = {
                    'balance': 0.0,
                    'locked': 0.0,
                    'avg_buy_price': 0.0,
                    'current_value': 0.0,
                    'profit_loss': 0.0,
                    'profit_loss_rate': 0.0,
                    'krw_balance': krw_balance,
                    'krw_locked': krw_locked
                }
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ASSET,
                        message=f"{symbol} 자산 정보 조회 완료 (보유 없음)",
                        data=result
                    )
                
                return result
                
            # 평가금액 계산
            current_value = float(asset['balance']) * float(current_price['trade_price'])
            
            # 평가손익 계산
            invested = float(asset['balance']) * float(asset['avg_buy_price'])
            profit_loss = current_value - invested
            profit_loss_rate = (profit_loss / invested * 100) if invested > 0 else 0.0
            
            result = {
                'balance': float(asset['balance']),
                'locked': float(asset['locked']),
                'avg_buy_price': float(asset['avg_buy_price']),
                'current_value': current_value,
                'profit_loss': profit_loss,
                'profit_loss_rate': profit_loss_rate,
                'krw_balance': krw_balance,
                'krw_locked': krw_locked
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ASSET,
                    message=f"{symbol} 자산 정보 조회 완료",
                    data=result
                )
            
            return result
            
        except Exception as e:
            error_msg = f"{symbol} 자산 정보 조회 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data={"error": str(e)}
                )
            raise
            
    def analyze(self, symbol: str) -> Dict:
        """심볼에 대한 전체 분석을 수행합니다.
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            Dict: {
                'success': bool,            # 분석 성공 여부
                'error': str,               # 에러 메시지 (실패시)
                'market_data': Dict,        # 시장 데이터
                'signals': Dict,            # 매매 신호
                'asset_info': Dict,         # 자산 정보
                'timestamp': datetime       # 분석 시간
            }
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{symbol} 시장 분석 시작",
                data={"symbol": symbol}
            )
        
        try:
            # 1. 시장 데이터 수집
            market_data = self.get_market_overview(symbol)

            # 2. 매매 신호 분석
            signals = self.get_trading_signals(market_data)

            # 3. 자산 정보 조회
            asset_info = self.get_asset_info(symbol)
            
            if not all([market_data, signals, asset_info]):
                error_msg = "데이터 조회 실패"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=error_msg,
                        data={
                            "market_data_success": bool(market_data),
                            "signals_success": bool(signals),
                            "asset_info_success": bool(asset_info)
                        }
                    )
                raise Exception(error_msg)
                
            result = {
                'success': True,
                'error': None,
                'market_data': market_data,
                'signals': signals,
                'asset_info': asset_info,
                'timestamp': datetime.now()
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{symbol} 시장 분석 완료",
                    data=result
                )
            
            return result
            
        except Exception as e:
            error_msg = f"{symbol} 분석 실패: {str(e)}"
            error_result = {
                'success': False,
                'error': str(e),
                'market_data': None,
                'signals': None,
                'asset_info': None,
                'timestamp': datetime.now()
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data=error_result
                )
            
            raise
            
    def format_analysis(self, symbol: str) -> str:
        """분석 결과를 보기 좋게 포맷팅
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            포맷팅된 분석 결과 문자열
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{symbol} 분석 결과 포맷팅 시작",
                data={"symbol": symbol}
            )
        
        # 분석 수행
        result = self.analyze(symbol)
        
        if not result['success']:
            return f"분석 실패: {result['error']}"
            
        market_data = result['market_data']
        signals = result['signals']
        asset_info = result['asset_info']
        
        output = []
        output.append(f"\n📊 {symbol} 매매 분석 ({result['timestamp'].strftime('%Y-%m-%d %H:%M')})")
        output.append("=" * 60)
        
        # 시장 상황
        output.append("\n🌍 시장 상황")
        output.append(f"• 현재가: {market_data['current_price']:,.0f} KRW ({market_data['daily_change']:+.2f}%)")
        output.append(f"• 거래량: {market_data['daily_volume']:,.0f}")
        output.append(f"• 이동평균: MA5 {market_data['ma5']:,.0f} / MA20 {market_data['ma20']:,.0f}")
        output.append(f"• RSI(14): {market_data['rsi_14']:.1f}")
        output.append(f"• 변동성: {market_data['volatility']:.1f}%")
        
        # 매매 신호
        output.append("\n🎯 매매 신호")
        output.append(f"• 가격 신호: {signals['price_signal']}")
        output.append(f"• 모멘텀 신호: {signals['momentum_signal']}")
        output.append(f"• 거래량 신호: {signals['volume_signal']}")
        output.append(f"• 호가창 신호: {signals['orderbook_signal']}")
        output.append(f"• 종합 신호: {signals['overall_signal']} (강도: {signals['signal_strength']:.1%})")
        
        # 자산 정보
        if asset_info['balance'] > 0:
            output.append("\n💰 자산 정보")
            output.append(f"• 보유수량: {asset_info['balance']:.8f} {symbol}")
            output.append(f"• 매수평균가: {asset_info['avg_buy_price']:,.0f} KRW")
            output.append(f"• 평가금액: {asset_info['current_value']:,.0f} KRW")
            output.append(f"• 평가손익: {asset_info['profit_loss']:,.0f} KRW ({asset_info['profit_loss_rate']:+.2f}%)")
            output.append(f"• 보유 현금: {asset_info['krw_balance']:,.0f} KRW")
            if asset_info['krw_locked'] > 0:
                output.append(f"• 거래중인 현금: {asset_info['krw_locked']:,.0f} KRW")
        
        formatted_result = "\n".join(output)
        return formatted_result 