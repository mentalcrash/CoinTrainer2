import logging
from typing import Optional, Dict, Any
import requests
from typing import Literal
import os

from src.new.models.bithumb.response import Candle, CandlesResponse, OrderbookResponse, Orderbook, TickerResponse, Ticker, TradesResponse, Trade, AllMarketInfoResponse, MarketInfo

logger = logging.getLogger(__name__)


class BithumbApiException(Exception):
    """빗썸 API 호출 중 발생하는 예외를 처리하기 위한 클래스"""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"빗썸 API 오류 (상태코드: {status_code}): {message}")


class BithumbApiClient:
    """
    빗썸 거래소 API와 상호작용하기 위한 클라이언트 클래스
    
    이 클래스는 빗썸 거래소의 공개 API를 호출하고 응답을 적절한 모델로 변환합니다.
    """
    
    BASE_URL = "https://api.bithumb.com/v1"
    
    def __init__(self):
        """
        빗썸 API 클라이언트 초기화
        
        Args:
            api_key: 빗썸 API 키 (인증이 필요한 엔드포인트에 사용)
            secret_key: 빗썸 시크릿 키 (인증이 필요한 엔드포인트에 사용)
        """
        self.api_key = os.getenv("BITHUMB_API_KEY")
        self.secret_key = os.getenv("BITHUMB_SECRET_KEY")
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                     data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        API 요청을 실행하고 응답을 반환합니다.
        
        Args:
            method: HTTP 메서드 (GET, POST 등)
            endpoint: API 엔드포인트 경로
            params: 쿼리 파라미터
            data: 요청 바디 데이터
            headers: HTTP 헤더
            
        Returns:
            Dict[str, Any]: API 응답 데이터
            
        Raises:
            BithumbApiException: API 호출 중 오류가 발생한 경우
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # 기본 헤더 설정
        request_headers = {
            "Accept": "application/json",
        }
        
        # 인증이 필요한 경우 헤더에 API 키 추가
        if self.api_key and self.secret_key:
            request_headers["Api-Key"] = self.api_key
            # TODO: 필요한 경우 인증 서명 로직 추가
        
        # 사용자 지정 헤더 병합
        if headers:
            request_headers.update(headers)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers,
                timeout=30  # 30초 타임아웃
            )
            
            # 응답 확인
            response.raise_for_status()
            result = response.json()
            
            # 빗썸 API 오류 확인 (status 필드가 있는 경우)
            if "status" in result and result["status"] != "0000":
                raise BithumbApiException(
                    status_code=int(result.get("status", 0)),
                    message=result.get("message", "알 수 없는 오류")
                )
                
            return result
            
        except requests.RequestException as e:
            logger.error(f"빗썸 API 요청 오류: {str(e)}")
            raise BithumbApiException(
                status_code=getattr(e.response, "status_code", 500),
                message=str(e)
            )
    
    def get_candles(self, market: str, interval: Literal["1m", "3m", "5m", "10m", "30m", "1h", "6h", "12h", "24h"] = "1m", limit: int = 100) -> CandlesResponse:
        """
        캔들 차트 데이터를 가져옵니다.
        
        Args:
            market: 거래 쌍 (예: 'BTC-KRW')
            interval: 시간 간격 (1m, 3m, 5m, 10m, 30m, 1h, 6h, 12h, 24h)
            limit: 반환할 캔들 개수 (최대 100)
            
        Returns:
            CandlesResponse: 캔들 데이터 응답 객체
        """
        # 빗썸 API에서 사용하는 interval 형식으로 변환
        interval_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "10m": "10",
            "30m": "30",
            "1h": "60",
            "6h": "360",
            "12h": "720",
            "24h": "1440"
        }
        
        unit = interval_map.get(interval, "1")
        
        # 빗썸 API 요청 파라미터 구성
        params = {
            "market": market,
            "count": min(limit, 100)  # 최대 100개로 제한
        }
        
        # API 요청 실행
        response = self._make_request("GET", f"/candles/minutes/{unit}", params=params)
        
        return CandlesResponse(candles=[Candle.model_validate(item) for item in response])
    
    def get_ticker(self, markets: str) -> TickerResponse:
        """
        특정 거래 쌍의 현재 시세 정보를 가져옵니다.
        
        Args:
            markets: 거래 쌍 (예: ' KRW-BTC, BTC-ETH')
            
        Returns:
            Dict[str, Any]: 시세 정보
        """
        params = {"markets": markets}
        response = self._make_request("GET", "/ticker", params=params)
        return TickerResponse(tickers=[Ticker.model_validate(item) for item in response])
    
    def get_orderbook(self, markets: str) -> OrderbookResponse:
        """
        특정 거래 쌍의 호가 정보를 가져옵니다.
        
        Args:
            markets: 거래 쌍 (예: 'KRW-BTC')

        Returns:
            Dict[str, Any]: 호가 정보
        """
        params = {"markets": markets}
        response = self._make_request("GET", "/orderbook", params=params)
        
        return OrderbookResponse(orderbooks=[Orderbook.model_validate(item) for item in response])
    
    def get_trades(self, market: str, count: int = 1) -> TradesResponse:
        """
        최근 거래 내역을 가져옵니다.
        
        Args:
            market: 거래 쌍 (예: 'KRW-BTC')
            limit: 반환할 거래 개수 (최대 100)
            
        Returns:
            Dict[str, Any]: 거래 내역
        """
        params = {
            "market": market,
            "count": count
        }
        response = self._make_request("GET", "/trades/ticks", params=params)
        return TradesResponse(trades=[Trade.model_validate(item) for item in response]) 
    
    def get_all_market_info(self) -> AllMarketInfoResponse:
        """
        모든 시장 정보를 가져옵니다.
        """
        response = self._make_request("GET", "/market/all")
        return AllMarketInfoResponse(market_info=[MarketInfo.model_validate(item) for item in response])
