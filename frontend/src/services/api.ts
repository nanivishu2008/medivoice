import { Doctor, AppointmentSlot, Booking, BookingCreatePayload } from '../types';

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : '/api';

export async function fetchDoctors(specialty?: string): Promise<Doctor[]> {
  const url = specialty 
    ? `${API_BASE}/doctors?specialty=${encodeURIComponent(specialty)}`
    : `${API_BASE}/doctors`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load doctors: ${res.statusText}`);
  return res.json();
}

export async function fetchSpecialties(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/doctors/specialties`);
  if (!res.ok) throw new Error(`Failed to load specialties: ${res.statusText}`);
  return res.json();
}

export async function fetchSlots(doctorId?: number): Promise<AppointmentSlot[]> {
  const url = doctorId ? `${API_BASE}/slots?doctor_id=${doctorId}` : `${API_BASE}/slots`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load slots: ${res.statusText}`);
  return res.json();
}

export async function createBooking(payload: BookingCreatePayload): Promise<Booking> {
  const res = await fetch(`${API_BASE}/bookings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Booking failed (${res.status})`);
  }
  return data;
}

export async function fetchBooking(referenceCode: string): Promise<Booking> {
  const res = await fetch(`${API_BASE}/bookings/${encodeURIComponent(referenceCode)}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Booking not found (${res.status})`);
  }
  return data;
}

export async function cancelBooking(referenceCode: string): Promise<Booking> {
  const res = await fetch(`${API_BASE}/bookings/${encodeURIComponent(referenceCode)}/cancel`, {
    method: 'POST',
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Cancellation failed (${res.status})`);
  }
  return data;
}
