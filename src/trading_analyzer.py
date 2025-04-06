from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
import os
import logging
from pathlib import Path
from src.account import Account
from src.ticker import Ticker
from src.candle import Candle

class TradingAnalyzer:
    """암호화폐 매매 판단을 위한 데이터 수집 및 분석 클래스"""
    
    def __init__(self, api_key: str, secret_key: str):
        """초기화
        
        Args:
            api_key: 빗썸 API 키
            secret_key: 빗썸 Secret 키
        """
        self.account = Account(api_key, secret_key)
        self.ticker = Ticker()
        self.candle = Candle()
        
        # 로거 설정
        self.logger = logging.getLogger("trading_analyzer")
        self.logger.setLevel(logging.INFO)
        
        # 로그 포맷 설정
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 파일 핸들러
        self._setup_log_directory()
        
    def _setup_log_directory(self):
        """로그 디렉토리 설정"""
        # 기본 로그 디렉토리 생성
        log_dir = Path(".temp/trading_analysis")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 날짜별 디렉토리 생성
        today = datetime.now().strftime("%Y%m%d")
        self.today_dir = log_dir / today
        self.today_dir.mkdir(exist_ok=True)
        
        # 파일 핸들러 추가
        file_handler = logging.FileHandler(
            self.today_dir / "trading_analysis.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        )
        self.logger.addHandler(file_handler)
        
    def _save_analysis_result(self, symbol: str, data: Dict, prefix: str):
        """분석 결과를 파일로 저장
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            data: 저장할 데이터
            prefix: 파일 이름 접두사
        """
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{prefix}_{symbol}_{timestamp}.json"
        filepath = self.today_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        self.logger.info(f"{symbol} {prefix} 저장 완료: {filepath}")
        
    def get_market_overview(self, symbol: str) -> Dict:
        """시장 전반적인 상황 조회
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            Dict: {
                'current_price': float,      # 현재가
                'daily_change': float,       # 일간 변동률(%)
                'daily_volume': float,       # 일간 거래량
                'ma5': float,                # 5일 이동평균
                'ma20': float,               # 20일 이동평균
                'rsi_14': float,             # 14일 RSI
                'volatility': float,         # 변동성 (표준편차)
                'price_trend': str,          # 가격 추세 (상승/하락/횡보)
                'volume_trend': str,         # 거래량 추세 (증가/감소/횡보)
            }
        """
        self.logger.info(f"{symbol} 시장 개요 조회 시작...")
        
        try:
            # 현재가 정보 조회
            current_data = self.ticker.get_current_price(symbol)
            if not current_data:
                raise Exception("현재가 조회 실패")
            self.logger.info(f"{symbol} 현재가 조회 완료")
                
            # 일봉 데이터 조회 (최근 20일)
            daily_candles = self.candle.get_daily_candles(symbol, count=20)
            if not daily_candles:
                raise Exception("일봉 데이터 조회 실패")
            self.logger.info(f"{symbol} 일봉 데이터 조회 완료")
                
            # 데이터프레임 변환
            df = pd.DataFrame(daily_candles)
            df['close'] = pd.to_numeric(df['trade_price'])
            df['volume'] = pd.to_numeric(df['candle_acc_trade_volume'])
            
            # 이동평균 계산
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]
            
            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 변동성 (20일 표준편차)
            volatility = df['close'].pct_change().std() * 100
            
            # 추세 판단 (3일 이동평균 기울기)
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
                'daily_change': current_data['signed_change_rate'],
                'daily_volume': current_data['acc_trade_volume_24h'],
                'ma5': ma5,
                'ma20': ma20,
                'rsi_14': rsi,
                'volatility': volatility,
                'price_trend': get_trend(price_slope),
                'volume_trend': get_trend(volume_slope)
            }
            
            # 결과 저장
            self._save_analysis_result(symbol, result, "market_overview")
            
            return result
            
        except Exception as e:
            self.logger.error(f"{symbol} 시장 개요 조회 실패: {str(e)}")
            return None
            
    def get_trading_signals(self, symbol: str) -> Dict:
        """매매 신호 분석
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            Dict: {
                'ma_signal': str,           # 이동평균 신호 (골든크로스/데드크로스/중립)
                'rsi_signal': str,          # RSI 신호 (과매수/과매도/중립)
                'volume_signal': str,        # 거래량 신호 (급증/급감/중립)
                'trend_signal': str,         # 추세 신호 (상승추세/하락추세/횡보)
                'overall_signal': str,       # 종합 신호 (매수/매도/관망)
                'signal_strength': float,    # 신호 강도 (0.0 ~ 1.0)
            }
        """
        self.logger.info(f"{symbol} 매매 신호 분석 시작...")
        
        try:
            # 시장 개요 데이터 활용
            market_data = self.get_market_overview(symbol)
            if not market_data:
                raise Exception("시장 데이터 조회 실패")
                
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
            if market_data['volume_trend'] == "상승" and abs(market_data['daily_volume']) > 30:
                volume_signal = "급증"
            elif market_data['volume_trend'] == "하락" and abs(market_data['daily_volume']) > 30:
                volume_signal = "급감"
                
            # 추세 신호
            trend_signal = market_data['price_trend']
            
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
            
            # 신호 강도 계산 (-1.0 ~ 1.0)
            signal_strength = signal_points / total_points
            
            # 종합 신호 결정
            if signal_strength > 0.3:
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
                'overall_signal': overall_signal,
                'signal_strength': abs(signal_strength)
            }
            
            # 결과 저장
            self._save_analysis_result(symbol, result, "trading_signals")
            
            return result
            
        except Exception as e:
            self.logger.error(f"{symbol} 매매 신호 분석 실패: {str(e)}")
            return None
            
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
            }
        """
        self.logger.info(f"{symbol} 자산 정보 조회 시작...")
        
        try:
            # 계정 잔고 조회
            balances = self.account.get_balance()
            if not balances:
                raise Exception("잔고 조회 실패")
                
            # 현재가 조회
            current_price = self.ticker.get_current_price(symbol)
            if not current_price:
                raise Exception("현재가 조회 실패")
                
            # 해당 심볼의 잔고 찾기
            asset = None
            for balance in balances:
                if balance['currency'] == symbol:
                    asset = balance
                    break
                    
            if not asset:
                return {
                    'balance': 0.0,
                    'locked': 0.0,
                    'avg_buy_price': 0.0,
                    'current_value': 0.0,
                    'profit_loss': 0.0,
                    'profit_loss_rate': 0.0
                }
                
            # 평가금액 계산
            current_value = asset['balance'] * current_price['trade_price']
            
            # 평가손익 계산
            invested = asset['balance'] * asset['avg_buy_price']
            profit_loss = current_value - invested
            profit_loss_rate = (profit_loss / invested * 100) if invested > 0 else 0.0
            
            result = {
                'balance': asset['balance'],
                'locked': asset['locked'],
                'avg_buy_price': asset['avg_buy_price'],
                'current_value': current_value,
                'profit_loss': profit_loss,
                'profit_loss_rate': profit_loss_rate
            }
            
            # 결과 저장
            self._save_analysis_result(symbol, result, "asset_info")
            
            return result
            
        except Exception as e:
            self.logger.error(f"{symbol} 자산 정보 조회 실패: {str(e)}")
            return None
            
    def format_analysis(self, symbol: str) -> str:
        """분석 결과를 보기 좋게 포맷팅
        
        Args:
            symbol: 심볼 (예: BTC, ETH)
            
        Returns:
            포맷팅된 분석 결과 문자열
        """
        self.logger.info(f"{symbol} 분석 결과 포맷팅 시작...")
        
        try:
            market_data = self.get_market_overview(symbol)
            signals = self.get_trading_signals(symbol)
            asset_info = self.get_asset_info(symbol)
            
            if not all([market_data, signals, asset_info]):
                self.logger.error(f"{symbol} 데이터 조회 실패")
                return "데이터 조회 실패"
                
            output = []
            output.append(f"\n📊 {symbol} 매매 분석 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
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
            
            formatted_result = "\n".join(output)
            
            # 포맷팅된 결과 저장
            timestamp = datetime.now().strftime("%H%M%S")
            filepath = self.today_dir / f"analysis_{symbol}_{timestamp}.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(formatted_result)
                
            self.logger.info(f"{symbol} 분석 결과 저장 완료: {filepath}")
            
            return formatted_result
            
        except Exception as e:
            error_msg = f"{symbol} 분석 결과 포맷팅 실패: {str(e)}"
            self.logger.error(error_msg)
            return error_msg 