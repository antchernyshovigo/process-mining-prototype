# 🚀 Process Mining Prototype

**Build your own Celonis-like system in Python**

This project is a prototype of a process mining platform that allows you to reconstruct and analyze real business processes from event logs.

---

## 🎯 What is it?

A lightweight process mining system that lets you:

- 📥 Upload event logs (CSV / Excel)
- 🔄 Reconstruct real process flows
- 🔍 Analyze process variants
- ⏱ Detect bottlenecks
- 📊 Visualize processes interactively

---

## ⚡ How it works (demo)

1. Upload CSV with event log  
2. Map columns:
   - `case_id`
   - `event_name`
   - `timestamp`  
3. System automatically:
   - normalizes data
   - builds process graph (DFG)
   - calculates variants
   - detects bottlenecks  
4. Explore results in UI

👉 Result: interactive process graph similar to Celonis / Disco

---

## ⚡ Quick start

⚠️ Run backend and UI in **separate terminals**

### Terminal 1 — Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
