import React from 'react';
import { Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegistrationPage from './pages/RegistrationPage';
import DashboardPage from './pages/DashboardPage';
import PositionsPage from './pages/PositionsPage'; // Import PositionsPage
import QueuePage from './pages/QueuePage'; // Import QueuePage
import RiskEnginePage from './pages/RiskEnginePage'; // Import RiskEnginePage
import LogsPage from './pages/LogsPage'; // Import LogsPage
import SettingsPage from './pages/SettingsPage'; // Import SettingsPage
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout'; // Import the Layout component
import './App.css';

function App() {
  return (
    <div className="App">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegistrationPage />} />

        {/* Protected routes using the Layout component */}
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<DashboardPage />} />
          {/* Placeholder for other core UI components */}
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/risk-engine" element={<RiskEnginePage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/" element={<DashboardPage />} /> {/* Default protected route */}
        </Route>
      </Routes>
    </div>
  );
}

export default App;