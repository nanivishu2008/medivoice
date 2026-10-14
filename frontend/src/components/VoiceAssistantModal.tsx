import React, { useState, useEffect, useRef } from 'react';
import { sendRetellChatMessage, RetellChatState } from '../services/api';

interface Message {
  sender: 'ai' | 'user';
  text: string;
}

interface VoiceAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBookingCreated?: () => void;
}

export const VoiceAssistantModal: React.FC<VoiceAssistantModalProps> = ({
  isOpen,
  onClose,
  onBookingCreated,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [state, setState] = useState<RetellChatState>({ step: 'GREETING' });
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [availableSlots, setAvailableSlots] = useState<Array<{ slot_id: number; doctor_name: string; formatted_time: string }>>([]);
  const [confirmedRef, setConfirmedRef] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, availableSlots]);

  // Text to speech function
  const speakText = (text: string) => {
    if (!voiceEnabled || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  // Initialize Speech Recognition if supported
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setIsListening(false);
        if (transcript.trim()) {
          handleSendMessage(transcript.trim());
        }
      };

      recognition.onerror = (err: any) => {
        console.warn('Speech recognition error:', err);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  // Initial Greeting when opened
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      const initialGreeting = async () => {
        setLoading(true);
        try {
          const res = await sendRetellChatMessage('Hello', { step: 'GREETING' });
          setMessages([{ sender: 'ai', text: res.ai_response }]);
          setState(res.next_state);
          speakText(res.ai_response);
        } catch (err: any) {
          const fallback = "Hello! I am your MediVoice AI assistant. What medical specialty or symptoms do you need assistance with today?";
          setMessages([{ sender: 'ai', text: fallback }]);
          speakText(fallback);
        } finally {
          setLoading(false);
        }
      };
      initialGreeting();
    }
  }, [isOpen]);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert("Voice speech recognition is not supported in this browser. Please use the text input below.");
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      window.speechSynthesis?.cancel();
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error("Recognition start error:", err);
      }
    }
  };

  const handleSendMessage = async (userText: string) => {
    if (!userText.trim()) return;

    // Add user message
    const updatedMessages = [...messages, { sender: 'user' as const, text: userText }];
    setMessages(updatedMessages);
    setInputVal('');
    setLoading(true);

    try {
      const res = await sendRetellChatMessage(userText, state);
      setMessages([...updatedMessages, { sender: 'ai', text: res.ai_response }]);
      setState(res.next_state);
      setAvailableSlots(res.available_slots || []);

      if (res.booking_reference) {
        setConfirmedRef(res.booking_reference);
        if (onBookingCreated) onBookingCreated();
      }

      speakText(res.ai_response);
    } catch (err: any) {
      const errMsg = err.message || "An error occurred communicating with the voice assistant.";
      setMessages([...updatedMessages, { sender: 'ai', text: errMsg }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSlotQuick = (slotId: number, slotTime: string) => {
    handleSendMessage(`I would like slot ${slotId} on ${slotTime}`);
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      width: '420px',
      maxWidth: 'calc(100vw - 48px)',
      height: '620px',
      maxHeight: 'calc(100vh - 48px)',
      background: '#ffffff',
      borderRadius: '16px',
      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
      border: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #0284c7 0%, #0d9488 100%)',
        color: '#ffffff',
        padding: '1rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            background: 'white',
            color: '#0284c7',
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.1rem',
            fontWeight: 700,
          }}>
            🎙️
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>MediVoice AI Assistant</div>
            <div style={{ fontSize: '0.75rem', opacity: 0.9 }}>Interactive Voice Scheduler</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            title={voiceEnabled ? "Mute AI Voice" : "Enable AI Voice"}
            onClick={() => setVoiceEnabled(!voiceEnabled)}
            style={{
              background: 'rgba(255, 255, 255, 0.2)',
              border: 'none',
              color: 'white',
              borderRadius: '8px',
              padding: '0.35rem 0.6rem',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            {voiceEnabled ? '🔊 Sound On' : '🔇 Muted'}
          </button>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'white',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '0.2rem 0.4rem',
            }}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Chat Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '1rem',
        background: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}>
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              background: m.sender === 'user' ? '#0284c7' : '#ffffff',
              color: m.sender === 'user' ? '#ffffff' : '#0f172a',
              padding: '0.75rem 1rem',
              borderRadius: m.sender === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
              boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              border: m.sender === 'user' ? 'none' : '1px solid #e2e8f0',
              fontSize: '0.9rem',
              lineHeight: 1.45,
            }}
          >
            {m.text}
          </div>
        ))}

        {/* Quick-Pick Slot Pills */}
        {availableSlots.length > 0 && state.step === 'SELECT_SLOT' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>
              Available Openings:
            </span>
            {availableSlots.map((s) => (
              <button
                key={s.slot_id}
                type="button"
                onClick={() => handleSelectSlotQuick(s.slot_id, s.formatted_time)}
                style={{
                  background: '#ffffff',
                  border: '1.5px solid #0284c7',
                  color: '#0284c7',
                  padding: '0.5rem 0.85rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  textAlign: 'left',
                  transition: 'background 0.15s ease',
                }}
              >
                📅 {s.formatted_time} ({s.doctor_name})
              </button>
            ))}
          </div>
        )}

        {/* Confirmed Reference Card */}
        {confirmedRef && (
          <div style={{
            background: '#f0fdf4',
            border: '2px solid #86efac',
            borderRadius: '10px',
            padding: '1rem',
            textAlign: 'center',
            marginTop: '0.5rem',
          }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>🎉</div>
            <div style={{ fontWeight: 700, color: '#166534' }}>Appointment Confirmed!</div>
            <div style={{
              display: 'inline-block',
              background: '#15803d',
              color: 'white',
              fontWeight: 700,
              padding: '0.3rem 0.8rem',
              borderRadius: '6px',
              margin: '0.5rem 0',
              letterSpacing: '0.05em',
            }}>
              {confirmedRef}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#166534' }}>
              Saved in database and verified.
            </div>
          </div>
        )}

        {loading && (
          <div style={{
            alignSelf: 'flex-start',
            background: '#ffffff',
            padding: '0.5rem 0.85rem',
            borderRadius: '12px',
            border: '1px solid #e2e8f0',
            fontSize: '0.85rem',
            color: '#64748b',
          }}>
            MediVoice AI is thinking...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input & Microphone Area */}
      <div style={{
        padding: '0.85rem 1rem',
        background: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
      }}>
        <button
          type="button"
          onClick={toggleListening}
          title={isListening ? "Listening... click to stop" : "Click to speak with microphone"}
          style={{
            background: isListening ? '#dc2626' : '#0284c7',
            border: 'none',
            color: 'white',
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.2rem',
            transition: 'all 0.2s ease',
            boxShadow: isListening ? '0 0 0 4px rgba(220, 38, 38, 0.3)' : 'none',
          }}
        >
          {isListening ? '🛑' : '🎙️'}
        </button>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(inputVal);
          }}
          style={{ display: 'flex', flex: 1, gap: '0.5rem' }}
        >
          <input
            type="text"
            className="form-input"
            style={{ borderRadius: '24px', padding: '0.55rem 1rem' }}
            placeholder={isListening ? "Listening to your voice..." : "Type or speak to assistant..."}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
          />
          <button
            type="submit"
            className="btn-primary"
            style={{ width: 'auto', borderRadius: '24px', padding: '0.55rem 1rem' }}
            disabled={!inputVal.trim() || loading}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
};
