import React from 'react';
import { Link, Outlet } from 'react-router-dom';
import useAuthStore from '../store/authStore';

const Layout: React.FC = () => {
  const logout = useAuthStore((state) => state.logout);

  const handleLogout = () => {
    logout();
  };

  return (
    <div>
      <nav>
        <ul>
          <li>
            <Link to="/dashboard">Dashboard</Link>
          </li>
          <li>
            <Link to="/positions">Positions</Link>
          </li>
          <li>
            <Link to="/queue">Queue</Link>
          </li>
          <li>
            <Link to="/risk-engine">Risk Engine</Link>
          </li>
          <li>
            <Link to="/logs">Logs</Link>
          </li>
          <li>
            <Link to="/settings">Settings</Link>
          </li>
          <li>
            <button onClick={handleLogout}>Logout</button>
          </li>
        </ul>
      </nav>
      <hr />
      <Outlet /> {/* This is where child routes will be rendered */}
    </div>
  );
};

export default Layout;
