from openai import OpenAI
import os
from datetime import datetime
from src.new.api.bithumb.client import BithumbApiClient
import json
class OpenAITrader:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.bithumb_client = BithumbApiClient()

    def get_indicators(self, market: str = "KRW-BTC") -> dict:
        ticker_response = self.bithumb_client.get_ticker(markets=market)
        ticker = ticker_response.tickers[0]
        
        orderbook_response = self.bithumb_client.get_orderbook(markets=market)
        orderbook = orderbook_response.orderbooks[0]
        
        trades_response = self.bithumb_client.get_trades(market=market, count=10)
        trades = trades_response.trades
        
        candles_response = self.bithumb_client.get_candles(market=market, interval="1h", limit=10)
        candles = candles_response.candles
        
        return {
            "ticker": ticker,
            "orderbook": orderbook,
            "trades": trades,
            "candles": candles
        }
    
    # 해당 정보들을 활용하여 프롬프트 스타일로 변환
    # 각종 정보를 모아서 openai 에게 분석을 요청할 수 있도록 함
    def make_prompt_style(self, indicators: dict) -> str:
        ticker = indicators["ticker"]
        orderbook = indicators["orderbook"]
        trades = indicators["trades"]
        candles = indicators["candles"]
        
        # 현재 시간
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        prompt = f"""
===== 시장 기본 정보 (현재가) =====
- 분석 시간: {current_time}
- 분석 대상: {ticker.market}
- 현재가: {ticker.trade_price}
- 시세 상태: {ticker.change} (변동률: {ticker.signed_change_rate})
- 시가: {ticker.opening_price}
- 고가: {ticker.high_price}
- 저가: {ticker.low_price}
- 전일 종가: {ticker.prev_closing_price}
- 거래량(24h): {ticker.acc_trade_volume_24h}
- 거래대금(24h): {ticker.acc_trade_price_24h}
- 52주 최고가: {ticker.highest_52_week_price} ({ticker.highest_52_week_date})
- 52주 최저가: {ticker.lowest_52_week_price} ({ticker.lowest_52_week_date})

===== 호가창 정보 =====
- 총 매도 주문량: {orderbook.total_ask_size}
- 총 매수 주문량: {orderbook.total_bid_size}
- 호가 정보:
{chr(10).join([f"  - 매도 {i+1}호가: 가격 {unit.ask_price}, 수량 {unit.ask_size} | 매수 {i+1}호가: 가격 {unit.bid_price}, 수량 {unit.bid_size}" for i, unit in enumerate(orderbook.orderbook_units)])}

===== 최근 체결 내역 =====
{chr(10).join([f"- 체결 {i+1}: 시간 {trade.trade_date_utc} {trade.trade_time_utc}, 가격 {trade.trade_price}, 수량 {trade.trade_volume}, 유형 {trade.ask_bid}" for i, trade in enumerate(trades)])}

===== 최근 캔들 데이터 =====
{chr(10).join([f"- 캔들 {i+1}: 시간 {candle.candle_date_time_kst}, 시가 {candle.opening_price}, 고가 {candle.high_price}, 저가 {candle.low_price}, 종가 {candle.trade_price}, 거래량 {candle.candle_acc_trade_volume}" for i, candle in enumerate(candles)])}
        """
        return prompt
    
    def get_analysis(self, prompt: str, model: str = "gpt-4.1-mini-2025-04-14") -> dict:
        system_prompt = """
당신은 초단기 암호화폐 매매에 특화된 스캘핑 트레이딩 전문가입니다.
주어진 데이터를 가지고 지표를 빠르고 정확하게 계산해 내야 합니다.

응답은 반드시 아래 JSON 형식을 따를 것:
{
  "current_price": float,                    // 현재 시세
  "orderbook_imbalance_ratio": float,        // 상위 5개 호가 기준 (매수량 / (매수량 + 매도량))
  "execution_bid_ratio": float,              // 최근 체결 중 BID 체결량 / 전체 체결량 (최근 10건)
  "volume_spike_ratio": float                // 최근 1개 캔들 거래량 / 이전 3개 캔들 평균 거래량
}
"""
        response = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        event = json.loads(response.output_text)
        return event
        