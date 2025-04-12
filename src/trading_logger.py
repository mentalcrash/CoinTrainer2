import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import TradeExecutionResult
from src.trading_order import OrderResponse, Trade

import uuid

class TradingLogger:
    """Google Sheets를 이용한 트레이딩 로거"""
    
    def __init__(self, log_manager: Optional[LogManager] = None):
        """
        Args:
            log_manager (LogManager): 로깅을 담당할 LogManager 인스턴스
            
        Environment Variables:
            GOOGLE_SHEETS_ID: 구글 스프레드시트 ID
            GOOGLE_CREDENTIALS_PATH: 구글 서비스 계정 키 파일 경로
        """
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_ID')  # 스프레드시트 ID
        self.log_manager = log_manager
        
        if not self.SPREADSHEET_ID:
            raise ValueError("GOOGLE_SHEETS_ID 환경 변수가 설정되지 않았습니다.")
        
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        if not credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH 환경 변수가 설정되지 않았습니다.")
        
        self.service = self._get_sheets_service(credentials_path)
        
        # 시트 이름 정의
        self.SHEETS = {
            'trades': 'Trading History',    # 매매 기록
            'assets': 'Asset History',      # 자산 현황
            'performance': 'Performance',    # 성과 지표
            'decisions': 'Trading Decisions', # 매매 판단
            'market': 'Market Data',         # 시장 데이터
            'order_request': 'Order Request',  # 주문 기록
            'order_response': 'Order Response',  # 주문 응답 데이터
            'trade_response': 'Trade Response'   # 체결 응답 데이터
        }
        
        # 시트 초기화
        self._initialize_sheets()
    
    def _get_sheets_service(self, credentials_path: str):
        """Google Sheets API 서비스 인스턴스를 생성합니다."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="Google Sheets API 서비스 생성 실패",
                    data={"error": str(e)}
                )
            raise
    
    def _initialize_sheets(self):
        """필요한 시트들을 초기화합니다."""
        try:
            # 기존 시트 목록 조회
            sheets = self.service.spreadsheets().get(
                spreadsheetId=self.SPREADSHEET_ID
            ).execute().get('sheets', [])
            
            existing_sheets = [sheet['properties']['title'] for sheet in sheets]
            
            # 필요한 시트 생성
            for sheet_name in self.SHEETS.values():
                if sheet_name not in existing_sheets:
                    self._create_sheet(sheet_name)
                    self._initialize_headers(sheet_name)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message="시트 초기화 완료"
                )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="시트 초기화 실패",
                    data={"error": str(e)}
                )
            raise
    
    def _create_sheet(self, sheet_name: str):
        """새로운 시트를 생성합니다."""
        try:
            request = {
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.SPREADSHEET_ID,
                body={'requests': [request]}
            ).execute()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"시트 생성 완료: {sheet_name}"
                )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="시트 생성 실패",
                    data={"sheet_name": sheet_name, "error": str(e)}
                )
            raise
    
    def _initialize_headers(self, sheet_name: str):
        """시트의 헤더를 초기화합니다."""
        headers = {
            'Trading History': [
                'Timestamp', 'Symbol',
                # 매매 판단 정보
                'Action', 'Entry Price', 'Take Profit', 'Stop Loss',
                'Confidence', 'Risk Level', 'Decision Reason',
                # 주문 정보
                'Order Type', 'Order Side', 'Order Volume', 'Order Price', 'Order Amount',
                # 체결 정보
                'Order Status', 'Executed Price', 'Executed Volume', 'Fee',
                # 자산 정보
                'Balance', 'Locked', 'Average Buy Price', 'Current Value',
                'Profit Loss', 'Profit Loss Rate', 'KRW Balance',
                # 시장 정보
                'Current Market Price', 'MA5', 'RSI'
            ],
            'Asset History': [
                'ID', 'Timestamp', 'Symbol', 'Balance', 'Locked', 'Average Buy Price',
                'Current Value', 'Profit Loss', 'Profit Loss Rate', 
                'KRW Balance', 'KRW Locked', 'Total Asset Value'
            ],
            'Performance': [
                'Timestamp', 'Symbol', 'Daily ROI', 'Weekly ROI',
                'Monthly ROI', 'Total Profit Loss', 'Win Rate'
            ],
            'Order Request': [
                'ID',                              # 고유 ID
                'Timestamp',                       # 타임스탬프
                'Symbol',                          # 심볼
                
                # Order Result 필드
                'Order UUID',                      # 주문 ID
                'Order Side',                      # 주문 방향
                'Order Type',                      # 주문 타입
                'Order State',                     # 주문 상태
                'Market',                          # 마켓 정보
                'Created At',                      # 주문 생성 시각
                'Trades Count',                    # 거래 횟수
                'Paid Fee',                        # 지불된 수수료
                'Executed Volume',                 # 체결된 수량
                'Order Price',                     # 주문 가격
                'Reserved Fee',                    # 예약된 수수료
                'Remaining Fee',                   # 남은 수수료
                'Locked Amount',                   # 잠긴 금액/수량
                'Order Volume',                    # 주문 수량
                'Remaining Volume',                # 남은 수량
                
                # TradingDecision 필드
                'Action',                          # 매매 행동
                'Entry Price',                     # 진입 가격
                'Take Profit',                     # 목표가
                'Stop Loss',                       # 손절가
                'Confidence',                      # 확신도
                'Risk Level',                      # 리스크 레벨
                'Decision Reason',                 # 판단 근거
                'Next Decision Interval',          # 다음 판단 시간
                'Next Decision Reason',            # 다음 판단 이유
                
                # Market Data 필드
                'Current Price',                   # 현재가
                'MA1',                            # 1분 이동평균
                'MA3',                            # 3분 이동평균
                'MA5',                            # 5분 이동평균
                'MA10',                           # 10분 이동평균
                'MA20',                           # 20분 이동평균
                'RSI 1m',                         # 1분 RSI
                'RSI 3m',                         # 3분 RSI
                'RSI 7m',                         # 7분 RSI
                'RSI 14m',                        # 14분 RSI
                'Volatility 3m',                  # 3분 변동성
                'Volatility 5m',                  # 5분 변동성
                'Volatility 10m',                 # 10분 변동성
                'Volatility 15m',                 # 15분 변동성
                'Price Trend 1m',                 # 1분 가격 추세
                'Volume Trend 1m',                # 1분 거래량 추세
                'VWAP 3m',                        # 3분 VWAP
                'BB Width',                       # 볼린저 밴드 폭
                'Order Book Ratio',               # 호가 비율
                'Spread',                         # 스프레드
                'Premium Rate',                   # 프리미엄
                'Funding Rate',                   # 펀딩비율
                'Price Stability',                # 가격 안정성
                'Candle Body Ratio',              # 캔들 실체 비율
                'Candle Strength',                # 캔들 강도
                'New High 5m',                    # 5분 신고가 갱신
                'New Low 5m'                      # 5분 신저가 갱신
            ],
            'Order Response': [
                'Order UUID',                      # 주문 ID
                'Timestamp',                       # 타임스탬프
                'Symbol',                          # 심볼
                'Order Side',                      # 주문 방향 (bid/ask)
                'Order Type',                      # 주문 타입
                'Price',                           # 주문 가격
                'Order State',                     # 주문 상태
                'Market',                          # 마켓 정보
                'Created At',                      # 주문 생성 시각
                'Volume',                          # 주문 수량
                'Remaining Volume',                # 남은 수량
                'Reserved Fee',                    # 예약된 수수료
                'Remaining Fee',                   # 남은 수수료
                'Paid Fee',                        # 지불된 수수료
                'Locked',                          # 잠긴 금액
                'Executed Volume',                 # 체결된 수량
                'Trades Count'                     # 체결 횟수
            ],
            'Trade Response': [
                'Trade UUID',                # 체결 고유 ID
                'Order UUID',                # 주문 ID
                'Timestamp',                 # 타임스탬프
                'Symbol',                    # 심볼
                'Market',                    # 마켓
                'Price',                     # 체결 가격
                'Volume',                    # 체결 수량
                'Funds',                     # 체결 금액
                'Side',                      # 매수/매도
                'Created At'                 # 체결 시각
            ]
        }
        
        if sheet_name in headers:
            values = [headers[sheet_name]]
            self._update_values(sheet_name, 'A1', values)
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{sheet_name} 헤더 초기화 완료"
                )
    
    def _update_values(self, sheet_name: str, range_: str, values: List[List]):
        """시트의 값을 업데이트합니다."""
        try:
            range_name = f"{sheet_name}!{range_}"
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="값 업데이트 실패",
                    data={"error": str(e)}
                )
            raise
    
    def _append_values(self, sheet_name: str, values: List[List]):
        """시트에 새로운 행을 추가합니다."""
        try:
            range_name = f"{sheet_name}!A:Z"
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="행 추가 실패",
                    data={"error": str(e)}
                )
            raise
    
    def log_trade(self, id: str, order_result: Dict):
        """매매 기록을 저장합니다.
        
        Args:
            id (str): 거래 기록의 고유 식별자 (다른 시트와의 연결을 위한 키)
            order_result (Dict): 주문 실행 결과
            {
                # 공통 필드
                "uuid": str,           # 주문 ID
                "side": str,           # 주문 방향 ("bid" 또는 "ask")
                "ord_type": str,       # 주문 타입
                "state": str,          # 주문 상태
                "market": str,         # 마켓 정보
                "created_at": str,     # 주문 생성 시각
                "trades_count": int,   # 거래 횟수
                "paid_fee": float,     # 지불된 수수료
                "executed_volume": str, # 체결된 수량

                # 매수 주문일 때 추가되는 필드
                "price": Optional[float],        # 주문 가격
                "reserved_fee": Optional[float], # 예약된 수수료
                "locked": float or str,         # 잠긴 금액 (KRW) 또는 수량 (코인)

                # 매도 주문일 때 추가되는 필드
                "volume": Optional[float],         # 주문 수량
                "remaining_volume": Optional[float] # 남은 수량
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            symbol = order_result['market'].split('-')[1]  # KRW-BTC에서 BTC 추출
            is_bid = order_result['side'] == "bid"
            
            # 가격 처리: 매수일 때는 price 필드 사용, 매도일 때는 locked/executed_volume으로 계산
            try:
                price = float(order_result.get('price', 0.0))
                if not price and not is_bid:
                    # 매도 주문이고 price가 없는 경우, locked/executed_volume으로 계산
                    executed_volume = float(order_result['executed_volume'])
                    locked = float(order_result['locked'])
                    if executed_volume > 0:
                        price = locked / executed_volume
            except (ValueError, TypeError, ZeroDivisionError):
                price = 0.0
            
            # 총 거래 금액 계산
            try:
                executed_volume = float(order_result['executed_volume'])
                total_amount = price * executed_volume
            except (ValueError, TypeError):
                executed_volume = 0.0
                total_amount = 0.0
            
            # 남은 수량 처리
            try:
                remaining_volume = float(order_result.get('remaining_volume', 0.0))
            except (ValueError, TypeError):
                remaining_volume = 0.0
            
            # 예약 수수료 처리
            try:
                reserved_fee = float(order_result.get('reserved_fee', 0.0))
            except (ValueError, TypeError):
                reserved_fee = 0.0
            
            values = [[
                id,                                     # ID (새로 추가)
                now,                                    # Timestamp
                symbol,                                 # Symbol
                order_result['uuid'],                  # Order ID
                "매수" if is_bid else "매도",            # Action
                order_result['ord_type'],              # Order Type
                order_result['state'],                 # Order Status
                str(price),                            # Price
                str(executed_volume),                  # Executed Volume
                str(remaining_volume),                 # Remaining Volume
                str(total_amount),                     # Total Amount
                str(order_result['paid_fee']),         # Fee Paid
                str(reserved_fee),                     # Reserved Fee
                order_result['trades_count'],          # Trades Count
                order_result['created_at']             # Created At
            ]]
            
            self._append_values(self.SHEETS['trades'], values)
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"매매 기록 저장 완료: {symbol}",
                    data={
                    "id": id,
                    "order_id": order_result['uuid'],
                    "symbol": symbol,
                    "action": "매수" if is_bid else "매도",
                    "price": price,
                    "executed_volume": executed_volume,
                    "total_amount": total_amount
                }
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="매매 기록 저장 실패",
                    data={"error": str(e)}
                )
            raise
    
    def log_asset_status(self, id: str, symbol: str, asset_data: Dict):
        """자산 현황을 저장합니다.
        
        Args:
            id (str): 자산 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: BTC)
            asset_data (Dict): 자산 현황 데이터
            {
                'balance': float,        # 보유 수량
                'locked': float,         # 거래 중인 수량
                'avg_buy_price': float,  # 평균 매수가
                'current_value': float,  # 현재 평가 금액
                'profit_loss': float,    # 평가 손익
                'profit_loss_rate': float, # 수익률
                'krw_balance': float,    # 보유 원화
                'krw_locked': float      # 거래 중인 원화
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 총 자산 가치 계산 (코인 평가금액 + 보유 원화 + 거래 중인 원화)
            total_asset_value = (
                asset_data['current_value'] + 
                asset_data['krw_balance'] + 
                asset_data['krw_locked']
            )
            
            values = [[
                id,                                 # ID
                now,                                # Timestamp
                symbol,                             # Symbol
                str(asset_data['balance']),         # Balance
                str(asset_data['locked']),          # Locked
                str(asset_data['avg_buy_price']),   # Average Buy Price
                str(asset_data['current_value']),   # Current Value
                str(asset_data['profit_loss']),     # Profit Loss
                str(asset_data['profit_loss_rate']), # Profit Loss Rate
                str(asset_data['krw_balance']),     # KRW Balance
                str(asset_data['krw_locked']),      # KRW Locked
                str(total_asset_value)              # Total Asset Value
            ]]
            
            self._append_values(self.SHEETS['assets'], values)
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ASSET,
                    message=f"자산 현황 저장 완료: {symbol}",
                    data={
                    "id": id,
                    "symbol": symbol,
                    "balance": asset_data['balance'],
                    "locked": asset_data['locked'],
                    "current_value": asset_data['current_value'],
                    "profit_loss_rate": asset_data['profit_loss_rate'],
                    "total_asset_value": total_asset_value,
                    "krw_balance": asset_data['krw_balance'],
                    "krw_locked": asset_data['krw_locked']
                }
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="자산 현황 저장 실패",
                    data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def log_performance(self, performance_data: Dict):
        """성과 지표를 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                now,
                performance_data['symbol'],
                performance_data['daily_roi'],
                performance_data['weekly_roi'],
                performance_data['monthly_roi'],
                performance_data['total_profit_loss'],
                performance_data['win_rate']
            ]]
            
            self._append_values(self.SHEETS['performance'], values)
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"성과 지표 저장 완료: {performance_data['symbol']}"
                )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="성과 지표 저장 실패",
                    data={"error": str(e)}
                )
            raise
    
    def log_decision(self, id: str, symbol: str, decision_data: Dict):
        """매매 판단을 저장합니다.
        
        Args:
            id (str): 매매 판단 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: XRP)
            decision_data (Dict): 매매 판단 데이터
            {
                "action": "매수" | "매도" | "관망",
                "reason": "판단 이유 (최대 100자)",
                "entry_price": float,  # 매수/매도 희망가격
                "stop_loss": float,    # 손절가격
                "take_profit": float,  # 목표가격
                "confidence": float,   # 확신도 (0.0 ~ 1.0)
                "risk_level": "상" | "중" | "하",
                "next_decision": {
                    "interval_minutes": 1 | 2 | 3 | 5,
                    "reason": str  # 다음 판단 시점 선택 이유
                }
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 다음 판단 시각 계산
            try:
                interval_minutes = int(decision_data['next_decision']['interval_minutes'])
                next_decision_time = (
                    datetime.now().replace(second=0, microsecond=0) +
                    timedelta(minutes=interval_minutes)
                ).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError) as e:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="다음 판단 시각 계산 실패",
                        data={
                        "error": str(e),
                        "interval_minutes": decision_data['next_decision'].get('interval_minutes')
                    }
                )
                # 기본값으로 5분 설정
                next_decision_time = (
                    datetime.now().replace(second=0, microsecond=0) +
                    timedelta(minutes=5)
                ).strftime("%Y-%m-%d %H:%M:%S")
            
            # 진입 타이밍 결정
            entry_timing = "즉시" if decision_data['action'] != "관망" else "대기"
            
            # 긴급도 결정
            urgency_level = {
                "상": "높음",
                "중": "중간",
                "하": "낮음"
            }.get(decision_data['risk_level'], "중간")
            
            values = [[
                id,                                     # 기록 ID
                now,                                    # 기록 시각
                symbol,                                 # 심볼
                decision_data['action'],                # 매매 행동
                str(decision_data['entry_price']),      # 진입 가격
                str(decision_data['take_profit']),      # 목표가
                str(decision_data['stop_loss']),        # 손절가
                str(decision_data['confidence']),       # 확신도
                decision_data['risk_level'],            # 리스크 레벨
                entry_timing,                           # 진입 타이밍
                urgency_level,                          # 긴급도
                decision_data['reason'],                # 판단 근거
                next_decision_time,                     # 다음 판단 시각
                decision_data['next_decision']['reason'] # 다음 판단 이유
            ]]
            
            self._append_values(self.SHEETS['decisions'], values)
            
            # 매매 판단의 중요도에 따라 로그 카테고리 결정
            log_category = (
                LogCategory.TRADING 
                if decision_data['action'] in ['매수', '매도'] and decision_data['risk_level'] == '하'
                else LogCategory.SYSTEM
            )
            
            self.log_manager.log(
                category=log_category,
                message=f"매매 판단 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "action": decision_data['action'],
                    "confidence": decision_data['confidence'],
                    "entry_timing": entry_timing,
                    "urgency_level": urgency_level,
                    "entry_price": decision_data['entry_price'],
                    "take_profit": decision_data['take_profit'],
                    "stop_loss": decision_data['stop_loss'],
                    "risk_level": decision_data['risk_level'],
                    "next_decision_time": next_decision_time,
                    "next_decision_reason": decision_data['next_decision']['reason']
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="매매 판단 저장 실패",
                data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def log_market_data(self, id: str, symbol: str, market_data: Dict):
        """시장 데이터를 저장합니다.
        
        Args:
            id (str): 시장 데이터 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: XRP)
            market_data (Dict): 시장 데이터
            {
                'current_price': float,       # 현재가
                'ma1': float,                 # 1분 이동평균
                'ma3': float,                 # 3분 이동평균
                'ma5': float,                 # 5분 이동평균
                'rsi_1': float,               # 1분 RSI
                'rsi_3': float,               # 3분 RSI
                'volatility_3m': float,       # 3분 변동성
                'volatility_5m': float,       # 5분 변동성
                'price_trend_1m': str,        # 1분 가격 추세
                'volume_trend_1m': str,       # 1분 거래량 추세
                'vwap_3m': float,            # 3분 VWAP
                'bb_width': float,           # 볼린저 밴드 폭
                'order_book_ratio': float,   # 매수/매도 호가 비율
                'spread': float,             # 호가 스프레드
                'premium_rate': float,       # 선물 프리미엄/디스카운트
                'funding_rate': float,       # 선물 펀딩비율
                'price_stability': float,    # 가격 안정성 점수
                'price_signal': str,         # 가격 신호
                'momentum_signal': str,      # 모멘텀 신호
                'volume_signal': str,        # 거래량 신호
                'orderbook_signal': str,     # 호가창 신호
                'futures_signal': str,       # 선물 신호
                'market_state': str,         # 시장 상태
                'overall_signal': str,       # 종합 신호
                'signal_strength': float,    # 신호 강도
                'entry_timing': str          # 진입 타이밍
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                id,                                     # ID
                now,                                    # Timestamp
                symbol,                                 # Symbol
                str(market_data['current_price']),      # Current Price
                str(market_data['ma1']),                # MA1
                str(market_data['ma3']),                # MA3
                str(market_data['ma5']),                # MA5
                str(market_data['vwap_3m']),           # VWAP (3m)
                str(market_data['rsi_1']),             # RSI (1m)
                str(market_data['rsi_3']),             # RSI (3m)
                str(market_data['bb_width']),          # BB Width
                str(market_data['volatility_3m']),     # Volatility (3m)
                str(market_data['volatility_5m']),     # Volatility (5m)
                str(market_data['order_book_ratio']),  # Order Book Ratio
                str(market_data['spread']),            # Spread
                str(market_data['premium_rate']),      # Premium Rate
                str(market_data['funding_rate']),      # Funding Rate
                str(market_data['price_stability']),   # Price Stability
                market_data['price_trend_1m'],         # Price Trend (1m)
                market_data['volume_trend_1m'],        # Volume Trend (1m)
                market_data['price_signal'],           # Price Signal
                market_data['momentum_signal'],        # Momentum Signal
                market_data['volume_signal'],          # Volume Signal
                market_data['orderbook_signal'],       # Orderbook Signal
                market_data['futures_signal'],         # Futures Signal
                market_data['market_state'],           # Market State
                market_data['overall_signal'],         # Overall Signal
                str(market_data['signal_strength']),   # Signal Strength
                market_data['entry_timing']            # Entry Timing
            ]]
            
            self._append_values(self.SHEETS['market'], values)
            
            # 시장 상태 설명 생성
            market_status = self._get_market_status_description(market_data)
            
            self.log_manager.log(
                category=LogCategory.MARKET,
                message=f"시장 데이터 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "current_price": market_data['current_price'],
                    "market_status": market_status,
                    "signals": {
                        "price": market_data['price_signal'],
                        "momentum": market_data['momentum_signal'],
                        "volume": market_data['volume_signal'],
                        "orderbook": market_data['orderbook_signal'],
                        "futures": market_data['futures_signal'],
                        "overall": market_data['overall_signal']
                    },
                    "indicators": {
                        "rsi_1": market_data['rsi_1'],
                        "rsi_3": market_data['rsi_3'],
                        "volatility_3m": market_data['volatility_3m'],
                        "order_book_ratio": market_data['order_book_ratio'],
                        "premium_rate": market_data['premium_rate']
                    },
                    "market_state": market_data['market_state'],
                    "signal_strength": market_data['signal_strength'],
                    "entry_timing": market_data['entry_timing']
                }
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="시장 데이터 저장 실패",
                    data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def _get_market_status_description(self, market_data: Dict) -> str:
        """시장 상태에 대한 설명을 생성합니다."""
        try:
            descriptions = []
            
            # RSI 상태 확인
            rsi_1 = float(market_data['rsi_1'])
            if rsi_1 >= 70:
                descriptions.append("단기 과매수")
            elif rsi_1 <= 30:
                descriptions.append("단기 과매도")
            
            # 변동성 상태 확인
            volatility_3m = float(market_data['volatility_3m'])
            if volatility_3m > 1.0:
                descriptions.append("높은 변동성")
            elif volatility_3m < 0.2:
                descriptions.append("낮은 변동성")
            
            # 호가창 상태 확인
            order_book_ratio = float(market_data['order_book_ratio'])
            if order_book_ratio > 1.2:
                descriptions.append("강한 매수세")
            elif order_book_ratio < 0.8:
                descriptions.append("강한 매도세")
            
            # 선물 시장 상태 확인
            premium_rate = float(market_data['premium_rate'])
            if abs(premium_rate) > 0.5:
                state = "프리미엄" if premium_rate > 0 else "디스카운트"
                descriptions.append(f"높은 선물 {state}")
            
            # 시장 안정성 확인
            if market_data['market_state'] == "불안정":
                descriptions.append("시장 불안정")
            
            return ", ".join(descriptions) if descriptions else "안정적인 시장"
            
        except (ValueError, KeyError) as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="시장 상태 설명 생성 실패",
                    data={"error": str(e)}
                )
            return "상태 분석 불가"

    def log_order_record(self, symbol: str, result: TradeExecutionResult):
        """주문 기록을 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            decision = result.decision_result.decision
            analysis = result.decision_result.analysis
            order_result = result.order_result
            market_data = analysis.market_data
            
            def safe_str(value) -> str:
                """None이나 빈 값을 안전하게 처리합니다."""
                return str(value) if value is not None else ""
            
            values = [[
                str(uuid.uuid4()),                      # ID
                now,                                    # Timestamp
                symbol,                                 # Symbol
                
                # Order Result
                order_result.uuid if order_result else "",                    # Order UUID
                order_result.side if order_result else "",                    # Order Side
                order_result.ord_type if order_result else "",               # Order Type
                order_result.state if order_result else "wait",              # Order State
                order_result.market if order_result else "",                 # Market
                order_result.created_at if order_result else "",             # Created At
                safe_str(order_result.trades_count if order_result else 0),  # Trades Count
                safe_str(order_result.paid_fee if order_result else 0),      # Paid Fee
                safe_str(order_result.executed_volume if order_result else ""), # Executed Volume
                safe_str(order_result.price if order_result else ""),        # Order Price
                safe_str(order_result.reserved_fee if order_result else ""), # Reserved Fee
                safe_str(order_result.remaining_fee if order_result else ""), # Remaining Fee
                safe_str(order_result.locked if order_result else ""),       # Locked Amount
                safe_str(order_result.volume if order_result else ""),       # Order Volume
                safe_str(order_result.remaining_volume if order_result else ""), # Remaining Volume

                # TradingDecision 데이터
                decision.action,                        # Action
                safe_str(decision.entry_price),         # Entry Price
                safe_str(decision.take_profit),         # Take Profit
                safe_str(decision.stop_loss),           # Stop Loss
                safe_str(decision.confidence),          # Confidence
                decision.risk_level,                    # Risk Level
                decision.reason,                        # Decision Reason
                
                safe_str(decision.next_decision.interval_minutes if decision.next_decision else ""), # Next Decision Interval
                decision.next_decision.reason if decision.next_decision else "",                     # Next Decision Reason
                
                # Market Data
                safe_str(market_data.current_price),    # Current Price
                safe_str(market_data.ma1),              # MA1
                safe_str(market_data.ma3),              # MA3
                safe_str(market_data.ma5),              # MA5
                safe_str(market_data.ma10),             # MA10
                safe_str(market_data.ma20),             # MA20
                safe_str(market_data.rsi_1),            # RSI 1m
                safe_str(market_data.rsi_3),            # RSI 3m
                safe_str(market_data.rsi_7),            # RSI 7m
                safe_str(market_data.rsi_14),           # RSI 14m
                safe_str(market_data.volatility_3m),    # Volatility 3m
                safe_str(market_data.volatility_5m),    # Volatility 5m
                safe_str(market_data.volatility_10m),   # Volatility 10m
                safe_str(market_data.volatility_15m),   # Volatility 15m
                market_data.price_trend_1m,             # Price Trend 1m
                market_data.volume_trend_1m,            # Volume Trend 1m
                safe_str(market_data.vwap_3m),          # VWAP 3m
                safe_str(market_data.bb_width),         # BB Width
                safe_str(market_data.order_book_ratio), # Order Book Ratio
                safe_str(market_data.spread),           # Spread
                safe_str(market_data.premium_rate),     # Premium Rate
                safe_str(market_data.funding_rate),     # Funding Rate
                safe_str(market_data.price_stability),  # Price Stability
                safe_str(market_data.candle_body_ratio), # Candle Body Ratio
                market_data.candle_strength,            # Candle Strength
                "Y" if market_data.new_high_5m else "N", # New High 5m
                "Y" if market_data.new_low_5m else "N"   # New Low 5m
            ]]
            
            self._append_values(self.SHEETS['order_request'], values)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"주문 기록 저장 완료: {symbol}",
                    data={
                    "symbol": symbol,
                    "action": decision.action,
                    "entry_price": decision.entry_price,
                    "order_status": order_result.state if order_result else "wait"
                }
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"주문 기록 저장 실패: {str(e)}",
                    data={"symbol": result.symbol if result else "Unknown"}
                )
            raise

    def log_trade_record(
        self,
        symbol: str,
        result: TradeExecutionResult
    ):
        """통합된 매매 기록을 저장합니다.
        
        Args:
            symbol (str): 매매 심볼 (예: BTC)
            result (TradeExecutionResult): 매매 실행 결과
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            decision = result.decision_result.decision
            analysis = result.decision_result.analysis
            order_info = result.order_info
            order_result = result.order_result
            
            values = [[
                now,                                    # Timestamp
                symbol,                                 # Symbol
                
                # 매매 판단 정보
                decision.action,                        # Action
                str(decision.entry_price),              # Entry Price
                str(decision.take_profit),              # Take Profit
                str(decision.stop_loss),                # Stop Loss
                str(decision.confidence),               # Confidence
                decision.risk_level,                    # Risk Level
                decision.reason,                        # Decision Reason
                
                # 주문 정보
                order_info.order_type,                  # Order Type
                order_info.side,                        # Order Side
                str(order_info.volume),                 # Order Volume
                str(order_info.price),                  # Order Price
                str(order_info.krw_amount),             # Order Amount
                
                # 체결 정보
                order_result.state if order_result else "미체결",  # Order Status
                str(order_result.price if order_result else 0),    # Executed Price
                str(order_result.executed_volume if order_result else 0),  # Executed Volume
                str(order_result.paid_fee if order_result else 0),        # Fee
                
                # 자산 정보
                str(analysis.asset_info.balance),       # Balance
                str(analysis.asset_info.locked),        # Locked
                str(analysis.asset_info.avg_buy_price), # Average Buy Price
                str(analysis.asset_info.current_value), # Current Value
                str(analysis.asset_info.profit_loss),   # Profit Loss
                str(analysis.asset_info.profit_loss_rate), # Profit Loss Rate
                str(analysis.asset_info.krw_balance),   # KRW Balance
                
                # 시장 정보
                str(analysis.market_data.current_price), # Current Market Price
                str(analysis.market_data.ma5),          # MA5
                str(analysis.market_data.rsi_1)         # RSI
            ]]
            
            self._append_values(self.SHEETS['trades'], values)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{symbol} 매매 기록 저장 완료",
                    data=result.to_dict()
                )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 매매 기록 저장 실패: {str(e)}"
                )
            raise

    def query_many(
        self,
        conditions: Dict[str, Any],
        sheet_name: str
    ) -> List[Dict]:
        """특정 조건에 맞는 거래 기록을 조회합니다.

        Args:
            conditions (Dict[str, Any]): 조회 조건 (예: {"Status": "wait", "Symbol": "BTC"})
            sheet_name (str): 조회할 시트 이름 (기본값: 'trades')

        Returns:
            List[Dict]: 조건에 맞는 기록 목록
        """
        try:
            # 시트의 모든 데이터 조회
            range_name = f"{self.SHEETS[sheet_name]}!A:Z"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
            
            # 헤더 추출
            headers = values[0]
            
            # 조건에 맞는 데이터 필터링
            filtered_records = []
            for row in values[1:]:
                record = dict(zip(headers, row))
                
                # 모든 조건 확인
                matches_all = True
                for field, value in conditions.items():
                    if field not in record or record[field] != str(value):
                        matches_all = False
                        break
                
                if matches_all:
                    filtered_records.append(record)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"조건부 데이터 조회 완료: {len(filtered_records)}건",
                    data={"conditions": conditions}
                )
            
            return filtered_records
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="조건부 데이터 조회 실패",
                    data={
                        "conditions": conditions,
                        "error": str(e)
                    }
                )
            raise 

    def update_data(
        self,
        conditions: Dict[str, Any],
        updates: Dict[str, Any],
        sheet_name: str
    ) -> None:
        """매매 기록을 수정합니다.

        Args:
            conditions (Dict[str, Any]): 수정할 레코드를 찾기 위한 조건 (예: {"ID": "trade_123"} 또는 {"Symbol": "BTC", "Order Status": "wait"})
            updates (Dict[str, Any]): 수정할 필드와 값의 딕셔너리
        """
        try:
            # 기록 조회
            range_name = f"{self.SHEETS[sheet_name]}!A:Z"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                raise ValueError("데이터가 없습니다.")
            
            # 헤더 추출
            headers = values[0]
            
            # 조건에 맞는 레코드 찾기
            target_rows = []
            for i, row in enumerate(values[1:], 1):
                record = dict(zip(headers, row))
                
                # 모든 조건 확인
                matches_all = True
                for field, value in conditions.items():
                    if field not in record or record[field] != str(value):
                        matches_all = False
                        break
                
                if matches_all:
                    target_rows.append(i)
            
            if not target_rows:
                raise ValueError(f"조건에 맞는 기록을 찾을 수 없습니다: {conditions}")
            
            if len(target_rows) > 1:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.WARNING,
                        message=f"여러 개의 레코드가 조건과 일치합니다: {len(target_rows)}개",
                        data={"conditions": conditions}
                    )
            
            # 업데이트할 값 준비
            updates_list = []
            for target_row in target_rows:
                for field, value in updates.items():
                    try:
                        col = headers.index(field)
                        updates_list.append({
                            'range': f"{self.SHEETS[sheet_name]}!{chr(65+col)}{target_row+1}",
                            'values': [[str(value)]]
                        })
                    except ValueError:
                        if self.log_manager:
                            self.log_manager.log(
                                category=LogCategory.WARNING,
                                message=f"필드 '{field}'를 찾을 수 없습니다.",
                                data={"conditions": conditions}
                            )
                        continue
            
            if not updates_list:
                raise ValueError("업데이트할 유효한 필드가 없습니다.")
            
            # 업데이트 실행
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': updates_list
            }
            
            response = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.SPREADSHEET_ID,
                body=body
            ).execute()

            print(response)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="매매 기록 수정 실패",
                    data={
                    "conditions": conditions,
                    "updates": updates,
                    "error": str(e)
                }
            )
            raise 

    def log_order_response(self, order_response: OrderResponse):
        """주문 응답 데이터를 저장합니다.
        
        Args:
            order_response (Dict): 주문 응답 데이터
            {
                "uuid": str,           # 주문 ID
                "side": str,           # 주문 방향 ("bid" 또는 "ask")
                "ord_type": str,       # 주문 타입
                "state": str,          # 주문 상태
                "market": str,         # 마켓 정보
                "created_at": str,     # 주문 생성 시각
                "volume": str,         # 주문 수량
                "remaining_volume": str, # 남은 수량
                "reserved_fee": str,   # 예약된 수수료
                "remaining_fee": str,  # 남은 수수료
                "paid_fee": str,       # 지불된 수수료
                "locked": str,         # 잠긴 금액
                "executed_volume": str, # 체결된 수량
                "trades": List[Dict]   # 체결 내역 리스트
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            symbol = order_response.market.split('-')[1]  # KRW-BTC에서 BTC 추출
            
            # 체결 내역이 있는 경우 각 체결에 대해 기록

            values = [[
                    order_response.uuid,                 # Order UUID
                    now,                                    # Timestamp
                    symbol,                                 # Symbol
                    order_response.side,                 # Order Side
                    order_response.ord_type,            # Order Type
                    order_response.price,
                    order_response.state,               # Order State
                    order_response.market,              # Market
                    order_response.created_at,          # Created At
                    order_response.volume,              # Volume
                    order_response.remaining_volume,    # Remaining Volume
                    order_response.reserved_fee,        # Reserved Fee
                    order_response.remaining_fee,       # Remaining Fee
                    order_response.paid_fee,            # Paid Fee
                    order_response.locked,              # Locked
                    order_response.executed_volume,     # Executed Volume
                    order_response.trades_count        # Trades Count
                ]]
                    
            self._append_values(self.SHEETS['order_response'], values)

            trades = order_response.trades            
            for trade in trades:
                self.log_trade_response(trade, order_response.uuid)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"주문 응답 저장 완료: {symbol}",
                    data={
                    "symbol": symbol,
                    "order_id": order_response['uuid'],
                    "state": order_response['state'],
                    "trades_count": len(trades)
                }
            )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 응답 저장 실패",
                    data={"error": str(e)}
                )
            raise 
        
    def log_trade_response(self, trade: Trade, order_id: str):
        """체결 응답 데이터를 저장합니다.
        
        Args:
            trade (Trade): 체결 응답 데이터
            order_id (str): 주문 ID
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            symbol = trade.market.split('-')[1]  # KRW-BTC에서 BTC 추출
            
            values = [[
                trade.uuid,                 # Trade UUID    
                order_id,                   # Order ID
                now,                        # Timestamp
                symbol,                     # Symbol
                trade.market,               # Trade Market
                trade.price,                # Trade Price
                trade.volume,               # Trade Volume
                trade.funds,                # Trade Funds
                trade.side,                 # Trade Side
                trade.created_at            # Trade Created At
            ]]
            
            self._append_values(self.SHEETS['trade_response'], values)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="체결 응답 저장 실패",
                    data={"error": str(e)}
                )
            raise 