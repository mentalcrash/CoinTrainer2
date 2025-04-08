import json

# 서버에서 받은 문자열
raw_str = '''```json
{
    "news_analysis": [
        {
            "id": 1,
            "summary": "비트코인은 시장의 불확실성 속에서도 장기 보유할 수 있는 최고의 자산으로 평가받고 있으며, 장기적인 수익률이 극대화될 것이라는 분석이 있다.",
            "sentiment_score": 1.0,
            "relevance_score": 1.0
        },
        {
            "id": 2,
            "summary": "전문가들은 비트코인이 지난 10년간 32,530%의 수익률을 기록했으며, 앞으로 13배 상승할 가능성이 있다고 분석하고 있다. 비트코인의 희소성이 주요 강점으로 강조된다.",
            "sentiment_score": 1.0,
            "relevance_score": 1.0
        },
        {
            "id": 3,
            "summary": "비트코인은 최근 6.4% 하락하며 1억1494만 원대에서 거래되고 있으며, 추가 하락 가능성에 대한 우려가 제기되고 있다. 시장 지배율은 62.76%이다.",
            "sentiment_score": -1.0,
            "relevance_score": 1.0
        },
        {
            "id": 4,
            "summary": "도널드 트럼프의 관세 정책으로 비트코인이 8만 달러 아래로 떨어지며 시장에 큰 변동성을 초래했다. 이로 인해 알트코인들도 동반 하락했다.",
            "sentiment_score": -1.0,
            "relevance_score": 1.0
        },
        {
            "id": 5,
            "summary": "비트코인의 현재 시세는 1억1000만원선이며, 다른 암호화폐들도 특정 가격선에서 거래되고 있다. 하지만 자세한 내용은 부족하다.",
            "sentiment_score": 0.0,
            "relevance_score": 0.5
        }
    ],
    "overall_summary": "비트코인에 대한 다양한 뉴스가 보도되었으며, 일부는 장기적인 상승 가능성과 희소성에 초점을 맞추고 긍정적인 평가를 하고 있다. 그러나 최근 시장에서는 비트코인과 다른 암호화폐들이 하락세를 보이며 부정적인 뉴스도 다수 보도되었다.",
    "average_sentiment": 0.0,
    "average_relevance": 0.8
}
```'''

def parse_json_from_markdown(markdown_str: str) -> dict:
    """마크다운 코드 블록에서 JSON을 파싱합니다.

    Args:
        markdown_str (str): 마크다운 형식의 JSON 문자열

    Returns:
        dict: 파싱된 JSON 데이터
    """
    # 1. 마크다운 코드 블록 제거
    json_str = markdown_str.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]  # "```json" 제거
    if json_str.endswith("```"):
        json_str = json_str[:-3]  # "```" 제거
    
    # 2. 문자열 앞뒤의 공백 제거
    json_str = json_str.strip()
    
    # 3. JSON 파싱
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 실패: {e}")
        return None

# 테스트
data = parse_json_from_markdown(raw_str)
if data:
    print("JSON 파싱 성공!")
    print(f"뉴스 개수: {len(data['news_analysis'])}")
    print(f"평균 감성 점수: {data['average_sentiment']}")
    print(f"평균 관련성 점수: {data['average_relevance']}")
    
    # 뉴스 요약 출력
    print("\n=== 뉴스 요약 ===")
    for news in data['news_analysis']:
        print(f"[{news['id']}] 감성: {news['sentiment_score']}, 관련성: {news['relevance_score']}")
        print(f"내용: {news['summary']}\n") 