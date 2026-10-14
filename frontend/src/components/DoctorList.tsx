import React from 'react';
import { Doctor } from '../types';

interface DoctorListProps {
  doctors: Doctor[];
  specialties: string[];
  selectedSpecialty: string | null;
  onSelectSpecialty: (spec: string | null) => void;
  selectedDoctorId: number | null;
  onSelectDoctor: (id: number) => void;
  loading: boolean;
}

export const DoctorList: React.FC<DoctorListProps> = ({
  doctors,
  specialties,
  selectedSpecialty,
  onSelectSpecialty,
  selectedDoctorId,
  onSelectDoctor,
  loading,
}) => {
  return (
    <div className="card">
      <div className="card-title">
        <span>👨‍⚕️ Available Providers</span>
        <span className="badge-tag">{doctors.length} Doctors</span>
      </div>

      {/* Specialty Filter Pills */}
      <div className="filter-pills">
        <button
          className={`pill-btn ${selectedSpecialty === null ? 'active' : ''}`}
          onClick={() => onSelectSpecialty(null)}
        >
          All Specialties
        </button>
        {specialties.map((spec) => (
          <button
            key={spec}
            className={`pill-btn ${selectedSpecialty === spec ? 'active' : ''}`}
            onClick={() => onSelectSpecialty(spec)}
          >
            {spec}
          </button>
        ))}
      </div>

      {/* Doctor Cards */}
      {loading ? (
        <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
          Loading providers...
        </p>
      ) : doctors.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
          No doctors match the selected specialty.
        </p>
      ) : (
        doctors.map((doctor) => {
          const isSelected = selectedDoctorId === doctor.id;
          return (
            <div
              key={doctor.id}
              className={`doctor-item ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectDoctor(doctor.id)}
            >
              <div className="doctor-header">
                <div className="doctor-name">{doctor.name}</div>
                <div className="doctor-spec">{doctor.specialty}</div>
              </div>
              <div className="doctor-qual">{doctor.qualification}</div>
              {doctor.bio && <div className="doctor-bio">{doctor.bio}</div>}
            </div>
          );
        })
      )}
    </div>
  );
};
