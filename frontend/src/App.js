import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Container, Nav, Navbar, Button } from 'react-bootstrap';
import './App.css';
import './components/components.css';

// Import components
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Calendar = React.lazy(() => import('./pages/Calendar'));

// Navigation item component
const NavItem = ({ to, icon, label, isActive, isSidebarCollapsed }) => (
  <Nav.Link 
    as={Link} 
    to={to} 
    className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
  >
    <i className={`bi bi-${icon} nav-icon`}></i>
    {!isSidebarCollapsed && <span className="nav-label">{label}</span>}
  </Nav.Link>
);

// Main layout component
const MainLayout = ({ children }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();
  
  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };
  
  return (
    <div className="dashboard-layout">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          {!sidebarCollapsed ? (
            <h5 className="sidebar-brand">
              <i className="bi bi-calendar-check me-2"></i>
              Rescheduling UI
            </h5>
          ) : (
            <h5 className="sidebar-brand-icon">
              <i className="bi bi-calendar-check"></i>
            </h5>
          )}
          <Button 
            variant="link" 
            className="sidebar-toggle" 
            onClick={toggleSidebar}
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <i className={`bi bi-chevron-${sidebarCollapsed ? 'right' : 'left'}`}></i>
          </Button>
        </div>
        
        <Nav className="sidebar-nav flex-column">
          <NavItem 
            to="/" 
            icon="speedometer2" 
            label="Dashboard" 
            isActive={location.pathname === '/'} 
            isSidebarCollapsed={sidebarCollapsed}
          />
          <NavItem 
            to="/calendar" 
            icon="calendar3" 
            label="Calendar" 
            isActive={location.pathname === '/calendar'} 
            isSidebarCollapsed={sidebarCollapsed}
          />
        </Nav>
        
        <div className="sidebar-footer">
          {!sidebarCollapsed && (
            <div className="sidebar-footer-content">
              <div className="user-info">
                <div className="user-avatar">
                  <i className="bi bi-person-circle"></i>
                </div>
                <div className="user-details">
                  <div className="user-name">Admin User</div>
                  <div className="user-role">Administrator</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Main content */}
      <div className={`main-content ${sidebarCollapsed ? 'expanded' : ''}`}>
        <header className="main-header">
          <div className="header-left">
            <h4 className="page-title">
              {location.pathname === '/' && 'Dashboard'}
              {location.pathname === '/calendar' && 'Calendar View'}
            </h4>
          </div>
          <div className="header-right">
            <div className="header-actions">
              <Button variant="light" className="action-button" title="Notifications">
                <i className="bi bi-bell"></i>
                <span className="notification-badge"></span>
              </Button>
              <Button variant="light" className="action-button" title="Settings">
                <i className="bi bi-gear"></i>
              </Button>
              <Button variant="light" className="action-button" title="Help">
                <i className="bi bi-question-circle"></i>
              </Button>
              <Button variant="primary" className="action-button">
                <i className="bi bi-plus-lg me-1"></i>
                New Task
              </Button>
            </div>
          </div>
        </header>
        
        <div className="content-wrapper">
          {children}
        </div>
      </div>
    </div>
  );
};

function App() {
  return (
    <Router>
      <div className="App">
        <React.Suspense fallback={
          <div className="loading-container">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p>Loading application...</p>
          </div>
        }>
          <Routes>
            <Route path="/" element={
              <MainLayout>
                <Dashboard />
              </MainLayout>
            } />
            <Route path="/calendar" element={
              <MainLayout>
                <Calendar />
              </MainLayout>
            } />
          </Routes>
        </React.Suspense>
      </div>
    </Router>
  );
}

export default App;