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
        분봉 기준 시장 개요 조회 (단기 트레이딩용)

        Args:
            symbol: 심볼 (예: BTC, ETH)

        Returns:
            Dict: {
                'current_price': float,       # 현재가
                'minute_change': float,       # 직전 1시간 대비 등락률 (%)
                'minute_volume': float,       # 1시간 누적 거래량
                'ma5': float,                 # 5분 이동평균
                'ma20': float,                # 20분 이동평균
                'rsi_14': float,              # 14분 RSI
                'volatility': float,          # 변동성 (20분 표준편차)
                'price_trend': str,           # 가격 추세 (상승/하락/횡보)
                'volume_trend': str,          # 거래량 추세 (증가/감소/횡보)
                'premium_rate': float,        # 선물 프리미엄/디스카운트 비율 (%)
                'funding_rate': float,        # 선물 펀딩비율 (%)
                'market_bias': str,           # 선물 시장 편향 (롱 편향/숏 편향/중립)
                'price_stability': float,     # 선물 가격 안정성 점수 (0~1)
                'signal_strength': float      # 선물 신호 강도 (-1 ~ 1)
            }
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.MARKET,
                message=f"{symbol} 시장 개요 조회 시작",
                data={"symbol": symbol}
            )

        try:
            current_data = self.ticker.get_current_price(symbol)
            if not current_data:
                raise Exception("현재가 조회 실패")

            # 선물 지표 조회
            futures_data = self.ticker.analyze_premium_index(symbol)
            if not futures_data:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=f"{symbol} 선물 지표 조회 실패",
                        data={"symbol": symbol}
                    )

            # 1분봉 60개 = 최근 1시간 데이터
            candles = self.candle.get_minute_candles(symbol=symbol, unit=1, count=60)
            if not candles:
                raise Exception("분봉 데이터 조회 실패")

            df = pd.DataFrame(candles)
            df['close'] = pd.to_numeric(df['trade_price'])
            df['volume'] = pd.to_numeric(df['candle_acc_trade_volume'])

            # 이동 평균 (분 기준)
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]

            # RSI 14분 기준
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            # 20분간의 변동성 (수익률 기준 표준편차, % 단위)
            volatility = df['close'].pct_change().rolling(window=20).std().iloc[-1] * 100

            # 가격/거래량 추세: 최근 3분간의 기울기
            ma3 = df['close'].rolling(window=3).mean()
            price_slope = (ma3.iloc[-1] - ma3.iloc[-2]) / ma3.iloc[-2] * 100
            volume_slope = (df['volume'].iloc[-1] - df['volume'].iloc[-2]) / df['volume'].iloc[-2] * 100

            def get_trend(slope: float) -> str:
                if slope > 1.0:
                    return "상승"
                elif slope < -1.0:
                    return "하락"
                else:
                    return "횡보"

            result = {
                'current_price': current_data['trade_price'],
                'minute_change': (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100,
                'minute_volume': df['volume'].sum(),
                'ma5': ma5,
                'ma20': ma20,
                'rsi_14': rsi,
                'volatility': volatility,
                'price_trend': get_trend(price_slope),
                'volume_trend': get_trend(volume_slope),
                'volume_slope': volume_slope,
                # 선물 지표 추가
                'premium_rate': futures_data['premium_rate'],
                'funding_rate': futures_data['funding_rate'],
                'market_bias': futures_data['market_bias'],
                'price_stability': futures_data['price_stability'],
                'signal_strength': futures_data['signal_strength']
            }

            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message=f"{symbol} 시장 개요 분석 완료",
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
        """매매 신호 분석
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            Dict: {
                'ma_signal': str,           # 이동평균 신호 (골든크로스/데드크로스/중립)
                'rsi_signal': str,          # RSI 신호 (과매수/과매도/중립)
                'volume_signal': str,        # 거래량 신호 (급증/급감/중립)
                'trend_signal': str,         # 추세 신호 (상승추세/하락추세/횡보)
                'futures_signal': str,       # 선물 신호 (매수/매도/중립)
                'futures_bias': str,         # 선물 시장 편향 (롱 편향/숏 편향/중립)
                'futures_stability': str,    # 선물 안정성 (안정/불안정)
                'overall_signal': str,       # 종합 신호 (매수/매도/관망)
                'signal_strength': float,    # 신호 강도 (0.0 ~ 1.0)
            }
        """
        try:
            # 이동평균 신호
            ma_signal = "중립"
            if market_data['ma5'] > market_data['ma20']:
                ma_signal = "골든크로스"
            elif market_data['ma5'] < market_data['ma20']:
                ma_signal = "데드크로스"
                
            # RSI 신호
            rsi_signal = "중립"
            if market_data['rsi_14'] > 70:
                rsi_signal = "과매수"
            elif market_data['rsi_14'] < 30:
                rsi_signal = "과매도"
                
            # 거래량 신호 (전일 대비 30% 이상 변화)
            volume_signal = "중립"
            if market_data['volume_trend'] == "상승" and abs(market_data['volume_slope']) > 30:
                volume_signal = "급증"
            elif market_data['volume_trend'] == "하락" and abs(market_data['volume_slope']) > 30:
                volume_signal = "급감"
                
            # 추세 신호
            trend_signal = market_data['price_trend']

            # 선물 신호 분석
            futures_signal = "중립"
            # 프리미엄이 높고 펀딩비율이 양수면 매도 신호
            if market_data['premium_rate'] > 0.5 and market_data['funding_rate'] > 0.01:
                futures_signal = "매도"
            # 디스카운트이고 펀딩비율이 음수면 매수 신호
            elif market_data['premium_rate'] < -0.5 and market_data['funding_rate'] < -0.01:
                futures_signal = "매수"

            # 선물 시장 편향
            futures_bias = market_data['market_bias']

            # 선물 안정성
            futures_stability = "안정"
            if market_data['price_stability'] < 0.7:  # 70% 미만이면 불안정
                futures_stability = "불안정"
            
            # 종합 신호 계산
            signal_points = 0
            total_points = 0
            
            # 이동평균 점수
            if ma_signal == "골든크로스":
                signal_points += 2
            elif ma_signal == "데드크로스":
                signal_points -= 2
            total_points += 2
            
            # RSI 점수
            if rsi_signal == "과매도":
                signal_points += 1.5
            elif rsi_signal == "과매수":
                signal_points -= 1.5
            total_points += 1.5
            
            # 거래량 점수
            if volume_signal == "급증":
                signal_points += 1
            elif volume_signal == "급감":
                signal_points -= 1
            total_points += 1
            
            # 추세 점수
            if trend_signal == "상승":
                signal_points += 1.5
            elif trend_signal == "하락":
                signal_points -= 1.5
            total_points += 1.5

            # 선물 신호 점수 (가중치 2.0)
            if futures_signal == "매수":
                signal_points += 2.0
            elif futures_signal == "매도":
                signal_points -= 2.0
            total_points += 2.0

            # 선물 시장 편향 점수 (가중치 1.0)
            if futures_bias == "롱 편향":
                signal_points -= 1.0  # 역방향 트레이딩
            elif futures_bias == "숏 편향":
                signal_points += 1.0  # 역방향 트레이딩
            total_points += 1.0
            
            # 신호 강도 계산 (-1.0 ~ 1.0)
            signal_strength = signal_points / total_points
            
            # 종합 신호 결정 (선물 안정성 고려)
            if futures_stability == "불안정":
                overall_signal = "관망"  # 불안정할 때는 관망
            elif signal_strength > 0.3:
                overall_signal = "매수"
            elif signal_strength < -0.3:
                overall_signal = "매도"
            else:
                overall_signal = "관망"
            
            result = {
                'ma_signal': ma_signal,
                'rsi_signal': rsi_signal,
                'volume_signal': volume_signal,
                'trend_signal': trend_signal,
                'futures_signal': futures_signal,
                'futures_bias': futures_bias,
                'futures_stability': futures_stability,
                'overall_signal': overall_signal,
                'signal_strength': abs(signal_strength)
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"매매 신호 분석 완료",
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
        output.append(f"• 이동평균: {signals['ma_signal']}")
        output.append(f"• RSI: {signals['rsi_signal']}")
        output.append(f"• 거래량: {signals['volume_signal']}")
        output.append(f"• 추세: {signals['trend_signal']}")
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