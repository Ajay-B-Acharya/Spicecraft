# SpiceCraft

**AI-Powered LTspice Circuit Generator**

Transform natural language circuit descriptions into simulation-ready LTspice files using AI.

---

## 🚀 Quick Start

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
**→** http://localhost:3000

### Backend (FastAPI)
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (macOS: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**→** http://localhost:8000

---

## 📋 Project Status

### ✅ Implemented (Frontend)

- 🔐 Firebase Authentication (Google + Email/Password)
- 📊 Dashboard with sidebar navigation
- 👤 User profile with Settings/Help/Logout
- 🌓 Dark/Light theme toggle
- ✨ Animated hero page with shader effects
- 🎨 Complete shadcn UI component library
- 📱 Fully responsive design

### ✅ Implemented (Backend)

- ⚡ FastAPI server with CORS
- 🗄️ SQLAlchemy database setup (PostgreSQL/SQLite)
- 📝 Environment configuration
- 📚 Auto-generated API documentation (Swagger/ReDoc)
- 🏗️ Clean project structure ready for development

### 🔜 Coming Next

- Circuit search and discovery
- AI-powered circuit generation
- Visual circuit editor
- LTspice `.asc` file export
- Component library management

---

## 🛠️ Tech Stack

### Frontend
- **Framework:** Next.js 16 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4
- **UI:** shadcn/ui + Radix UI
- **Auth:** Firebase
- **Animations:** Framer Motion + Three.js
- **State:** React 19 with hooks

### Backend
- **Framework:** FastAPI
- **Language:** Python 3.x
- **Database:** SQLAlchemy (PostgreSQL/SQLite)
- **Validation:** Pydantic
- **AI:** OpenAI API (planned)

---

## 📁 Project Structure

```
Spice Craft/
│
├── frontend/                    # Next.js Application
│   ├── app/                    # App Router pages
│   │   ├── dashboard/          # Dashboard page
│   │   ├── login/              # Login page
│   │   ├── signup/             # Signup page
│   │   └── layout.tsx          # Root layout
│   ├── components/             # React components
│   │   ├── ui/                # shadcn UI components
│   │   ├── dashboard-shell.tsx
│   │   └── hero-section.tsx
│   ├── lib/                   # Utilities
│   │   ├── firebase.ts        # Firebase config
│   │   └── utils.ts           # Helper functions
│   └── package.json
│
├── backend/                    # FastAPI Application
│   ├── app/
│   │   ├── main.py            # FastAPI entry point
│   │   ├── database.py        # Database config
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── routers/           # API routes
│   │   └── services/          # Business logic
│   ├── .env                   # Environment variables
│   ├── requirements.txt       # Python dependencies
│   └── README.md             # Backend docs
│
├── SETUP.md                   # Complete setup guide
├── package.json              # Workspace scripts
└── README.md                 # This file
```

---

## 📖 Documentation

- **[Complete Setup Guide](./SETUP.md)** - Detailed installation and configuration
- **[Backend README](./backend/README.md)** - Backend-specific documentation
- **[Frontend Package](./frontend/package.json)** - Frontend dependencies and scripts

---

## 🔧 Development

### Run Frontend
```bash
npm run dev:frontend
```

### Run Backend
```bash
npm run dev:backend  # (requires venv activated)
```

### Build Frontend
```bash
cd frontend
npm run build
```

---

## 🌐 API Endpoints

### Available Now

- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

### Coming Soon

- `POST /api/auth/login` - User authentication
- `POST /api/circuits/generate` - Generate circuit from prompt
- `GET /api/circuits` - List user circuits
- `POST /api/circuits/export` - Export to LTspice

---

## 🤝 Contributing

This is a Phase 1 foundation project. Backend API development is the next priority.

---

## 📄 License

Private project - All rights reserved

---

## 👨‍💻 Development Team

Building the future of circuit design automation.

---

**Ready for Phase 2 Development** 🎯
