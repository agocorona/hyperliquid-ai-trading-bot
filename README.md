# Hyperliquid AI Trading Bot

## Bot Description

This is an automated trading bot that operates on the Hyperliquid platform using artificial intelligence (DeepSeek) to generate executable trading orders. The bot analyzes real-time market data and executes trading orders with automatic risk management.

## Key Features

### ✅ Implemented Features
- **AI-Generated Orders**: DeepSeek analyzes market data and generates executable orders
- **Hyperliquid API Integration**: Direct connection using EIP-712 signing
- **Automatic Leverage Management**: Configures leverage before each order
- **Price Validation**: Uses Hyperliquid reference prices to avoid rejections
- **Dynamic Minimum Calculation**: Automatically calculates minimum sizes for each asset
- **Portfolio Management**: Monitors balances and positions in real-time

### 📊 Supported Assets
- **BTC**: Minimum 0.001 BTC (~$111)
- **ETH**: Minimum 0.001 ETH (~$4)
- **SOL**: Minimum 0.1 SOL (~$19)
- **BNB**: Minimum 0.001 BNB (~$1)
- **ADA**: Minimum 16.0 ADA (~$10.50)

## Project Files

### 📁 File Structure
```
hyperliquid/
├── hyperliquid_bot_executable_orders.py  # 🎯 MAIN BOT
├── hyperliquid_minimal_order.py          # Minimum order tests
├── technical_analyzer_simple.py          # Basic technical analysis
├── check_current_positions.py            # Position checker
├── close_sol_position.py                 # SOL position closer
├── .env                                  # 🔐 Environment variables
├── requirements.txt                      # Python dependencies
├── README.md                             # 📋 This manual
└── logs/                                 # 📊 Execution logs
```

## Setup and Usage

### 🔧 Initial Configuration
1. **Environment variables** (`.env`):
   ```
   HYPERLIQUID_PRIVATE_KEY=your_hyperliquid_private_key_here
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### 🚀 Bot Execution

**Single cycle mode (testing):**
```bash
python hyperliquid_bot_executable_orders.py --single-cycle
```

**Continuous mode (production):**
```bash
python hyperliquid_bot_executable_orders.py
```

### 🛠️ Auxiliary Tools

**Check current positions:**
```bash
python check_current_positions.py
```

**Close specific position (SOL):**
```bash
python close_sol_position.py
```

**Test minimum orders:**
```bash
python hyperliquid_minimal_order.py
```

## Operation Flow

### 🔄 Trading Cycle
1. **Data Collection**: Gets real-time prices from Binance API
2. **AI Analysis**: DeepSeek generates executable orders based on market data
3. **Validation**: Verifies balances, minimums and market conditions
4. **Leverage Configuration**: Sets leverage before each order
5. **Execution**: Sends orders to Hyperliquid using EIP-712 signing
6. **Monitoring**: Records results and updates portfolio status

### ⚙️ Order Parameters
Each AI-generated order includes:
- **Action**: buy, sell, hold, close_position
- **Size**: Exact quantity in asset units
- **Leverage**: Leverage multiplier (1-25x)
- **Confidence**: Confidence score (0.1-1.0)
- **Reasoning**: Detailed decision justification

## Risk Management

### 🛡️ Protection Mechanisms
- **Minimum Validation**: Ensures all orders meet Hyperliquid requirements
- **Margin Calculation**: Verifies fund availability before execution
- **Leverage Limits**: Uses maximum allowed by Hyperliquid for each asset
- **Price Precision**: Adjusts to specific tick sizes for each asset

### 📈 Minimums by Asset
| Asset | Minimum | Approx. Value |
|-------|---------|---------------|
| BTC | 0.001 | $111 |
| ETH | 0.001 | $4 |
| SOL | 0.1 | $19 |
| BNB | 0.001 | $1 |
| ADA | 16.0 | $10.50 |

## Troubleshooting

### 🔍 Common Problems Solved

1. **"Order price cannot be more than 95% away from reference price"**
   - ✅ Solved: Uses Hyperliquid API reference prices

2. **"User or API Wallet does not exist" (ADA)**
   - ✅ Solved: Unified EIP-712 implementation for all assets

3. **Leverage function not executing**
   - ✅ Solved: Automatic call before each order

4. **Incorrect minimums for ADA**
   - ✅ Solved: Dynamic calculation based on current price (16.0 ADA = $10.50)

### 📋 Status Verification
- Check logs in `logs/hyperliquid_bot_executable.log`
- Verify balances with `check_current_positions.py`
- Monitor executions in real-time

## Technical Considerations

### 🔐 Security
- Private keys stored only in `.env`
- HTTPS communication with all APIs
- EIP-712 signing for Hyperliquid authentication

### 📊 Performance
- Cycle time: ~30-45 seconds
- Real-time price updates
- Efficient API connection management

### 🎯 Precision
- Dynamic tick sizes based on market prices
- Automatic rounding to required precisions
- Cross-validation of data between multiple sources

---

**Current Status**: ✅ OPERATIONAL - All features working correctly
**Last Updated**: October 25, 2025