from src.new.models.bithumb.response import Orderbook
from src.new.api.bithumb.client import BithumbApiClient
from math import ceil, floor

class TargetCalculator:
    def __init__(self, market: str):
        self.market = market
        
        api_client = BithumbApiClient()
        orderbook_res = api_client.get_orderbook(self.market)
        
        self.tick_size = self.get_tick_size(orderbook_res.orderbooks[0])
        self.take_ticks = 4
        self.stop_ticks = 2
        self.take_profit_rate = 0.002
        self.stop_loss_rate = 0.001
        
    def get_tick_size(self, orderbook: Orderbook) -> float:
        orderbook_units = orderbook.orderbook_units
        ask_prices = [float(item.ask_price) for item in orderbook_units]
        bid_prices = [float(item.bid_price) for item in orderbook_units]
        ask_tick_size = abs(ask_prices[0] - ask_prices[1])
        bid_tick_size = abs(bid_prices[0] - bid_prices[1])
        return max(ask_tick_size, bid_tick_size)

    def calculate(self, current_price: float) -> tuple[int, int]:
        target_price_for_tick = ceil(current_price + self.tick_size * self.take_ticks)
        stop_loss_price_for_tick = floor(current_price - self.tick_size * self.stop_ticks)

        target_price_for_rate = ceil(current_price * (1 + self.take_profit_rate))
        stop_loss_price_for_rate = floor(current_price * (1 - self.stop_loss_rate))
            
        target_price = max(target_price_for_tick, target_price_for_rate)
        stop_loss_price = min(stop_loss_price_for_tick, stop_loss_price_for_rate)

        return target_price, stop_loss_price