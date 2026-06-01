# SpiceCraft - Complete Setup Guide

This guide walks you through setting up both the **Next.js frontend** and **FastAPI backend**.

---

## 📁 Project Structure

```
Spice Craft/
├── frontend/           # Next.js 16 + TypeScript + Tailwind
├── backend/            # FastAPI + SQLAlchemy + PostgreSQL
├── package.json        # Workspace scripts
└── SETUP.md           # This file
```

---

## 🎨 Frontend Setup (Next.js)

The frontend is **already configured** and ready to run!

### Quick Start

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: **http://localhost:3000**

### Features Already Implemented

✅ Firebase Authentication (Google + Email/Password)  
✅ Dashboard with sidebar navigation  
✅ User profile dropdown with Settings/Help/Logout  
✅ Dark/Light theme toggle  
✅ Hero landing page with animated shader background  
✅ Complete shadcn UI component library  
✅ TypeScript + Tailwind CSS + React 19  

### Frontend Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-auth-domain
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-storage-bucket
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=your-measurement-id
```

---

## ⚙️ Backend Setup (FastAPI)

### 1. Create Virtual Environment

**Windows:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

The `.env` file is already created. Edit `backend/.env`:

```env
# Database (leave empty to use SQLite for development)
DATABASE_URL=

# OpenAI API
OPENAI_API_KEY=

# App Config
APP_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production
CORS_ORIGINS=http://localhost:3000
```

**For PostgreSQL (production):**
```env
DATABASE_URL=postgresql://username:password@localhost:5432/spicecraft
```

### 4. Run Backend Server

```bash
uvicorn app.main:app --reload
```

Backend runs at: **http://localhost:8000**

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🚀 Running Both Servers

### Option 1: Separate Terminals

**Terminal 1 (Frontend):**
```bash
cd frontend
npm run dev
```

**Terminal 2 (Backend):**
```bash
cd backend
venv\Scripts\activate  # or source venv/bin/activate on macOS/Linux
uvicorn app.main:app --reload
```

### Option 2: Workspace Scripts (from root)

**Frontend:**
```bash
npm run dev:frontend
```

**Backend:**
```bash
npm run dev:backend  # Note: You still need venv activated
```

---

## 🔗 Connecting Frontend to Backend

The frontend is already configured to connect to `http://localhost:8000`.

### Example API Call (from Next.js)

```typescript
// In your frontend service file
const response = await fetch('http://localhost:8000/api/circuits');
const data = await response.json();
```

The backend already has CORS configured for `http://localhost:3000`.

---

## 📦 Next Steps

### Backend Development

1. **Add Authentication Router**
   - Create `backend/app/routers/auth.py`
   - Implement login/signup endpoints

2. **Add Circuit Models**
   - Create `backend/app/models/circuit.py`
   - Define SQLAlchemy models

3. **Integrate OpenAI**
   - Create `backend/app/services/ai_service.py`
   - Add circuit generation logic

4. **Add Database Migrations**
   ```bash
   pip install alembic
   alembic init alembic
   ```

### Frontend Development

1. **Connect to Backend API**
   - Update `frontend/lib` with API service files
   - Replace demo data with real backend calls

2. **Add Circuit Editor**
   - Create circuit visualization components
   - Implement drag-and-drop circuit builder

3. **Add LTspice Export**
   - Create export functionality
   - Connect to backend export endpoints

---

## 🛠️ Troubleshooting

### Backend Won't Start

**Issue:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:** Make sure virtual environment is activated:
```bash
cd backend
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### Frontend Build Errors

**Issue:** TypeScript errors about missing Firebase config

**Solution:** Create `frontend/.env.local` with your Firebase credentials (see Frontend Environment Variables section above).

### CORS Errors

**Issue:** Frontend can't connect to backend

**Solution:** Check that:
1. Backend is running on port 8000
2. Frontend is running on port 3000
3. CORS is configured in `backend/app/main.py` (already done)

---

## 📚 Documentation

- [Next.js Docs](https://nextjs.org/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Firebase Docs](https://firebase.google.com/docs)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)

---

## ✅ Verification Checklist

- [ ] Frontend runs successfully at http://localhost:3000
- [ ] Backend runs successfully at http://localhost:8000
- [ ] Backend `/` endpoint returns: `{"message":"SpiceCraft Backend Running"}`
- [ ] Backend `/health` endpoint returns: `{"status":"healthy","service":"SpiceCraft API"}`
- [ ] Swagger docs accessible at http://localhost:8000/docs
- [ ] Frontend can sign in with Firebase
- [ ] Dark mode toggle works
- [ ] Hero page shader animation visible

---

**You're all set! 🎉**

Frontend is fully functional, and backend is ready for Phase 2 development.
