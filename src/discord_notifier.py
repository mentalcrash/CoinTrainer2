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
        asset_info: Dict,
        order_result: Optional[Dict] = None
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
        if order_result:
            order_embed = {
                "title": f"💰 {symbol} 주문 실행",
                "color": 0x00ff00,
                "fields": [
                    {"name": "주문 ID", "value": order_result["uuid"], "inline": True},
                    {"name": "주문 방향", "value": "매수" if order_result["side"] == "bid" else "매도", "inline": True},
                    {"name": "주문 타입", "value": order_result["ord_type"], "inline": True},
                    {"name": "주문 상태", "value": order_result["state"], "inline": True},
                    {"name": "마켓", "value": order_result["market"], "inline": True},
                    {"name": "주문 시각", "value": order_result["created_at"], "inline": True}
                ]
            }

            # 매수/매도에 따라 다른 필드 추가
            if decision["decision"] == "매수":
                order_embed["fields"].extend([
                    {"name": "주문 가격", "value": f"{float(order_result['price']):,} KRW", "inline": True},
                    {"name": "체결 수량", "value": order_result["executed_volume"], "inline": True},
                    {"name": "거래 횟수", "value": str(order_result["trades_count"]), "inline": True},
                    {"name": "수수료", "value": f"{float(order_result['paid_fee']):,} KRW", "inline": True},
                    {"name": "예약 수수료", "value": f"{float(order_result['reserved_fee']):,} KRW", "inline": True},
                    {"name": "잠긴 금액", "value": f"{float(order_result['locked']):,} KRW", "inline": True}
                ])
            else:  # 매도
                order_embed["fields"].extend([
                    {"name": "주문 수량", "value": order_result["volume"], "inline": True},
                    {"name": "남은 수량", "value": order_result["remaining_volume"], "inline": True},
                    {"name": "체결 수량", "value": order_result["executed_volume"], "inline": True},
                    {"name": "거래 횟수", "value": str(order_result["trades_count"]), "inline": True},
                    {"name": "수수료", "value": f"{float(order_result['paid_fee']):,} KRW", "inline": True},
                    {"name": "잠긴 수량", "value": order_result["locked"], "inline": True}
                ])

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
        
        # order_result가 None이면 order_embed를 제외
        embeds = [decision_embed, asset_embed] if order_result is None else [decision_embed, order_embed, asset_embed]
        self._send_message(content, embeds)

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