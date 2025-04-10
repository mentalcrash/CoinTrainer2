import json
from datetime import datetime
from typing import Dict, Optional

import requests
from requests import Response
from src.models.market_data import TradeExecutionResult
from src.utils.log_manager import LogManager, LogCategory

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

    def send_trade_notification(
        self,
        symbol: str,
        result: TradeExecutionResult
    ):
        """매매 알림을 Discord로 전송합니다.

        Args:
            symbol (str): 매매 심볼 (예: BTC)
            result (TradeExecutionResult): 매매 실행 결과
        """
        try:
            decision = result.decision_result.decision
            analysis = result.decision_result.analysis
            order_info = result.order_info
            order_result = result.order_result

            # 매매 행동에 따른 이모지 선택
            emoji = "🔵" if decision.action == "매수" else "🔴"
            
            # 메시지 생성
            message = (
                f"{emoji} **{symbol} {decision.action}**\n"
                f"```\n"
                f"가격: {order_info.price:,.0f} KRW\n"
                f"수량: {order_info.volume:.8f} {symbol}\n"
                f"금액: {order_info.krw_amount:,.0f} KRW\n"
                f"체결상태: {order_result.state if order_result else '미체결'}\n"
                f"\n"
                f"보유수량: {analysis.asset_info.balance:.8f} {symbol}\n"
                f"평가금액: {analysis.asset_info.current_value:,.0f} KRW\n"
                f"수익률: {analysis.asset_info.profit_loss_rate:.2f}%\n"
                f"\n"
                f"판단근거: {decision.reason}\n"
                f"```"
            )

            self._send_message(message)
            self.log_manager.log(
                category=LogCategory.DISCORD,
                message=f"{symbol} 매매 알림 전송 완료",
                data={
                    "symbol": symbol,
                    "action": decision.action,
                    "price": order_info.price,
                    "volume": order_info.volume
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"Discord 매매 알림 전송 실패: {str(e)}"
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