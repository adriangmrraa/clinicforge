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
import ROIDashboardView from './views/ROIDashboardView';
import LeadsManagementView from './views/LeadsManagementView';
import LeadDetailView from './views/LeadDetailView';
import DashboardStatusView from './views/DashboardStatusView';
import PrivacyTermsView from './views/PrivacyTermsView';
import AnamnesisPublicView from './views/AnamnesisPublicView';
import FinancialCommandCenterView from './views/FinancialCommandCenterView';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import ProtectedRoute from './components/ProtectedRoute';

function RoleLandingRedirect() {
  const { user } = useAuth();
  if (user?.role === 'ceo') return <DashboardView />;
  return <Navigate to="/agenda" replace />;
}

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
            <Route path="/anamnesis/:tenantId/:token" element={<AnamnesisPublicView />} />

            <Route path="/*" element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route index element={<RoleLandingRedirect />} />
                    <Route path="dashboard/status" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <DashboardStatusView />
                      </ProtectedRoute>
                    } />
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
                    <Route path="tratamientos" element={
                      <ProtectedRoute allowedRoles={['ceo', 'secretary']}>
                        <TreatmentsView />
                      </ProtectedRoute>
                    } />
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
                    <Route path="roi" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <ROIDashboardView />
                      </ProtectedRoute>
                    } />
                    <Route path="templates" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <MetaTemplatesView />
                      </ProtectedRoute>
                    } />
                    <Route path="leads" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <LeadsManagementView />
                      </ProtectedRoute>
                    } />
                    <Route path="leads/:id" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <LeadDetailView />
                      </ProtectedRoute>
                    } />
                    <Route path="finanzas" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <FinancialCommandCenterView />
                      </ProtectedRoute>
                    } />
                    <Route path="mis-liquidaciones" element={
                      <ProtectedRoute allowedRoles={['professional']}>
                        <div className="h-screen flex items-center justify-center text-white/40">
                          Próximamente: Mis Liquidaciones
                        </div>
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
