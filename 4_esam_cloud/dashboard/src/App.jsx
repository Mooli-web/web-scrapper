import React, { useState } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import LiveMissionControl from './components/LiveMissionControl';
import DbTestModal from './components/DbTestModal';
import EsamTestModal from './components/EsamTestModal';
import ErrorBoundary from './components/ErrorBoundary';

import Overview from './pages/Overview';
import EsamExplorer from './pages/EsamExplorer';
import Auctions from './pages/Auctions';
import Events from './pages/Events';
import Categories from './pages/Categories';
import DatabasePage from './pages/Database';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [isEsamModalOpen, setIsEsamModalOpen] = useState(false);

  const renderPage = () => {
    switch (activeTab) {
      case 'overview':
        return <Overview onNavigate={setActiveTab} />;
      case 'items':
        return <EsamExplorer />;
      case 'auctions':
        return <Auctions />;
      case 'events':
        return <Events />;
      case 'categories':
        return <Categories />;
      case 'database':
        return <DatabasePage />;
      default:
        return <Overview onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-vazir" dir="rtl">
      <Navbar
        onOpenDbModal={() => setIsDbModalOpen(true)}
        onOpenEsamModal={() => setIsEsamModalOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            <LiveMissionControl onStatusChange={() => {}} />

            <ErrorBoundary>
              {renderPage()}
            </ErrorBoundary>
          </div>
        </main>
      </div>

      <DbTestModal isOpen={isDbModalOpen} onClose={() => setIsDbModalOpen(false)} />
      <EsamTestModal isOpen={isEsamModalOpen} onClose={() => setIsEsamModalOpen(false)} />
    </div>
  );
}
