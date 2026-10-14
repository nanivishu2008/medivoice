# MediVoice AI 🩺

An AI-powered healthcare appointment booking system designed for real-time provider scheduling, dynamic slot management, and Voice AI readiness.

Built for the **Applied AI Engineer** internship assignment.

---

## 🏗️ Architecture & Technology Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2
- **Frontend**: React 18, TypeScript, Vite, Modern Responsive CSS
- **Testing**: Pytest, FastAPI TestClient (`httpx`)
- **Voice AI Readiness**: Standardized HTTP endpoints for Retell AI custom functions

---

## 📁 Project Structure

```text
MediVoice-AI/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application & CORS configuration
│   │   ├── database.py          # SQLAlchemy SQLite engine & session dependency
│   │   ├── models.py            # Database tables (Doctor, AppointmentSlot, Booking)
│   │   ├── schemas.py           # Pydantic validation & response schemas
│   │   ├── crud.py              # Atomic database operations & double-booking locks
│   │   ├── seed_data.py         # Synthetic demonstration doctors and slots
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── doctors.py       # Doctor listings & specialty filters
│   │       ├── slots.py         # Real-time slot availability
│   │       └── bookings.py      # Booking creation, reference lookup, & cancellations
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Pytest in-memory SQLite fixtures & TestClient
│   │   ├── test_doctors.py      # Doctor endpoint test suite
│   │   ├── test_slots.py        # Slot availability & query test suite
│   │   └── test_bookings.py     # Concurrency & double-booking prevention tests
│   ├── requirements.txt         # Backend Python dependencies
│   └── .env.example             # Example environment variables
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DoctorList.tsx   # Provider cards & specialty filter
│   │   │   ├── SlotPicker.tsx   # Interactive slot selector
│   │   │   ├── BookingForm.tsx  # Patient booking form & validation
│   │   │   └── BookingLookup.tsx# Reference code lookup & cancellation
│   │   ├── services/
│   │   │   └── api.ts           # Typed API client for FastAPI backend
│   │   ├── types.ts             # TypeScript interfaces matching backend models
│   │   ├── App.tsx              # Main dashboard view & navigation
│   │   ├── main.tsx             # Vite React mount
│   │   └── index.css            # Responsive healthcare design styling
│   ├── package.json             # Frontend NPM scripts & dependencies
│   ├── tsconfig.json            # TypeScript configuration
│   ├── vite.config.ts           # Vite server & backend API proxy
│   └── index.html               # Web application HTML entrypoint
└── README.md
```

---

## 🔒 Concurrency & Double-Booking Prevention

1. **Database-Level Unique Constraint**:
   - `Booking` enforces a `UNIQUE(slot_id)` constraint on the foreign key (`uq_booking_slot_id`). Even in concurrent multi-threaded execution, SQLite will reject any duplicate booking attempt.
2. **Atomic Verification & Mutation**:
   - `crud.create_booking()` verifies `slot.is_booked == False`, sets `slot.is_booked = True`, and inserts the `Booking` record within an atomic database transaction.
3. **Transaction Rollback & HTTP 409 Conflict**:
   - If two requests collide on the same slot, the second request catches an `IntegrityError`, executes `db.rollback()`, and returns an explicit `HTTP 409 Conflict` response with an explanatory error message.
4. **Never Return Success Unless Committed**:
   - The API only returns an HTTP 201 Created response when `db.commit()` and `db.refresh()` have completed successfully.

---

## 🚀 Quickstart Guide

### 1. Backend Setup

```powershell
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the synthetic demonstration seeder
python -m app.seed_data

# Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

The interactive Swagger documentation will be available at:
`http://localhost:8000/docs`

### 2. Frontend Setup

In a separate terminal:

```powershell
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

The responsive dashboard will be available at:
`http://localhost:5173`

---

## 🧪 Running Automated Tests

MediVoice AI includes comprehensive Pytest unit and integration tests covering:
- Provider listing and specialty queries
- Real-time slot availability
- Input validation (emails, missing fields)
- **Double-booking race condition prevention**
- Booking lookup and slot release upon cancellation

```powershell
cd backend
pytest tests/ -v
```

---

## 🎙️ Retell AI Integration Readiness

The backend architecture is structured to support Retell AI custom functions once the core booking logic is tested:
- Clean JSON request/response formats
- Flat query parameters (`doctor_id`, `specialty`, `start_time`)
- Spoken confirmation generation for voice playback
