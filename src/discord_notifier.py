import json
from datetime import datetime
from typing import Dict, Optional, Any

import requests
from requests import Response
from src.models.market_data import TradeExecutionResult
from src.utils.log_manager import LogManager, LogCategory
from src.round.models import TradingRound


class DiscordNotifier:
    def __init__(self, webhook_url: str, log_manager: LogManager):
        """Discord 웹훅을 통해 알림을 보내는 클래스

        Args:
            webhook_url (str): Discord 웹훅 URL
            log_manager (LogManager): 로깅을 담당할 LogManager 인스턴스
        """
        self.webhook_url = webhook_url
        self.log_manager = log_manager

    def _send_message(self, content: str, embeds: Optional[list] = None) -> Response:
        """Discord로 메시지를 전송합니다.

        Args:
            content (str): 메시지 내용
            embeds (Optional[list], optional): Discord 임베드. Defaults to None.

        Returns:
            Response: 요청 응답
        """
        data = {"content": content}
        if embeds:
            data["embeds"] = embeds

        response = requests.post(
            self.webhook_url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 204:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="Discord 메시지 전송 실패",
                data={
                    "status_code": response.status_code,
                    "response": response.text
                }
            )
        
        return response

    def _format_number(self, value) -> str:
        """숫자를 포맷팅합니다."""
        try:
            if isinstance(value, str):
                value = float(value)
            return f"{value:,.0f}"
        except (ValueError, TypeError):
            return str(value)

    def _create_order_message(self, result: TradeExecutionResult) -> str:
        """주문 실행 결과로부터 디스코드 메시지를 생성합니다."""
        try:
            order_info = result.order_result
            decision = result.decision_result.decision
            market_data = result.decision_result.analysis.market_data
            
            def safe_str(value: Any) -> str:
                """None이나 빈 값을 안전하게 문자열로 변환합니다."""
                return str(value) if value is not None else "N/A"
            
            def safe_float(value: Any) -> str:
                """숫자 값을 안전하게 포맷팅합니다."""
                try:
                    if value is None:
                        return "N/A"
                    float_val = float(value)
                    return f"{float_val:,.2f}" if float_val != 0 else 0
                except (ValueError, TypeError):
                    return "N/A"
            
            def safe_percent(value: Any) -> str:
                """퍼센트 값을 안전하게 포맷팅합니다."""
                try:
                    if value is None:
                        return "N/A"
                    float_val = float(value)
                    return f"{float_val:.1f}%" if float_val != 0 else "N/A"
                except (ValueError, TypeError):
                    return "N/A"
            
            # 기본 정보 설정
            action_emoji = "🔵" if order_info and order_info.side == "bid" else "🔴"
            symbol = result.decision_result.symbol.upper()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 메시지 생성
            message = f"""
{action_emoji} **{symbol} 주문 실행 결과** ({timestamp})
```ini
[주문 정보]
주문 가격: {safe_float(order_info.price if order_info else None)} KRW
주문 수량: {safe_str(order_info.volume if order_info else "N/A")}
주문 유형: {safe_str(order_info.side if order_info else "N/A")}

[매매 판단]
신뢰도: {safe_percent(decision.confidence)}
위험 수준: {safe_str(decision.risk_level)}
진입 가격: {safe_float(decision.entry_price)} KRW
목표 가격: {safe_float(decision.take_profit)} KRW
손절 가격: {safe_float(decision.stop_loss)} KRW

[시장 데이터]
현재 가격: {safe_float(market_data.current_price)} KRW
이동평균선:
• MA1: {safe_float(market_data.ma1)} KRW
• MA3: {safe_float(market_data.ma3)} KRW
• MA5: {safe_float(market_data.ma5)} KRW
• MA10: {safe_float(market_data.ma10)} KRW

RSI 지표:
• 3분: {safe_float(market_data.rsi_3)}
• 7분: {safe_float(market_data.rsi_7)}
• 14분: {safe_float(market_data.rsi_14)}

변동성:
• 3분: {safe_percent(market_data.volatility_3m)}
• 5분: {safe_percent(market_data.volatility_5m)}
• 10분: {safe_percent(market_data.volatility_10m)}
• 15분: {safe_percent(market_data.volatility_15m)}

호가 정보:
• 매수/매도 비율: {safe_float(market_data.order_book_ratio)}
• 스프레드: {safe_percent(market_data.spread)}

선물 시장:
• 프리미엄: {safe_percent(market_data.premium_rate)}
• 펀딩비율: {safe_percent(market_data.funding_rate)}

캔들 분석:
• 캔들 강도: {safe_str(market_data.candle_strength)}
• 실체비율: {safe_percent(market_data.candle_body_ratio)}
• 신규 고가: {'O' if market_data.new_high_5m else 'X'}
• 신규 저가: {'O' if market_data.new_low_5m else 'X'}

[판단 근거]
{safe_str(decision.reason)}

[다음 판단]
다음 판단 시간: {safe_str(decision.next_decision.interval_minutes if decision.next_decision else "N/A")}분 후
```"""
            return message
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"디스코드 메시지 생성 실패: {str(e)}",
                data={"symbol": result.decision_result.symbol if result.decision_result else "Unknown"}
            )
            return "⚠️ 메시지 생성 중 오류가 발생했습니다."

    def send_trade_notification(self, result: TradeExecutionResult) -> None:
        """매매 실행 결과를 Discord로 전송합니다."""
        try:     
            # 메시지 생성
            message = self._create_order_message(result)

            # Discord로 전송
            self._send_message(message)
            
            self.log_manager.log(
                category=LogCategory.DISCORD,
                message=f"매매 알림 전송 완료",
                data={
                    "message": message
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"Discord 매매 알림 전송 실패: {str(e)}",
                data={"error": str(e)}
            )

    def send_error_notification(self, error_message: str) -> None:
        """에러 메시지를 Discord로 전송합니다.

        Args:
            error_message (str): 에러 메시지
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        embed = {
            "title": "⚠️ 에러 발생",
            "color": 0xff0000,
            "description": error_message,
            "footer": {"text": now}
        }

        self._send_message("", [embed])
        self.log_manager.log(
            category=LogCategory.DISCORD,
            message="에러 알림 전송 완료",
            data={"error_message": error_message}
        )
        
    def send_start_round_notification(self, round: TradingRound) -> bool:
        """라운드 시작 알림을 Discord로 전송합니다."""
        try:
            message = f"라운드 시작: {round.id}"
            self._send_message(message)
            return True
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"라운드 시작 알림 전송 실패: {str(e)}",
                data={"error": str(e)}
            )
            return False
    
    def send_end_round_notification(self, round: TradingRound) -> bool:
        """라운드 종료 알림을 Discord로 전송합니다."""
        try:
            entry_price = float(round.entry_order.price)
            exit_price = float(round.exit_order.price)
            profit = exit_price - entry_price
            profit_rate = profit / entry_price * 100
            volume = float(round.exit_order.volume)
            #수수료
            fee = float(round.entry_order.order_result.paid_fee) + float(round.exit_order.order_result.paid_fee)
            #수수료를 포함한 수익률
            profit_rate_with_fee = ((profit * volume) - fee) / (entry_price * volume) * 100
            #승리 or 패배
            was_victorious = profit_rate_with_fee > 0
            
            message = f"""
라운드 종료: {round.id}
결과: {"승리" if was_victorious else "패배"}

매수가: {entry_price:,.0f}
매도가: {exit_price:,.0f}
수익률: {profit_rate:.2f}%

수수료: {fee:,.0f}
수수료 포함 수익률: {profit_rate_with_fee:.2f}%

진입 이유: 
{round.entry_reason}
청산 이유: 
{round.exit_reason}
"""
            self._send_message(message)
            return True
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"라운드 종료 알림 전송 실패: {str(e)}",
                data={"error": str(e)}
            )
            return False