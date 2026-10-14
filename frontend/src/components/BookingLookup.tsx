import React, { useState } from 'react';
import { Booking } from '../types';
import { fetchBooking, cancelBooking } from '../services/api';

export const BookingLookup: React.FC = () => {
  const [refCode, setRefCode] = useState('');
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!refCode.trim()) return;

    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const res = await fetchBooking(refCode.trim());
      setBooking(res);
    } catch (err: any) {
      setError(err.message || 'Booking not found');
      setBooking(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!booking) return;
    if (!window.confirm(`Are you sure you want to cancel appointment ${booking.reference_code}?`)) {
      return;
    }

    setCancelling(true);
    setError(null);
    try {
      const updated = await cancelBooking(booking.reference_code);
      setBooking(updated);
      setInfo('Appointment successfully cancelled. The slot has been released back to availability.');
    } catch (err: any) {
      setError(err.message || 'Failed to cancel appointment');
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '640px', margin: '0 auto' }}>
      <div className="card-title">
        <span>🔍 Manage or Verify Appointment</span>
      </div>

      <form onSubmit={handleLookup} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Enter reference code (e.g. MV-4A7F2B)"
          value={refCode}
          onChange={(e) => setRefCode(e.target.value)}
          style={{ textTransform: 'uppercase' }}
        />
        <button
          type="submit"
          className="btn-primary"
          style={{ width: 'auto', whiteSpace: 'nowrap' }}
          disabled={loading}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {info && (
        <div className="alert alert-success">
          <span>✓</span>
          <span>{info}</span>
        </div>
      )}

      {booking && (
        <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span className="ref-code-badge" style={{ margin: 0, fontSize: '1rem' }}>
              {booking.reference_code}
            </span>
            <span
              style={{
                fontWeight: 700,
                fontSize: '0.85rem',
                color: booking.status === 'CONFIRMED' ? 'var(--success)' : 'var(--danger)',
                background: booking.status === 'CONFIRMED' ? '#dcfce7' : '#fee2e2',
                padding: '0.2rem 0.6rem',
                borderRadius: '6px',
              }}
            >
              {booking.status}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.9rem', marginBottom: '1rem' }}>
            <div>
              <p style={{ color: 'var(--text-muted)' }}>Patient:</p>
              <p style={{ fontWeight: 600 }}>{booking.patient_name}</p>
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)' }}>Doctor:</p>
              <p style={{ fontWeight: 600 }}>{booking.slot.doctor?.name}</p>
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)' }}>Specialty:</p>
              <p style={{ fontWeight: 600 }}>{booking.slot.doctor?.specialty}</p>
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)' }}>Scheduled Time:</p>
              <p style={{ fontWeight: 600 }}>
                {new Date(booking.slot.start_time).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
              </p>
            </div>
          </div>

          {booking.status === 'CONFIRMED' && (
            <button
              type="button"
              className="btn-danger"
              style={{ width: '100%', padding: '0.65rem' }}
              onClick={handleCancel}
              disabled={cancelling}
            >
              {cancelling ? 'Cancelling...' : 'Cancel Appointment & Release Slot'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
