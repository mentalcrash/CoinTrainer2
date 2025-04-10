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
        asset_data: Dict
    ) -> str:
        """스캘핑 트레이딩을 위한 의사결정 프롬프트 생성

        Args:
            symbol: 거래 심볼 (예: XRP)
            market_data: 시장 데이터 및 신호
            asset_data: 자산 정보

        Returns:
            str: GPT 프롬프트
        """
        # 기본 시장 데이터 포맷
        market_info = f"""
[시장 기술 지표]
1. 가격 동향:
- 현재가: {market_data['current_price']:,.0f} KRW
- 1분 이동평균: {market_data['ma1']:,.0f} KRW
- 3분 이동평균: {market_data['ma3']:,.0f} KRW
- 5분 이동평균: {market_data['ma5']:,.0f} KRW
- VWAP(3분): {market_data['vwap_3m']:,.0f} KRW

2. 모멘텀 지표:
- 1분 RSI: {market_data['rsi_1']:.1f}
- 3분 RSI: {market_data['rsi_3']:.1f}
- 볼린저밴드 폭: {market_data['bb_width']:.2f}%

3. 변동성/추세:
- 3분 변동성: {market_data['volatility_3m']:.2f}%
- 5분 변동성: {market_data['volatility_5m']:.2f}%
- 1분 가격추세: {market_data['price_trend_1m']}
- 1분 거래량추세: {market_data['volume_trend_1m']}

4. 호가/선물 지표:
- 매수/매도 비율: {market_data['order_book_ratio']:.2f}
- 호가 스프레드: {market_data['spread']:.3f}%
- 선물 프리미엄: {market_data['premium_rate']:.3f}%
- 펀딩비율: {market_data['funding_rate']:.4f}%
- 가격 안정성: {market_data['price_stability']:.2f}

[현재 신호 분석]
- 가격 신호: {market_data['price_signal']}
- 모멘텀 신호: {market_data['momentum_signal']}
- 거래량 신호: {market_data['volume_signal']}
- 호가창 신호: {market_data['orderbook_signal']}
- 선물 신호: {market_data['futures_signal']}
- 시장 상태: {market_data['market_state']}
- 종합 신호: {market_data['overall_signal']} (강도: {market_data['signal_strength']:.2f})
- 진입 타이밍: {market_data['entry_timing']}

[보유 자산 정보]
- 보유수량: {asset_data['balance']:.8f} {symbol}
- 평균단가: {asset_data['avg_buy_price']:,.0f} KRW
- 평가손익: {asset_data['profit_loss_rate']:+.2f}%
- 거래가능 KRW: {asset_data['krw_balance']:,.0f}"""

        # 매매 규칙 및 판단 기준
        trading_rules = """
[매매 판단 액션 가이드]
- 매매 판단 시, 가능한 한 적극적으로 "매수" 또는 "매도"를 선택하세요.
- "관망" 포지션은 다음과 같은 경우에만 허용합니다:
  a. 신호 강도가 0.2 미만으로 매우 낮고, 시장 상태가 극도로 불확실할 때.
  b. 여러 신호(가격, 모멘텀, 거래량, 호가창, 선물) 사이에 명백한 상충이 발생하여 명확한 방향성을 찾기 어려울 때.
- "매수" 또는 "매도" 액션을 선택할 때, 다음 중 최소 2가지 이상 근거를 구체적으로 제시하세요:
  a. 이동평균 및 RSI 등 모멘텀 지표의 명확한 신호
  b. 거래량 및 호가창 지표의 뚜렷한 방향성 일치
  c. 선물 프리미엄 및 펀딩비율 등 파생상품 지표의 명확한 신호
  d. 최근 3분간의 가격추세와 거래량추세의 방향 일치성
- 신호 강도가 0.4를 넘으면 반드시 "매수" 또는 "매도" 중 하나를 선택해야 합니다.
- 판단이 모호한 경우라도, 관망보다는 신호의 방향성을 우선 고려해 적극적으로 판단을 내리세요.

[다음 판단 시점 결정 기준]

1. 시장 상태가 "불안정"이거나, 신호 강도가 0.4 이상으로 강력한 매수/매도 신호가 나올 때는 30초~1분 간격으로 즉시 재판단하여 빠르게 대응합니다.
2. 보유 포지션이 있을 때는 목표가 또는 손절가 근처의 가격에 진입할 경우 30초~1분 단위로 신속히 모니터링하여 수익 실현 또는 손실 최소화를 즉시 실행합니다.
3. 가격 급등락, 거래량 급증, 호가창의 급격한 변화 등 특이 상황 발생 시 즉시(30초~1분 이내) 판단을 수행하여 트레이딩 기회를 놓치지 않습니다.
4. 이번 판단이 "관망"이라면, 시장 변동성 또는 신호 강도에 따라 다음과 같이 충분한 대기시간을 두고 판단을 재수행합니다:
   - 신호 강도 0.2 이하로 매우 낮고, 시장 움직임이 거의 없을 때: 최소 10분 대기 후 판단 재수행
   - 신호 강도 0.2~0.4 범위로 중립적이며, 명확한 방향성이 없을 때: 최소 5분 대기 후 판단 재수행
   - 다만, 관망 중 시장에서 가격이나 거래량의 갑작스러운 변화가 감지되면 즉시(1분 이내) 판단을 재수행합니다.
"""

        # JSON 응답 형식 (포맷 지정자와 충돌하지 않도록 따옴표 처리)
        json_format = '''
위 정보를 바탕으로 다음 형식의 JSON으로 매매 판단을 해주세요:
{
    "action": "매수" | "매도" | "관망",
    "reason": "판단 이유 (최대 100자)",
    "entry_price": 매수/매도 희망가격 (현재가 기준 ±0.5% 이내),
    "stop_loss": 손절가격 (매수 시 -1% 이내, 매도 시 +1% 이내),
    "take_profit": 목표가격 (매수 시 +1% 이내, 매도 시 -1% 이내),
    "confidence": 확신도 (0.0 ~ 1.0),
    "risk_level": "상" | "중" | "하",
    "next_decision": {
        "interval_minutes": 0.5 | 1 | 2 | 3 | 5 | 10 | 30,
        "reason": "다음 판단 시점까지의 대기 시간 선택 이유 (최대 50자)"
    }
}'''

        # 최종 프롬프트 조합
        prompt = f"""당신은 암호화폐 스캘핑 트레이딩 전문가입니다. {symbol}에 대한 매매 판단이 필요합니다.

{market_info}

{trading_rules}

{json_format}"""

        return prompt
        
    def _call_gpt4(self, prompt: str) -> Dict:
        """GPT-4 API를 호출하여 스캘핑 트레이딩 판단을 얻습니다."""
        headers = {
            "Authorization": f"Bearer {self.news_summarizer.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "role": "system",
                    "content": """당신은 암호화폐 스캘핑 트레이딩 전문가입니다.
- 1~5분 단위의 단기 매매에 특화되어 있습니다.
- 기술적 지표, 호가창, 선물 시장 데이터를 종합적으로 분석합니다.
- 신속하고 명확한 매매 판단이 필요합니다.
- 수수료를 고려한 실현 가능한 수익을 추구합니다.
- 시장 안정성과 리스크 관리를 중시합니다.
- 응답은 반드시 지정된 JSON 형식을 따라야 합니다."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,  # 일관된 판단을 위해 낮은 temperature 사용
            "max_tokens": 500,   # 간결한 응답을 위해 토큰 수 제한
            "response_format": { "type": "json_object" }  # JSON 응답 강제
        }
        
        try:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="스캘핑 트레이딩 판단을 위한 GPT-4 API 호출",
                    data={"endpoint": self.news_summarizer.api_endpoint}
                )
            
            response = requests.post(
                self.news_summarizer.api_endpoint,
                headers=headers,
                json=data,
                timeout=10  # 신속한 판단을 위해 타임아웃 단축
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
                        message="스캘핑 매매 판단 결과 파싱 완료",
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
            # 2. 시장 분석 데이터 수집
            analysis_result = self.trading_analyzer.analyze(symbol)
                
            market_data = {
                **analysis_result['market_data'],
                **analysis_result['signals']
            }
            asset_info = analysis_result['asset_info']
            
            # 3. 매매 판단 프롬프트 생성
            prompt = self._create_decision_prompt(
                symbol,
                market_data,
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

    def _analyze_market_conditions(self, symbol: str, market_data: Dict) -> Dict:
        """시장 상황을 분석합니다."""
        try:
            # 기존 분석
            conditions = super()._analyze_market_conditions(symbol, market_data)
            
            # 프리미엄 인덱스 분석 추가
            premium_index = self.market_analyzer.analyze_premium_index(symbol)
            
            # 프리미엄 인덱스 기반 추가 분석
            conditions['funding_rate'] = premium_index['funding_rate']
            conditions['market_bias'] = premium_index['market_bias']
            conditions['price_stability'] = premium_index['price_stability']
            
            # 매매 신호 보정
            if abs(premium_index['funding_rate']) > 0.1:  # 펀딩비율이 큰 경우
                conditions['trading_signals'].append({
                    'signal': "매수" if premium_index['funding_rate'] < 0 else "매도",
                    'strength': min(abs(premium_index['funding_rate']) / 0.2, 1.0),  # 0.2%를 최대 강도로
                    'reason': f"펀딩비율 {premium_index['funding_rate']:.4f}% ({premium_index['market_bias']})"
                })
            
            # 프리미엄/디스카운트 반영
            if abs(premium_index['premium_rate']) > 0.5:  # 0.5% 이상 차이
                conditions['trading_signals'].append({
                    'signal': "매수" if premium_index['premium_rate'] < 0 else "매도",
                    'strength': min(abs(premium_index['premium_rate']) / 2.0, 1.0),  # 2%를 최대 강도로
                    'reason': f"{'프리미엄' if premium_index['premium_rate'] > 0 else '디스카운트'} {abs(premium_index['premium_rate']):.4f}%"
                })
            
            return conditions
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시장 상황 분석 실패",
                data={"error": str(e)}
            )
            return super()._analyze_market_conditions(symbol, market_data)