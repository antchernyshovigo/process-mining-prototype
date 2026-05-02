# 🚀 Process Mining Prototype

Прототип системы анализа процессов (process mining), который позволяет:

- 📥 загружать event log (CSV / Excel)
- ⚙️ автоматически нормализовать данные
- 📊 строить process graph (DFG)
- 🔍 анализировать variants
- ⏱ находить bottlenecks
- 📈 смотреть summary метрики

---

## 🏗 Архитектура


---

## ▶️ Быстрый старт

### 1️⃣ Запуск Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
backend/
  app/
    api/
    services/
    engines/
  data/
    raw/
    processed/

ui/
  streamlit_app.py
case_id,event_name,timestamp
1,Start,2026-01-01 10:00:00
1,Check,2026-01-01 10:05:00
1,Approve,2026-01-01 10:10:00
Anton Chernyshov
