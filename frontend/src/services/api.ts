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

export interface RetellChatState {
  step: string;
  specialty?: string;
  doctor_id?: number;
  doctor_name?: string;
  slot_id?: number;
  slot_time_str?: string;
  patient_name?: string;
  patient_phone?: string;
  patient_email?: string;
  reason?: string;
}

export interface RetellChatResponse {
  ai_response: string;
  next_state: RetellChatState;
  available_slots?: Array<{
    slot_id: number;
    doctor_name: string;
    start_time: string;
    formatted_time: string;
  }>;
  booking_reference?: string;
}

export async function sendRetellChatMessage(
  userMessage: string,
  state?: RetellChatState
): Promise<RetellChatResponse> {
  const res = await fetch(`${API_BASE}/retell/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_message: userMessage, state }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Voice chat request failed (${res.status})`);
  }
  return data;
}

