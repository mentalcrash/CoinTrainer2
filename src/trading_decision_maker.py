from typing import Dict, Optional, List
import json
import os
from datetime import datetime
import requests
from pathlib import Path
from src.trading_analyzer import TradingAnalyzer
from src.news_summarizer import NewsSummarizer
from src.utils.logger import setup_logger

logger = setup_logger('trading_decision')

class TradingDecisionMaker:
    """뉴스와 시장 분석을 종합하여 매매 판단을 내리는 클래스"""
    
    # OpenAI API 엔드포인트 상수
    _OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
    
    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        openai_api_key: str,
    ):
        """초기화
        
        Args:
            bithumb_api_key: 빗썸 API 키
            bithumb_secret_key: 빗썸 Secret 키
            openai_api_key: OpenAI API 키
        """
        self.trading_analyzer = TradingAnalyzer(bithumb_api_key, bithumb_secret_key)
        self.news_summarizer = NewsSummarizer(openai_api_key, self._OPENAI_API_ENDPOINT)
        
        # 로그 디렉토리 설정
        self._setup_log_directory()
        
    def _setup_log_directory(self):
        """로그 디렉토리 설정"""
        # 기본 로그 디렉토리 생성
        base_dir = Path(".temp")
        base_dir.mkdir(exist_ok=True)
        
        # 실행 시간 기반 디렉토리 생성
        now = datetime.now()
        run_id = now.strftime("%Y%m%d_%H%M%S")
        self.run_dir = base_dir / run_id
        self.run_dir.mkdir(exist_ok=True)
        
        # 로그 디렉토리 생성
        self.log_dir = self.run_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
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
        prompt = f"""당신은 암호화폐 매매 전문가입니다. 
아래 제공된 {symbol}에 대한 시장 분석과 뉴스 분석을 바탕으로 매매 판단을 내려주세요.

=== 시장 분석 데이터 ===
• 현재가: {market_data['current_price']:,.0f} KRW ({market_data['daily_change']:+.2f}%)
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
    "quantity_percent": "매수/매도 수량 (보유자산 대비 %)",
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
        "interval_minutes": "다음 매매 판단까지의 시간 (1-1440 사이의 정수, 분 단위)",
        "reason": "해당 시간 간격을 선택한 이유"
    }}
}}

판단 시 다음 사항을 고려해주세요:
1. 기술적 지표와 뉴스 감성 분석의 일치성
2. 현재 보유 포지션과 손익 상황
3. 시장의 전반적인 추세와 모멘텀
4. 거래량과 변동성 패턴
5. 잠재적인 위험 요소들
6. 다음 매매 판단까지의 적절한 시간 간격 (시장 상황에 따라 1-1440분 사이에서 결정)"""

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
            response = requests.post(
                self.news_summarizer.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"API 오류 응답: {response.status_code} - {response.text}")
                return None
                
            response_data = response.json()
            if not response_data or "choices" not in response_data:
                logger.error("API 응답에 choices가 없습니다.")
                return None
                
            content = response_data["choices"][0]["message"]["content"]
            logger.info("API 응답 내용:")
            logger.info(content)
            
            # 마크다운 포맷팅 제거
            content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {str(e)}")
                logger.error(f"파싱 실패한 내용: {content}")
                return None
            
        except Exception as e:
            logger.error(f"GPT-4 API 호출 실패: {str(e)}")
            return None
            
    def _save_decision_data(self, symbol: str, data: Dict, category: str):
        """매매 판단 데이터를 파일로 저장
        
        Args:
            symbol: 심볼 (예: BTC)
            data: 저장할 데이터
            category: 저장 카테고리 (market_data/news_data/decision/prompts/responses)
        """
        categories = {
            'market_data': '07_market_data',
            'news_data': '08_news_data',
            'prompts': '09_prompt',
            'responses': '10_response',
            'decision': '11_decision'
        }
        
        if category not in categories:
            logger.error(f"잘못된 카테고리입니다: {category}")
            return
            
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{categories[category]}_{symbol}_{timestamp}.json"
        filepath = self.log_dir / filename
        
        # datetime 객체 변환
        data = self._convert_datetime(data)
        
        # 데이터 포맷팅
        formatted_data = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "data_type": category,
            "content": data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"{symbol} {category} 저장 완료: {filepath}")
        
    def make_decision(
        self,
        symbol: str,
        max_age_hours: int = 24,
        limit: int = 5,
        dev_mode: bool = False
    ) -> Dict:
        """매매 판단을 수행합니다.
        
        Args:
            symbol: 심볼 (예: BTC)
            max_age_hours: 뉴스 수집 시 최대 기사 나이 (시간)
            limit: 수집할 뉴스 기사 수
            dev_mode: 개발 모드 여부
            
        Returns:
            매매 판단 결과
        """
        try:
            logger.info(f"{symbol} 매매 판단 시작...")
            
            # 1. 시장 분석 데이터 수집
            analysis_result = self.trading_analyzer.analyze(symbol)
            if not analysis_result['success']:
                raise Exception(f"시장 데이터 수집 실패: {analysis_result['error']}")
                
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
            if not news_data["success"]:
                raise Exception("뉴스 분석 실패")
            
            # 3. 매매 판단 프롬프트 생성
            prompt = self._create_decision_prompt(
                symbol,
                market_data,
                news_data,
                asset_info
            )
            self._save_decision_data(symbol, {"prompt": prompt}, "prompts")
            
            # 4. GPT-4 API 호출
            if dev_mode:
                # 개발 모드일 경우 더미 데이터 반환
                decision = {
                    "decision": "매수",
                    "quantity_percent": 20,
                    "target_price": int(market_data['current_price'] * 1.1),
                    "stop_loss": int(market_data['current_price'] * 0.95),
                    "confidence": 0.75,
                    "reasons": [
                        "RSI가 과매도 구간에서 반등 시도",
                        "뉴스 감성이 긍정적",
                        "거래량 증가 추세"
                    ],
                    "risk_factors": [
                        "단기 이동평균선이 하락 추세",
                        "시장 변동성 증가"
                    ],
                    "additional_info": {
                        "short_term_outlook": "변동성 높으나 반등 가능성",
                        "long_term_outlook": "상승 추세 유지 전망",
                        "key_events": [
                            "다가오는 반감기",
                            "기관 투자자 유입 증가"
                        ]
                    },
                    "next_decision": {
                        "interval_minutes": 240,
                        "reason": "현재 시장의 변동성과 추세를 고려한 적정 모니터링 주기"
                    }
                }
            else:
                response = self._call_gpt4(prompt)
                if not response:
                    raise Exception("GPT-4 API 호출 실패")
                self._save_decision_data(symbol, response, "responses")
                decision = response
            
            # 5. 결과 저장
            result = {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "market_data": market_data,
                "news_data": news_data,
                "asset_info": asset_info,
                "decision": decision
            }
            
            self._save_decision_data(symbol, result, "decision")
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"{symbol} 매매 판단 실패: {str(e)}")
            return error_result
            
    def format_decision(self, result: Dict) -> str:
        """매매 판단 결과를 보기 좋게 포맷팅"""
        if not result["success"]:
            return f"매매 판단 실패: {result.get('error', '알 수 없는 오류')}"
            
        symbol = result["symbol"]
        decision = result["decision"]
        market_data = result["market_data"]
        timestamp = datetime.fromisoformat(result["timestamp"]).strftime("%Y-%m-%d %H:%M")
        
        output = []
        output.append(f"\n💰 {symbol} 매매 판단 ({timestamp})")
        output.append("=" * 60)
        
        # 매매 판단
        output.append(f"\n📊 매매 판단: {decision['decision']}")
        output.append(f"• 수량: 보유자산의 {decision['quantity_percent']}%")
        output.append(f"• 목표가: {decision['target_price']:,} KRW")
        output.append(f"• 손절가: {decision['stop_loss']:,} KRW")
        output.append(f"• 신뢰도: {decision['confidence']:.1%}")
        
        # 판단 이유
        output.append("\n📝 판단 이유")
        for reason in decision["reasons"]:
            output.append(f"• {reason}")
            
        # 위험 요소
        output.append("\n⚠️ 위험 요소")
        for risk in decision["risk_factors"]:
            output.append(f"• {risk}")
            
        # 추가 정보
        output.append("\n📌 추가 정보")
        output.append(f"• 단기 전망: {decision['additional_info']['short_term_outlook']}")
        output.append(f"• 장기 전망: {decision['additional_info']['long_term_outlook']}")
        output.append("\n🔔 주목할 이벤트")
        for event in decision['additional_info']['key_events']:
            output.append(f"• {event}")
            
        # 현재 시장 상황
        output.append("\n📈 현재 시장 상황")
        output.append(f"• 현재가: {market_data['current_price']:,} KRW ({market_data['daily_change']:+.2f}%)")
        output.append(f"• RSI(14): {market_data['rsi_14']:.1f}")
        output.append(f"• 이동평균: MA5 {market_data['ma5']:,} / MA20 {market_data['ma20']:,}")
        output.append(f"• 변동성: {market_data['volatility']:.1f}%")
        
        # 다음 매매 판단 정보
        output.append("\n⏰ 다음 매매 판단")
        output.append(f"• 시간 간격: {decision['next_decision']['interval_minutes']}분 후")
        output.append(f"• 선택 이유: {decision['next_decision']['reason']}")
        
        return "\n".join(output) 