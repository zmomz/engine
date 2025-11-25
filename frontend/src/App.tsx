import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './layouts/Layout';
import LoginPage from './pages/LoginPage';
import RegistrationPage from './pages/RegistrationPage';
import DashboardPage from './pages/DashboardPage';
import PositionsPage from './pages/PositionsPage';
import QueuePage from './pages/QueuePage';
import RiskPage from './pages/RiskPage';
import SettingsPage from './pages/SettingsPage';
import LogsPage from './pages/LogsPage';
import ProtectedRoute from './components/ProtectedRoute';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import NotificationManager from './components/NotificationManager';
import GlobalConfirmDialog from './components/GlobalConfirmDialog';
import { Box, Toolbar } from '@mui/material';

function App() {
  // For now, a dummy function. In a real app, this might toggle a mobile sidebar.
  const handleMenuClick = () => {
    // Menu icon clicked
  };

  return (
    <Layout>
      <NotificationManager />
      <GlobalConfirmDialog />
      <Header onMenuClick={handleMenuClick} />
      <Sidebar />
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar /> {/* This is important for spacing below the AppBar */}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegistrationPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/logs" element={<LogsPage />} />
            {/* Default redirect for authenticated users */}
            <Route path="*" element={<DashboardPage />} /> 
          </Route>
          {/* Default redirect for unauthenticated users */}
          <Route path="*" element={<LoginPage />} /> 
        </Routes>
      </Box>
    </Layout>
  );
}

export default App;
