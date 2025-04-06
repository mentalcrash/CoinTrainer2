import requests
from datetime import datetime
from typing import Optional, List, Dict, Any

class Candle:
    """빗썸 캔들 데이터 관리 클래스"""
    
    BASE_URL = "https://api.bithumb.com/v1/candles"
    
    def __init__(self):
        self.session = requests.Session()
    
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
            
        response = self.session.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    
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
            
        response = self.session.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    
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
            
        response = self.session.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    
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
            
        response = self.session.get(endpoint, params=params)
        response.raise_for_status()
        return response.json() 