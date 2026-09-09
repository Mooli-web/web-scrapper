import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import LoginModal from './components/LoginModal';

import Overview from './pages/Overview';
import FakeDiscounts from './pages/FakeDiscounts';
import SellerWar from './pages/SellerWar';
import CategoryExplorer from './pages/CategoryExplorer';
import Products from './pages/Products';
import Events from './pages/Events';
import DatabaseView from './pages/Database';
import Status from './pages/Status';

import { getAuthToken, checkAuthStatus } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState('all');

  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('auth_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return Boolean(getAuthToken());
  });

  useEffect(() => {
    if (getAuthToken()) {
      checkAuthStatus().then((res) => {
        if (res && res.authenticated) {
          setIsAuthenticated(true);
          setCurrentUser({ username: res.username, role: res.role });
        } else {
          setIsAuthenticated(false);
          setCurrentUser(null);
        }
      });
    }
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((k) => k + 1);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    setIsAuthenticated(true);
  };

  const handleDrilldownCategory = (categoryKey) => {
    setSelectedCategoryFilter(categoryKey);
    setActiveTab('products');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-rose-500 selection:text-white" dir="rtl">
      {!isAuthenticated && (
        <LoginModal onLoginSuccess={handleLoginSuccess} />
      )}

      <Navbar onRefresh={handleRefresh} isRefreshing={isRefreshing} currentUser={currentUser} />

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        <Sidebar activeTab={activeTab} onSelectTab={setActiveTab} />

        <main className="flex-1 p-6 overflow-y-auto max-h-[calc(100vh-61px)]">
          <div key={refreshKey} className="max-w-7xl mx-auto">
            {activeTab === 'overview' && (
              <Overview
                onNavigateToProducts={() => setActiveTab('products')}
                onNavigateToFakeDiscounts={() => setActiveTab('fake-discounts')}
                onNavigateToSellerWar={() => setActiveTab('seller-war')}
              />
            )}
            {activeTab === 'fake-discounts' && <FakeDiscounts />}
            {activeTab === 'seller-war' && <SellerWar />}
            {activeTab === 'categories' && <CategoryExplorer onSelectCategory={handleDrilldownCategory} />}
            {activeTab === 'products' && <Products initialCategory={selectedCategoryFilter} />}
            {activeTab === 'events' && <Events />}
            {activeTab === 'database' && <DatabaseView />}
            {activeTab === 'status' && <Status />}
          </div>
        </main>
      </div>
    </div>
  );
}
