from src.new.api.bithumb import BithumbApiClient

class Indicators:
    def __init__(self, market: str = "KRW-BTC"):
        self.market = market
        self.client = BithumbApiClient()

    # 0.5를 기준으로 0.5 초과면 매수 우위, 0.5 미만이면 매도 우위
    def getOrderBookImbalanceRatio(self) -> float:
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        return orderbook.total_bid_size / (orderbook.total_ask_size + orderbook.total_bid_size)
    
    def getOrderBookImbalanceDifference(self) -> float:
        orderbook_res = self.client.get_orderbook(self.market)
        orderbook = orderbook_res.orderbooks[0]
        return orderbook.total_bid_size - orderbook.total_ask_size
