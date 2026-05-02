# Process Mining Prototype

Прототип системы анализа процессов (process mining), который позволяет:

- загружать event log (CSV / Excel)
- автоматически строить процессный граф (DFG)
- анализировать варианты процесса (variants)
- находить узкие места (bottlenecks)
- смотреть основные метрики процесса

## Возможности MVP

### Загрузка данных

- поддержка CSV и Excel
- маппинг колонок:
  - case_id
  - event_name
  - timestamp

### Обработка

- нормализация данных
- сохранение в Parquet
- обработка через Polars

### Аналитика

- Process Graph / DFG
- Variants
- Bottlenecks
- Summary metrics

### UI

- Streamlit интерфейс
- визуализация графа
- таблицы и метрики

## Архитектура

```text
UI (Streamlit)
      ↓
FastAPI backend
      ↓
Parquet
      ↓
Process Mining Engine (Polars)


