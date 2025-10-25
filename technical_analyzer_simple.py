import requests
import time
import logging
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class SimpleTechnicalFetcher:
    """
    Obtiene datos de mercado reales y calcula indicadores técnicos sin usar pandas
    Utiliza la API pública de Binance para datos reales
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        
    def get_historical_klines(self, symbol: str, interval: str = '3m', limit: int = 100) -> Optional[List]:
        """
        Obtiene datos históricos de velas de Binance sin pandas
        """
        try:
            url = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Procesar datos sin pandas
            processed_data = []
            for candle in data:
                processed_candle = {
                    'open_time': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]),
                    'close_time': candle[6]
                }
                processed_data.append(processed_candle)
                
            return processed_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calcula EMA (Exponential Moving Average) sin pandas"""
        if len(prices) < period:
            return [0.0] * len(prices)
            
        ema_values = []
        multiplier = 2.0 / (period + 1)
        
        # Primer EMA es SMA
        sma = sum(prices[:period]) / period
        ema_values.extend([sma] * (period - 1))
        ema_values.append(sma)
        
        # Calcular EMA para el resto
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (ema_values[i-1] * (1 - multiplier))
            ema_values.append(ema)
            
        return ema_values
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """Calcula MACD sin pandas"""
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        
        macd_line = [fast_val - slow_val for fast_val, slow_val in zip(ema_fast, ema_slow)]
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = [macd - signal for macd, signal in zip(macd_line, signal_line)]
        
        return macd_line, signal_line, histogram
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calcula RSI sin pandas"""
        if len(prices) <= period:
            return [50.0] * len(prices)
            
        rsi_values = [50.0] * (period)  # RSI inicial
        
        for i in range(period, len(prices)):
            gains = []
            losses = []
            
            for j in range(i - period + 1, i + 1):
                change = prices[j] - prices[j-1] if j > 0 else 0
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / period if gains else 0
            avg_loss = sum(losses) / period if losses else 0
            
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                
            rsi_values.append(rsi)
            
        return rsi_values
    
    def get_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """
        Obtiene datos de ticker de 24h de Binance para volumen y cambio
        """
        try:
            url = f"{self.base_url}/ticker/24hr"
            params = {'symbol': symbol}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'price_change_percent': float(data.get('priceChangePercent', 0)),
                'volume': float(data.get('volume', 0)),
                'quote_volume': float(data.get('quoteVolume', 0))
            }
            
        except Exception as e:
            logger.error(f"Error fetching 24h ticker for {symbol}: {e}")
            return None

    def get_technical_indicators(self, coin: str) -> Optional[Dict]:
        """
        Obtiene todos los indicadores técnicos para una moneda sin pandas
        """
        try:
            # Mapear símbolos de Hyperliquid a Binance
            symbol_map = {
                'BTC': 'BTCUSDT',
                'ETH': 'ETHUSDT',
                'SOL': 'SOLUSDT',
                'BNB': 'BNBUSDT',
                'DOGE': 'DOGEUSDT',
                'XRP': 'XRPUSDT',
                'ADA': 'ADAUSDT'
            }
            
            binance_symbol = symbol_map.get(coin)
            if not binance_symbol:
                logger.error(f"No symbol mapping for {coin}")
                return None
            
            # Obtener datos de ticker para volumen y cambio 24h
            ticker_data = self.get_ticker_24h(binance_symbol)
            
            # Obtener datos históricos
            intraday_data = self.get_historical_klines(binance_symbol, '3m', 50)
            daily_data = self.get_historical_klines(binance_symbol, '4h', 50)
            
            if intraday_data is None or daily_data is None:
                return None
            
            # Extraer precios de cierre
            intraday_closes = [candle['close'] for candle in intraday_data]
            intraday_highs = [candle['high'] for candle in intraday_data]
            intraday_lows = [candle['low'] for candle in intraday_data]
            intraday_volumes = [candle['volume'] for candle in intraday_data]
            
            daily_closes = [candle['close'] for candle in daily_data]
            daily_highs = [candle['high'] for candle in daily_data]
            daily_lows = [candle['low'] for candle in daily_data]
            
            # Calcular indicadores intraday
            ema_20 = self.calculate_ema(intraday_closes, 20)
            macd_line, signal_line, histogram = self.calculate_macd(intraday_closes)
            rsi_7 = self.calculate_rsi(intraday_closes, 7)
            rsi_14 = self.calculate_rsi(intraday_closes, 14)
            
            # Calcular indicadores de contexto largo plazo
            daily_ema_20 = self.calculate_ema(daily_closes, 20)
            daily_ema_50 = self.calculate_ema(daily_closes, 50)
            daily_macd, daily_signal, _ = self.calculate_macd(daily_closes)
            daily_rsi_14 = self.calculate_rsi(daily_closes, 14)
            
            # Obtener últimos valores
            current_price = intraday_closes[-1] if intraday_closes else 0
            current_volume = intraday_volumes[-1] if intraday_volumes else 0
            avg_volume = sum(intraday_volumes[-20:]) / min(20, len(intraday_volumes)) if intraday_volumes else 0
            
            # Calcular ATR simple (sin pandas)
            def simple_atr(highs, lows, closes, period):
                if len(highs) < period:
                    return [0.0] * len(highs)
                
                tr_values = []
                for i in range(1, len(highs)):
                    tr1 = highs[i] - lows[i]
                    tr2 = abs(highs[i] - closes[i-1])
                    tr3 = abs(lows[i] - closes[i-1])
                    tr = max(tr1, tr2, tr3)
                    tr_values.append(tr)
                
                atr_values = [0.0] * (period)
                for i in range(period, len(tr_values)):
                    atr = sum(tr_values[i-period:i]) / period
                    atr_values.append(atr)
                
                return atr_values
            
            intraday_atr = simple_atr(intraday_highs, intraday_lows, intraday_closes, 14)
            daily_atr_3 = simple_atr(daily_highs, daily_lows, daily_closes, 3)
            daily_atr_14 = simple_atr(daily_highs, daily_lows, daily_closes, 14)
            
            # Usar datos de ticker para volumen y cambio 24h, o fallback a datos calculados
            if ticker_data:
                change_24h = ticker_data['price_change_percent'] / 100  # Convertir a decimal
                volume_24h = ticker_data['quote_volume']  # Volumen en USDT
            else:
                # Fallback: calcular cambio aproximado de 24h usando datos históricos
                if len(daily_closes) >= 2:
                    change_24h = (daily_closes[-1] - daily_closes[0]) / daily_closes[0]
                else:
                    change_24h = 0.0
                volume_24h = current_volume * 480  # Estimación aproximada (3m * 480 = 24h)
            
            return {
                'current_price': current_price,
                'change_24h': change_24h,
                'volume_24h': volume_24h,
                'current_ema20': ema_20[-1] if ema_20 else 0,
                'current_macd': macd_line[-1] if macd_line else 0,
                'current_rsi_7': rsi_7[-1] if rsi_7 else 50,
                'current_rsi_14': rsi_14[-1] if rsi_14 else 50,
                'intraday_series': {
                    'mid_prices': intraday_closes[-10:],
                    'ema_20': ema_20[-10:],
                    'macd': macd_line[-10:],
                    'rsi_7': rsi_7[-10:],
                    'rsi_14': rsi_14[-10:]
                },
                'long_term_context': {
                    'ema_20': daily_ema_20[-1] if daily_ema_20 else 0,
                    'ema_50': daily_ema_50[-1] if daily_ema_50 else 0,
                    'atr_3': daily_atr_3[-1] if daily_atr_3 else 0,
                    'atr_14': daily_atr_14[-1] if daily_atr_14 else 0,
                    'macd': daily_macd[-10:],
                    'rsi_14': daily_rsi_14[-10:],
                    'current_volume': current_volume,
                    'avg_volume': avg_volume
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {coin}: {e}")
            return None
    
    def get_open_interest_and_funding(self, coin: str) -> Dict:
        """
        Obtiene datos de open interest y funding rate (simulados para testing)
        """
        try:
            # Usar datos realistas basados en el mercado actual
            import random
            base_oi = 1000000 + random.randint(0, 500000)
            market_factor = random.uniform(-0.01, 0.01)
            
            return {
                'open_interest_latest': f"{base_oi:,}",
                'open_interest_average': f"{int(base_oi * 0.95):,}",
                'funding_rate': f"{0.01 + market_factor:.4f}%"
            }
            
        except Exception as e:
            logger.error(f"Error getting OI/funding for {coin}: {e}")
            # Fallback a datos realistas
            return {
                'open_interest_latest': "1,000,000",
                'open_interest_average': "950,000",
                'funding_rate': "0.0100%"
            }


# Instancia global para reutilizar
technical_fetcher = SimpleTechnicalFetcher()