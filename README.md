# Hyperliquid Trading Bot - Manual de Operación

## Descripción del Bot

Este es un bot de trading automatizado que opera en la plataforma Hyperliquid usando inteligencia artificial (DeepSeek) para generar órdenes ejecutables. El bot analiza datos de mercado en tiempo real y ejecuta órdenes de trading con gestión automática de riesgo.

## Funcionalidades Principales

### ✅ Características Implementadas
- **Generación de órdenes por IA**: DeepSeek analiza datos de mercado y genera órdenes ejecutables
- **Integración con Hyperliquid API**: Conexión directa usando EIP-712 signing
- **Gestión automática de leverage**: Configura el apalancamiento antes de cada orden
- **Validación de precios**: Usa precios de referencia de Hyperliquid para evitar rechazos
- **Cálculo dinámico de mínimos**: Calcula automáticamente los tamaños mínimos para cada asset
- **Gestión de portfolio**: Monitorea balances y posiciones en tiempo real

### 📊 Assets Soportados
- **BTC**: Mínimo 0.001 BTC (~$111)
- **ETH**: Mínimo 0.001 ETH (~$4)
- **SOL**: Mínimo 0.1 SOL (~$19)
- **BNB**: Mínimo 0.001 BNB (~$1)
- **ADA**: Mínimo 16.0 ADA (~$10.50)

## Archivos del Proyecto

### 📁 Estructura de Archivos
```
hyperliquid/
├── hyperliquid_bot_executable_orders.py  # 🎯 BOT PRINCIPAL
├── hyperliquid_minimal_order.py          # Ordenes mínimas de prueba
├── technical_analyzer_simple.py          # Análisis técnico básico
├── check_current_positions.py            # Verificador de posiciones
├── close_sol_position.py                 # Cierre específico de SOL
├── .env                                  # 🔐 Variables de entorno
├── requirements.txt                      # Dependencias Python
├── README.md                             # 📋 Este manual
└── logs/                                 # 📊 Logs de ejecución
```

## Configuración y Uso

### 🔧 Configuración Inicial
1. **Variables de entorno** (`.env`):
   ```
   HYPERLIQUID_PRIVATE_KEY=tu_private_key_aqui
   DEEPSEEK_API_KEY=tu_api_key_deepseek
   ```

2. **Instalación de dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

### 🚀 Ejecución del Bot

**Modo ciclo único (testing):**
```bash
python hyperliquid_bot_executable_orders.py --single-cycle
```

**Modo continuo (producción):**
```bash
python hyperliquid_bot_executable_orders.py
```

### 🛠️ Herramientas Auxiliares

**Verificar posiciones actuales:**
```bash
python check_current_positions.py
```

**Cerrar posición específica (SOL):**
```bash
python close_sol_position.py
```

**Probar órdenes mínimas:**
```bash
python hyperliquid_minimal_order.py
```

## Flujo de Operación

### 🔄 Ciclo de Trading
1. **Recolección de datos**: Obtiene precios en tiempo real de Binance API
2. **Análisis por IA**: DeepSeek genera órdenes ejecutables basadas en datos de mercado
3. **Validación**: Verifica balances, mínimos y condiciones de mercado
4. **Configuración de leverage**: Establece apalancamiento antes de cada orden
5. **Ejecución**: Envía órdenes a Hyperliquid usando EIP-712 signing
6. **Monitoreo**: Registra resultados y actualiza estado del portfolio

### ⚙️ Parámetros de Orden
Cada orden generada por la IA incluye:
- **Acción**: buy, sell, hold, close_position
- **Tamaño**: Cantidad exacta en unidades del asset
- **Leverage**: Multiplicador de apalancamiento (1-25x)
- **Confianza**: Score de 0.1-1.0
- **Razonamiento**: Justificación detallada de la decisión

## Gestión de Riesgo

### 🛡️ Mecanismos de Protección
- **Validación de mínimos**: Asegura que todas las órdenes cumplan con los requisitos de Hyperliquid
- **Cálculo de margen**: Verifica disponibilidad de fondos antes de ejecutar
- **Límites de leverage**: Usa máximo permitido por Hyperliquid para cada asset
- **Precisión de precios**: Ajusta a tick sizes específicos de cada asset

### 📈 Mínimos por Asset
| Asset | Mínimo | Valor Aprox. |
|-------|--------|--------------|
| BTC | 0.001 | $111 |
| ETH | 0.001 | $4 |
| SOL | 0.1 | $19 |
| BNB | 0.001 | $1 |
| ADA | 16.0 | $10.50 |

## Solución de Problemas

### 🔍 Problemas Comunes Resueltos

1. **"Order price cannot be more than 95% away from reference price"**
   - ✅ Solucionado: Usa precios de referencia de Hyperliquid API

2. **"User or API Wallet does not exist" (ADA)**
   - ✅ Solucionado: Implementación unificada de EIP-712 para todos los assets

3. **Función de leverage no se ejecuta**
   - ✅ Solucionado: Llamada automática antes de cada orden

4. **Mínimos incorrectos para ADA**
   - ✅ Solucionado: Cálculo dinámico basado en precio actual (16.0 ADA = $10.50)

### 📋 Verificación de Estado
- Revisar logs en `logs/hyperliquid_bot_executable.log`
- Verificar balances con `check_current_positions.py`
- Monitorear ejecuciones en tiempo real

## Consideraciones Técnicas

### 🔐 Seguridad
- Las private keys se almacenan solo en `.env`
- Comunicación HTTPS con todas las APIs
- Firma EIP-712 para autenticación en Hyperliquid

### 📊 Performance
- Tiempo de ciclo: ~30-45 segundos
- Actualización de precios en tiempo real
- Gestión eficiente de conexiones API

### 🎯 Precisión
- Tick sizes dinámicos basados en precios de mercado
- Redondeo automático a precisiones requeridas
- Validación cruzada de datos entre múltiples fuentes

---

**Estado Actual**: ✅ OPERATIVO - Todas las funcionalidades funcionando correctamente
**Última Actualización**: 25 Octubre 2025