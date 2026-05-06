import { ReactNode } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import MobileNav from './MobileNav';
import { useUIStore } from '../../stores/uiStore';
import { clsx } from 'clsx';
import SelectionBar from '../photos/SelectionBar';

interface Props {
  children: ReactNode;
}

export default function AppShell({ children }: Props) {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div
        className={clsx(
          'flex flex-1 flex-col overflow-hidden transition-all duration-200',
          sidebarOpen ? 'md:ml-64' : 'md:ml-16',
        )}
      >
        <Header />
        {/* pb-16 reserves space for the mobile bottom nav */}
        <main className="flex-1 overflow-y-auto p-4 pb-20 md:pb-4">{children}</main>
      </div>
      <SelectionBar />
      <MobileNav />
    </div>
  );
}
