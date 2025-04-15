from typing import List, Optional
from pydantic import BaseModel, Field


class Candle(BaseModel):
    """
    빗썸 캔들 차트 데이터를 표현하는 Pydantic 모델
    
    캔들 차트: 주가, 환율, 암호화폐 등의 시세 변동을 시각적으로 표현하는 차트로,
    일정 기간 동안의 시가, 고가, 저가, 종가를 하나의 막대 형태로 나타냅니다.
    """
    market: str = Field(description="시장 정보 (예: KRW-BTC)")
    candle_date_time_utc: str = Field(description="UTC 기준 캔들 생성 시각")
    candle_date_time_kst: str = Field(description="KST 기준 캔들 생성 시각")
    opening_price: float = Field(description="시가")
    high_price: float = Field(description="고가")
    low_price: float = Field(description="저가")
    trade_price: float = Field(description="종가(체결가)")
    timestamp: int = Field(description="타임스탬프 (밀리초)")
    candle_acc_trade_price: float = Field(description="누적 거래 금액")
    candle_acc_trade_volume: float = Field(description="누적 거래량")
    unit: int = Field(description="분 단위 (예: 1분, 3분, 5분, 10분, 15분, 30분, 60분, 240분)")

    class Config:
        schema_extra = {
            "example": {
                "market": "KRW-BTC",
                "candle_date_time_utc": "2018-04-18T10:16:00",
                "candle_date_time_kst": "2018-04-18T19:16:00",
                "opening_price": 8615000,
                "high_price": 8618000,
                "low_price": 8611000,
                "trade_price": 8616000,
                "timestamp": 1524046594584,
                "candle_acc_trade_price": 60018891.90054,
                "candle_acc_trade_volume": 6.96780929,
                "unit": 1
            }
        }


class CandlesResponse(BaseModel):
    """빗썸 캔들 차트 데이터 응답"""
    candles: List[Candle] = Field(description="캔들 데이터 목록")


class OrderbookUnit(BaseModel):
    """
    호가창의 개별 호가 단위를 표현하는 Pydantic 모델
    
    매수/매도 주문의 가격과 수량 정보를 포함합니다.
    """
    ask_price: float = Field(description="매도 호가")
    bid_price: float = Field(description="매수 호가")
    ask_size: float = Field(description="매도 주문 수량")
    bid_size: float = Field(description="매수 주문 수량")


class Orderbook(BaseModel):
    """
    빗썸 호가창 데이터를 표현하는 Pydantic 모델
    
    호가창(Orderbook): 현재 시장에서 거래 가능한 매수/매도 주문의 가격과 수량 정보를 표시하는 창
    """
    market: str = Field(description="시장 정보 (예: KRW-BTC)")
    timestamp: int = Field(description="타임스탬프 (밀리초)")
    total_ask_size: float = Field(description="총 매도 주문 수량")
    total_bid_size: float = Field(description="총 매수 주문 수량")
    orderbook_units: List[OrderbookUnit] = Field(description="호가 단위 목록")

    class Config:
        schema_extra = {
            "example": {
                "market": "KRW-BTC",
                "timestamp": 1529910247984,
                "total_ask_size": 8.83621228,
                "total_bid_size": 2.43976741,
                "orderbook_units": [
                    {
                        "ask_price": 6956000,
                        "bid_price": 6954000,
                        "ask_size": 0.24078656,
                        "bid_size": 0.00718341
                    }
                ]
            }
        }


class OrderbookResponse(BaseModel):
    """빗썸 호가창 데이터 응답"""
    orderbooks: List[Orderbook] = Field(description="호가창 데이터 목록")


