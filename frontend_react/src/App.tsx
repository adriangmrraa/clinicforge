import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import ProtectedRoute from './components/ProtectedRoute';

const DashboardView = lazy(() => import('./views/DashboardView'));
const AgendaView = lazy(() => import('./views/AgendaView'));
const PatientsView = lazy(() => import('./views/PatientsView'));
const PatientDetail = lazy(() => import('./views/PatientDetail'));
const ProfessionalAnalyticsView = lazy(() => import('./views/ProfessionalAnalyticsView'));
const ChatsView = lazy(() => import('./views/ChatsView'));
const TreatmentsView = lazy(() => import('./views/TreatmentsView'));
const LoginView = lazy(() => import('./views/LoginView'));
const LandingView = lazy(() => import('./views/LandingView'));
const UserApprovalView = lazy(() => import('./views/UserApprovalView'));
const ProfileView = lazy(() => import('./views/ProfileView'));
const ClinicsView = lazy(() => import('./views/ClinicsView'));
const ConfigView = lazy(() => import('./views/ConfigView'));
const MetaTemplatesView = lazy(() => import('./views/MetaTemplatesView'));
const PlaybooksView = lazy(() => import('./views/PlaybooksView'));
const MarketingHubView = lazy(() => import('./views/MarketingHubView'));
const ROIDashboardView = lazy(() => import('./views/ROIDashboardView'));
const LeadsManagementView = lazy(() => import('./views/LeadsManagementView'));
const LeadDetailView = lazy(() => import('./views/LeadDetailView'));
const DashboardStatusView = lazy(() => import('./views/DashboardStatusView'));
const PrivacyTermsView = lazy(() => import('./views/PrivacyTermsView'));
const AnamnesisPublicView = lazy(() => import('./views/AnamnesisPublicView'));
const FinancialCommandCenterView = lazy(() => import('./views/FinancialCommandCenterView'));
const ProfessionalLiquidationsView = lazy(() => import('./views/ProfessionalLiquidationsView'));

const PageLoader = () => (
  <div className="flex items-center justify-center h-screen bg-[#06060e] text-white">
    Cargando...
  </div>
);

function RoleLandingRedirect() {
  const { user } = useAuth();
  if (user?.role === 'ceo' || user?.role === 'secretary') return <DashboardView />;
  return <Navigate to="/agenda" replace />;
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <LanguageProvider>
          <Suspense fallback={<PageLoader />}>
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
                      <ProtectedRoute allowedRoles={['ceo', 'secretary']}>
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
                    <Route path="playbooks" element={
                      <ProtectedRoute allowedRoles={['ceo']}>
                        <PlaybooksView />
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
                        <ProfessionalLiquidationsView />
                      </ProtectedRoute>
                    } />

                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            } />
          </Routes>
          </Suspense>
        </LanguageProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
