#!/usr/bin/env python3
"""
ORDEN MÍNIMA FUNCIONAL PARA HYPERLIQUID
Script que hace UNA SOLA orden mínima con el esquema EIP-712 correcto
"""

import json
import time
import requests
import os
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data
import msgpack
from Crypto.Hash import keccak

# ===== CONFIGURACIÓN MÍNIMA =====
load_dotenv()
PRIVATE_KEY = os.getenv("HYPERLIQUID_PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
BASE_URL = "https://api.hyperliquid.xyz"

# ===== IMPLEMENTACIÓN EXACTA DEL SDK OFICIAL =====

def address_to_bytes(address):
    """Convierte dirección Ethereum a bytes"""
    return bytes.fromhex(address[2:].lower())

def action_hash(action, vault_address, nonce, expires_after):
    """Hash de acción - EXACTO como SDK oficial"""
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
    """Agente fantasma - EXACTO como SDK oficial"""
    return {
        "source": "a" if is_mainnet else "b",
        "connectionId": "0x" + hash_bytes.hex()
    }

def l1_payload(phantom_agent):
    """Payload EIP-712 - EXACTO como SDK oficial"""
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

def sign_l1_action_exact(wallet, action, vault_address, nonce, expires_after, is_mainnet=True):
    """sign_l1_action - EXACTA implementación"""
    hash_bytes = action_hash(action, vault_address, nonce, expires_after)
    phantom_agent = construct_phantom_agent(hash_bytes, is_mainnet)
    data = l1_payload(phantom_agent)
    
    structured_data = encode_typed_data(full_message=data)
    signed = wallet.sign_message(structured_data)
    
    return {
        "r": hex(signed.r),
        "s": hex(signed.s), 
        "v": signed.v
    }

# ===== ORDEN MÍNIMA =====

def get_timestamp_ms():
    """Timestamp en milisegundos"""
    return int(time.time() * 1000)

def get_asset_id(coin):
    """Obtiene el asset ID para una moneda"""
    url = f"{BASE_URL}/info"
    response = requests.post(url, json={"type": "meta"})
    if response.status_code == 200:
        meta = response.json()
        for i, asset in enumerate(meta.get("universe", [])):
            if asset.get("name") == coin:
                return i
    return None

def create_minimal_order(coin, is_buy, sz, limit_px):
    """Crea una orden MÍNIMA y FUNCIONAL"""
    asset_id = get_asset_id(coin)
    if asset_id is None:
        print(f"❌ No se encontró asset ID para {coin}")
        return None
    
    print(f"✅ Asset ID para {coin}: {asset_id}")
    
    # Orden mínima según formato Hyperliquid
    order_wire = {
        "a": asset_id,  # Asset ID correcto
        "b": is_buy,    # Buy/Sell
        "p": str(limit_px),  # Price como string
        "s": str(sz),   # Size como string
        "r": False,     # Reduce only
        "t": {"limit": {"tif": "Gtc"}}  # Order type
    }
    
    return {
        "type": "order",
        "orders": [order_wire],
        "grouping": "na"
    }

def send_minimal_order():
    """Envía UNA SOLA orden mínima a Hyperliquid"""
    print("=== ORDEN MÍNIMA HYPERLIQUID ===")
    
    # Crear wallet
    account = Account.from_key(PRIVATE_KEY)
    print(f"💰 Wallet: {account.address}")
    
    # Crear orden MÍNIMA
    coin = "ETH"
    is_buy = True
    size = 0.01  # 0.01 ETH = ~$40 (mínimo $10)
    price = 4000M  # Precio razonable
    
    print(f"📝 Orden: {coin} {'BUY' if is_buy else 'SELL'} {size} @ ${price}")
    
    order_action = create_minimal_order(coin, is_buy, size, price)
    if not order_action:
        return False
    
    print("✅ Acción de orden creada")
    
    # Obtener timestamp
    timestamp = get_timestamp_ms()
    print(f"⏰ Nonce: {timestamp}")
    
    # Firmar con esquema CORRECTO
    print("🔐 Firmando...")
    signature = sign_l1_action_exact(
        wallet=account,
        action=order_action,
        vault_address=None,
        nonce=timestamp,
        expires_after=None,
        is_mainnet=True
    )
    
    print("✅ Firma generada")
    
    # Crear payload final
    payload = {
        "action": order_action,
        "nonce": timestamp,
        "signature": signature,
        "vaultAddress": None
    }
    
    print("📦 Payload completo:")
    print(json.dumps(payload, indent=2))
    
    # Enviar orden
    print("\n🚀 ENVIANDO ORDEN REAL...")
    url = f"{BASE_URL}/exchange"
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"📡 Status: {response.status_code}")
        print(f"📨 Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("🎉 ¡ORDEN EXITOSA!")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"💬 Mensaje: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def verify_wallet_balance():
    """Verifica el balance de la wallet"""
    print("\n=== VERIFICANDO BALANCE ===")
    
    url = f"{BASE_URL}/info"
    payload = {
        "type": "clearinghouseState",
        "user": WALLET_ADDRESS
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Estado del usuario: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ Error al verificar balance: {response.status_code}")
            print(f"💬 {response.text}")
            return False
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("ORDEN MÍNIMA HYPERLIQUID")
    print("Una sola orden funcional con EIP-712 correcto")
    print("=" * 50)
    print()
    
    # Verificar balance primero
    verify_wallet_balance()
    
    # Preguntar si enviar orden
    if input("\n¿Enviar orden mínima REAL a Hyperliquid? (y/n): ").lower() == 'y':
        print("\n" + "="*30)
        send_minimal_order()
    else:
        print("\n📋 Orden preparada pero no enviada")
        print("Para enviar manualmente, ejecuta el script y responde 'y'")