class Ticker(BaseModel):
    """
    빗썸 현재가(Ticker) 데이터를 표현하는 Pydantic 모델
    
    현재가(Ticker): 특정 시장의 현재 가격 및 거래 정보를 포함하는 실시간 시세 데이터
    """
    market: str = Field(description="종목 구분 코드 (예: KRW-BTC)")
    trade_date: str = Field(description="최근 거래 일자(UTC) 포맷: yyyyMMdd")
    trade_time: str = Field(description="최근 거래 시각(UTC) 포맷: HHmmss")
    trade_date_kst: str = Field(description="최근 거래 일자(KST) 포맷: yyyyMMdd")
    trade_time_kst: str = Field(description="최근 거래 시각(KST) 포맷: HHmmss")
    trade_timestamp: int = Field(description="최근 거래 일시(UTC) 포맷: Unix Timestamp")
    opening_price: float = Field(description="시가")
    high_price: float = Field(description="고가")
    low_price: float = Field(description="저가")
    trade_price: float = Field(description="종가(현재가)")
    prev_closing_price: float = Field(description="전일 종가(KST 0시 기준)")
    change: str = Field(description="EVEN: 보합, RISE: 상승, FALL: 하락")
    change_price: float = Field(description="변화액의 절대값")
    change_rate: float = Field(description="변화율의 절대값")
    signed_change_price: float = Field(description="부호가 있는 변화액")
    signed_change_rate: float = Field(description="부호가 있는 변화율")
    trade_volume: float = Field(description="가장 최근 거래량")
    acc_trade_price: float = Field(description="누적 거래대금(KST 0시 기준)")
    acc_trade_price_24h: float = Field(description="24시간 누적 거래대금")
    acc_trade_volume: float = Field(description="누적 거래량(KST 0시 기준)")
    acc_trade_volume_24h: float = Field(description="24시간 누적 거래량")
    highest_52_week_price: float = Field(description="52주 신고가")
    highest_52_week_date: str = Field(description="52주 신고가 달성일 포맷: yyyy-MM-dd")
    lowest_52_week_price: float = Field(description="52주 신저가")
    lowest_52_week_date: str = Field(description="52주 신저가 달성일 포맷: yyyy-MM-dd")
    timestamp: int = Field(description="타임스탬프")

    class Config:
        schema_extra = {
            "example": {
                "market": "KRW-BTC",
                "trade_date": "20180418",
                "trade_time": "102340",
                "trade_date_kst": "20180418",
                "trade_time_kst": "192340",
                "trade_timestamp": 1524047020000,
                "opening_price": 8450000,
                "high_price": 8679000,
                "low_price": 8445000,
                "trade_price": 8621000,
                "prev_closing_price": 8450000,
                "change": "RISE",
                "change_price": 171000,
                "change_rate": 0.0202366864,
                "signed_change_price": 171000,
                "signed_change_rate": 0.0202366864,
                "trade_volume": 0.02467802,
                "acc_trade_price": 108024804862.58253,
                "acc_trade_price_24h": 232702901371.09308,
                "acc_trade_volume": 12603.53386105,
                "acc_trade_volume_24h": 27181.31137002,
                "highest_52_week_price": 28885000,
                "highest_52_week_date": "2018-01-06",
                "lowest_52_week_price": 4175000,
                "lowest_52_week_date": "2017-09-25",
                "timestamp": 1524047026072
            }
        }


class TickerResponse(BaseModel):
    """빗썸 현재가(Ticker) 데이터 응답"""
    tickers: List[Ticker] = Field(description="현재가 데이터 목록")


class Trade(BaseModel):
    """
    빗썸 체결 내역 데이터를 표현하는 Pydantic 모델
    
    체결 내역(Trade): 특정 시장에서 발생한 실제 거래 내역 정보
    """
    market: str = Field(description="마켓 구분 코드 (예: KRW-BTC)")
    trade_date_utc: str = Field(description="체결 일자(UTC 기준) 포맷: yyyy-MM-dd")
    trade_time_utc: str = Field(description="체결 시각(UTC 기준) 포맷: HH:mm:ss")
    timestamp: int = Field(description="체결 타임스탬프")
    trade_price: float = Field(description="체결 가격")
    trade_volume: float = Field(description="체결량")
    prev_closing_price: float = Field(description="전일 종가(UTC 0시 기준)")
    change_price: float = Field(description="변화량")
    ask_bid: str = Field(description="매도/매수 (ASK: 매도, BID: 매수)")
    sequential_id: Optional[int] = Field(None, description="체결 번호(Unique)")

    class Config:
        schema_extra = {
            "example": {
                "market": "KRW-BTC",
                "trade_date_utc": "2018-04-18",
                "trade_time_utc": "10:19:58",
                "timestamp": 1524046798000,
                "trade_price": 8616000,
                "trade_volume": 0.03060688,
                "prev_closing_price": 8450000,
                "change_price": 166000,
                "ask_bid": "ASK",
                "sequential_id": 1524046798000000
            }
        }


class TradesResponse(BaseModel):
    """빗썸 체결 내역 데이터 응답"""
    trades: List[Trade] = Field(description="체결 내역 데이터 목록")