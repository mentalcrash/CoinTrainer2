import requests
import traceback
from typing import Dict, Optional
from datetime import datetime
from src.utils.log_manager import LogManager, LogCategory

class Ticker:
    def __init__(self, log_manager: Optional[LogManager] = None):
        """빗썸 시세 조회 클래스 초기화
        
        Args:
            log_manager (Optional[LogManager]): 로그 매니저 (선택사항)
        """
        self.base_url = "https://api.bithumb.com"
        self.binance_url = "https://fapi.binance.com"
        self.log_manager = log_manager
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """현재가 조회
        
        Args:
            symbol (str): 심볼 (예: "BTC_KRW")
            
        Returns:
            Optional[Dict]: 
                - 성공시: {
                    'symbol': str,           # 심볼
                    'current_price': float,  # 현재가
                    'daily_change': float,   # 전일대비
                    'daily_volume': float,   # 거래량
                    'timestamp': int         # 타임스탬프
                }
                - 오류 발생시: None
        """

        market = f'KRW-{symbol}'

        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 현재가 조회 요청",
                data={"symbol": symbol}
            )
        
        try:
            response = requests.get(
                f"{self.base_url}/v1/ticker",
                params={"markets": market}
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    if self.log_manager:
                        self.log_manager.log(
                            category=LogCategory.ERROR,
                            message="빗썸 API: 현재가 조회 실패 - 오류 응답",
                            data=result['error']
                        )
                    return None
                else:
                    if self.log_manager:
                        self.log_manager.log(
                            category=LogCategory.API,
                            message="빗썸 API: 현재가 조회 성공",
                            data={
                                "request_url": f"{self.base_url}/v1/ticker",
                                "response_status": response.status_code,
                                "symbol": symbol,
                                "response": result
                            }
                        )
                    
                    return result[0]
            else:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="빗썸 API: 현재가 조회 실패 - HTTP 오류",
                        data={
                            "request_url": f"{self.base_url}/v1/ticker",
                            "response_status": response.status_code,
                            "symbol": symbol,
                            "response": response.text,
                            "error_traceback": traceback.format_stack()
                        }
                    )
                return None
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="빗썸 API: 현재가 조회 실패 - 예외 발생",
                    data={
                        "request_url": f"{self.base_url}/v1/ticker",
                        "symbol": symbol,
                        "error": str(e),
                        "error_traceback": traceback.format_exc().split('\n')
                    }
                )
            return None
    
    def _format_ticker_data(self, data: Dict) -> Dict:
        """시세 데이터 포맷팅
        
        Args:
            data (Dict): API 응답 데이터
            
        Returns:
            Dict: 포맷팅된 시세 정보
        """
        return {
            'market': data['market'],
            'trade_date': data['trade_date'],
            'trade_time': data['trade_time'],
            'trade_date_kst': data['trade_date_kst'],
            'trade_time_kst': data['trade_time_kst'],
            'opening_price': float(data['opening_price']),
            'high_price': float(data['high_price']),
            'low_price': float(data['low_price']),
            'trade_price': float(data['trade_price']),
            'prev_closing_price': float(data['prev_closing_price']),
            'change': data['change'],
            'change_price': float(data['change_price']),
            'change_rate': float(data['change_rate']),
            'signed_change_price': float(data['signed_change_price']),
            'signed_change_rate': float(data['signed_change_rate']),
            'trade_volume': float(data['trade_volume']),
            'acc_trade_volume': float(data['acc_trade_volume']),
            'acc_trade_volume_24h': float(data['acc_trade_volume_24h']),
            'acc_trade_price': float(data['acc_trade_price']),
            'acc_trade_price_24h': float(data['acc_trade_price_24h']),
            'highest_52_week_price': float(data['highest_52_week_price']),
            'highest_52_week_date': data['highest_52_week_date'],
            'lowest_52_week_price': float(data['lowest_52_week_price']),
            'lowest_52_week_date': data['lowest_52_week_date'],
            'timestamp': int(data['timestamp'])
        } 

    def analyze_premium_index(self, symbol: str) -> Dict:
        """프리미엄 인덱스 데이터를 분석합니다.

        Args:
            symbol (str): 분석할 심볼 (예: XRP)

        Returns:
            Dict: 분석 결과
            {
                'premium_rate': float,      # 프리미엄/디스카운트 비율 (%)
                'funding_rate': float,      # 펀딩비율
                'market_bias': str,         # 시장 편향 ('롱 편향', '숏 편향', '중립')
                'price_stability': float,   # 가격 안정성 점수 (0~1)
                'signal_strength': float    # 신호 강도 (-1 ~ 1)
            }
        """
        try:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="바이낸스 API: 프리미엄 인덱스 조회 요청",
                    data={"symbol": symbol}
                )

            # Binance API 호출
            response = requests.get(f"{self.binance_url}/fapi/v1/premiumIndex?symbol={symbol}USDT")
            response.raise_for_status()
            data = response.json()

            # 프리미엄/디스카운트 계산
            mark_price = float(data['markPrice'])
            index_price = float(data['indexPrice'])
            premium_rate = ((mark_price - index_price) / index_price) * 100

            # 펀딩비율
            funding_rate = float(data['lastFundingRate']) * 100

            # 시장 편향 판단
            if funding_rate > 0.008:  # 0.008% 이상 (기존 0.01%)
                market_bias = "롱 편향"
            elif funding_rate < -0.008:  # -0.008% 이하 (기존 -0.01%)
                market_bias = "숏 편향"
            else:
                market_bias = "중립"

            # 가격 안정성 점수 계산 (마크가격과 인덱스가격의 유사도)
            price_stability = 1 - min(abs(premium_rate) / 0.8, 1)  # 0.8% 차이를 기준으로 (기존 1%)

            # 신호 강도 계산 (-1: 강한 매도, 1: 강한 매수)
            signal_strength = -funding_rate * 1.2  # 신호 강도 20% 증가

            result = {
                'premium_rate': premium_rate,
                'funding_rate': funding_rate,
                'market_bias': market_bias,
                'price_stability': price_stability,
                'signal_strength': signal_strength
            }

            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message=f"{symbol} 프리미엄 인덱스 분석 완료",
                    data=result
                )

            return result

        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="프리미엄 인덱스 분석 실패",
                    data={"symbol": symbol, "error": str(e)}
                )
            return {
                'premium_rate': 0.0,
                'funding_rate': 0.0,
                'market_bias': "중립",
                'price_stability': 1.0,
                'signal_strength': 0.0
            } 