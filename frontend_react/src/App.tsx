import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import DashboardView from './views/DashboardView';
import AgendaView from './views/AgendaView';
import PatientsView from './views/PatientsView';
import PatientDetail from './views/PatientDetail';
import ProfessionalAnalyticsView from './views/ProfessionalAnalyticsView';
import ChatsView from './views/ChatsView';
import TreatmentsView from './views/TreatmentsView';
import LoginView from './views/LoginView';
import LandingView from './views/LandingView';
import UserApprovalView from './views/UserApprovalView';
import ProfileView from './views/ProfileView';
import ClinicsView from './views/ClinicsView';
import ConfigView from './views/ConfigView';
import MetaTemplatesView from './views/MetaTemplatesView';
import MarketingHubView from './views/MarketingHubView';
import PrivacyTermsView from './views/PrivacyTermsView';
import { AuthProvider } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <Router>
      <AuthProvider>
        <LanguageProvider>
          <Routes>
            <Route path="/login" element={<LoginView />} />
            <Route path="/demo" element={<LandingView />} />
            <Route path="/privacy" element={<PrivacyTermsView />} />
            <Route path="/terms" element={<PrivacyTermsView />} />

            <Route path="/*" element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route index element={<DashboardView />} />
                    <Route path="agenda" element={<AgendaView />} />
                    <Route path="pacientes" element={<PatientsView />} />
                    <Route path="pacientes/:id" element={<PatientDetail />} />
                    <Route path="chats" element={<ChatsView />} />
                    <Route path="profesionales" element={<Navigate to="/aprobaciones" replace />} />
                    <Route path="analytics/professionals" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <ProfessionalAnalyticsView />
                      </ProtectedRoute>
                    } />
                    <Route path="tratamientos" element={<TreatmentsView />} />
                    <Route path="perfil" element={<ProfileView />} />
                    <Route path="aprobaciones" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <UserApprovalView />
                      </ProtectedRoute>
                    } />

                    <Route path="sedes" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <ClinicsView />
                      </ProtectedRoute>
                    } />
                    <Route path="configuracion" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <ConfigView />
                      </ProtectedRoute>
                    } />
                    <Route path="marketing" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <MarketingHubView />
                      </ProtectedRoute>
                    } />
                    <Route path="templates" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <MetaTemplatesView />
                      </ProtectedRoute>
                    } />

                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            } />
          </Routes>
        </LanguageProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
