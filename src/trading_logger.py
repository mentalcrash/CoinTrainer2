import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import TradeExecutionResult
from src.models.order import OrderResponse, Trade
from src.round.models import TradingRound

import uuid
import traceback

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
            'order_request': 'Order Request',  # 주문 기록
            'order_response': 'Order Response',  # 주문 응답 데이터
            'trade_response': 'Trade Response',   # 체결 응답 데이터
            'round_summary': 'Round Summary'   # 라운드 요약 정보
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
            ],
            'Round Summary': [
                'Round ID',                # 라운드 ID
                'Timestamp',               # 기록 시간
                'Symbol',                  # 심볼
                'Status',                  # 라운드 상태
                'Start Time',              # 시작 시간
                'End Time',                # 종료 시간
                'Entry Price',             # 진입 가격
                'Exit Price',              # 청산 가격
                'Take Profit',             # 목표가
                'Stop Loss',               # 손절가
                'Entry Order UUID',        # 진입 주문 ID
                'Exit Order UUID',         # 청산 주문 ID
                'Quantity',                # 수량
                'Entry Fee',               # 진입 수수료
                'Exit Fee',                # 청산 수수료
                'Total Fee',               # 총 수수료
                'PnL',                     # 손익
                'PnL Rate',                # 손익률(%)
                'Is Win',                  # 수익 여부
                'Round Duration',          # 라운드 지속 시간(분)
                'Entry Reasons',           # 진입 이유
                'Exit Reasons',            # 청산 이유
                'Entry Model Type',        # 진입 결정 모델
                'Exit Model Type'          # 청산 결정 모델
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

    def log_order_response(self, order_result: OrderResponse):
        """주문 응답 데이터를 저장합니다.
        
        Args:
            order_result (OrderResult): 주문 응답 데이터
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            symbol = order_result.market.split('-')[1]  # KRW-BTC에서 BTC 추출
            
            values = [[
                order_result.uuid,                 # Order UUID
                now,                              # Timestamp
                symbol,                           # Symbol
                order_result.side,                # Order Side
                order_result.ord_type,            # Order Type
                str(order_result.price) if order_result.price else '',  # Price
                order_result.state,               # Order State
                order_result.market,              # Market
                order_result.created_at,          # Created At
                str(order_result.volume) if order_result.volume else '', # Volume
                str(order_result.remaining_volume) if order_result.remaining_volume else '', # Remaining Volume
                str(order_result.reserved_fee) if order_result.reserved_fee else '',   # Reserved Fee
                str(order_result.remaining_fee) if order_result.remaining_fee else '',  # Remaining Fee
                str(order_result.paid_fee),       # Paid Fee
                str(order_result.locked) if order_result.locked else '',  # Locked
                order_result.executed_volume,     # Executed Volume
                order_result.trades_count         # Trades Count
            ]]
                    
            self._append_values(self.SHEETS['order_response'], values)

            if order_result.trades:
                for trade in order_result.trades:
                    self.log_trade_response(trade, order_result.uuid)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"주문 응답 저장 완료: {symbol}",
                    data={
                        "symbol": symbol,
                        "order_id": order_result.uuid,
                        "state": order_result.state,
                        "trades_count": len(order_result.trades) if order_result.trades else 0
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

    def log_round_summary(self, trading_round: TradingRound):
        """라운드 요약 정보를 저장합니다.
        
        Args:
            trading_round: 거래 라운드 객체
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # PnL 및 지속 시간 계산
            pnl = 0.0
            pnl_rate = 0.0
            round_duration = 0
            entry_fee = 0.0
            exit_fee = 0.0
            total_fee = 0.0
            is_win = False
            entry_price = 0.0
            exit_price = 0.0
            quantity = 0.0
            
            if trading_round.entry_order and trading_round.entry_order.order_result:
                entry_price = float(trading_round.entry_order.price)
                entry_fee = float(trading_round.entry_order.order_result.paid_fee) if trading_round.entry_order.order_result.paid_fee else 0.0
                quantity = float(trading_round.entry_order.order_result.executed_volume) if trading_round.entry_order.order_result.executed_volume else 0.0
                
                if trading_round.entry_order.order_result.created_at:
                    entry_time = datetime.strptime(trading_round.entry_order.order_result.created_at, "%Y-%m-%dT%H:%M:%S%z")
                    
                    if trading_round.exit_order and trading_round.exit_order.order_result and trading_round.exit_order.order_result.created_at:
                        exit_time = datetime.strptime(trading_round.exit_order.order_result.created_at, "%Y-%m-%dT%H:%M:%S%z")
                        exit_price = float(trading_round.exit_order.price)
                        exit_fee = float(trading_round.exit_order.order_result.paid_fee) if trading_round.exit_order.order_result.paid_fee else 0.0
                        
                        # 지속 시간(분)
                        round_duration = (exit_time - entry_time).total_seconds() / 60
                        
                        # PnL 계산
                        total_fee = entry_fee + exit_fee
                        pnl = (exit_price - entry_price) * quantity - total_fee
                        pnl_rate = ((exit_price - entry_price) / entry_price * 100) - ((total_fee / (entry_price * quantity)) * 100)
                        is_win = pnl > 0
            
            # 진입/청산 이유 포맷팅
            entry_reasons = ", ".join(trading_round.entry_reason) if hasattr(trading_round, 'entry_reason') and trading_round.entry_reason else ""
            exit_reasons = ", ".join(trading_round.exit_reason) if hasattr(trading_round, 'exit_reason') and trading_round.exit_reason else ""
            
            # 진입/청산 모델 타입
            entry_model_type = trading_round.entry_model_type if hasattr(trading_round, 'entry_model_type') else ""
            exit_model_type = trading_round.exit_model_type if hasattr(trading_round, 'exit_model_type') else ""
            
            # 시작/종료 시간 결정
            start_time = ""
            end_time = ""
            
            # start_time 결정 (여러 필드 중 존재하는 것 사용)
            if hasattr(trading_round, 'start_time') and trading_round.start_time:
                start_time = trading_round.start_time.strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(trading_round, 'created_at') and trading_round.created_at:
                start_time = trading_round.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # end_time 결정 (여러 필드 중 존재하는 것 사용)
            if hasattr(trading_round, 'end_time') and trading_round.end_time:
                end_time = trading_round.end_time.strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(trading_round, 'updated_at') and trading_round.updated_at:
                end_time = trading_round.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                trading_round.id,                            # Round ID
                now,                                         # Timestamp
                trading_round.symbol,                        # Symbol
                trading_round.status,                        # Status
                start_time,                                  # Start Time
                end_time,                                    # End Time
                str(entry_price),                            # Entry Price
                str(exit_price) if exit_price else "",       # Exit Price
                str(trading_round.take_profit) if hasattr(trading_round, 'take_profit') and trading_round.take_profit else "",  # Take Profit
                str(trading_round.stop_loss) if hasattr(trading_round, 'stop_loss') and trading_round.stop_loss else "",       # Stop Loss
                trading_round.entry_order.order_result.uuid if trading_round.entry_order and trading_round.entry_order.order_result else "",  # Entry Order UUID
                trading_round.exit_order.order_result.uuid if trading_round.exit_order and trading_round.exit_order.order_result else "",    # Exit Order UUID
                str(quantity),                                # Quantity
                str(entry_fee),                               # Entry Fee
                str(exit_fee),                                # Exit Fee
                str(total_fee),                               # Total Fee
                str(pnl),                                     # PnL
                f"{pnl_rate:.2f}%",                           # PnL Rate
                "Y" if is_win else "N",                       # Is Win
                f"{round_duration:.1f}",                      # Round Duration
                entry_reasons,                                # Entry Reasons
                exit_reasons,                                 # Exit Reasons
                entry_model_type,                             # Entry Model Type
                exit_model_type                               # Exit Model Type
            ]]
            
            self._append_values(self.SHEETS['round_summary'], values)
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"라운드 요약 저장 완료: {trading_round.id}",
                    data={
                        "round_id": trading_round.id,
                        "symbol": trading_round.symbol,
                        "status": trading_round.status,
                        "pnl_rate": f"{pnl_rate:.2f}%",
                        "is_win": is_win
                    }
                )
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="라운드 요약 저장 실패",
                    data={
                        "round_id": trading_round.id if hasattr(trading_round, 'id') else "Unknown",
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                )
            raise 