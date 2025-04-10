import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.utils.log_manager import LogManager, LogCategory

class Candle:
    """빗썸 캔들 데이터 관리 클래스"""
    
    BASE_URL = "https://api.bithumb.com/v1/candles"
    
    def __init__(self, log_manager: Optional[LogManager] = None):
        """
        Args:
            log_manager (Optional[LogManager]): 로그 매니저 (선택사항)
        """
        self.session = requests.Session()
        self.log_manager = log_manager
    
    def _get_market_code(self, symbol: str) -> str:
        """심볼에서 마켓 코드 생성
        
        Args:
            symbol: 심볼 코드 (예: BTC, ETH)
            
        Returns:
            마켓 코드 (예: KRW-BTC)
        """
        return f"KRW-{symbol.upper()}"
    
    def get_minute_candles(
        self,
        symbol: str,
        unit: int,
        to: Optional[str] = None,
        count: int = 200
    ) -> List[Dict[str, Any]]:
        """분 캔들 데이터 조회
        
        Args:
            symbol: 심볼 코드 (예: BTC, ETH)
            unit: 분 단위 (1, 3, 5, 10, 15, 30, 60, 240)
            to: 마지막 캔들 시각 (ISO8601 형식)
            count: 캔들 개수 (최대 200개)
            
        Returns:
            캔들 데이터 리스트
        """
        endpoint = f"{self.BASE_URL}/minutes/{unit}"
        params = {
            "market": self._get_market_code(symbol),
            "count": min(count, 200)
        }
        if to:
            params["to"] = to
            
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            result = response.json()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 분봉 데이터 조회 성공",
                    data={
                        "request_url": endpoint,
                        "response_status": response.status_code,
                        "symbol": symbol,
                        "candles_count": len(result),
                        "unit": unit,
                        "result": result
                    }
                )
                
            return result
            
        except Exception as e:
            error_msg = f"분봉 데이터 조회 중 오류 발생: {e}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 분봉 데이터 조회 실패",
                    data={
                        "request_url": endpoint,
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
            print(error_msg)
            raise
    
    def get_daily_candles(
        self,
        symbol: str,
        to: Optional[str] = None,
        count: int = 200,
        converting_price_unit: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """일 캔들 데이터 조회
        
        Args:
            symbol: 심볼 코드 (예: BTC, ETH)
            to: 마지막 캔들 시각 (ISO8601 형식)
            count: 캔들 개수 (최대 200개)
            converting_price_unit: 종가 환산 화폐 단위 (예: KRW)
            
        Returns:
            캔들 데이터 리스트
        """
        endpoint = f"{self.BASE_URL}/days"
        params = {
            "market": self._get_market_code(symbol),
            "count": min(count, 200)
        }
        if to:
            params["to"] = to
        if converting_price_unit:
            params["convertingPriceUnit"] = converting_price_unit
            
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 일봉 데이터 조회 요청",
                data={
                    "symbol": symbol,
                    "count": params["count"],
                    "to": to,
                    "converting_price_unit": converting_price_unit
                }
            )
            
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            result = response.json()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 일봉 데이터 조회 성공",
                    data={
                        "request_url": endpoint,
                        "response_status": response.status_code,
                        "symbol": symbol,
                        "candles_count": len(result)
                    }
                )
                
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message="일봉 데이터 업데이트",
                    data={
                        "symbol": symbol,
                        "candles_count": len(result),
                        "first_candle_time": result[0]["candle_date_time_kst"] if result else None,
                        "last_candle_time": result[-1]["candle_date_time_kst"] if result else None
                    }
                )
                
            return result
            
        except Exception as e:
            error_msg = f"일봉 데이터 조회 중 오류 발생: {e}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 일봉 데이터 조회 실패",
                    data={
                        "request_url": endpoint,
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
            print(error_msg)
            raise
    
    def get_weekly_candles(
        self,
        symbol: str,
        to: Optional[str] = None,
        count: int = 200
    ) -> List[Dict[str, Any]]:
        """주 캔들 데이터 조회
        
        Args:
            symbol: 심볼 코드 (예: BTC, ETH)
            to: 마지막 캔들 시각 (ISO8601 형식)
            count: 캔들 개수 (최대 200개)
            
        Returns:
            캔들 데이터 리스트
        """
        endpoint = f"{self.BASE_URL}/weeks"
        params = {
            "market": self._get_market_code(symbol),
            "count": min(count, 200)
        }
        if to:
            params["to"] = to
            
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 주봉 데이터 조회 요청",
                data={
                    "symbol": symbol,
                    "count": params["count"],
                    "to": to
                }
            )
            
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            result = response.json()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 주봉 데이터 조회 성공",
                    data={
                        "request_url": endpoint,
                        "response_status": response.status_code,
                        "symbol": symbol,
                        "candles_count": len(result)
                    }
                )
                
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message="주봉 데이터 업데이트",
                    data={
                        "symbol": symbol,
                        "candles_count": len(result),
                        "first_candle_time": result[0]["candle_date_time_kst"] if result else None,
                        "last_candle_time": result[-1]["candle_date_time_kst"] if result else None
                    }
                )
                
            return result
            
        except Exception as e:
            error_msg = f"주봉 데이터 조회 중 오류 발생: {e}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 주봉 데이터 조회 실패",
                    data={
                        "request_url": endpoint,
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
            print(error_msg)
            raise
    
    def get_monthly_candles(
        self,
        symbol: str,
        to: Optional[str] = None,
        count: int = 200
    ) -> List[Dict[str, Any]]:
        """월 캔들 데이터 조회
        
        Args:
            symbol: 심볼 코드 (예: BTC, ETH)
            to: 마지막 캔들 시각 (ISO8601 형식)
            count: 캔들 개수 (최대 200개)
            
        Returns:
            캔들 데이터 리스트
        """
        endpoint = f"{self.BASE_URL}/months"
        params = {
            "market": self._get_market_code(symbol),
            "count": min(count, 200)
        }
        if to:
            params["to"] = to
            
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 월봉 데이터 조회 요청",
                data={
                    "symbol": symbol,
                    "count": params["count"],
                    "to": to
                }
            )
            
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            result = response.json()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 월봉 데이터 조회 성공",
                    data={
                        "request_url": endpoint,
                        "response_status": response.status_code,
                        "symbol": symbol,
                        "candles_count": len(result)
                    }
                )
                
                self.log_manager.log(
                    category=LogCategory.MARKET,
                    message="월봉 데이터 업데이트",
                    data={
                        "symbol": symbol,
                        "candles_count": len(result),
                        "first_candle_time": result[0]["candle_date_time_kst"] if result else None,
                        "last_candle_time": result[-1]["candle_date_time_kst"] if result else None
                    }
                )
                
            return result
            
        except Exception as e:
            error_msg = f"월봉 데이터 조회 중 오류 발생: {e}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 월봉 데이터 조회 실패",
                    data={
                        "request_url": endpoint,
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
            print(error_msg)
            raise 