from typing import Dict, Optional, List
import json
import os
from datetime import datetime
import requests
from pathlib import Path
from src.trading_analyzer import TradingAnalyzer
from src.news_summarizer import NewsSummarizer
from src.utils.log_manager import LogManager, LogCategory

class TradingDecisionMaker:
    """뉴스와 시장 분석을 종합하여 매매 판단을 내리는 클래스"""
    
    # OpenAI API 엔드포인트 상수
    _OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
    
    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        openai_api_key: str,
        log_manager: LogManager
    ):
        """초기화
        
        Args:
            bithumb_api_key: 빗썸 API 키
            bithumb_secret_key: 빗썸 Secret 키
            openai_api_key: OpenAI API 키
            log_manager: 로그 매니저
        """
        self.trading_analyzer = TradingAnalyzer(bithumb_api_key, bithumb_secret_key, log_manager=log_manager)
        self.news_summarizer = NewsSummarizer(openai_api_key, self._OPENAI_API_ENDPOINT, log_manager=log_manager)
        self.log_manager = log_manager
        
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message="매매 판단기 초기화 완료",
                data={
                    "openai_endpoint": self._OPENAI_API_ENDPOINT
                }
            )
        
    def _convert_datetime(self, data: Dict) -> Dict:
        """datetime 객체를 ISO 형식 문자열로 변환합니다."""
        if isinstance(data, dict):
            return {k: self._convert_datetime(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data
    
    def _create_decision_prompt(
        self,
        symbol: str,
        market_data: Dict,
        news_data: Dict,
        asset_data: Dict
    ) -> str:
        """매매 판단을 위한 프롬프트 생성
        
        Args:
            symbol: 심볼 (예: BTC)
            market_data: 시장 분석 데이터
            news_data: 뉴스 분석 데이터
            asset_data: 자산 정보 데이터
            
        Returns:
            프롬프트 문자열
        """
        prompt = f"""당신은 매우 짧은 거래 주기를 가지고 단기 손익을 노리고 투자를 해서 고수익을 내는 암호화폐 투자 전문가입니다. 
아래 제공된 {symbol}에 대한 시장 분석과 뉴스 분석을 바탕으로 매매 판단을 내려주세요.

=== 시장 분석 데이터 ===
• 현재가: {market_data['current_price']:,.0f} KRW ({market_data['minute_change']:+.2f}%)
• 이동평균: MA5 {market_data['ma5']:,.0f} / MA20 {market_data['ma20']:,.0f}
• RSI(14): {market_data['rsi_14']:.1f}
• 변동성: {market_data['volatility']:.1f}%
• 가격 추세: {market_data['price_trend']}
• 거래량 추세: {market_data['volume_trend']}

=== 기술적 매매 신호 ===
• 이동평균 신호: {market_data['ma_signal']}
• RSI 신호: {market_data['rsi_signal']}
• 거래량 신호: {market_data['volume_signal']}
• 종합 신호: {market_data['overall_signal']} (강도: {market_data['signal_strength']:.1%})

=== 뉴스 분석 ===
• 분석된 뉴스: {len(news_data.get('news_analysis', []))}개
• 평균 감성 점수: {news_data.get('analysis', {}).get('average_sentiment', 0):.2f}
• 주요 내용: {news_data.get('analysis', {}).get('overall_summary', '정보 없음')}

=== 보유 자산 정보 ===
• 보유수량: {asset_data['balance']:.8f} {symbol}
• 매수평균가: {asset_data['avg_buy_price']:,.0f} KRW
• 평가손익: {asset_data['profit_loss']:,.0f} KRW ({asset_data['profit_loss_rate']:+.2f}%)

위 정보를 종합적으로 분석하여 다음 JSON 형식으로 매매 판단을 제시해주세요:

{{
    "decision": "매수 또는 매도 또는 관망",
    "quantity_percent": "매수/매도 수량 (매수시 현재 보유 KRW 대비 비율 0~100 사이 값, 매도시 타겟 코인 수량 대비 비율 0~100 사이 값)",
    "target_price": "목표가 (KRW)",
    "stop_loss": "손절가 (KRW)",
    "confidence": "신뢰도 (0.0 ~ 1.0)",
    "reasons": [
        "판단 이유 1",
        "판단 이유 2",
        "판단 이유 3"
    ],
    "risk_factors": [
        "위험 요소 1",
        "위험 요소 2"
    ],
    "additional_info": {{
        "short_term_outlook": "단기 전망",
        "long_term_outlook": "장기 전망",
        "key_events": [
            "주목할 이벤트 1",
            "주목할 이벤트 2"
        ]
    }},
    "next_decision": {{
        "interval_minutes": "다음 매매 판단까지의 시간 (1-30 사이의 정수, 분 단위)",
        "reason": "해당 시간 간격을 선택한 이유"
    }}
}}

판단 시 다음 사항을 고려해주세요:
1. 기술적 지표와 뉴스 감성 분석의 일치성
2. 현재 보유 포지션과 손익 상황
3. 시장의 전반적인 추세와 모멘텀
4. 거래량과 변동성 패턴
5. 잠재적인 위험 요소들
6. 다음 매매 판단까지의 적절한 시간 간격 (시장 상황에 따라 1-30분 사이에서 결정)"""

        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message="매매 판단 프롬프트 생성 완료",
                data={
                    "symbol": symbol,
                    "prompt": prompt
                }
            )

        return prompt
        
    def _call_gpt4(self, prompt: str) -> Dict:
        """GPT-4 API를 호출합니다."""
        headers = {
            "Authorization": f"Bearer {self.news_summarizer.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 암호화폐 매매 전문가입니다. 제공된 데이터를 바탕으로 매매 판단을 내립니다. JSON 형식으로만 응답해주세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="GPT-4 API 호출 시작",
                    data={"endpoint": self.news_summarizer.api_endpoint}
                )
            
            response = requests.post(
                self.news_summarizer.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API 오류 응답: {response.status_code} - {response.text}"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="GPT-4 API 호출 실패",
                        data={
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                return None
                
            response_data = response.json()
            if not response_data or "choices" not in response_data:
                error_msg = "API 응답에 choices가 없습니다."
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=error_msg,
                        data={"response": response_data}
                    )
                return None
                
            content = response_data["choices"][0]["message"]["content"]
            
            # 마크다운 포맷팅 제거
            content = content.replace("```json", "").replace("```", "").strip()
            
            # JSON 파싱 전에 숫자의 콤마 제거
            content = self._remove_commas_in_numbers(content)
            
            try:
                decision = json.loads(content)
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.SYSTEM,
                        message="매매 판단 결과 파싱 완료",
                        data=decision
                    )
                return decision
            except json.JSONDecodeError as e:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="매매 판단 결과 파싱 실패",
                        data={
                            "error": str(e),
                            "content": content
                        }
                    )
                return None
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="GPT-4 API 호출 중 예외 발생",
                    data={"error": str(e)}
                )
            return None

    def _remove_commas_in_numbers(self, json_str: str) -> str:
        """JSON 문자열 내의 숫자에 포함된 콤마를 제거합니다.

        Args:
            json_str (str): 원본 JSON 문자열

        Returns:
            str: 숫자의 콤마가 제거된 JSON 문자열
        """
        import re
        # 숫자 내의 콤마만 제거 (숫자,숫자 패턴을 찾아서 콤마 제거)
        # 예: "123,456" -> "123456"
        while True:
            # 콤마를 포함한 숫자 패턴을 찾아서 콤마 제거
            new_str = re.sub(r'(\d),(\d)', r'\1\2', json_str)
            # 더 이상 변경이 없으면 종료
            if new_str == json_str:
                break
            json_str = new_str
        return json_str

    def make_decision(
        self,
        symbol: str,
        max_age_hours: int = 24,
        limit: int = 5,
        dev_mode: bool = False
    ) -> Dict:
        """뉴스와 시장 분석을 종합하여 매매 판단
        
        Args:
            symbol: 심볼 (예: 'BTC')
            max_age_hours: 뉴스 수집 시 최대 기사 나이 (시간)
            limit: 수집할 뉴스 기사 수
            dev_mode: 개발 모드 여부
            
        Returns:
            Dict: 매매 판단 결과
        """
        try:            
            # 1. 시장 분석 데이터 수집
            analysis_result = self.trading_analyzer.analyze(symbol)
                
            market_data = {
                **analysis_result['market_data'],
                **analysis_result['signals']
            }
            asset_info = analysis_result['asset_info']
            
            # 2. 뉴스 분석
            news_data = self.news_summarizer.analyze_news(
                symbol=symbol,
                max_age_hours=max_age_hours,
                limit=limit
            )
            
            # 3. 매매 판단 프롬프트 생성
            prompt = self._create_decision_prompt(
                symbol,
                market_data,
                news_data,
                asset_info
            )
            
            response = self._call_gpt4(prompt)
            if not response:
                raise Exception("GPT-4 API 호출 실패")
            decision = response
            
            # 5. 결과 반환
            result = {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "market_data": market_data,
                "news_data": news_data,
                "asset_info": asset_info,
                "decision": decision
            }
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.DECISION,
                    message=f"{symbol} 매매 판단 완료",
                    data=result
                )
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e)
            }
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 매매 판단 실패",
                    data=error_result
                )
            return error_result