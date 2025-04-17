from src.new.models.bithumb.response import Orderbook

class TargetCalculator:
    @staticmethod
    def from_orderbook(
        current_price: float,
        orderbook: Orderbook,
        take_ticks: int = 5,
        stop_ticks: int = 2,
        take_profit_rate: float = 0.1,
        stop_loss_rate: float = 0.05
    ) -> tuple[int, int]:
        """
        스프레드 및 틱 단위를 기반으로 목표가와 손절가를 계산합니다.

        Args:
            current_price (float): 현재가
            orderbook (dict): 빗썸 호가 정보 (최소 2개 이상의 ask, bid)
            take_ticks (int): 목표 수익 틱 수
            stop_ticks (int): 손절 허용 틱 수

        Returns:
            tuple[int, int]: (목표가, 손절가)
        """
        try:
            orderbook_units = orderbook.orderbook_units
            
            ask_prices = [float(item.ask_price) for item in orderbook_units]
            bid_prices = [float(item.bid_price) for item in orderbook_units]

            if len(ask_prices) < 2 or len(bid_prices) < 2:
                raise ValueError("호가 데이터가 부족합니다.")

            # 틱 크기 추정 (상위 두 개 호가 차이)
            ask_tick_size = abs(ask_prices[0] - ask_prices[1])
            bid_tick_size = abs(bid_prices[0] - bid_prices[1])
            tick_size = max(ask_tick_size, bid_tick_size)

            if tick_size == 0:
                raise ValueError("틱 단위 계산 오류")

            # 목표가 및 손절가 계산
            target_price_for_tick = int(current_price + tick_size * take_ticks)
            stop_loss_price_for_tick = int(current_price - tick_size * stop_ticks)

            target_price_for_rate = int(current_price * (1 + take_profit_rate))
            stop_loss_price_for_rate = int(current_price * (1 - stop_loss_rate))
            
            target_price = max(target_price_for_tick, target_price_for_rate)
            stop_loss_price = min(stop_loss_price_for_tick, stop_loss_price_for_rate)

            return target_price, stop_loss_price

        except Exception as e:
            print(f"[TargetCalculator] 계산 실패: {e}")
            return int(current_price * 1.05), int(current_price * 0.975)  # fallback 값