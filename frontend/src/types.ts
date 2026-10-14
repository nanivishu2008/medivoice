export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  qualification: string;
  bio?: string;
}

export interface AppointmentSlot {
  id: number;
  doctor_id: number;
  start_time: string;
  end_time: string;
  is_booked: boolean;
  doctor?: Doctor;
}

export interface BookingCreatePayload {
  slot_id: number;
  patient_name: string;
  patient_phone: string;
  patient_email: string;
  reason_for_visit?: string;
}

export interface Booking {
  id: number;
  reference_code: string;
  slot_id: number;
  patient_name: string;
  patient_phone: string;
  patient_email: string;
  reason_for_visit?: string;
  status: string;
  created_at: string;
  slot: AppointmentSlot;
}

export interface ApiError {
  detail: string;
}
