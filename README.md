# 암호화폐 자동매매 프로그램

이 프로그램은 암호화폐 거래소 API를 사용하여 자동으로 매매를 수행하는 파이썬 프로그램입니다.

## 기능
- 실시간 시세 모니터링
- 기술적 분석 (이동평균선)
- 자동 매매 실행
- 계좌 잔고 조회

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. `.env` 파일 생성:
```
API_KEY=your_api_key
SECRET_KEY=your_secret_key
```

## 사용 방법

1. 설정 파일(`config.py`)에서 거래 설정을 조정합니다.
2. 프로그램 실행:
```bash
python main.py
```

## 주의사항
- 이 프로그램은 실제 금전적 손실을 초래할 수 있습니다.
- 반드시 테스트 후 실제 거래에 사용하세요.
- API 키는 절대 공개하지 마세요. 