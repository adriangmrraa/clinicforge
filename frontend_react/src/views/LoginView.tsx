import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import { Lock, Mail, Shield, AlertCircle, CheckCircle } from 'lucide-react';

const DEMO_EMAIL = 'gamarraadrian200@gmail.com';
const DEMO_PASSWORD = 'Wstg1793.';

const SPECIALTIES: { value: string; key: string }[] = [
  { value: 'Odontología General', key: 'specialty_general' },
  { value: 'Ortodoncia', key: 'specialty_orthodontics' },
  { value: 'Endodoncia', key: 'specialty_endodontics' },
  { value: 'Periodoncia', key: 'specialty_periodontics' },
  { value: 'Cirugía Oral', key: 'specialty_oral_surgery' },
  { value: 'Prótesis Dental', key: 'specialty_prosthodontics' },
  { value: 'Odontopediatría', key: 'specialty_pediatric' },
  { value: 'Implantología', key: 'specialty_implantology' },
  { value: 'Estética Dental', key: 'specialty_aesthetic' },
];

interface ClinicOption {
  id: number;
  clinic_name: string;
}

const LoginView: React.FC = () => {
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [role, setRole] = useState('professional');
  const [tenantId, setTenantId] = useState<number | ''>('');
  const [specialty, setSpecialty] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [registrationId, setRegistrationId] = useState('');
  const [googleCalendarId, setGoogleCalendarId] = useState('');
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const from = location.state?.from?.pathname || "/";
  const isDemo = new URLSearchParams(location.search).get('demo') === '1';

  useEffect(() => {
    if (isDemo) {
      setEmail(DEMO_EMAIL);
      setPassword(DEMO_PASSWORD);
    }
  }, [isDemo]);

  useEffect(() => {
    if (isRegistering) {
      api.get<ClinicOption[]>('/auth/clinics')
        .then((res) => setClinics(res.data || []))
        .catch(() => setClinics([]));
    }
  }, [isRegistering]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email, password });
      login(response.data.access_token, response.data.user);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email: DEMO_EMAIL, password: DEMO_PASSWORD });
      login(response.data.access_token, response.data.user);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if ((role === 'professional' || role === 'secretary') && !tenantId) {
      setError(t('login.clinic_required'));
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/register', {
        email,
        password,
        role,
        first_name: firstName,
        last_name: lastName,
        tenant_id: role === 'professional' || role === 'secretary' ? Number(tenantId) : null,
        specialty: role === 'professional' ? (specialty || null) : null,
        phone_number: phoneNumber || null,
        registration_id: registrationId || null,
        google_calendar_id: role === 'professional' ? (googleCalendarId || null) : null,
      });
      setMessage(t('login.register_success'));
      setIsRegistering(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.register_error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card glass">
        <div className="login-header">
          <div className="logo-icon">
            <Shield size={32} color="var(--accent)" />
          </div>
          <h1>{t('login.title')}</h1>
          <p>{isRegistering ? t('login.request_access') : t('login.welcome')}</p>
        </div>

        {error && (
          <div className="auth-alert error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {message && (
          <div className="auth-alert success">
            <CheckCircle size={18} />
            <span>{message}</span>
          </div>
        )}

        <form onSubmit={isRegistering ? handleRegister : isDemo ? handleDemoLogin : handleLogin} className="auth-form">
          {isDemo && !isRegistering && (
            <div className="input-group mb-6">
              <p className="text-sm text-gray-300 mb-4">{t('login_extra.demo_ready')}</p>
              <button type="submit" className="btn-primary auth-btn w-full" disabled={loading}>
                {loading ? t('login.processing') : 'Entrar a la demo'}
              </button>
              <div className="mt-4 text-center">
                <Link to="/login" className="text-sm text-cyan-300 hover:text-white">{t('login_extra.sign_in_link')}</Link>
              </div>
            </div>
          )}
          {!isDemo && isRegistering && (
            <>
              <div className="input-group">
                <label>{t('login.first_name')}</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder={t('login.first_name')}
                    required
                  />
                </div>
              </div>
              <div className="input-group">
                <label>{t('login.last_name')}</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder={t('login.last_name')}
                  />
                </div>
              </div>
            </>
          )}

          {!isDemo && (
          <>
          <div className="input-group">
            <label>{t('login.email')}</label>
            <div className="input-wrapper">
              <Mail className="input-icon" size={18} />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ejemplo@clinica.com"
                required
              />
            </div>
          </div>

          <div className="input-group">
            <label>{t('login.password')}</label>
            <div className="input-wrapper">
              <Lock className="input-icon" size={18} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          {isRegistering && (
            <div className="input-group">
              <label>{t('login.role')}</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="professional">{t('login.role_professional')}</option>
                <option value="secretary">{t('login.role_secretary')}</option>
                <option value="ceo">{t('login.role_ceo')}</option>
              </select>
            </div>
          )}

          {isRegistering && (role === 'professional' || role === 'secretary') && (
            <div className="input-group">
              <label>{t('login.clinic')} <span className="required-dot">*</span></label>
              <select
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value === '' ? '' : Number(e.target.value))}
                required={role === 'professional' || role === 'secretary'}
              >
                <option value="">{t('login.choose_clinic')}</option>
                {clinics.map((c) => (
                  <option key={c.id} value={c.id}>{c.clinic_name}</option>
                ))}
              </select>
              {clinics.length === 0 && (
                <p className="text-sm mt-1.5 text-white/80">
                  {t('login.no_clinics')}
                </p>
              )}
            </div>
          )}

          {isRegistering && role === 'professional' && (
            <>
              <div className="input-group">
                <label>{t('login.specialty')}</label>
                <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
                  <option value="">{t('login.select_specialty')}</option>
                  {SPECIALTIES.map((s) => (
                    <option key={s.value} value={s.value}>{t('approvals.' + s.key)}</option>
                  ))}
                </select>
              </div>
              <div className="input-group">
                <label>{t('login.phone')}</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="Ej. +54 11 1234-5678"
                  />
                </div>
              </div>
              <div className="input-group">
                <label>{t('login.registration_id')}</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    value={registrationId}
                    onChange={(e) => setRegistrationId(e.target.value)}
                    placeholder={t('login.placeholder_optional')}
                  />
                </div>
              </div>
              <div className="input-group">
                <label>Google Calendar ID</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    value={googleCalendarId}
                    onChange={(e) => setGoogleCalendarId(e.target.value)}
                    placeholder={t('login.placeholder_calendar')}
                  />
                </div>
              </div>
            </>
          )}

          {isRegistering && role === 'secretary' && (
            <div className="input-group">
              <label>{t('login.phone')}</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder={t('login.placeholder_optional')}
                />
              </div>
            </div>
          )}

          <button type="submit" className="btn-primary auth-btn" disabled={loading}>
            {loading ? t('login.processing') : (isRegistering ? t('login.submit_register') : t('login.submit_login'))}
          </button>
          </>
          )}
        </form>

        {!isDemo && (
        <div className="auth-footer">
          <button
            type="button"
            className="btn-link"
            onClick={() => {
              setIsRegistering(!isRegistering);
              setError(null);
              setMessage(null);
            }}
          >
            {isRegistering ? t('login.have_account') : t('login.request_access_link')}
          </button>
        </div>
        )}
      </div>

      <style>{`
        .login-container {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
          background: radial-gradient(circle at top right, #1a1a2e, #0f0f1a);
          padding: 20px;
        }
        .login-card {
          width: 100%;
          max-width: 440px;
          padding: 40px;
          border-radius: 24px;
          text-align: center;
          animation: slideUp 0.6s ease-out;
        }
        .login-header h1 {
          font-size: 2rem;
          margin: 10px 0 5px;
          color: white;
          letter-spacing: -0.5px;
        }
        .login-header p {
          color: rgba(255, 255, 255, 0.9);
          margin-bottom: 30px;
        }
        .logo-icon {
          background: rgba(var(--accent-rgb), 0.1);
          width: 64px;
          height: 64px;
          border-radius: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 20px;
        }
        .auth-form {
          text-align: left;
        }
        .input-group {
          margin-bottom: 20px;
        }
        .input-group label {
          display: block;
          font-size: 0.9rem;
          font-weight: 500;
          color: rgba(255, 255, 255, 0.95);
          margin-bottom: 8px;
        }
        .input-wrapper {
          position: relative;
        }
        .input-icon {
          position: absolute;
          left: 12px;
          top: 50%;
          transform: translateY(-50%);
          color: rgba(255, 255, 255, 0.4);
        }
        .input-wrapper input, .input-group select {
          width: 100%;
          padding: 12px 12px 12px 40px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: white;
          transition: all 0.3s;
        }
        .input-group select {
           padding-left: 12px;
        }
        .input-wrapper input:focus {
          border-color: var(--accent);
          background: rgba(255, 255, 255, 0.08);
          outline: none;
        }
        .auth-btn {
          width: 100%;
          padding: 14px;
          font-weight: 600;
          margin-top: 10px;
        }
        .auth-alert {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px;
          border-radius: 12px;
          margin-bottom: 20px;
          font-size: 0.9rem;
          text-align: left;
        }
        .auth-alert.error {
          background: rgba(255, 77, 77, 0.1);
          border: 1px solid rgba(255, 77, 77, 0.2);
          color: #ff4d4d;
        }
        .auth-alert.success {
          background: rgba(77, 255, 140, 0.1);
          border: 1px solid rgba(77, 255, 140, 0.2);
          color: #4dff8c;
        }
        .btn-link {
          background: none;
          border: none;
          color: #4da6ff; /* Higher contrast blue */
          font-size: 0.95rem;
          cursor: pointer;
          margin-top: 20px;
          text-decoration: none;
          font-weight: 500;
          transition: all 0.3s;
        }
        .btn-link:hover {
          color: white;
          text-decoration: underline;
        }
        .input-group select option {
          background: #1a1a2e;
          color: white;
        }
        .required-dot {
          color: rgba(255, 255, 255, 0.95);
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};

export default LoginView;
