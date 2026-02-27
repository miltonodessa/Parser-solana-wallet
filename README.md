# Solana Wallet Transaction Parser

Парсер всех транзакций кошелька Solana с полным декодированием данных — без ограничения в 1000 транзакций.

## Возможности

| Функция | Описание |
|---------|----------|
| **Полная история** | Пагинация через курсор `before`, собирает все транзакции |
| **jsonParsed декодирование** | RPC-нода декодирует System Program, SPL Token автоматически |
| **Кастомные декодеры** | System Program, SPL Token, Token-2022 (свои Borsh-декодеры) |
| **100+ известных программ** | Jupiter, Raydium, Orca, Metaplex, Serum, Marinade и др. |
| **SOL/токен балансы** | Изменения pre/post balances на каждую транзакцию |
| **Детектирование свопов** | Автоопределение DEX-свопов |
| **NFT-события** | Mint, transfer, sale через Metaplex/Magic Eden |
| **Экспорт** | JSON, CSV, XLSX (многолистовой Excel) |
| **Rate-limit защита** | Задержки + exponential backoff при ошибках |
| **Параллельная загрузка** | Thread pool для getTransaction |

## Установка

```bash
git clone <repo>
cd Parser-solana-wallet
pip install -r requirements.txt
```

## Быстрый старт

```bash
# Все транзакции кошелька
python main.py <WALLET_ADDRESS>

# С кастомным RPC (рекомендуется для больших кошельков)
python main.py <WALLET_ADDRESS> --rpc https://your-private-rpc.com

# Только последние 500 транзакций
python main.py <WALLET_ADDRESS> --limit 500

# Через переменную окружения
SOLANA_RPC_URL=https://your-rpc.com python main.py <WALLET_ADDRESS>
```

## Параметры командной строки

```
python main.py <wallet> [options]

Позиционные аргументы:
  wallet              Публичный ключ кошелька Solana (base-58)

Опции:
  --rpc URL           URL RPC-эндпоинта
  --output DIR        Директория для результатов (по умолчанию: output/)
  --limit N           Максимальное число транзакций (по умолчанию: все)
  --before SIG        Начать пагинацию перед этой подписью
  --until SIG         Остановить пагинацию на этой подписи
  --commitment        finalized | confirmed | processed
  --no-xlsx           Пропустить XLSX-экспорт
  --delay SECS        Задержка между RPC-вызовами (по умолчанию: 0.3)
  --workers N         Параллельных потоков для загрузки (по умолчанию: 5)
  -v, --verbose       Подробный лог
```

## Структура выходных файлов

После запуска в директории `output/` появятся:

```
output/
├── <wallet>_transactions.json     ← Все транзакции (полные данные)
├── <wallet>_analysis.json         ← Аналитика: сводка, трансферы, свопы
├── <wallet>_transactions.csv      ← Плоская таблица транзакций
├── <wallet>_sol_transfers.csv     ← SOL-переводы
├── <wallet>_token_transfers.csv   ← Токен-переводы
├── <wallet>_swaps.csv             ← DEX-свопы
└── <wallet>_full_report.xlsx      ← Excel с 7 листами
```

### Листы Excel

| Лист | Содержимое |
|------|-----------|
| Transactions | Все транзакции |
| SOL Transfers | SOL-переводы |
| Token Transfers | Токен-переводы |
| Swaps | DEX-свопы |
| NFT Events | NFT-события |
| Summary | Сводная статистика |
| Programs Used | Статистика программ |

## Структура транзакции (JSON)

```json
{
  "signature": "5J...",
  "slot": 280000000,
  "block_time": 1700000000,
  "block_time_utc": "2023-11-14T22:13:20+00:00",
  "success": true,
  "error": null,
  "fee_lamports": 5000,
  "fee_sol": 0.000005,
  "fee_payer": "Wallet123...",
  "accounts": ["Wallet123...", "TokenAccount...", "..."],
  "writable_accounts": ["Wallet123...", "TokenAccount..."],
  "signer_accounts": ["Wallet123..."],
  "sol_changes": [
    {
      "account": "Wallet123...",
      "pre_lamports": 1000000000,
      "post_lamports": 999995000,
      "delta_lamports": -5000,
      "delta_sol": -0.000005
    }
  ],
  "token_changes": [
    {
      "account_index": 1,
      "owner": "Wallet123...",
      "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "pre_amount": 1000000,
      "post_amount": 2000000,
      "delta": 1000000,
      "decimals": 6,
      "ui_pre": 1.0,
      "ui_post": 2.0,
      "ui_delta": 1.0
    }
  ],
  "instructions": [
    {
      "index": 0,
      "program_id": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
      "program_name": "SPL Token",
      "program_category": "token",
      "accounts": ["TokenAccount...", "Mint...", "Wallet123..."],
      "data_raw": null,
      "decoded": {
        "type": "transferChecked",
        "info": {
          "source": "TokenAccount...",
          "mint": "Mint...",
          "destination": "TokenAccount2...",
          "authority": "Wallet123...",
          "tokenAmount": {
            "amount": "1000000",
            "decimals": 6,
            "uiAmount": 1.0
          }
        }
      },
      "is_parsed": true
    }
  ],
  "inner_instructions": [...],
  "log_messages": ["Program TokenkegQ... invoke [1]", "..."],
  "loaded_writable": [],
  "loaded_readonly": [],
  "memo": null,
  "version": "legacy"
}
```

## Примечания по RPC

Публичный RPC (`api.mainnet-beta.solana.com`) имеет жёсткие rate limits.
Для кошельков с тысячами транзакций рекомендуется приватный RPC:

- [Helius](https://helius.dev) — бесплатный план 1M запросов/мес
- [QuickNode](https://quicknode.com)
- [Alchemy](https://alchemy.com)
- [Triton One](https://triton.one)

```bash
python main.py <WALLET> --rpc https://mainnet.helius-rpc.com/?api-key=YOUR_KEY --workers 10 --delay 0.1
```

## Ограничение Solana и как мы его обходим

Solana RPC метод `getSignaturesForAddress` возвращает максимум **1000 подписей за вызов**.
Solscan также ограничивает историю 1000 транзакциями в UI.

Наш парсер обходит это через пагинацию курсором `before`:

```
Page 1: signatures[0..999]     (newest)
         cursor = signatures[999].signature
Page 2: signatures[1000..1999]
         cursor = signatures[1999].signature
Page N: ...
         последняя страница < 1000 → конец
```

Каждая страница — отдельный HTTP-запрос к RPC. Теоретического ограничения
на глубину истории нет.
