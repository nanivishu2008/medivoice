import React, { useState } from 'react';
import { AppointmentSlot, Booking } from '../types';

interface BookingFormProps {
  selectedSlot: AppointmentSlot | null;
  onSubmit: (formData: {
    patient_name: string;
    patient_phone: string;
    patient_email: string;
    reason_for_visit?: string;
  }) => Promise<void>;
  isSubmitting: boolean;
  errorMessage: string | null;
  successBooking: Booking | null;
  onReset: () => void;
}

export const BookingForm: React.FC<BookingFormProps> = ({
  selectedSlot,
  onSubmit,
  isSubmitting,
  errorMessage,
  successBooking,
  onReset,
}) => {
  const [patientName, setPatientName] = useState('');
  const [patientPhone, setPatientPhone] = useState('');
  const [patientEmail, setPatientEmail] = useState('');
  const [reason, setReason] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSlot) return;

    await onSubmit({
      patient_name: patientName,
      patient_phone: patientPhone,
      patient_email: patientEmail,
      reason_for_visit: reason || undefined,
    });
  };

  if (successBooking) {
    const slotDate = new Date(successBooking.slot.start_time);
    return (
      <div className="card">
        <div className="confirmation-card">
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
          <h3 style={{ color: 'var(--success)', fontWeight: 700 }}>Appointment Confirmed!</h3>
          <p style={{ color: '#166534', margin: '0.5rem 0' }}>
            Your booking reference code has been generated.
          </p>
          <div className="ref-code-badge">{successBooking.reference_code}</div>
          <div style={{ textAlign: 'left', marginTop: '1rem', background: 'white', padding: '1rem', borderRadius: '8px' }}>
            <p><strong>Patient:</strong> {successBooking.patient_name}</p>
            <p><strong>Doctor:</strong> {successBooking.slot.doctor?.name} ({successBooking.slot.doctor?.specialty})</p>
            <p><strong>Date & Time:</strong> {slotDate.toLocaleString([], { dateStyle: 'full', timeStyle: 'short' })}</p>
            <p><strong>Email:</strong> {successBooking.patient_email}</p>
            <p><strong>Status:</strong> <span style={{ color: 'var(--success)', fontWeight: 700 }}>{successBooking.status}</span></p>
          </div>
          <button
            style={{ marginTop: '1.25rem' }}
            className="btn-primary"
            onClick={onReset}
          >
            Book Another Appointment
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">
        <span>📝 Patient Information</span>
      </div>

      {!selectedSlot ? (
        <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>👉</p>
          <p style={{ fontWeight: 600 }}>Please select an appointment time slot from the left to continue.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          {errorMessage && (
            <div className="alert alert-error">
              <span>⚠️</span>
              <span>{errorMessage}</span>
            </div>
          )}

          <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '8px', marginBottom: '1rem', border: '1px solid var(--border)' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Selected Time Slot:</p>
            <p style={{ fontWeight: 700, color: 'var(--primary)' }}>
              {new Date(selectedSlot.start_time).toLocaleString([], { dateStyle: 'full', timeStyle: 'short' })}
            </p>
            {selectedSlot.doctor && (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                With {selectedSlot.doctor.name} ({selectedSlot.doctor.specialty})
              </p>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Full Name *</label>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. Eleanor Vance"
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Phone Number *</label>
            <input
              type="tel"
              required
              className="form-input"
              placeholder="e.g. +1 555-0143"
              value={patientPhone}
              onChange={(e) => setPatientPhone(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email Address *</label>
            <input
              type="email"
              required
              className="form-input"
              placeholder="e.g. eleanor.vance@example.com"
              value={patientEmail}
              onChange={(e) => setPatientEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Reason for Visit (Optional)</label>
            <textarea
              rows={3}
              className="form-textarea"
              placeholder="Briefly describe your symptoms or reason for visit..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Confirming with Database...' : 'Confirm Appointment Booking'}
          </button>
        </form>
      )}
    </div>
  );
};
