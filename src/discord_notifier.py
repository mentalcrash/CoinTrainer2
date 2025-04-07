import json
import logging
from datetime import datetime
from typing import Dict, Optional

import requests
from requests import Response

logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        """Discord 웹훅을 통해 알림을 보내는 클래스

        Args:
            webhook_url (str): Discord 웹훅 URL
        """
        self.webhook_url = webhook_url

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
            logger.error(f"Discord 메시지 전송 실패: {response.status_code} - {response.text}")
        
        return response

    def send_trade_notification(
        self,
        symbol: str,
        decision: Dict,
        order_result: Dict,
        asset_info: Dict
    ) -> None:
        """매매 실행 결과를 Discord로 전송합니다.

        Args:
            symbol (str): 매매 심볼 (예: BTC)
            decision (Dict): 매매 판단 정보
            order_result (Dict): 주문 실행 결과
            asset_info (Dict): 자산 정보
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 매매 판단 임베드
        decision_embed = {
            "title": f"🤖 {symbol} 매매 판단",
            "color": 0x00ff00 if decision["decision"] == "매수" else 0xff0000,
            "fields": [
                {"name": "결정", "value": decision["decision"], "inline": True},
                {"name": "수량 비율", "value": f"{decision['quantity_percent']}%", "inline": True},
                {"name": "신뢰도", "value": f"{decision['confidence']:.2f}", "inline": True},
                {"name": "목표가", "value": f"{decision['target_price']:,} KRW", "inline": True},
                {"name": "손절가", "value": f"{decision['stop_loss']:,} KRW", "inline": True},
                {"name": "판단 이유", "value": "\\n".join(decision["reasons"])},
                {"name": "리스크 요인", "value": "\\n".join(decision["risk_factors"])}
            ],
            "footer": {"text": f"다음 판단: {decision['next_decision']['interval_minutes']}분 후"}
        }

        # 주문 실행 임베드
        order_embed = {
            "title": f"💰 {symbol} 주문 실행",
            "color": 0x00ff00,
            "fields": [
                {"name": "주문 타입", "value": order_result["type"], "inline": True},
                {"name": "주문 상태", "value": order_result["status"], "inline": True},
                {"name": "주문 수량", "value": f"{order_result['volume']}", "inline": True},
                {"name": "주문 가격", "value": f"{order_result['price']:,} KRW", "inline": True},
                {"name": "체결 수량", "value": f"{order_result['executed_volume']}", "inline": True},
                {"name": "미체결 수량", "value": f"{order_result['remaining_volume']}", "inline": True}
            ]
        }

        # 자산 정보 임베드
        asset_embed = {
            "title": "💼 자산 정보",
            "color": 0x0000ff,
            "fields": [
                {"name": "보유 수량", "value": f"{asset_info['balance']}", "inline": True},
                {"name": "평균 매수가", "value": f"{asset_info['avg_buy_price']:,} KRW", "inline": True},
                {"name": "현재 평가액", "value": f"{asset_info['current_value']:,} KRW", "inline": True},
                {"name": "수익률", "value": f"{asset_info['profit_loss_rate']:.2f}%", "inline": True},
                {"name": "KRW 잔고", "value": f"{asset_info['krw_balance']:,} KRW", "inline": True}
            ]
        }

        content = f"📊 {symbol} 매매 알림 ({now})"
        self._send_message(content, [decision_embed, order_embed, asset_embed])

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