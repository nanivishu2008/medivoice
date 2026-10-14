import React, { useEffect, useState } from 'react';
import { Doctor, AppointmentSlot, Booking } from './types';
import { fetchDoctors, fetchSpecialties, fetchSlots, createBooking } from './services/api';
import { DoctorList } from './components/DoctorList';
import { SlotPicker } from './components/SlotPicker';
import { BookingForm } from './components/BookingForm';
import { BookingLookup } from './components/BookingLookup';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'book' | 'lookup'>('book');

  // Doctors & Specialties
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [selectedSpecialty, setSelectedSpecialty] = useState<string | null>(null);
  const [selectedDoctorId, setSelectedDoctorId] = useState<number | null>(null);
  const [loadingDoctors, setLoadingDoctors] = useState(true);

  // Slots
  const [slots, setSlots] = useState<AppointmentSlot[]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null);
  const [loadingSlots, setLoadingSlots] = useState(false);

  // Booking action state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successBooking, setSuccessBooking] = useState<Booking | null>(null);

  // Load initial doctors and specialties
  useEffect(() => {
    async function loadInitial() {
      try {
        setLoadingDoctors(true);
        const [docsData, specsData] = await Promise.all([
          fetchDoctors(selectedSpecialty || undefined),
          fetchSpecialties(),
        ]);
        setDoctors(docsData);
        setSpecialties(specsData);
        if (docsData.length > 0 && !selectedDoctorId) {
          setSelectedDoctorId(docsData[0].id);
        }
      } catch (err: any) {
        console.error('Failed to load initial data:', err);
      } finally {
        setLoadingDoctors(false);
      }
    }
    loadInitial();
  }, [selectedSpecialty]);

  // Load slots when doctor changes
  useEffect(() => {
    async function loadDoctorSlots() {
      if (!selectedDoctorId) {
        setSlots([]);
        return;
      }
      try {
        setLoadingSlots(true);
        setSelectedSlotId(null);
        setErrorMessage(null);
        const slotsData = await fetchSlots(selectedDoctorId);
        setSlots(slotsData);
      } catch (err: any) {
        console.error('Failed to load slots:', err);
      } finally {
        setLoadingSlots(false);
      }
    }
    loadDoctorSlots();
  }, [selectedDoctorId]);

  const handleBookingSubmit = async (formData: {
    patient_name: string;
    patient_phone: string;
    patient_email: string;
    reason_for_visit?: string;
  }) => {
    if (!selectedSlotId) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await createBooking({
        slot_id: selectedSlotId,
        ...formData,
      });
      setSuccessBooking(result);

      // Refresh slots for the doctor
      if (selectedDoctorId) {
        const refreshedSlots = await fetchSlots(selectedDoctorId);
        setSlots(refreshedSlots);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'An unexpected error occurred while booking.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetBooking = () => {
    setSuccessBooking(null);
    setSelectedSlotId(null);
    setErrorMessage(null);
  };

  const selectedDoctor = doctors.find((d) => d.id === selectedDoctorId);
  const selectedSlot = slots.find((s) => s.id === selectedSlotId) || null;

  return (
    <div>
      {/* Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="logo-area">
            <div className="logo-icon">MV</div>
            <div className="logo-text">
              <h1>Medi<span>Voice</span> AI</h1>
            </div>
          </div>

          <nav className="nav-tabs">
            <button
              className={`nav-btn ${activeTab === 'book' ? 'active' : ''}`}
              onClick={() => setActiveTab('book')}
            >
              📅 Schedule Appointment
            </button>
            <button
              className={`nav-btn ${activeTab === 'lookup' ? 'active' : ''}`}
              onClick={() => setActiveTab('lookup')}
            >
              🔍 Find Booking
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="app-main">
        {/* Hero Section */}
        <div className="dashboard-hero">
          <h2>AI-Powered Healthcare Appointment System</h2>
          <p>
            Seamless real-time provider scheduling backed by FastAPI and SQLite concurrency safeguards. 
            Integrated with Voice AI endpoints ready for conversational Retell agents.
          </p>
        </div>

        {activeTab === 'book' ? (
          <div className="dashboard-grid">
            {/* Left Column: Doctor list and slots */}
            <div>
              <DoctorList
                doctors={doctors}
                specialties={specialties}
                selectedSpecialty={selectedSpecialty}
                onSelectSpecialty={setSelectedSpecialty}
                selectedDoctorId={selectedDoctorId}
                onSelectDoctor={(id) => setSelectedDoctorId(id)}
                loading={loadingDoctors}
              />

              <SlotPicker
                slots={slots}
                selectedSlotId={selectedSlotId}
                onSelectSlot={(id) => setSelectedSlotId(id)}
                loading={loadingSlots}
                selectedDoctorName={selectedDoctor?.name}
              />
            </div>

            {/* Right Column: Booking intake form */}
            <div>
              <BookingForm
                selectedSlot={selectedSlot}
                onSubmit={handleBookingSubmit}
                isSubmitting={isSubmitting}
                errorMessage={errorMessage}
                successBooking={successBooking}
                onReset={handleResetBooking}
              />
            </div>
          </div>
        ) : (
          <BookingLookup />
        )}
      </main>
    </div>
  );
};
