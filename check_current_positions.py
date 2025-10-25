#!/usr/bin/env python3
"""
Script para verificar posiciones actuales en Hyperliquid
"""

import os
import sys
import json
import requests
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
WALLET_ADDRESS = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
PRIVATE_KEY = os.getenv('HYPERLIQUID_PRIVATE_KEY')
BASE_URL = "https://api.hyperliquid.xyz"

def get_user_state():
    """Obtener estado del usuario desde Hyperliquid API"""
    url = f"{BASE_URL}/info"
    payload = {
        "type": "clearinghouseState",
        "user": WALLET_ADDRESS
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error al obtener estado del usuario: {e}")
        return None

def get_meta():
    """Obtener metadata de Hyperliquid"""
    url = f"{BASE_URL}/info"
    payload = {"type": "meta"}
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al obtener metadata: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=== VERIFICACIÓN DE POSICIONES ACTUALES ===")
    print(f"Wallet: {WALLET_ADDRESS}")
    print()
    
    # Obtener metadata
    print("Obteniendo metadata...")
    meta = get_meta()
    if not meta:
        print("❌ No se pudo obtener metadata")
        return
    
    print(f"✅ Metadata obtenida - {len(meta.get('universe', []))} monedas disponibles")
    
    # Obtener estado del usuario
    print("\nObteniendo estado del usuario...")
    user_state = get_user_state()
    if not user_state:
        print("❌ No se pudo obtener estado del usuario")
        return
    
    # Procesar balance
    if 'marginSummary' in user_state:
        margin = user_state['marginSummary']
        total_account_value = Decimal(str(margin.get('accountValue', 0)))
        total_margin_used = Decimal(str(margin.get('totalMarginUsed', 0)))
        withdrawable = Decimal(str(margin.get('withdrawable', 0)))
        
        print(f"💰 Balance Total: ${total_account_value:.2f}")
        print(f"💳 Disponible: ${withdrawable:.2f}")
        print(f"📊 Margen Usado: ${total_margin_used:.2f}")
        
        if total_account_value > 0:
            margin_usage = (total_margin_used / total_account_value) * 100
            print(f"📈 Uso de Margen: {margin_usage:.1f}%")
    
    # Procesar posiciones
    print("\n📊 POSICIONES ACTUALES:")
    positions = user_state.get('assetPositions', [])
    
    if not positions:
        print("   No hay posiciones abiertas")
    else:
        for position in positions:
            position_data = position.get('position', {})
            coin = position_data.get('coin', 'Unknown')
            size = Decimal(str(position_data.get('szi', 0)))
            entry_px = Decimal(str(position_data.get('entryPx', 0)))
            unrealized_pnl = Decimal(str(position_data.get('unrealizedPnl', 0)))
            margin_used = Decimal(str(position_data.get('positionValue', 0))) - unrealized_pnl
            
            if size != 0:
                position_value = abs(size * entry_px)
                leverage = position_value / margin_used if margin_used > 0 else Decimal('0')
                
                print(f"   {coin}:")
                print(f"     Tamaño: {size} {coin}")
                print(f"     Precio Entrada: ${entry_px:.2f}")
                print(f"     PnL: ${unrealized_pnl:.4f}")
                print(f"     Margen Usado: ${margin_used:.4f}")
                print(f"     Valor Posición: ${position_value:.2f}")
                print(f"     Apalancamiento: {leverage:.2f}x")
                print(f"     Tipo: {'LONG' if size > 0 else 'SHORT'}")
                print()

if __name__ == "__main__":
    main()