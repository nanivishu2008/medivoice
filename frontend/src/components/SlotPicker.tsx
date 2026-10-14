import React from 'react';
import { AppointmentSlot } from '../types';

interface SlotPickerProps {
  slots: AppointmentSlot[];
  selectedSlotId: number | null;
  onSelectSlot: (slotId: number) => void;
  loading: boolean;
  selectedDoctorName?: string;
}

export const SlotPicker: React.FC<SlotPickerProps> = ({
  slots,
  selectedSlotId,
  onSelectSlot,
  loading,
  selectedDoctorName,
}) => {
  const formatSlotTime = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatSlotDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <div className="card-title">
        <span>🕒 Available Times</span>
        {selectedDoctorName && (
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            for {selectedDoctorName}
          </span>
        )}
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
          Loading real-time availability...
        </p>
      ) : slots.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
          No open slots found. Please select another doctor or check back soon.
        </p>
      ) : (
        <div className="slots-container">
          {slots.map((slot) => {
            const isSelected = selectedSlotId === slot.id;
            return (
              <button
                key={slot.id}
                type="button"
                disabled={slot.is_booked}
                className={`slot-button ${isSelected ? 'active' : ''}`}
                onClick={() => onSelectSlot(slot.id)}
              >
                <div className="slot-date">{formatSlotDate(slot.start_time)}</div>
                <div className="slot-time">{formatSlotTime(slot.start_time)}</div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
