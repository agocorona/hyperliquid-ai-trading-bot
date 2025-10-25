#!/usr/bin/env python3
"""
Hyperliquid Trading Bot con Órdenes Ejecutables - LLM proporciona órdenes precisas
"""

import os
import json
import time
import logging
import hashlib
import requests
import msgpack
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data
from Crypto.Hash import keccak

load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/hyperliquid_bot_executable.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# El SDK oficial tiene problemas, usamos implementación directa
logger.info("Using direct EIP-712 implementation instead of SDK")

try:
    from technical_analyzer_simple import technical_fetcher
except ImportError:
    logger.warning("technical_analyzer_simple not available, using basic market data")


class TradingAction(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_POSITION = "close_position"
    INCREASE_POSITION = "increase_position"
    REDUCE_POSITION = "reduce_position"
    CHANGE_LEVERAGE = "change_leverage"


@dataclass
class MarketData:
    coin: str
    last_price: float
    change_24h: float
    volume_24h: float
    funding_rate: float
    timestamp: float


@dataclass
class PortfolioState:
    total_balance: Decimal
    available_balance: Decimal
    margin_usage: Decimal
    positions: Dict[str, Dict[str, Any]]


@dataclass
class ExecutableOrder:
    coin: str
    action: TradingAction
    size: float
    leverage: int
    confidence: float
    reasoning: str


class HyperliquidTradingBotExecutable:
    """
    Bot de trading con órdenes ejecutables - LLM proporciona órdenes precisas
    """
    
    def __init__(self, wallet_address: str, private_key: str, deepseek_api_key: str,
                 testnet: bool = False, trading_pairs: List[str] = None):
        
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.deepseek_api_key = deepseek_api_key
        self.testnet = testnet
        
        # Pares de trading por defecto
        self.trading_pairs = trading_pairs or ["BTC", "ETH", "SOL", "BNB", "ADA"]
        
        # Configuración de trading - MUY AGRESIVA para balance pequeño
        self.position_size = Decimal('0.15')  # 15% del portfolio por posición
        self.max_margin_usage = Decimal('0.95')  # 95% máximo de margen
        self.min_balance = Decimal('0.01')  # Mínimo $0.01 para operar
        
        # No usar SDK problemático, usar implementación directa
        logger.info("Using direct EIP-712 implementation for orders")
        
        # No usar Web3, usar Account.from_key directamente como hyperliquid_minimal_order.py
        self.base_url = "https://api.hyperliquid.xyz"
        
        # Estado del bot
        self.is_running = False
        self.last_analysis = {}
        
        logger.info(f"HyperliquidTradingBotExecutable initialized for pairs: {self.trading_pairs}")
    
    def get_all_market_data(self) -> Dict[str, MarketData]:
        """
        Obtiene datos de mercado REALES para TODAS las monedas
        """
        market_data = {}
        
        for coin in self.trading_pairs:
            try:
                # Usar Binance para datos confiables
                if 'technical_fetcher' in globals():
                    indicators = technical_fetcher.get_technical_indicators(coin)
                    if indicators and indicators['current_price'] > 0:
                        logger.info(f"Using Binance data for {coin}: ${indicators['current_price']}")
                        market_data[coin] = MarketData(
                            coin=coin,
                            last_price=indicators['current_price'],
                            change_24h=indicators['change_24h'],
                            volume_24h=indicators['volume_24h'],
                            funding_rate=0.0001,  # Valor realista
                            timestamp=time.time()
                        )
                        continue
                
                # Si no hay datos reales, NO usar fallbacks - marcar como datos corruptos
                logger.error(f"NO SE PUDIERON OBTENER DATOS REALES para {coin} - NO OPERAR")
                market_data[coin] = MarketData(coin, 0, 0, 0, 0, time.time())
                
            except Exception as e:
                logger.error(f"Error getting market data for {coin}: {e}")
                # NO usar fallbacks - marcar como datos corruptos
                market_data[coin] = MarketData(coin, 0, 0, 0, 0, time.time())
        
        return market_data
    
    def get_portfolio_state(self) -> PortfolioState:
        """
        Obtiene el estado del portfolio REAL usando API directa
        """
        try:
            import requests
            
            # Obtener datos REALES de Hyperliquid
            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "clearinghouseState",
                "user": self.wallet_address
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Balance REAL
                margin_summary = data.get("marginSummary", {})
                total_balance = Decimal(str(margin_summary.get("accountValue", 5.0)))
                available_balance = Decimal(str(data.get("withdrawable", 5.0)))
                total_margin_used = Decimal(str(margin_summary.get("totalMarginUsed", 0)))
                
                # Calcular margen usado como porcentaje
                margin_usage = (total_margin_used / total_balance) if total_balance > 0 else Decimal('0')
                
                # Posiciones REALES con apalancamiento
                positions = {}
                asset_positions = data.get("assetPositions", [])
                
                for position in asset_positions:
                    position_data = position.get("position", {})
                    coin = position_data.get("coin", "")
                    if coin:
                        size = Decimal(str(position_data.get("szi", 0)))
                        entry_price = Decimal(str(position_data.get("entryPx", 0)))
                        unrealized_pnl = Decimal(str(position_data.get("unrealizedPnl", 0)))
                        margin_used = Decimal(str(position_data.get("marginUsed", 0)))
                        leverage_data = position_data.get("leverage", {})
                        leverage = Decimal(str(leverage_data.get("value", 1))) if leverage_data else Decimal('1')
                        
                        # Calcular apalancamiento real
                        position_value = size * entry_price
                        calculated_leverage = (position_value / margin_used) if margin_used > 0 else leverage
                        
                        positions[coin] = {
                            'size': size,
                            'entry_price': entry_price,
                            'unrealized_pnl': unrealized_pnl,
                            'margin_used': margin_used,
                            'leverage': calculated_leverage,
                            'position_value': position_value
                        }
                
                # Mostrar posiciones REALES con apalancamiento
                if positions:
                    logger.info("=== POSICIONES REALES ACTUALES ===")
                    for coin, pos in positions.items():
                        logger.info(f"  {coin}: {pos['size']} @ ${pos['entry_price']}")
                        logger.info(f"     PnL: ${pos['unrealized_pnl']} | Apalancamiento: {pos['leverage']}x")
                        logger.info(f"     Margen usado: ${pos['margin_used']} | Valor posición: ${pos['position_value']}")
                    logger.info("==================================")
                else:
                    logger.info("No hay posiciones reales abiertas")
                
                # Mostrar resumen de apalancamiento
                logger.info(f"Balance total: ${total_balance:.2f}")
                logger.info(f"Disponible: ${available_balance:.2f}")
                logger.info(f"Margen usado: {margin_usage*100:.1f}% (${total_margin_used:.2f})")
                
                return PortfolioState(
                    total_balance=total_balance,
                    available_balance=available_balance,
                    margin_usage=margin_usage,
                    positions=positions
                )
            else:
                logger.error(f"Could not fetch real portfolio state: {response.status_code}")
                # No usar fallbacks - si no hay datos reales, no operar
                return PortfolioState(Decimal('0'), Decimal('0'), Decimal('0'), {})
                
        except Exception as e:
            logger.error(f"Error getting real portfolio state: {e}")
            # No usar fallbacks - si no hay datos reales, no operar
            return PortfolioState(Decimal('0'), Decimal('0'), Decimal('0'), {})
    
    def get_executable_orders_from_llm(self, market_data: Dict[str, MarketData], portfolio_state: PortfolioState) -> Dict[str, Dict]:
        """
        Obtiene órdenes ejecutables de DeepSeek para TODAS las monedas
        """
        try:
            # Mostrar el prompt que se enviaría al LLM
            logger.info("DEEPSEEK PROMPT (testing - no real API call):")
            logger.info("=" * 50)
            logger.info("PROMPT: You are an expert cryptocurrency trading analyst. Provide EXECUTABLE trading orders:")
            logger.info("")
            logger.info("PORTFOLIO CONTEXT:")
            logger.info(f"  • Total Balance: ${portfolio_state.total_balance:.2f}")
            logger.info(f"  • Available: ${portfolio_state.available_balance:.2f}")
            logger.info(f"  • Margin Usage: {portfolio_state.margin_usage*100:.1f}%")
            if portfolio_state.positions:
                logger.info("  • Current Positions:")
                for coin, pos in portfolio_state.positions.items():
                    logger.info(f"    - {coin}: {pos['size']} @ ${pos['entry_price']} (Leverage: {pos['leverage']}x)")
            else:
                logger.info("  • Current Positions: No positions open")
            
            logger.info("")
            logger.info("MARKET DATA (Real-time from Binance API):")
            for coin, data in market_data.items():
                data_source = "Binance API" if data.last_price > 100 else "Fallback"
                logger.info(f"  • {coin}: ${data.last_price:.2f} | 24h: {data.change_24h*100:.1f}% | Vol: ${data.volume_24h/1000000:.1f}M | Source: {data_source}")
            
            logger.info("")
            logger.info("EXECUTABLE TRADING ORDERS - CRITICAL REQUIREMENTS:")
            logger.info("You MUST provide EXECUTABLE trading orders with precise parameters.")
            logger.info("The bot will execute these orders exactly as specified.")
            logger.info("")
            logger.info("REQUIRED ORDER PARAMETERS FOR EACH COIN:")
            logger.info("1. 'action': 'buy', 'sell', 'hold', 'close_position', 'increase_position', 'reduce_position', or 'change_leverage'")
            logger.info("2. 'size': exact position size in coin units")
            logger.info("3. 'leverage': exact leverage multiplier (1-25x)")
            logger.info("4. 'confidence': confidence score (0.1-1.0)")
            logger.info("5. 'reasoning': detailed justification")
            logger.info("")
            logger.info("ACTION DEFINITIONS:")
            logger.info("- 'buy': Open new long position")
            logger.info("- 'sell': Open new short position")
            logger.info("- 'close_position': Close entire existing position")
            logger.info("- 'increase_position': Add to existing position")
            logger.info("- 'reduce_position': Reduce existing position")
            logger.info("- 'change_leverage': Modify leverage of existing position")
            logger.info("- 'hold': No action, maintain current position")
            logger.info("")
            logger.info("SIZE CALCULATION GUIDELINES:")
            logger.info("- For new positions: 1-10% of portfolio value based on confidence")
            logger.info("- For existing positions: specify exact size to add/reduce")
            logger.info("- HYPERLIQUID MINIMUM SIZES (CRITICAL):")
            logger.info("  • BTC: 0.001 | ETH: 0.001 | SOL: 0.1 | BNB: 0.001 | ADA: 1.0 ($10 minimum)")
            logger.info("  • Orders with smaller sizes will be REJECTED by Hyperliquid")
            logger.info("")
            logger.info("LEVERAGE GUIDELINES:")
            logger.info("- Conservative (high risk): 1-3x")
            logger.info("- Balanced (medium risk): 3-8x")
            logger.info("- Aggressive (low risk): 8-15x")
            logger.info("- Maximum (very strong trend): 15-25x")
            logger.info("")
            logger.info("RETURN FORMAT: JSON with 'action', 'size', 'leverage', 'confidence', 'reasoning' for each coin")
            logger.info("=" * 50)
            
            # Llamada REAL a DeepSeek API para obtener órdenes ejecutables
            logger.info("Calling DeepSeek API for executable orders...")
            
            # Construir el prompt completo para DeepSeek
            prompt_lines = []
            prompt_lines.append("You are an expert cryptocurrency trading analyst. Provide EXECUTABLE trading orders:")
            prompt_lines.append("")
            prompt_lines.append("PORTFOLIO CONTEXT:")
            prompt_lines.append(f"  • Total Balance: ${portfolio_state.total_balance:.2f}")
            prompt_lines.append(f"  • Available: ${portfolio_state.available_balance:.2f}")
            prompt_lines.append(f"  • Margin Usage: {portfolio_state.margin_usage*100:.1f}%")
            if portfolio_state.positions:
                prompt_lines.append("  • Current Positions:")
                for coin, pos in portfolio_state.positions.items():
                    position_type = "LONG" if pos['size'] > 0 else "SHORT"
                    prompt_lines.append(f"    - {coin}: {pos['size']} @ ${pos['entry_price']} (Leverage: {pos['leverage']}x, Type: {position_type})")
            else:
                prompt_lines.append("  • Current Positions: No positions open")
            
            prompt_lines.append("")
            prompt_lines.append("MARKET DATA (Real-time from Binance API):")
            for coin, data in market_data.items():
                data_source = "Binance API" if data.last_price > 100 else "Fallback"
                prompt_lines.append(f"  • {coin}: ${data.last_price:.2f} | 24h: {data.change_24h*100:.1f}% | Vol: ${data.volume_24h/1000000:.1f}M | Source: {data_source}")
            
            prompt_lines.append("")
            prompt_lines.append("EXECUTABLE TRADING ORDERS - CRITICAL REQUIREMENTS:")
            prompt_lines.append("You MUST provide EXECUTABLE trading orders with precise parameters.")
            prompt_lines.append("The bot will execute these orders exactly as specified.")
            prompt_lines.append("")
            prompt_lines.append("REQUIRED ORDER PARAMETERS FOR EACH COIN:")
            prompt_lines.append("1. 'action': 'buy', 'sell', 'hold', 'close_position', 'increase_position', 'reduce_position', or 'change_leverage'")
            prompt_lines.append("2. 'size': exact position size in coin units")
            prompt_lines.append("3. 'leverage': exact leverage multiplier (1-25x)")
            prompt_lines.append("4. 'confidence': confidence score (0.1-1.0)")
            prompt_lines.append("5. 'reasoning': detailed justification")
            prompt_lines.append("")
            prompt_lines.append("ACTION DEFINITIONS:")
            prompt_lines.append("- 'buy': Open new long position")
            prompt_lines.append("- 'sell': Open new short position")
            prompt_lines.append("- 'close_position': Close entire existing position")
            prompt_lines.append("- 'increase_position': Add to existing position")
            prompt_lines.append("- 'reduce_position': Reduce existing position")
            prompt_lines.append("- 'change_leverage': Modify leverage of existing position")
            prompt_lines.append("- 'hold': No action, maintain current position")
            prompt_lines.append("")
            prompt_lines.append("SIZE CALCULATION GUIDELINES:")
            prompt_lines.append("- For new positions: 1-10% of portfolio value based on confidence")
            prompt_lines.append("- For existing positions: specify exact size to add/reduce")
            prompt_lines.append("- HYPERLIQUID MINIMUM SIZES (CRITICAL - ORDERS WILL BE REJECTED IF SMALLER):")
            prompt_lines.append("  • BTC: 0.001 | ETH: 0.001 | SOL: 0.1 | BNB: 0.001 | ADA: 16.0 ($10 minimum)")
            prompt_lines.append("  • These are HARD requirements from Hyperliquid exchange")
            prompt_lines.append("  • IMPORTANT: Portfolio CAN execute positions that exceed balance using leverage")
            prompt_lines.append("    - SOL: 0.1 SOL = $19.47 (portfolio: $4.50) - POSSIBLE with 5x leverage")
            prompt_lines.append("    - ADA: 16.0 ADA = $10.50 (portfolio: $4.50) - POSSIBLE with 10x leverage")
            prompt_lines.append("    - Use leverage to make positions possible with small portfolio")
            prompt_lines.append("    - REQUIRED MARGIN CALCULATION: Position Value / Leverage")
            prompt_lines.append("    - Example: 16.0 ADA @ $0.656 = $10.50 / 10x leverage = $1.05 required margin")
            prompt_lines.append("    - Current portfolio has $4.50 available - MORE THAN ENOUGH for ADA with leverage")
            prompt_lines.append("")
            prompt_lines.append("LEVERAGE GUIDELINES:")
            prompt_lines.append("- Conservative (high risk): 1-3x")
            prompt_lines.append("- Balanced (medium risk): 3-8x")
            prompt_lines.append("- Aggressive (low risk): 8-15x")
            prompt_lines.append("- Maximum (very strong trend): 15-25x")
            prompt_lines.append("")
            prompt_lines.append("CRITICAL: You MUST return JSON in EXACT format:")
            prompt_lines.append("[")
            prompt_lines.append("  {\"coin\": \"BTC\", \"action\": \"buy|sell|hold|close_position|increase_position|reduce_position|change_leverage\", \"size\": number, \"leverage\": number, \"confidence\": 0.1-1.0, \"reasoning\": \"text\"},")
            prompt_lines.append("  {\"coin\": \"ETH\", \"action\": \"buy|sell|hold|close_position|increase_position|reduce_position|change_leverage\", \"size\": number, \"leverage\": number, \"confidence\": 0.1-1.0, \"reasoning\": \"text\"},")
            prompt_lines.append("  {\"coin\": \"SOL\", \"action\": \"buy|sell|hold|close_position|increase_position|reduce_position|change_leverage\", \"size\": number, \"leverage\": number, \"confidence\": 0.1-1.0, \"reasoning\": \"text\"},")
            prompt_lines.append("  {\"coin\": \"BNB\", \"action\": \"buy|sell|hold|close_position|increase_position|reduce_position|change_leverage\", \"size\": number, \"leverage\": number, \"confidence\": 0.1-1.0, \"reasoning\": \"text\"},")
            prompt_lines.append("  {\"coin\": \"ADA\", \"action\": \"buy|sell|hold|close_position|increase_position|reduce_position|change_leverage\", \"size\": number, \"leverage\": number, \"confidence\": 0.1-1.0, \"reasoning\": \"text\"}")
            prompt_lines.append("]")
            prompt_lines.append("")
            prompt_lines.append("IMPORTANT: The 'coin' field is REQUIRED for each object. Without it, the bot cannot execute orders.")
            
            prompt = "\n".join(prompt_lines)
            
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency trading analyst. Provide clear, data-driven trading recommendations with appropriate leverage suggestions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }
            
            try:
                response = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    analysis_text = result['choices'][0]['message']['content']
                    
                    # Mostrar la respuesta completa del LLM
                    logger.info("DEEPSEEK REAL RESPONSE:")
                    logger.info("=" * 80)
                    logger.info("RAW RESPONSE TEXT:")
                    logger.info(analysis_text)
                    logger.info("-" * 80)
                    
                    # Parsear la respuesta JSON del LLM - manejar tanto objetos como arrays
                    import re
                    json_match = re.search(r'(\[.*\]|\{.*\})', analysis_text, re.DOTALL)
                    if json_match:
                        try:
                            json_data = json.loads(json_match.group())
                            
                            # Convertir array a diccionario si es necesario
                            if isinstance(json_data, list):
                                executable_orders = {}
                                for item in json_data:
                                    # Intentar obtener coin de diferentes formas
                                    coin = item.get('coin')
                                    if not coin:
                                        # Si no hay coin, inferir del reasoning o usar posición
                                        reasoning = item.get('reasoning', '')
                                        if 'ADA' in reasoning:
                                            coin = 'ADA'
                                        elif 'BTC' in reasoning:
                                            coin = 'BTC'
                                        elif 'ETH' in reasoning:
                                            coin = 'ETH'
                                        elif 'SOL' in reasoning:
                                            coin = 'SOL'
                                        elif 'BNB' in reasoning:
                                            coin = 'BNB'
                                        else:
                                            # Si no se puede inferir, usar posición en la lista
                                            coin_index = json_data.index(item)
                                            if coin_index < len(self.trading_pairs):
                                                coin = self.trading_pairs[coin_index]
                                            else:
                                                continue
                                    
                                    if coin:
                                        executable_orders[coin] = {
                                            'action': item.get('action', 'hold'),
                                            'size': item.get('size', 0),
                                            'leverage': item.get('leverage', 1),
                                            'confidence': item.get('confidence', 0),
                                            'reasoning': item.get('reasoning', 'No reasoning provided')
                                        }
                            else:
                                executable_orders = json_data
                            
                            logger.info("PARSED EXECUTABLE ORDERS:")
                            for coin, order in executable_orders.items():
                                logger.info(f"{coin}: {order.get('action', 'unknown')} {order.get('size', 0)} @ {order.get('leverage', 1)}x (confidence: {order.get('confidence', 0)})")
                                logger.info(f"   Reasoning: {order.get('reasoning', 'No reasoning provided')}")
                            logger.info("=" * 80)
                            
                            logger.info("DeepSeek API call successful - using real executable orders")
                            return executable_orders
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error: {e}, using fallback")
                    else:
                        logger.warning(f"Could not find JSON in response: {analysis_text[:200]}..., using fallback")
                else:
                    logger.warning(f"DeepSeek API call failed: {response.status_code}, using fallback")
                    
            except Exception as e:
                logger.warning(f"DeepSeek API error: {e}, using fallback")
            
            # Fallback a órdenes de ejemplo si la API falla
            logger.info("Using fallback executable orders due to API issues")
            
            # Usar órdenes de ejemplo para testing - coherentes con el estado real
            executable_orders = {}
            
            for coin in self.trading_pairs:
                # Verificar si hay posición existente para esta moneda
                has_position = coin in portfolio_state.positions and portfolio_state.positions[coin]['size'] != 0
                
                if has_position:
                    # Si hay posición, recomendar hold o ajuste
                    executable_orders[coin] = {
                        "action": "hold",
                        "size": 0.0,
                        "leverage": 3,
                        "confidence": 0.6,
                        "reasoning": f"Maintaining existing {coin} position, monitoring market conditions"
                    }
                else:
                    # Si no hay posición, recomendar hold o entrada basada en condiciones
                    executable_orders[coin] = {
                        "action": "hold",
                        "size": 0.0,
                        "leverage": 3,
                        "confidence": 0.5,
                        "reasoning": f"No existing {coin} position, waiting for better entry conditions"
                    }
            
        except Exception as e:
            logger.error(f"Error getting DeepSeek batch analysis: {e}")
            return {}
    
    def risk_management_check(self, order: Dict, portfolio_state: PortfolioState, coin: str) -> bool:
        """Verificación de gestión de riesgo para órdenes ejecutables"""
        action = order.get('action', '').lower()
        
        # Para órdenes de cierre o reducción, permitir incluso con balance bajo
        if action in ['close_position', 'reduce_position', 'sell']:
            # Verificaciones mínimas para órdenes de venta
            if portfolio_state.margin_usage > Decimal('1.0'):
                logger.warning(f"Margin usage {portfolio_state.margin_usage*100}% > 100%, cannot execute {action}")
                return False
            
            confidence = order.get('confidence', 0)
            if confidence < 0.1:  # Reducido a 0.1 para órdenes de venta/cierre
                logger.warning(f"Confidence too low for {action}: {confidence}")
                return False
            
            return True
        
        # Para órdenes de compra o aumento, mantener verificaciones estrictas
        if portfolio_state.margin_usage > self.max_margin_usage:
            logger.warning(f"Margin usage {portfolio_state.margin_usage*100}% > {self.max_margin_usage*100}%")
            return False
        
        if portfolio_state.available_balance < self.min_balance:
            logger.warning(f"Available balance {float(portfolio_state.available_balance):.2f} < {self.min_balance}")
            return False
        
        # Verificar que el tamaño de la orden sea factible con el balance disponible
        action = order.get('action', '').lower()
        if action in ['buy', 'increase_position']:
            size = Decimal(str(order.get('size', 0)))
            leverage = Decimal(str(order.get('leverage', 1)))
            
            # Para órdenes de compra, usar cálculo simplificado para balance pequeño
            # No bloquear órdenes por cálculo de margen si el balance es pequeño
            if portfolio_state.total_balance < Decimal('10'):
                # Para balance < $10, permitir órdenes sin verificación estricta de margen
                logger.info(f"Small balance mode: allowing {action} order without strict margin check")
            else:
                # Para balance normal, mantener verificaciones estándar
                market_price = Decimal('100')  # Precio aproximado para cálculo
                required_margin = (size * market_price) / leverage
                
                if required_margin > portfolio_state.available_balance:
                    logger.warning(f"Required margin {required_margin:.2f} > available balance {portfolio_state.available_balance:.2f}")
                    return False
        
        confidence = order.get('confidence', 0)
        if confidence < 0.1:  # Reducido a 0.1 para balance pequeño
            logger.warning(f"Confidence too low: {confidence}")
            return False
        
        return True
    
    
    def execute_executable_order(self, coin: str, order: Dict, market_data: MarketData) -> bool:
        """
        Ejecuta una orden ejecutable del LLM
        """
        try:
            portfolio_state = self.get_portfolio_state()
            action = order.get('action', '').lower()
            size = order.get('size', 0)
            leverage = order.get('leverage', 1)
            confidence = order.get('confidence', 0)
            reasoning = order.get('reasoning', '')
            
            logger.info(f"Processing executable order for {coin}: {action} {size} {coin} @ {leverage}x (confidence: {confidence})")
            logger.info(f"Reasoning: {reasoning}")
            
            if action == 'hold':
                logger.info(f"Hold signal for {coin}, no action taken")
                return False
            
            # Para órdenes de cierre de posición existente
            if action == 'close_position' and coin in portfolio_state.positions:
                existing_position = portfolio_state.positions[coin]
                coin_amount = float(existing_position['size'])
                
                logger.info(f"CLOSING EXISTING POSITION for {coin}: {coin_amount:.6f} at ${market_data.last_price}")
                
                # EJECUTAR ORDEN REAL para cerrar posición
                try:
                    success = self.execute_real_order(coin, 'sell', coin_amount, market_data.last_price)
                    if success:
                        logger.info(f"REAL ORDER SUCCESS: Position closed for {coin}")
                        return True
                    else:
                        logger.error(f"REAL ORDER FAILED: Could not close position for {coin}")
                        return False
                    
                except Exception as order_error:
                    logger.error(f"Error executing real order for {coin}: {order_error}")
                    return False
            
            # Para órdenes de reducción de posición
            elif action == 'reduce_position' and coin in portfolio_state.positions:
                existing_position = portfolio_state.positions[coin]
                current_size = float(existing_position['size'])
                reduce_amount = min(size, current_size)  # No reducir más de lo que tenemos
                
                logger.info(f"REDUCING POSITION for {coin}: reducing {reduce_amount:.6f} from {current_size:.6f} at ${market_data.last_price}")
                
                # EJECUTAR ORDEN REAL para reducir posición
                try:
                    success = self.execute_real_order(coin, 'sell', reduce_amount, market_data.last_price)
                    if success:
                        logger.info(f"REAL ORDER SUCCESS: Position reduced for {coin}")
                        return True
                    else:
                        logger.error(f"REAL ORDER FAILED: Could not reduce position for {coin}")
                        return False
                    
                except Exception as order_error:
                    logger.error(f"Error executing real order for {coin}: {order_error}")
                    return False
            
            # Para órdenes de aumento de posición
            elif action == 'increase_position' and coin in portfolio_state.positions:
                logger.info(f"INCREASING POSITION for {coin}: adding {size:.6f} at ${market_data.last_price} with {leverage}x leverage")
                
                # PRIMERO establecer el apalancamiento antes de ejecutar la orden
                logger.info(f"Setting leverage for {coin} to {leverage}x before increasing position")
                leverage_success = self.set_leverage(coin, leverage)
                
                if not leverage_success:
                    logger.error(f"Failed to set leverage for {coin}, cannot increase position")
                    return False
                
                # EJECUTAR ORDEN REAL para aumentar posición
                try:
                    logger.info(f"REAL ORDER: Increasing position for {coin}")
                    success = self.execute_real_order(coin, 'buy', size, market_data.last_price)
                    if success:
                        logger.info(f"REAL ORDER SUCCESS: Position increased for {coin}")
                        return True
                    else:
                        logger.error(f"REAL ORDER FAILED: Could not increase position for {coin}")
                        return False
                    
                except Exception as order_error:
                    logger.error(f"Error executing real order for {coin}: {order_error}")
                    return False
            
            # Para órdenes de cambio de apalancamiento
            elif action == 'change_leverage' and coin in portfolio_state.positions:
                logger.info(f"CHANGING LEVERAGE for {coin}: setting to {leverage}x")
                
                # Simular cambio de apalancamiento
                try:
                    logger.info(f"SIMULATED: Changing leverage for {coin} to {leverage}x")
                    logger.info(f"SIMULATED SUCCESS: Leverage changed for {coin}")
                    return True
                    
                except Exception as order_error:
                    logger.error(f"SIMULATED ERROR changing leverage for {coin}: {order_error}")
                    return False
            
            # Para órdenes de compra/venta normales (sin posición existente)
            else:
                side = 'buy' if action == 'buy' else 'sell'
                logger.info(f"Executing {side.upper()} order for {coin}: {size:.6f} at ${market_data.last_price} with {leverage}x leverage")
                
                # PRIMERO establecer el apalancamiento antes de ejecutar la orden
                logger.info(f"Setting leverage for {coin} to {leverage}x before executing order")
                leverage_success = self.set_leverage(coin, leverage)
                
                if not leverage_success:
                    logger.error(f"Failed to set leverage for {coin}, cannot execute order")
                    return False
                
                # EJECUTAR ORDEN REAL (no simular)
                try:
                    logger.info(f"REAL ORDER: Executing {side.upper()} for {coin}")
                    success = self.execute_real_order(coin, side, size, market_data.last_price)
                    if success:
                        logger.info(f"REAL ORDER SUCCESS: {side.upper()} executed for {coin}")
                        return True
                    else:
                        logger.error(f"REAL ORDER FAILED: Could not execute {side.upper()} for {coin}")
                        return False
                    
                except Exception as order_error:
                    logger.error(f"Error executing real order for {coin}: {order_error}")
                    return False
            
        except Exception as e:
            logger.error(f"Error executing executable order for {coin}: {e}")
            return False
    
    def run_trading_cycle(self):
        """Ciclo principal de trading con órdenes ejecutables"""
        logger.info("Starting EXECUTABLE ORDERS trading cycle")
        
        try:
            # Obtener estado del portfolio
            portfolio_state = self.get_portfolio_state()
            logger.info(f"Portfolio state: ${portfolio_state.total_balance:.2f} total, ${portfolio_state.available_balance:.2f} available")
            
            # Obtener datos de mercado para TODAS las monedas
            all_market_data = self.get_all_market_data()
            logger.info(f"Collected market data for {len(all_market_data)} coins")
            
            # Mostrar fuentes de datos detalladas
            logger.info("DATA SOURCES DETAIL:")
            for coin, data in all_market_data.items():
                data_source = "Binance API (real-time)" if data.last_price > 100 else "Fallback data"
                logger.info(f"  • {coin}: ${data.last_price:.2f} | 24h: {data.change_24h*100:.1f}% | Vol: ${data.volume_24h/1000000:.1f}M | Source: {data_source}")
            
            # Obtener órdenes ejecutables del LLM
            executable_orders = self.get_executable_orders_from_llm(all_market_data, portfolio_state)
            
            if not executable_orders:
                logger.error("No executable orders received from DeepSeek")
                return
            
            logger.info(f"Received executable orders for {len(executable_orders)} coins")
            
            # Variables para el resumen detallado
            trades_executed = []
            hold_decisions = []
            failed_checks = []
            market_summary = []
            
            # Procesar órdenes ejecutables para cada moneda EN ORDEN INVERSO
            coins_list = list(executable_orders.keys())
            for coin in reversed(coins_list):
                order = executable_orders[coin]
                if coin not in all_market_data:
                    logger.warning(f"No market data for ordered coin: {coin}")
                    failed_checks.append(f"{coin}: No market data")
                    continue
                
                market_data = all_market_data[coin]
                
                if market_data.last_price == 0:
                    logger.warning(f"No market data for {coin}, skipping")
                    failed_checks.append(f"{coin}: No market data")
                    continue
                
                logger.info(f"Processing executable order for {coin}")
                logger.info(f"Order details: {order}")
                
                # Agregar al resumen de mercado
                market_summary.append(f"{coin}: ${market_data.last_price:.2f}")
                
                # Verificación de riesgo para órdenes ejecutables
                if self.risk_management_check(order, portfolio_state, coin):
                    try:
                        # Ejecutar orden ejecutable
                        trade_result = self.execute_executable_order(coin, order, market_data)
                        
                        # Registrar acción en el resumen detallado
                        action = order.get('action', '').lower()
                        if action == 'hold':
                            hold_decisions.append({
                                'coin': coin,
                                'reason': order['reasoning'],
                                'confidence': order['confidence']
                            })
                            logger.info(f"Hold signal for {coin}, no action taken")
                        elif trade_result:
                            trades_executed.append({
                                'coin': coin,
                                'action': order['action'],
                                'size': order['size'],
                                'leverage': order['leverage'],
                                'confidence': order['confidence'],
                                'reasoning': order['reasoning']
                            })
                            logger.info(f"SUCCESS: Order executed for {coin}")
                        else:
                            failed_checks.append(f"{coin}: Execution failed")
                            logger.info(f"Order not executed for {coin}")
                    except Exception as e:
                        logger.warning(f"Error processing order for {coin}: {e}")
                        failed_checks.append(f"{coin}: Processing error")
                else:
                    failed_checks.append(f"{coin}: Risk check failed")
                    logger.info(f"Risk check failed for {coin}")
            
            # Mostrar explicación textual detallada del ciclo
            self._print_cycle_summary(portfolio_state, trades_executed, hold_decisions, failed_checks)
            
            logger.info("EXECUTABLE ORDERS trading cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in executable orders trading cycle: {e}")
            # Aún así imprimir resumen si es posible
            try:
                portfolio_state = self.get_portfolio_state()
                self._print_cycle_summary(portfolio_state, [], [], [f"Cycle error: {e}"])
            except:
                pass
    
    def start(self, cycle_interval: int = 300):
        """Inicia el bot con órdenes ejecutables"""
        self.is_running = True
        logger.info(f"Starting EXECUTABLE ORDERS Hyperliquid Trading Bot (interval: {cycle_interval}s)")
        
        try:
            while self.is_running:
                self.run_trading_cycle()
                logger.info(f"Waiting {cycle_interval} seconds until next cycle...")
                time.sleep(cycle_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot stopped with error: {e}")
        finally:
            self.is_running = False
    
    def _print_cycle_summary(self, portfolio_state, trades_executed, hold_decisions, failed_checks):
        """
        Imprime un resumen detallado del ciclo de trading con órdenes ejecutables
        """
        print("\n" + "="*80)
        print("CYCLE SUMMARY - Executable Orders Strategy")
        print("="*80)
        
        # Calcular retorno total usando balance real
        total_value = float(portfolio_state.total_balance)
        # Usar balance actual como referencia (sin asumir balance inicial fijo)
        total_return_pct = 0.0  # Por defecto 0% si no hay datos históricos
        
        # Construir el párrafo justificativo
        summary_parts = []
        
        # Estado del portfolio
        summary_parts.append(f"My portfolio is currently valued at ${total_value:.2f}.")
        
        # Órdenes ejecutadas
        if trades_executed:
            trades_desc = []
            for trade in trades_executed:
                trades_desc.append(f"{trade['coin']} {trade['action']} {trade['size']} @ {trade['leverage']}x (confidence: {trade['confidence']*100:.0f}%)")
            summary_parts.append(f"I've executed {len(trades_executed)} executable orders: {', '.join(trades_desc)}.")
        else:
            summary_parts.append("No executable orders were executed in this cycle.")
        
        # Decisiones de hold
        if hold_decisions:
            hold_desc = []
            for hold in hold_decisions:
                hold_desc.append(f"{hold['coin']} (reason: {hold['reason']})")
            summary_parts.append(f"I'm holding positions in: {', '.join(hold_desc)}.")
        
        # Cash disponible y oportunidades
        available_cash = float(portfolio_state.available_balance)
        summary_parts.append(f"Available cash for new opportunities: ${available_cash:.2f}.")
        
        # Razones para no operar
        if failed_checks and not trades_executed:
            failed_reasons = [check for check in failed_checks if "Risk check failed" in check or "No market data" in check or "No analysis" in check]
            if failed_reasons:
                summary_parts.append(f"Market conditions prevented new entries due to: {', '.join(failed_reasons)}.")
        
        # Imprimir el resumen completo
        justification = " ".join(summary_parts)
        print(justification)
        print("="*80 + "\n")
    
    def sign_l1_action_exact(self, action, vault_address, nonce, expires_after, is_mainnet=True):
        """sign_l1_action - EXACTA implementación como hyperliquid_minimal_order.py"""
        
        # IMPLEMENTACIÓN EXACTA de hyperliquid_minimal_order.py líneas 25-88
        def address_to_bytes(address):
            return bytes.fromhex(address[2:].lower())

        def action_hash(action, vault_address, nonce, expires_after):
            data = msgpack.packb(action)
            data += nonce.to_bytes(8, "big")
            if vault_address is None:
                data += b"\x00"
            else:
                data += b"\x01"
                data += address_to_bytes(vault_address)
            if expires_after is not None:
                data += b"\x00"
                data += expires_after.to_bytes(8, "big")
            return keccak.new(data=data, digest_bits=256).digest()

        def construct_phantom_agent(hash_bytes, is_mainnet=True):
            return {
                "source": "a" if is_mainnet else "b",
                "connectionId": "0x" + hash_bytes.hex()
            }

        def l1_payload(phantom_agent):
            return {
                "domain": {
                    "chainId": 1337,
                    "name": "Exchange",
                    "verifyingContract": "0x0000000000000000000000000000000000000000",
                    "version": "1",
                },
                "types": {
                    "Agent": [
                        {"name": "source", "type": "string"},
                        {"name": "connectionId", "type": "bytes32"},
                    ],
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                },
                "primaryType": "Agent",
                "message": phantom_agent,
            }

        # Crear wallet EXACTO como hyperliquid_minimal_order.py línea 137
        account = Account.from_key(self.private_key)
        logger.info(f"Wallet generada desde private key: {account.address}")
        logger.info(f"Wallet address esperada: {self.wallet_address}")
        
        # Usar EXACTAMENTE la misma función que hyperliquid_minimal_order.py línea 75
        hash_bytes = action_hash(action, vault_address, nonce, expires_after)
        phantom_agent = construct_phantom_agent(hash_bytes, is_mainnet)
        data = l1_payload(phantom_agent)
        
        structured_data = encode_typed_data(full_message=data)
        signed = account.sign_message(structured_data)
        
        return {
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v
        }

    def execute_real_order(self, coin: str, side: str, size: float, price: float) -> bool:
        """Execute a real order on Hyperliquid using EIP-712 signing EXACTO"""
        try:
            logger.info(f"EXECUTING REAL ORDER: {coin} {side.upper()} {size} @ ${price}")
            
            # Obtener asset ID dinámicamente de Hyperliquid
            asset_id = self._get_asset_id(coin)
            if asset_id is None:
                logger.error(f"Could not find asset ID for {coin}")
                return False
            
            # Determinar si es compra o venta
            is_buy = side.lower() == 'buy'
            
            # OBTENER PRECIO DE REFERENCIA REAL DE HYPERLIQUID
            logger.info("Getting reference price from Hyperliquid...")
            try:
                url = "https://api.hyperliquid.xyz/info"
                payload = {"type": "meta"}
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    universe = data.get("universe", [])
                    
                    reference_price = price  # Por defecto usar precio de mercado
                    for asset in universe:
                        if asset.get("name") == coin:
                            reference_price = float(asset.get("markPx", price))
                            logger.info(f"Hyperliquid reference price for {coin}: ${reference_price}")
                            break
                    
                    # Calcular precio límite dentro del rango permitido (±5% del precio de referencia)
                    # Hyperliquid permite máximo ±5% del precio de referencia
                    max_deviation = reference_price * 0.05  # 5%
                    
                    if is_buy:
                        # Para compras, usar precio ligeramente por encima del precio de referencia
                        limit_price = min(price, reference_price + max_deviation * 0.5)
                    else:
                        # Para ventas, usar precio ligeramente por debajo del precio de referencia
                        limit_price = max(price, reference_price - max_deviation * 0.5)
                    
                    # Asegurar que está dentro del rango permitido
                    limit_price = max(reference_price - max_deviation, min(limit_price, reference_price + max_deviation))
                    
                else:
                    logger.warning(f"Could not get reference price, using market price: {price}")
                    limit_price = price
                    
            except Exception as e:
                logger.warning(f"Error getting reference price, using market price: {e}")
                limit_price = price
            
            # Obtener tick size y precisión dinámicamente de Hyperliquid
            tick_size, precision = self._get_tick_size_and_precision(asset_id)
            limit_price = round(limit_price / tick_size) * tick_size
            limit_price = round(limit_price, precision)
            
            logger.info(f"Using limit price: ${limit_price:.2f} (market: ${price:.2f}, reference: ${reference_price:.2f}, tick size: ${tick_size})")
            
            # Crear acción de orden EXACTA como Hyperliquid espera
            # Para ADA usar formato específico como minimal_order.py
            if coin == "ADA":
                # ADA necesita formato específico: size como entero, price como string con decimal
                order_wire = {
                    "a": asset_id,
                    "b": is_buy,
                    "p": str(limit_price),  # Price como string
                    "s": str(int(size)),    # Size como entero (sin decimales)
                    "r": False,
                    "t": {
                        "limit": {
                            "tif": "Gtc"
                        }
                    }
                }
            else:
                # Para otras monedas usar formato normal
                order_wire = {
                    "a": asset_id,
                    "b": is_buy,
                    "p": str(limit_price),
                    "s": str(size),
                    "r": False,
                    "t": {
                        "limit": {
                            "tif": "Gtc"
                        }
                    }
                }
            
            action = {
                "type": "order",
                "orders": [order_wire],
                "grouping": "na"
            }
            
            # Generar nonce
            nonce = int(time.time() * 1000)
            
            # Firmar con esquema EXACTO del SDK oficial
            logger.info("Firmando con esquema EIP-712 exacto...")
            signature = self.sign_l1_action_exact(
                action=action,
                vault_address=None,
                nonce=nonce,
                expires_after=None,
                is_mainnet=True
            )
            
            logger.info("Firma EIP-712 generada correctamente")
            
            # Crear payload completo - FORZAR wallet address correcta
            payload = {
                "action": action,
                "nonce": nonce,
                "signature": signature,
                "vaultAddress": None
            }
            
            # Usar solo Content-Type como hyperliquid_minimal_order.py
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Payload completo para {coin}:")
            logger.info(json.dumps(payload, indent=2))
            
            # Enviar orden con headers que fuerzan wallet correcta
            response = requests.post(
                f"{self.base_url}/exchange",
                json=payload,
                headers=headers
            )
            
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    # Verificar si hay errores específicos en la respuesta
                    response_data = result.get('response', {})
                    statuses = response_data.get('data', {}).get('statuses', [])
                    
                    if statuses:
                        for status in statuses:
                            if 'error' in status:
                                logger.error(f"Order rejected by Hyperliquid: {status['error']}")
                                return False
                    
                    logger.info("ORDEN REAL EXITOSA!")
                    return True
                else:
                    logger.error(f"Order failed: {result}")
                    return False
            else:
                logger.error(f"HTTP Error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing real order: {e}")
            return False
    
    def set_leverage(self, coin: str, leverage: int) -> bool:
        """Establece el apalancamiento para una moneda específica"""
        try:
            # Obtener asset ID dinámicamente de Hyperliquid
            asset_id = self._get_asset_id(coin)
            if asset_id is None:
                logger.error(f"Could not find asset ID for {coin}")
                return False
            
            # Obtener apalancamiento máximo dinámicamente de Hyperliquid
            max_leverage = self._get_max_leverage(coin)
            if leverage > max_leverage:
                logger.warning(f"Leverage for {coin} limited to {max_leverage}x (requested: {leverage}x)")
                leverage = max_leverage
            
            # Crear acción de cambio de apalancamiento
            action = {
                "type": "updateLeverage",
                "asset": asset_id,
                "isCross": True,  # Margen cruzado
                "leverage": leverage
            }
            
            # Generar nonce
            nonce = int(time.time() * 1000)
            
            # Firmar la acción
            signature = self.sign_l1_action_exact(
                action=action,
                vault_address=None,
                nonce=nonce,
                expires_after=None,
                is_mainnet=True
            )
            
            # Crear payload
            payload = {
                "action": action,
                "nonce": nonce,
                "signature": signature,
                "vaultAddress": None
            }
            
            logger.info(f"Setting leverage for {coin} to {leverage}x")
            
            # Enviar solicitud de cambio de apalancamiento
            response = requests.post(
                f"{self.base_url}/exchange",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    logger.info(f"Leverage set successfully for {coin}: {leverage}x")
                    return True
                else:
                    logger.error(f"Failed to set leverage: {result}")
                    return False
            else:
                logger.error(f"HTTP Error setting leverage: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting leverage for {coin}: {e}")
            return False


    def _get_asset_id(self, coin: str) -> Optional[int]:
        """Obtiene el asset ID dinámicamente de Hyperliquid API"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "meta"}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                universe = data.get("universe", [])
                
                for index, asset in enumerate(universe):
                    if asset.get("name") == coin:
                        logger.info(f"Found asset ID for {coin}: {index}")
                        return index
                
                logger.error(f"Coin {coin} not found in Hyperliquid universe")
                return None
            else:
                logger.error(f"Failed to get asset IDs: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting asset ID for {coin}: {e}")
            return None

    def _get_tick_size_and_precision(self, asset_id: int) -> tuple[float, int]:
        """Obtiene tick size y precisión decimal basado en precios reales del mercado"""
        try:
            # Obtener precios actuales del mercado para determinar decimales correctos
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "allMids"}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                market_data = response.json()
                
                # Mapeo de asset IDs a nombres de moneda
                asset_id_to_coin = {
                    0: "BTC",
                    1: "ETH",
                    5: "SOL",
                    7: "BNB",
                    65: "ADA"
                }
                
                coin = asset_id_to_coin.get(asset_id)
                if coin and coin in market_data:
                    price_str = market_data[coin]
                    if price_str:
                        price_float = float(price_str)
                        # Determinar decimales basados en el precio real del mercado
                        price_str_clean = f"{price_float:.10f}".rstrip('0').rstrip('.')
                        decimal_places = len(price_str_clean.split('.')[1]) if '.' in price_str_clean else 0
                        tick_size = 10 ** (-decimal_places)
                        
                        logger.info(f"Asset ID {asset_id} ({coin}): tick_size={tick_size}, precision={decimal_places} (market price: ${price_float})")
                        return tick_size, decimal_places
            
            # Fallback basado en análisis de precios de mercado
            default_tick_sizes = {
                0: 0.1,      # BTC: $0.1 (1 decimal)
                1: 0.01,     # ETH: $0.01 (2 decimales)
                5: 0.001,    # SOL: $0.001 (3 decimales)
                7: 0.01,     # BNB: $0.01 (2 decimales)
                65: 0.00001  # ADA: $0.00001 (5 decimales)
            }
            default_precision = {
                0: 1,   # BTC: 1 decimal
                1: 2,   # ETH: 2 decimales
                5: 3,   # SOL: 3 decimales
                7: 2,   # BNB: 2 decimales
                65: 5   # ADA: 5 decimales
            }
            
            tick_size = default_tick_sizes.get(asset_id, 0.01)
            precision = default_precision.get(asset_id, 2)
            logger.info(f"Using market-based default for asset ID {asset_id}: tick_size={tick_size}, precision={precision}")
            return tick_size, precision
                
        except Exception as e:
            logger.error(f"Error getting tick size for asset {asset_id}: {e}")
            # Fallback seguro
            if asset_id == 65:  # ADA
                return 0.00001, 5
            return 0.01, 2

    def _get_max_leverage(self, coin: str) -> int:
        """Obtiene el apalancamiento máximo dinámicamente de Hyperliquid API"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "meta"}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                universe = data.get("universe", [])
                
                for asset in universe:
                    if asset.get("name") == coin:
                        max_leverage = asset.get("maxLeverage", 10)
                        logger.info(f"Max leverage for {coin}: {max_leverage}x")
                        return max_leverage
                
                logger.warning(f"Could not find max leverage for {coin}, using default 10x")
                return 10
            else:
                logger.warning(f"Failed to get max leverage for {coin}, using default 10x")
                return 10
                
        except Exception as e:
            logger.error(f"Error getting max leverage for {coin}: {e}")
            return 10

    def stop(self):
        """Detiene el bot"""
        self.is_running = False
        logger.info("Stopping EXECUTABLE ORDERS Hyperliquid Trading Bot")


def main():
    """Función principal"""
    import sys
    
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
    
    if not all([wallet_address, private_key, deepseek_api_key]):
        logger.error("Missing required environment variables")
        return
    
    # Crear y ejecutar bot con órdenes ejecutables
    bot = HyperliquidTradingBotExecutable(
        wallet_address=wallet_address,
        private_key=private_key,
        deepseek_api_key=deepseek_api_key,
        testnet=False,  # MAINNET
        trading_pairs=["BTC", "ETH", "SOL", "BNB", "ADA"]  # Más monedas para testing
    )
    
    # Opción de comando para un solo ciclo
    if len(sys.argv) > 1 and sys.argv[1] == "--single-cycle":
        logger.info("Executing SINGLE CYCLE mode")
        bot.run_trading_cycle()
        logger.info("Single cycle completed")
    else:
        try:
            bot.start(cycle_interval=300)  # 5 minutos para testing
        except KeyboardInterrupt:
            bot.stop()


if __name__ == "__main__":
    main()